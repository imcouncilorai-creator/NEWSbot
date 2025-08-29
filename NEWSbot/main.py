#!/usr/bin/env python3
"""
Основной файл для запуска новостного Telegram бота на Replit
Этот файл объединяет новостной бот и keep-alive сервер
"""

import threading
import time
import logging
from newsbot import main as newsbot_main

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Главная функция для запуска новостного бота с keep-alive"""
    try:
        logger.info("🚀 Запуск новостного Telegram бота на Replit...")
        
        # Запуск новостного бота (включает в себя keep-alive)
        newsbot_main()
        
    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()
