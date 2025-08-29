#!/usr/bin/env python3
"""
Telegram бот с базовой функциональностью
Поддерживает основные команды и простое взаимодействие
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from config import BOT_TOKEN, BOT_USERNAME

# Настройка логирования
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        """Инициализация бота"""
        self.application = None
        
    async def start_command(self, update: Update, context: CallbackContext):
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_message = f"""
🤖 Привет, {user.first_name}!

Добро пожаловать в мой Telegram бот!

📋 Доступные команды:
/start - Показать это сообщение
/help - Получить помощь
/status - Проверить статус бота
/info - Информация о боте

💬 Просто напишите мне что-нибудь, и я отвечу!
        """
        await update.message.reply_text(welcome_message)
        logger.info(f"Пользователь {user.username} ({user.id}) запустил бота")

    async def help_command(self, update: Update, context: CallbackContext):
        """Обработчик команды /help"""
        help_text = """
🆘 Помощь по боту

Этот бот работает 24/7 на платформе Replit.

🔧 Основные функции:
• Ответы на сообщения
• Обработка команд
• Логирование действий

📞 Поддержка:
Если у вас есть вопросы, обратитесь к администратору.

🔄 Статус: Бот работает стабильно
        """
        await update.message.reply_text(help_text)
        logger.info(f"Пользователь {update.effective_user.username} запросил помощь")

    async def status_command(self, update: Update, context: CallbackContext):
        """Обработчик команды /status"""
        status_message = """
📊 Статус бота

🟢 Статус: Активен
🕒 Время работы: 24/7
🌐 Платформа: Replit
🔄 Keep-alive: Включен

✅ Все системы работают нормально!
        """
        await update.message.reply_text(status_message)
        logger.info(f"Пользователь {update.effective_user.username} проверил статус")

    async def info_command(self, update: Update, context: CallbackContext):
        """Обработчик команды /info"""
        info_message = f"""
ℹ️ Информация о боте

🤖 Имя: {BOT_USERNAME}
🏗️ Платформа: Replit
🐍 Язык: Python
📚 Библиотека: python-telegram-bot

🔧 Возможности:
• Обработка команд
• Ответы на сообщения  
• Работа 24/7
• Автоматический keep-alive

📅 Создан: 2025
        """
        await update.message.reply_text(info_message)

    async def handle_message(self, update: Update, context: CallbackContext):
        """Обработчик текстовых сообщений"""
        user_message = update.message.text
        user = update.effective_user
        
        # Простые ответы на популярные фразы
        responses = {
            "привет": "👋 Привет! Как дела?",
            "как дела": "У меня всё отлично! А у тебя?",
            "спасибо": "😊 Пожалуйста! Всегда рад помочь!",
            "пока": "👋 До свидания! Возвращайся скорее!",
            "хорошо": "😊 Отлично! Рад это слышать!",
            "плохо": "😔 Сочувствую... Надеюсь, всё наладится!",
            "помощь": "🆘 Используй команду /help для получения справки"
        }
        
        # Поиск ключевых слов в сообщении
        response = None
        for keyword, reply in responses.items():
            if keyword.lower() in user_message.lower():
                response = reply
                break
        
        # Если не найдено ключевое слово, отправляем общий ответ
        if not response:
            response = f"📝 Ты написал: '{user_message}'\n\n💭 Это интересно! Напиши /help для списка команд."
        
        await update.message.reply_text(response)
        logger.info(f"Сообщение от {user.username} ({user.id}): {user_message}")

    async def error_handler(self, update: object, context: CallbackContext):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}")
        
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        if not self.application:
            logger.error("Application не инициализирован")
            return
            
        # Добавляем обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("info", self.info_command))
        
        # Добавляем обработчик текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Добавляем обработчик ошибок
        self.application.add_error_handler(self.error_handler)
        
        logger.info("✅ Обработчики команд настроены")

    def run(self):
        """Запуск бота"""
        try:
            # Создаем приложение
            self.application = Application.builder().token(BOT_TOKEN).build()
            
            # Настраиваем обработчики
            self.setup_handlers()
            
            logger.info(f"🚀 Запуск бота @{BOT_USERNAME}...")
            
            # Запускаем бота
            self.application.run_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}")
            raise

def start_bot():
    """Функция для запуска бота из main.py"""
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    start_bot()
