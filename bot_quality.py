import os
import asyncio
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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

# Настройки качества
QUALITY_SETTINGS = {
    'low': {
        'size': 240,
        'crf': 23,
        'preset': 'fast',
        'name': '240p (быстро)',
        'bitrate': '500k'
    },
    'medium': {
        'size': 480,
        'crf': 20,
        'preset': 'medium', 
        'name': '480p (средне)',
        'bitrate': '1000k'
    },
    'high': {
        'size': 720,
        'crf': 18,
        'preset': 'slow',
        'name': '720p (высокое)',
        'bitrate': '2000k'
    },
    'ultra': {
        'size': 1080,
        'crf': 16,
        'preset': 'slow',
        'name': '1080p (максимум)',
        'bitrate': '4000k'
    }
}

class VideoCircleBot:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.pending_videos = {}  # Хранилище для видео в ожидании выбора качества
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_msg = """🎥 Привет! Я бот для создания видеокружков с выбором качества!

📹 Отправь мне видео, и я предложу выбрать качество:
• 240p - быстро, маленький размер
• 480p - средне, баланс качества и размера  
• 720p - высокое качество
• 1080p - максимальное качество

/help - подробная справка"""
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_msg = """🔧 Как использовать бота:

1. Отправьте видео файл любого формата
2. Выберите качество обработки из предложенных вариантов
3. Дождитесь обработки и получите видеокружок

📊 Качества:
• 240p - размер видеокружка 240×240, быстрая обработка
• 480p - размер видеокружка 480×480, среднее качество
• 720p - размер видеокружка 720×720, высокое качество  
• 1080p - размер видеокружка 1080×1080, максимальное качество

⚠️ Чем выше качество, тем дольше обработка!

✅ Поддерживаемые форматы: MP4, AVI, MOV, MKV, WebM и другие
🔊 Звук всегда сохраняется в высоком качестве"""
        await update.message.reply_text(help_msg)
    
    def process_video_to_circle_sync(self, input_path, output_path, quality='medium'):
        """Высококачественная конвертация видео с выбранным качеством"""
        try:
            settings = QUALITY_SETTINGS[quality]
            
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
            
            # Обработка с выбранным качеством
            input_stream = ffmpeg.input(input_path)
            
            # Обрабатываем видео
            video_processed = (
                input_stream
                .video
                .filter('crop', size, size, x_offset, y_offset)
                .filter('scale', settings['size'], settings['size'])
            )
            
            # Настройки для выбранного качества
            output_args = {
                'vcodec': 'libx264',
                'preset': settings['preset'],
                'crf': settings['crf'],
                'pix_fmt': 'yuv420p',
                'movflags': 'faststart',
                'profile:v': 'high',
                'level': '4.0',
                'maxrate': settings['bitrate'],
                'bufsize': f"{int(settings['bitrate'][:-1]) * 2}k"  # Буфер в 2 раза больше битрейта
            }
            
            # Добавляем аудио если есть
            if has_audio:
                audio_processed = input_stream.audio
                output_args.update({
                    'acodec': 'aac',
                    'audio_bitrate': '192k',  # Увеличиваем качество звука
                    'ar': 48000,              # Профессиональная частота
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
        """Обработчик видео сообщений - показывает выбор качества"""
        try:
            # Получаем видео файл
            video = update.message.video or update.message.document
            
            if not video:
                await update.message.reply_text("❌ Не удалось получить видео файл")
                return
            
            # Проверяем размер файла
            if video.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await update.message.reply_text(f"❌ Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE_MB}MB")
                return
            
            # Сохраняем информацию о видео
            user_id = update.effective_user.id
            self.pending_videos[user_id] = {
                'file_id': video.file_id,
                'file_size': video.file_size,
                'message_id': update.message.message_id
            }
            
            # Создаем клавиатуру с выбором качества
            keyboard = []
            for quality_key, settings in QUALITY_SETTINGS.items():
                keyboard.append([
                    InlineKeyboardButton(
                        f"📹 {settings['name']}", 
                        callback_data=f"quality_{quality_key}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем сообщение с выбором качества
            await update.message.reply_text(
                "🎬 Выберите качество для обработки видео:\n\n"
                "• 240p - быстро (5-10 сек)\n"
                "• 480p - средне (10-20 сек)\n" 
                "• 720p - высокое (20-40 сек)\n"
                "• 1080p - максимум (30-60 сек)\n\n"
                "⚠️ Чем выше качество, тем больше времени и размер файла!",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Ошибка при обработке видео: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке видео")
    
    async def handle_quality_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора качества"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            
            # Проверяем, есть ли сохраненное видео
            if user_id not in self.pending_videos:
                await query.edit_message_text("❌ Видео не найдено. Отправьте видео заново.")
                return
            
            # Получаем выбранное качество
            quality = query.data.replace('quality_', '')
            if quality not in QUALITY_SETTINGS:
                await query.edit_message_text("❌ Неверное качество. Попробуйте еще раз.")
                return
            
            settings = QUALITY_SETTINGS[quality]
            video_info = self.pending_videos[user_id]
            
            # Обновляем сообщение
            await query.edit_message_text(f"🔄 Обрабатываю видео в качестве {settings['name']}...")
            
            # Скачиваем файл
            file = await context.bot.get_file(video_info['file_id'])
            
            # Создаем временные файлы
            input_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            output_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            
            input_path = input_file.name
            output_path = output_file.name
            
            input_file.close()
            output_file.close()
            
            # Скачиваем видео
            await file.download_to_drive(input_path)
            
            await query.edit_message_text(f"🎬 Создаю видеокружок {settings['name']}...")
            
            # Запускаем обработку в отдельном потоке
            # Динамические таймауты в зависимости от качества
            timeouts = {
                'low': 60,     # 1 минута для 240p
                'medium': 90,  # 1.5 минуты для 480p
                'high': 180,   # 3 минуты для 720p
                'ultra': 300   # 5 минут для 1080p
            }
            timeout = timeouts.get(quality, 120)
            
            try:
                loop = asyncio.get_event_loop()
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, self.process_video_to_circle_sync, input_path, output_path, quality),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.error("Таймаут при обработке видео")
                await query.edit_message_text("❌ Видео слишком длинное для обработки. Попробуйте покороче или меньше качество.")
                return
            
            if success:
                # Проверяем размер выходного файла
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    await query.edit_message_text(f"📤 Отправляю видеокружок {settings['name']}...")
                    
                    # Отправляем видеокружок
                    with open(output_path, 'rb') as video_file:
                        await context.bot.send_video_note(
                            chat_id=update.effective_chat.id,
                            video_note=video_file,
                            duration=min(60, MAX_DURATION_SECONDS),
                            length=settings['size'],  # Размер соответствует качеству
                            reply_to_message_id=video_info['message_id']
                        )
                    
                    await query.edit_message_text(f"✅ Готово! Видеокружок {settings['name']} создан!")
                else:
                    await query.edit_message_text("❌ Ошибка: выходной файл пустой")
                
            else:
                await query.edit_message_text("❌ Ошибка при обработке видео. Проверьте формат файла.")
            
            # Удаляем из хранилища
            del self.pending_videos[user_id]
            
            # Удаляем временные файлы
            try:
                os.unlink(input_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Ошибка при обработке выбора качества: {e}")
            await query.edit_message_text("❌ Произошла ошибка при обработке видео")
    
    async def handle_other_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик других типов сообщений"""
        await update.message.reply_text(
            "📹 Отправьте видео файл, и я предложу выбрать качество для создания видеокружка!\n\n"
            "Используйте /help для получения дополнительной информации."
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
    
    # Обработчик выбора качества
    application.add_handler(CallbackQueryHandler(bot.handle_quality_choice, pattern=r'^quality_'))
    
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
    print("🤖 Бот с выбором качества запущен!")
    print("📹 Доступные качества: 240p, 480p, 720p, 1080p")
    print("Нажмите Ctrl+C для остановки")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
