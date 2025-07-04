"""
Конфигурация для Telegram-бота создания видеокружков
"""

import os
from typing import Tuple

# Токен бота (через переменную окружения)
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Настройки видеокружков
VIDEO_CIRCLE_SIZE = 240  # Размер видеокружка в пикселях
MAX_FILE_SIZE_MB = 50    # Максимальный размер файла в МБ
MAX_DURATION_SECONDS = 60  # Максимальная длительность видеокружка в секундах

# Настройки обработки видео
VIDEO_CODEC = 'libx264'  # Кодек для видео
AUDIO_CODEC = 'aac'      # Кодек для аудио
VIDEO_BITRATE = '1000k'  # Битрейт видео
AUDIO_BITRATE = '128k'   # Битрейт аудио

# Качество сжатия (0-51, где 0 - без потерь, 23 - по умолчанию, 51 - максимальное сжатие)
CRF_VALUE = 23

# Настройки временных файлов
TEMP_DIR = '/tmp/video_circle_bot'  # Директория для временных файлов
CLEANUP_TEMP_FILES = True           # Автоматическая очистка временных файлов

# Настройки логирования
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Сообщения бота
MESSAGES = {
    'welcome': """🎥 Привет! Я бот для создания видеокружков!

Просто отправь мне любое видео, и я превращу его в видеокружок.
Поддерживаются все популярные форматы видео.

📝 Команды:
/start - показать это сообщение
/help - подробная помощь

Отправь видео для начала!""",
    
    'help': """🔧 Как использовать бота:

1. Отправьте видео файл любого формата
2. Бот автоматически обработает видео
3. Получите готовый видеокружок

✅ Поддерживаемые форматы:
MP4, AVI, MOV, MKV, WebM и другие

⚡ Особенности:
• Сохраняется звук
• Автоматическое масштабирование
• Круглая обрезка видео
• Быстрая обработка

⚠️ Ограничения:
• Максимальный размер файла: {max_size}MB
• Максимальная длительность: {max_duration} секунд""".format(
        max_size=MAX_FILE_SIZE_MB,
        max_duration=MAX_DURATION_SECONDS
    ),
    
    'processing': '🔄 Обрабатываю видео...',
    'creating_circle': '🎬 Создаю видеокружок...',
    'sending': '📤 Отправляю видеокружок...',
    'error_file_size': f'❌ Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE_MB}MB',
    'error_no_video': '❌ Не удалось получить видео файл',
    'error_processing': '❌ Ошибка при обработке видео. Попробуйте другой файл.',
    'error_general': '❌ Произошла ошибка при обработке видео',
    'send_video': """📹 Отправьте видео файл, и я превращу его в видеокружок!

Используйте /help для получения дополнительной информации."""
}

# Проверка конфигурации
def validate_config() -> bool:
    """Проверяет корректность конфигурации"""
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("❌ Не установлен токен бота!")
        print("Установите токен в config.py или через переменную окружения TELEGRAM_BOT_TOKEN")
        return False
    
    if VIDEO_CIRCLE_SIZE <= 0:
        print("❌ Размер видеокружка должен быть больше 0")
        return False
    
    if MAX_FILE_SIZE_MB <= 0:
        print("❌ Максимальный размер файла должен быть больше 0")
        return False
    
    return True

# Создание директории для временных файлов
def setup_temp_directory():
    """Создает директорию для временных файлов"""
    os.makedirs(TEMP_DIR, exist_ok=True)
