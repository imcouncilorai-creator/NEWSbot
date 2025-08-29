#!/usr/bin/env python3
"""
Конфигурация для Telegram бота
Управление настройками и переменными окружения
"""

import os
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

def get_bot_token():
    """Получение токена бота из переменных окружения"""
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        error_msg = """
❌ ОШИБКА: Токен бота не найден!

🔧 Инструкция по настройке:

1. Создайте бота у @BotFather в Telegram
2. Получите токен (выглядит как: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
3. В Replit перейдите в секцию "Secrets" (замок слева)
4. Добавьте новый секрет:
   - Key: BOT_TOKEN
   - Value: ваш_токен_от_BotFather
5. Перезапустите приложение

📖 Подробная инструкция: https://core.telegram.org/bots#6-botfather
        """
        print(error_msg)
        logger.error("Токен бота не настроен в переменных окружения")
        raise ValueError("BOT_TOKEN не найден в переменных окружения")
    
    logger.info("✅ Токен бота успешно загружен")
    return token

def get_channel_id():
    """Получение ID канала из переменных окружения"""
    channel_id = os.getenv('CHANNEL_ID')
    
    if not channel_id:
        error_msg = """
❌ ОШИБКА: ID канала не найден!

🔧 Инструкция по настройке:

1. Создайте канал в Telegram
2. Добавьте бота в канал как администратора
3. Получите ID канала (например: -1001234567890)
4. В Replit перейдите в секцию "Secrets" (замок слева)
5. Добавьте новый секрет:
   - Key: CHANNEL_ID
   - Value: ваш_ID_канала
6. Перезапустите приложение
        """
        print(error_msg)
        logger.error("ID канала не настроен в переменных окружения")
        raise ValueError("CHANNEL_ID не найден в переменных окружения")
    
    logger.info(f"✅ ID канала успешно загружен: {channel_id}")
    return channel_id

def get_bot_username():
    """Получение имени бота (опционально)"""
    username = os.getenv('BOT_USERNAME', 'your_bot')
    logger.info(f"📛 Имя бота: @{username}")
    return username

def validate_config():
    """Проверка корректности конфигурации"""
    try:
        token = get_bot_token()
        
        # Проверяем формат токена
        if ':' not in token or len(token) < 45:
            raise ValueError("Неверный формат токена. Токен должен выглядеть как: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
        
        logger.info("✅ Конфигурация валидна")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка валидации конфигурации: {e}")
        raise

# Загружаем конфигурацию при импорте модуля
try:
    BOT_TOKEN = get_bot_token()
    BOT_USERNAME = get_bot_username()
    CHANNEL_ID = get_channel_id()
    validate_config()
    
    logger.info("🔧 Конфигурация успешно загружена")
    
except Exception as e:
    logger.error(f"💥 Критическая ошибка конфигурации: {e}")
    # Не используем sys.exit() так как это может помешать импорту
    BOT_TOKEN = None
    BOT_USERNAME = None
    CHANNEL_ID = None

# Дополнительные настройки
KEEP_ALIVE_PORT = int(os.getenv('KEEP_ALIVE_PORT', '5000'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Настройки для продакшена
PRODUCTION_MODE = os.getenv('PRODUCTION_MODE', 'true').lower() == 'true'

logger.info(f"🚀 Режим работы: {'Production' if PRODUCTION_MODE else 'Development'}")
logger.info(f"🔧 Keep-alive порт: {KEEP_ALIVE_PORT}")
logger.info(f"📊 Уровень логирования: {LOG_LEVEL}")
