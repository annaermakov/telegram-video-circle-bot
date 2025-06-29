# Telegram Video Circle Bot

Бот для создания видеокружков из любых видео файлов.

## 🚀 Возможности

- Конвертация любых видео в видеокружки
- Сохранение звука
- Автоматическая обрезка и масштабирование
- Поддержка всех популярных форматов

## 🌐 Деплой на Railway (бесплатно)

### 1. Подготовка

1. Создайте аккаунт на [Railway.app](https://railway.app)
2. Привяжите свой GitHub аккаунт

### 2. Загрузка проекта

```bash
# Инициализация git репозитория
git init
git add .
git commit -m "Initial commit"

# Создание репозитория на GitHub
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

### 3. Деплой на Railway

1. Зайдите на [Railway.app](https://railway.app)
2. Нажмите "New Project"
3. Выберите "Deploy from GitHub repo"
4. Выберите ваш репозиторий
5. Добавьте переменную окружения:
   - Name: `TELEGRAM_BOT_TOKEN`
   - Value: ваш токен бота

### 4. Получение токена бота

1. Напишите [@BotFather](https://t.me/botfather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте полученный токен

## 💻 Локальный запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Установка переменной окружения
export TELEGRAM_BOT_TOKEN="ваш_токен_здесь"

# Запуск
python bot.py
```

## 📁 Структура проекта

- `bot.py` - основной файл бота
- `config.py` - конфигурация
- `requirements.txt` - зависимости Python
- `Procfile` - конфигурация для Railway
- `nixpacks.toml` - настройки системных зависимостей

## 🔧 Настройки

- **Размер видеокружка**: 240x240 пикселей
- **Максимальный размер файла**: 50MB
- **Максимальная длительность**: 60 секунд

## 🎯 Использование

1. Найдите бота в Telegram
2. Отправьте `/start`
3. Отправьте видео
4. Получите видеокружок!
