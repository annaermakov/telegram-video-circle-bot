#!/bin/bash

# Скрипт запуска Telegram-бота для создания видеокружков

echo "🤖 Запуск Telegram-бота для создания видеокружков..."

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено!"
    echo "Выполните: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Проверяем наличие токена
if ! python3 -c "from config import validate_config; validate_config()" 2>/dev/null; then
    echo "❌ Не настроен токен бота!"
    echo "Получите токен у @BotFather и установите его в config.py"
    exit 1
fi

# Запускаем бота
echo "🚀 Запуск бота..."
python3 bot.py
