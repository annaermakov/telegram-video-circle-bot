import os
import asyncio
import logging
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import ffmpeg

# Импорт конфигурации
from config import (
    BOT_TOKEN, VIDEO_CIRCLE_SIZE, MAX_FILE_SIZE_MB, MAX_DURATION_SECONDS,
    VIDEO_CODEC, AUDIO_CODEC, CRF_VALUE, TEMP_DIR, CLEANUP_TEMP_FILES,
    LOG_LEVEL, LOG_FORMAT, MESSAGES, validate_config, setup_temp_directory
)

# Настройка логирования
logging.basicConfig(
    format=LOG_FORMAT,
    level=getattr(logging, LOG_LEVEL)
)
logger = logging.getLogger(__name__)

class VideoCircleBot:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(MESSAGES['welcome'])
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        await update.message.reply_text(MESSAGES['help'])
    
    async def process_video_to_circle(self, input_path, output_path):
        """Конвертирует видео в круглый формат используя только ffmpeg"""
        try:
            # Получаем информацию о видео
            probe = ffmpeg.probe(input_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            
            width = int(video_info['width'])
            height = int(video_info['height'])
            
            # Определяем размер квадрата (минимальная сторона)
            size = min(width, height)
            
            # Вычисляем координаты для центрирования
            x_offset = (width - size) // 2
            y_offset = (height - size) // 2
            
            # Создаем круглую маску с помощью ffmpeg
            # Сначала обрезаем до квадрата и масштабируем
            input_stream = ffmpeg.input(input_path)
            
            # Обрезаем видео до квадрата
            cropped = input_stream.filter('crop', size, size, x_offset, y_offset)
            
            # Масштабируем до нужного размера
            scaled = cropped.filter('scale', VIDEO_CIRCLE_SIZE, VIDEO_CIRCLE_SIZE)
            
            # Создаем круглую маску
            # Используем формулу для создания круга: sqrt((x-cx)^2 + (y-cy)^2) <= radius
            center = VIDEO_CIRCLE_SIZE // 2
            radius = center
            
            # Применяем круглую маску
            masked = scaled.filter(
                'geq',
                f'if(lt(sqrt(pow(X-{center},2)+pow(Y-{center},2)),{radius}),255,0)',
                f'if(lt(sqrt(pow(X-{center},2)+pow(Y-{center},2)),{radius}),255,0)', 
                f'if(lt(sqrt(pow(X-{center},2)+pow(Y-{center},2)),{radius}),255,0)'
            )
            
            # Выводим результат
            output = ffmpeg.output(
                masked,
                input_stream.audio,
                output_path,
                vcodec=VIDEO_CODEC,
                acodec=AUDIO_CODEC,
                crf=CRF_VALUE,
                preset='fast',
                shortest=None
            )
            
            # Запускаем ffmpeg
            ffmpeg.run(output, overwrite_output=True, quiet=True)
            
            return True
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Ошибка ffmpeg: {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при обработке видео: {e}")
            return False
    
    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик видео сообщений"""
        try:
            # Отправляем сообщение о начале обработки
            processing_msg = await update.message.reply_text(MESSAGES['processing'])
            
            # Получаем видео файл
            video = update.message.video or update.message.document
            
            if not video:
                await processing_msg.edit_text(MESSAGES['error_no_video'])
                return
            
            # Проверяем размер файла
            if video.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await processing_msg.edit_text(MESSAGES['error_file_size'])
                return
            
            # Скачиваем файл
            file = await context.bot.get_file(video.file_id)
            
            # Создаем временные файлы
            input_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            output_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            
            input_path = input_file.name
            output_path = output_file.name
            
            input_file.close()
            output_file.close()
            
            # Скачиваем видео
            await file.download_to_drive(input_path)
            
            await processing_msg.edit_text(MESSAGES['creating_circle'])
            
            # Обрабатываем видео
            success = await self.process_video_to_circle(input_path, output_path)
            
            if success:
                await processing_msg.edit_text(MESSAGES['sending'])
                
                # Отправляем видеокружок
                with open(output_path, 'rb') as video_file:
                    await context.bot.send_video_note(
                        chat_id=update.effective_chat.id,
                        video_note=video_file,
                        duration=min(30, MAX_DURATION_SECONDS),
                        length=VIDEO_CIRCLE_SIZE,
                        reply_to_message_id=update.message.message_id
                    )
                
                await processing_msg.delete()
                
            else:
                await processing_msg.edit_text(MESSAGES['error_processing'])
            
            # Удаляем временные файлы
            try:
                os.unlink(input_path)
                os.unlink(output_path)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Ошибка при обработке видео: {e}")
            await update.message.reply_text(MESSAGES['error_general'])
    
    async def handle_other_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик других типов сообщений"""
        await update.message.reply_text(MESSAGES['send_video'])

def main():
    """Запуск бота"""
    # Проверяем конфигурацию
    if not validate_config():
        return
    
    # Настраиваем директории
    setup_temp_directory()
    
    # Создаем экземпляр бота
    bot = VideoCircleBot()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    
    # Обработчик видео
    application.add_handler(MessageHandler(
        filters.VIDEO | (filters.Document.VIDEO), 
        bot.handle_video
    ))
    
    # Обработчик остальных сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        bot.handle_other_messages
    ))
    
    # Запускаем бота
    print("🤖 Упрощенный бот запущен!")
    print("Нажмите Ctrl+C для остановки")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
