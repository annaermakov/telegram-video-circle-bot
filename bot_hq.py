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
    
    def process_video_to_circle_sync(self, input_path, output_path):
        """Высококачественная конвертация видео с сохранением звука"""
        try:
            # Получаем информацию о видео
            probe = ffmpeg.probe(input_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            
            # Проверяем наличие аудио
            audio_streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
            has_audio = len(audio_streams) > 0
            
            width = int(video_info['width'])
            height = int(video_info['height'])
            
            # Определяем размер квадрата (минимальная сторона)
            size = min(width, height)
            
            # Вычисляем координаты для центрирования
            x_offset = (width - size) // 2
            y_offset = (height - size) // 2
            
            # Высококачественная обработка с сохранением звука
            input_stream = ffmpeg.input(input_path)
            
            # Обрабатываем видео
            video_processed = (
                input_stream
                .video
                .filter('crop', size, size, x_offset, y_offset)
                .filter('scale', VIDEO_CIRCLE_SIZE, VIDEO_CIRCLE_SIZE)
            )
            
            # Настройки для высокого качества
            output_args = {
                'vcodec': 'libx264',
                'preset': 'medium',  # Баланс качества и скорости
                'crf': 18,           # Высокое качество (18 = очень хорошо)
                'pix_fmt': 'yuv420p',
                'movflags': 'faststart',
                'profile:v': 'high',
                'level': '4.0'
            }
            
            # Добавляем аудио если есть
            if has_audio:
                audio_processed = input_stream.audio
                output_args.update({
                    'acodec': 'aac',
                    'audio_bitrate': '128k',  # Высокое качество звука
                    'ar': 44100,              # Стандартная частота дискретизации
                    'ac': 2                   # Стерео
                })
                
                # Объединяем видео и аудио
                output = ffmpeg.output(
                    video_processed,
                    audio_processed,
                    output_path,
                    **output_args
                )
            else:
                # Только видео без звука
                output = ffmpeg.output(
                    video_processed,
                    output_path,
                    **output_args
                )
            
            # Запускаем обработку
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
            
            # Запускаем обработку в отдельном потоке
            try:
                loop = asyncio.get_event_loop()
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, self.process_video_to_circle_sync, input_path, output_path),
                    timeout=120.0  # Увеличиваем таймаут для качественной обработки
                )
            except asyncio.TimeoutError:
                logger.error("Таймаут при обработке видео")
                await processing_msg.edit_text("❌ Видео слишком длинное для обработки. Попробуйте покороче.")
                return
            
            if success:
                # Проверяем размер выходного файла
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    await processing_msg.edit_text(MESSAGES['sending'])
                    
                    # Отправляем видеокружок
                    with open(output_path, 'rb') as video_file:
                        await context.bot.send_video_note(
                            chat_id=update.effective_chat.id,
                            video_note=video_file,
                            duration=min(60, MAX_DURATION_SECONDS),  # Увеличиваем до 60 секунд
                            length=VIDEO_CIRCLE_SIZE,
                            reply_to_message_id=update.message.message_id
                        )
                    
                    await processing_msg.delete()
                else:
                    await processing_msg.edit_text("❌ Ошибка: выходной файл пустой")
                
            else:
                await processing_msg.edit_text("❌ Ошибка при обработке видео. Проверьте формат файла.")
            
            # Удаляем временные файлы
            try:
                os.unlink(input_path)
                if os.path.exists(output_path):
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
    print("🤖 Высококачественный бот запущен!")
    print("📹 Сохраняет качество видео и звук!")
    print("Нажмите Ctrl+C для остановки")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
