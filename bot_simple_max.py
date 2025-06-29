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
        welcome_msg = """🎥 Привет! Я бот для создания видеокружков максимального качества!

📹 Просто отправь мне любое видео!
🎯 Автоматически создам видеокружок в 640p - максимальном качестве для Telegram
🔊 Звук: 192kbps стерео высочайшего качества!

✨ Поддерживаю все форматы: MP4, AVI, MOV, MKV, WebM и другие
⚡ Быстрая обработка с максимальным качеством!

/help - справка"""
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_msg = """🔧 Как использовать:

1. Отправьте видео файл любого формата
2. Бот автоматически создаст видеокружок максимального качества
3. Получите результат!

🎯 Автоматические настройки:
• Разрешение: 640×640 (максимум для Telegram)
• Звук: 192 кбит/с стерео, 48kHz
• Кодек: H.264 высокого профиля
• Битрейт: 1500 кбит/с

✅ Поддержка: MP4, AVI, MOV, MKV, WebM, FLV и другие
📏 Ограничения: до 50MB, до 60 секунд

⚡ Алгоритм:
1. Обрезка до квадрата (по центру)
2. Масштабирование до 640×640
3. Максимальное качество видео и звука
4. Оптимизация для Telegram"""
        await update.message.reply_text(help_msg)
    
    def process_video_to_circle_sync(self, input_path, output_path):
        """Обработка видео в максимальном качестве 640p"""
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
            
            # Создаем ffmpeg pipeline
            input_stream = ffmpeg.input(input_path)
            
            # Обрабатываем видео в максимальном качестве 640p
            video_stream = (
                input_stream
                .video
                .filter('crop', size, size, x_offset, y_offset)
                .filter('scale', 640, 640)  # Максимальное поддерживаемое разрешение
            )
            
            # Максимальные настройки качества
            video_args = {
                'vcodec': 'libx264',
                'preset': 'medium',        # Баланс качества и скорости
                'crf': 16,                 # Очень высокое качество
                'pix_fmt': 'yuv420p',
                'movflags': 'faststart',
                'maxrate': '1500k',        # Высокий битрейт
                'bufsize': '3000k',        # Большой буфер
                'profile:v': 'high',       # Высокий профиль
                'level': '4.0',
                't': min(60, MAX_DURATION_SECONDS)
            }
            
            # Добавляем аудио максимального качества
            if has_audio:
                audio_stream = input_stream.audio
                audio_args = {
                    'acodec': 'aac',
                    'audio_bitrate': '192k',  # Максимальное качество звука
                    'ar': 48000,              # Профессиональная частота
                    'ac': 2                   # Стерео
                }
                
                # Объединяем все параметры
                all_args = {**video_args, **audio_args}
                
                # Создаем output с видео и аудио
                output = ffmpeg.output(
                    video_stream,
                    audio_stream,
                    output_path,
                    **all_args
                )
            else:
                # Только видео
                output = ffmpeg.output(
                    video_stream,
                    output_path,
                    **video_args
                )
            
            # Запускаем обработку
            ffmpeg.run(output, overwrite_output=True, quiet=True)
            
            return True
            
        except ffmpeg.Error as e:
            logger.error(f"Ошибка ffmpeg: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при обработке видео: {e}")
            return False
    
    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик видео сообщений"""
        try:
            # Отправляем сообщение о начале обработки
            processing_msg = await update.message.reply_text("🔄 Обрабатываю видео в максимальном качестве 640p...")
            
            # Получаем видео файл
            video = update.message.video or update.message.document
            
            if not video:
                await processing_msg.edit_text("❌ Не удалось получить видео файл")
                return
            
            # Проверяем размер файла
            if video.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await processing_msg.edit_text(f"❌ Файл слишком большой. Максимум: {MAX_FILE_SIZE_MB}MB")
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
            
            await processing_msg.edit_text("🎬 Создаю видеокружок 640p максимального качества...")
            
            # Запускаем обработку в отдельном потоке с большим таймаутом
            try:
                loop = asyncio.get_event_loop()
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, self.process_video_to_circle_sync, input_path, output_path),
                    timeout=90.0  # Большой таймаут для максимального качества
                )
            except asyncio.TimeoutError:
                logger.error("Таймаут при обработке видео")
                await processing_msg.edit_text("❌ Видео слишком длинное для обработки. Попробуйте покороче.")
                return
            
            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                await processing_msg.edit_text("📤 Отправляю видеокружок максимального качества...")
                
                # Отправляем видеокружок
                with open(output_path, 'rb') as video_file:
                    await context.bot.send_video_note(
                        chat_id=update.effective_chat.id,
                        video_note=video_file,
                        duration=min(60, MAX_DURATION_SECONDS),
                        length=640,  # Максимальный размер
                        reply_to_message_id=update.message.message_id
                    )
                
                await processing_msg.edit_text("✅ Готово! Видеокружок 640p создан в максимальном качестве!")
                
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
            await update.message.reply_text("❌ Произошла ошибка при обработке видео")
    
    async def handle_other_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик других типов сообщений"""
        await update.message.reply_text(
            "📹 Отправьте видео для создания видеокружка максимального качества!\n\n"
            "🎯 Автоматически: 640p, 192kbps звук, максимальное качество\n"
            "/help - подробная справка"
        )

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
    print("🤖 Простой бот максимального качества запущен!")
    print("🎯 Автоматически: 640p (максимум для Telegram)")
    print("🔊 Звук: 192kbps стерео профессиональное качество")
    print("⚡ Без выбора - сразу максимальное качество!")
    print("Нажмите Ctrl+C для остановки")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
