#!/usr/bin/env python3
"""
Скрипт установки и проверки зависимостей для Telegram-бота видеокружков
"""

import subprocess
import sys
import os
import platform

def run_command(command, description):
    """Выполняет команду и выводит результат"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - успешно")
            return True
        else:
            print(f"❌ {description} - ошибка:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ {description} - исключение: {e}")
        return False

def check_python_version():
    """Проверяет версию Python"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - подходит")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - требуется 3.8+")
        return False

def check_ffmpeg():
    """Проверяет установку FFmpeg"""
    return run_command("ffmpeg -version", "Проверка FFmpeg")

def install_ffmpeg():
    """Устанавливает FFmpeg в зависимости от ОС"""
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        print("📦 Установка FFmpeg через Homebrew...")
        if run_command("which brew", "Проверка Homebrew"):
            return run_command("brew install ffmpeg", "Установка FFmpeg")
        else:
            print("❌ Homebrew не найден. Установите его с https://brew.sh/")
            return False
    
    elif system == "linux":
        # Определяем дистрибутив
        if os.path.exists("/etc/debian_version"):
            return run_command("sudo apt update && sudo apt install -y ffmpeg", "Установка FFmpeg (Debian/Ubuntu)")
        elif os.path.exists("/etc/redhat-release"):
            return run_command("sudo yum install -y ffmpeg", "Установка FFmpeg (RedHat/CentOS)")
        else:
            print("❌ Неизвестный дистрибутив Linux. Установите FFmpeg вручную.")
            return False
    
    elif system == "windows":
        print("❌ Windows обнаружен. Скачайте FFmpeg с https://ffmpeg.org/download.html")
        return False
    
    else:
        print(f"❌ Неизвестная ОС: {system}")
        return False

def install_python_dependencies():
    """Устанавливает Python зависимости"""
    return run_command(f"{sys.executable} -m pip install -r requirements.txt", "Установка Python зависимостей")

def create_env_example():
    """Создает пример файла с переменными окружения"""
    env_content = """# Telegram Bot Token
# Получите токен у @BotFather в Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Опциональные настройки
# VIDEO_CIRCLE_SIZE=240
# MAX_FILE_SIZE_MB=50
# MAX_DURATION_SECONDS=60
"""
    
    with open('.env.example', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("✅ Создан файл .env.example")

def main():
    """Основная функция установки"""
    print("🚀 Установка Telegram-бота для создания видеокружков")
    print("=" * 50)
    
    # Проверяем Python
    if not check_python_version():
        print("❌ Обновите Python до версии 3.8 или выше")
        return False
    
    # Проверяем FFmpeg
    if not check_ffmpeg():
        print("⚠️ FFmpeg не найден. Попытка установки...")
        if not install_ffmpeg():
            print("❌ Не удалось установить FFmpeg. Установите вручную.")
            return False
    
    # Устанавливаем Python зависимости
    if not install_python_dependencies():
        print("❌ Не удалось установить Python зависимости")
        return False
    
    # Создаем пример файла окружения
    create_env_example()
    
    print("\n" + "=" * 50)
    print("✅ Установка завершена успешно!")
    print("\n📋 Следующие шаги:")
    print("1. Получите токен бота у @BotFather в Telegram")
    print("2. Откройте config.py и замените 'YOUR_BOT_TOKEN_HERE' на ваш токен")
    print("   или создайте файл .env с TELEGRAM_BOT_TOKEN=ваш_токен")
    print("3. Запустите бота: python bot.py")
    print("\n🔗 Полная инструкция в файле README.md")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
