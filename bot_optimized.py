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

# Настройки качества для видеокружков (реальные ограничения Telegram)
QUALITY_SETTINGS = {
    'fast': {
        'size': 240,
        'crf': 25,
        'preset': 'ultrafast',
        'name': '240p (быстро)',
        'bitrate': '300k',
        'desc': '~5 сек'
    },
    'balanced': {
        'size': 320,
        'crf': 23,
        'preset': 'fast', 
        'name': '320p (баланс)',
        'bitrate': '500k',
        'desc': '~10 сек'
    },
    'quality': {
        'size': 480,
        'crf': 20,
        'preset': 'medium',
        'name': '480p (качество)',
        'bitrate': '800k',
        'desc': '~15 сек'
    },
    'best': {
        'size': 512,
        'crf': 18,
        'preset': 'medium',
        'name': '512p (высокое)',
        'bitrate': '1000k',
        'desc': '~25 сек'
    },
    'ultra': {
        'size': 680,
        'crf': 16,
        'preset': 'medium',
        'name': '680p (поиск макс)',
        'bitrate': '1500k',
        'desc': '~40 сек обработки'
    }
}

class VideoCircleBot:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.pending_videos = {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_msg = """🎥 Привет! Я бот для создания высококачественных видеокружков!

📹 Отправь мне видео, и я предложу выбрать качество:
• 240p - быстро и компактно
• 320p - оптимальный баланс
• 480p - высокое качество
• 512p - максимальное качество
• 720p - экспериментальное!

🔊 Звук всегда сохраняется в отличном качестве!

/help - подробная справка"""
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_msg = """🔧 Как использовать бота:

1. Отправьте видео файл
2. Выберите качество обработки
3. Получите видеокружок!

📊 Доступные качества:
• 240p - быстрая обработка, маленький размер
• 320p - оптимальный баланс качества и скорости
• 480p - высокое качество, четкая картинка
• 512p - максимальное качество для видеокружков

✅ Поддерживаемые форматы: MP4, AVI, MOV, MKV, WebM
🔊 Звук: 192 кбит/с стерео высокого качества
📏 Ограничения: до 50MB, до 60 сек

⚡ Алгоритм:
1. Обрезка до квадрата (центрированно)
2. Масштабирование до выбранного размера
3. Оптимизация для Telegram
4. Сохранение высококачественного звука"""
        await update.message.reply_text(help_msg)
    
    def process_video_to_circle_sync(self, input_path, output_path, quality='balanced'):
        """Оптимизированная конвертация видео"""
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
            
            # Создаем ffmpeg pipeline
            input_stream = ffmpeg.input(input_path)
            
            # Обрабатываем видео
            video_stream = (
                input_stream
                .video
                .filter('crop', size, size, x_offset, y_offset)
                .filter('scale', settings['size'], settings['size'])
            )
            
            # Базовые настройки для оптимизации
            video_args = {
                'vcodec': 'libx264',
                'preset': settings['preset'],
                'crf': settings['crf'],
                'pix_fmt': 'yuv420p',
                'movflags': 'faststart',
                'maxrate': settings['bitrate'],
                'bufsize': settings['bitrate'],
                't': min(60, MAX_DURATION_SECONDS)  # Ограничиваем длительность
            }
            
            # Добавляем аудио если есть
            if has_audio:
                audio_stream = input_stream.audio
                audio_args = {
                    'acodec': 'aac',
                    'audio_bitrate': '192k',
                    'ar': 48000,
                    'ac': 2
                }
                
                # Объединяем все параметры
                all_args = {**video_args, **audio_args}
                
                # Создаем output
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
            
            # Запускаем с минимальным выводом для скорости
            ffmpeg.run(output, overwrite_output=True, quiet=True, capture_stdout=True)
            
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
            video = update.message.video or update.message.document
            
            if not video:
                await update.message.reply_text("❌ Не удалось получить видео файл")
                return
            
            # Проверяем размер файла
            if video.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await update.message.reply_text(f"❌ Файл слишком большой. Максимум: {MAX_FILE_SIZE_MB}MB")
                return
            
            # Сохраняем информацию о видео
            user_id = update.effective_user.id
            self.pending_videos[user_id] = {
                'file_id': video.file_id,
                'file_size': video.file_size,
                'message_id': update.message.message_id
            }
            
            # Создаем клавиатуру
            keyboard = []
            for quality_key, settings in QUALITY_SETTINGS.items():
                keyboard.append([
                    InlineKeyboardButton(
                        f"📹 {settings['name']} ({settings['desc']})", 
                        callback_data=f"q_{quality_key}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎬 Выберите качество видеокружка:\n\n"
                "📊 Время обработки приблизительное\n"
                "🔊 Звук всегда высокого качества\n"
                "⚡ Оптимизировано для Telegram",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Ошибка при обработке видео: {e}")
            await update.message.reply_text("❌ Произошла ошибка")
    
    async def handle_quality_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора качества"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            
            if user_id not in self.pending_videos:
                await query.edit_message_text("❌ Видео не найдено. Отправьте заново.")
                return
            
            # Получаем качество
            quality = query.data.replace('q_', '')
            if quality not in QUALITY_SETTINGS:
                await query.edit_message_text("❌ Неверное качество.")
                return
            
            settings = QUALITY_SETTINGS[quality]
            video_info = self.pending_videos[user_id]
            
            # Статус обработки
            await query.edit_message_text(f"🔄 Обрабатываю {settings['name']}...")
            
            # Скачиваем файл
            file = await context.bot.get_file(video_info['file_id'])
            
            # Временные файлы
            input_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            output_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            
            input_path = input_file.name
            output_path = output_file.name
            
            input_file.close()
            output_file.close()
            
            # Скачиваем
            await file.download_to_drive(input_path)
            
            await query.edit_message_text(f"🎬 Создаю видеокружок {settings['name']}...")
            
            # Обработка с коротким таймаутом
            try:
                loop = asyncio.get_event_loop()
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, self.process_video_to_circle_sync, input_path, output_path, quality),
                    timeout=45.0  # Короткий универсальный таймаут
                )
            except asyncio.TimeoutError:
                await query.edit_message_text("❌ Таймаут. Попробуйте более короткое видео или меньше качество.")
                return
            
            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                await query.edit_message_text(f"📤 Отправляю {settings['name']}...")
                
                # Отправляем видеокружок
                with open(output_path, 'rb') as video_file:
                    await context.bot.send_video_note(
                        chat_id=update.effective_chat.id,
                        video_note=video_file,
                        duration=min(60, MAX_DURATION_SECONDS),
                        length=settings['size'],
                        reply_to_message_id=video_info['message_id']
                    )
                
                await query.edit_message_text(f"✅ Готово! {settings['name']} создан!")
            else:
                await query.edit_message_text("❌ Ошибка обработки. Проверьте формат видео.")
            
            # Очистка
            del self.pending_videos[user_id]
            
            try:
                os.unlink(input_path)
                if os.path.exists(output_path):
                    os.unlink(output_path)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Ошибка выбора качества: {e}")
            await query.edit_message_text("❌ Произошла ошибка")
    
    async def handle_other_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик других сообщений"""
        await update.message.reply_text(
            "📹 Отправьте видео для создания видеокружка!\n"
            "/help - справка по использованию"
        )

def main():
    """Запуск бота"""
    if not validate_config():
        return
    
    setup_temp_directory()
    
    bot = VideoCircleBot()
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CallbackQueryHandler(bot.handle_quality_choice, pattern=r'^q_'))
    application.add_handler(MessageHandler(filters.VIDEO | (filters.Document.VIDEO), bot.handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_other_messages))
    
    print("🤖 Оптимизированный бот запущен!")
    print("📹 Качества: 240p, 320p, 480p, 512p, 720p (эксперимент)")
    print("⚡ Быстрая обработка, высокое качество звука")
    print("Нажмите Ctrl+C для остановки")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
