#!/usr/bin/env python3
"""
Новостной Telegram бот для Replit с keep-alive
Автоматически собирает и публикует новости из RSS-лент
"""

import logging
import asyncio
import aiohttp
import feedparser
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.error import TimedOut, TelegramError
from bs4 import BeautifulSoup
import re
import random
import os
import datetime
import threading
import time

try:
    from rss_feeds import RSS_SOURCES
    from config import BOT_TOKEN, BOT_USERNAME, CHANNEL_ID
    from keep_alive import keep_alive
    from scheduler import NewsScheduler
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Создайте config.py с BOT_TOKEN, CHANNEL_ID!")
    exit()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('newsbot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Главное меню
main_keyboard = ReplyKeyboardMarkup([
    ['📰 Свежие новости на сегодня', '📢 Опубликовать в канал'],
    ['📊 Статистика', '📅 Автопубликация'],
    ['🆘 Поддержка']
], resize_keyboard=True)

# Глобальные счётчики
news_fetched = 0
news_posted = 0

# Глобальный планировщик
scheduler_instance = None

class RealNewsParser:
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15'
    ]

    @staticmethod
    async def fetch_rss_content(url: str, timeout=60):
        headers = {'User-Agent': random.choice(RealNewsParser.USER_AGENTS)}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout, headers=headers, ssl=False) as response:
                    if response.status == 200:
                        return await response.text(), None
                    logger.error(f"HTTP {response.status} для {url}")
                    return None, f"HTTP {response.status}"
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            return None, str(e)

    @staticmethod
    def generate_summary(title: str, summary: str, url: str) -> str:
        desc = BeautifulSoup(summary[:600], 'html.parser').get_text(strip=True)
        if len(desc) < 150:
            return ""
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', desc)
        sentences = [s.strip() for s in sentences if s.strip() and s.lower() != title.lower().strip()]
        points = []
        for s in sentences[:3]:
            if s.endswith(('.', '?', '!')):
                points.append(s)
            elif not points:
                return ""
        if not points or len(' '.join(points)) < 150:
            return ""
        return '\n'.join(points)

    @staticmethod
    async def process_news_item(title: str, summary: str, link: str) -> str:
        description = RealNewsParser.generate_summary(title, summary, link)
        if not description:
            return None
        return f"📰 <b>{title}</b>\n{description}\n<a href=\"{link}\">👉 Читать далее</a>"

    @staticmethod
    async def fetch_rss_news(context: CallbackContext, limit: int = 6):
        global news_fetched
        news_items = []
        error_urls = []
        seen_links_file = 'seen_links.txt'
        seen_links = set()
        used_sources = set()

        if os.path.exists(seen_links_file):
            with open(seen_links_file, 'r', encoding='utf-8') as f:
                seen_links = set(f.read().splitlines())

        random.shuffle(RSS_SOURCES['general'])
        for rss_url in RSS_SOURCES['general']:
            if len(news_items) >= limit:
                break
            logger.info(f"Загружаю RSS: {rss_url}")
            rss_content, error = await RealNewsParser.fetch_rss_content(rss_url)
            if not rss_content:
                error_urls.append(f"{rss_url} ({error})")
                continue
            feed = feedparser.parse(rss_content)
            if not feed.entries:
                error_urls.append(f"{rss_url} (пустая лента)")
                continue
            random.shuffle(feed.entries)
            for entry in feed.entries:
                try:
                    link = entry.get('link', '')
                    if link not in seen_links and rss_url not in used_sources:
                        title = entry.get('title', 'Без заголовка')
                        summary = entry.get('summary', entry.get('description', ''))
                        if not summary:
                            continue
                        processed = await RealNewsParser.process_news_item(title, summary, link)
                        if processed:
                            news_items.append({
                                'title': title,
                                'summary': summary,
                                'link': link
                            })
                            seen_links.add(link)
                            used_sources.add(rss_url)
                            logger.info(f"Добавлена новость: {title}")
                            news_fetched += 1
                            break
                except Exception as e:
                    logger.error(f"Ошибка обработки записи {entry.get('link', 'unknown')}: {e}")

        with open(seen_links_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(seen_links))

        return news_items[:limit], error_urls

    @staticmethod
    async def format_news_message(news_items):
        message = f"🔥 <b>АКТУАЛЬНЫЕ НОВОСТИ</b> 🔥\n\n"
        for item in news_items:
            processed = await RealNewsParser.process_news_item(
                item['title'], item['summary'], item['link']
            )
            if processed:
                message += processed + "\n\n—\n\n"
        message += "📢 <b>Новостной дайджест составлен с помощью автоматического Telegram-бота</b> 🎉"
        return message

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    logger.info(f"Пользователь {user.id} запустил /start")
    # Очищаем просмотренные ссылки при запуске
    seen_links_file = 'seen_links.txt'
    if os.path.exists(seen_links_file):
        os.remove(seen_links_file)
    
    try:
        await update.message.reply_html(
            f"👋 <b>Добро пожаловать в новостной бот!</b> 🎉\n\n"
            f"Я помогу вам получать свежие новости и публиковать их в канал.\n\n"
            f"Выберите действие ниже:",
            reply_markup=main_keyboard
        )
        logger.info(f"Приветственное сообщение отправлено пользователю {user.id}")
    except TelegramError as e:
        logger.error(f"Ошибка при отправке приветствия: {e}")
        await update.message.reply_html(
            f"❌ <b>Ошибка!</b> Проверьте права бота.", 
            reply_markup=main_keyboard
        )

async def send_news(update: Update, context: CallbackContext):
    try:
        logger.info(f"Пользователь {update.effective_user.id} запросил новости")
        await update.message.reply_html(
            f"📡 <b>Загружаю свежие новости...</b>", 
            reply_markup=main_keyboard
        )
        
        all_news, error_urls = await RealNewsParser.fetch_rss_news(context)
        
        if not all_news:
            error_msg = f"⚠️ <b>Нет новостей!</b> 😔"
            if error_urls:
                error_msg += f"\nПроблемы с источниками: {len(error_urls)}"
            logger.warning(f"Не удалось загрузить новости: {error_urls}")
            await update.message.reply_html(error_msg, reply_markup=main_keyboard)
            return
        
        message = await RealNewsParser.format_news_message(all_news)
        context.user_data['last_news'] = {
            'items': all_news,
            'message': message
        }
        
        await update.message.reply_html(
            message, 
            disable_web_page_preview=True, 
            reply_markup=main_keyboard
        )
        logger.info(f"Новости отправлены пользователю {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка загрузки новостей: {e}")
        await update.message.reply_html(
            f"❌ <b>Ошибка загрузки!</b> Попробуйте позже.", 
            reply_markup=main_keyboard
        )

async def post_to_channel(update: Update, context: CallbackContext):
    global news_posted
    try:
        logger.info(f"Пользователь {update.effective_user.id} запросил публикацию в канал")
        
        if 'last_news' not in context.user_data:
            await update.message.reply_html(
                f"❌ <b>Сначала загрузите новости!</b>", 
                reply_markup=main_keyboard
            )
            return
        
        news_data = context.user_data['last_news']
        await update.message.reply_html(
            f"📢 <b>Публикую новости в канал...</b>", 
            reply_markup=main_keyboard
        )
        
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=news_data['message'],
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        await update.message.reply_html(
            f"✅ <b>Новости опубликованы!</b> 🎉", 
            reply_markup=main_keyboard
        )
        
        news_posted += len(news_data['items'])
        logger.info(f"Новости опубликованы в канал {CHANNEL_ID}")
        
    except TelegramError as e:
        logger.error(f"Ошибка при публикации в канал: {e}")
        await update.message.reply_html(
            f"❌ <b>Ошибка публикации!</b> Проверьте права бота в канале.", 
            reply_markup=main_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        await update.message.reply_html(
            f"❌ <b>Ошибка публикации!</b> Попробуйте позже.", 
            reply_markup=main_keyboard
        )

async def show_autopublish_info(update: Update, context: CallbackContext):
    """Показать информацию об автопубликации"""
    try:
        logger.info(f"Пользователь {update.effective_user.id} запросил информацию об автопубликации")
        
        # Получаем информацию о планировщике
        schedule_info = scheduler_instance.get_schedule_info() if scheduler_instance else {
            'auto_posts_count': 0,
            'last_auto_post': 'Нет',
            'next_auto_post': 'Не активно',
            'schedule_times': ['09:00', '12:00', '15:00', '18:00', '21:00'],
            'is_running': False
        }
        
        auto_message = (
            f"📅 <b>Автоматическая публикация новостей</b>\n\n"
            f"⏰ <b>Расписание (МСК):</b>\n"
        )
        
        for time_str in schedule_info['schedule_times']:
            auto_message += f"   • {time_str}\n"
        
        auto_message += (
            f"\n📊 <b>Статистика:</b>\n"
            f"🤖 Автопубликаций выполнено: {schedule_info['auto_posts_count']}\n"
            f"🕐 Последняя публикация: {schedule_info['last_auto_post']}\n"
            f"⏳ Следующая публикация: {schedule_info['next_auto_post']}\n\n"
            f"🔄 <b>Статус:</b> {'✅ Активна' if schedule_info['is_running'] else '❌ Неактивна'}\n\n"
            f"ℹ️ <i>Бот автоматически собирает свежие новости и публикует их в канал 5 раз в день. "
            f"Новости берутся из проверенных RSS-источников и форматируются для удобного чтения.</i>"
        )
        
        await update.message.reply_html(auto_message, reply_markup=main_keyboard)
        logger.info(f"Информация об автопубликации отправлена пользователю {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка показа информации об автопубликации: {e}")
        await update.message.reply_html(
            f"❌ <b>Ошибка загрузки информации!</b>", 
            reply_markup=main_keyboard
        )

async def show_stats(update: Update, context: CallbackContext):
    try:
        logger.info(f"Пользователь {update.effective_user.id} запросил статистику")
        
        # Получаем количество подписчиков канала
        try:
            subscriber_count = await context.bot.get_chat_member_count(CHANNEL_ID)
        except Exception as e:
            logger.error(f"Ошибка получения статистики канала: {e}")
            subscriber_count = "Недоступно"
        
        # Сохраняем статистику подписчиков
        subscribers_file = 'subscribers.txt'
        if isinstance(subscriber_count, int):
            with open(subscribers_file, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.datetime.now().isoformat()},{subscriber_count}\n")
        
        # Получаем информацию о планировщике
        schedule_info = scheduler_instance.get_schedule_info() if scheduler_instance else {
            'auto_posts_count': 0,
            'last_auto_post': 'Нет',
            'next_auto_post': 'Не активно',
            'is_running': False
        }
        
        stats_message = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"📈 Получено новостей: {news_fetched}\n"
            f"📤 Отправлено вручную: {news_posted}\n"
            f"🤖 Автопубликаций: {schedule_info['auto_posts_count']}\n"
            f"👥 Подписчиков в канале: {subscriber_count}\n\n"
            f"📅 <b>Автопубликация:</b>\n"
            f"⏰ Расписание: 9:00, 12:00, 15:00, 18:00, 21:00 МСК\n"
            f"🕐 Последняя: {schedule_info['last_auto_post']}\n"
            f"⏳ Следующая: {schedule_info['next_auto_post']}\n"
            f"🔄 Статус: {'✅ Активна' if schedule_info['is_running'] else '❌ Неактивна'}\n\n"
            f"🕒 Бот работает 24/7 на Replit"
        )
        
        await update.message.reply_html(stats_message, reply_markup=main_keyboard)
        logger.info(f"Статистика отправлена пользователю {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await update.message.reply_html(
            f"❌ <b>Ошибка загрузки статистики!</b>", 
            reply_markup=main_keyboard
        )

async def handle_message(update: Update, context: CallbackContext):
    text = update.message.text
    logger.info(f"Получено сообщение: {text}")
    
    try:
        if text == '📰 Свежие новости на сегодня':
            await send_news(update, context)
        elif text == '📢 Опубликовать в канал':
            await post_to_channel(update, context)
        elif text == '📊 Статистика':
            await show_stats(update, context)
        elif text == '📅 Автопубликация':
            await show_autopublish_info(update, context)
        elif text == '🆘 Поддержка':
            await update.message.reply_text(
                "📞 Поддержка бота:\n\n"
                "🔧 Новостной бот работает автоматически\n"
                "⚡ Работает 24/7 на платформе Replit\n"
                "📰 Собирает новости из проверенных источников\n"
                "📅 Автоматическая публикация 5 раз в день\n\n"
                "❓ Если есть вопросы - обратитесь к администратору @imcouncilor", 
                reply_markup=main_keyboard
            )
        else:
            await update.message.reply_html(
                f"📝 <b>Используйте кнопки меню для работы с ботом!</b> 😊", 
                reply_markup=main_keyboard
            )
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}")
        await update.message.reply_html(
            f"❌ <b>Произошла ошибка!</b> Попробуйте позже.", 
            reply_markup=main_keyboard
        )

async def error_callback(update: Update, context: CallbackContext):
    logger.error(f"Ошибка в боте: {context.error}")
    if update and hasattr(update, 'message') and update.message:
        try:
            await update.message.reply_html(
                f"❌ <b>Произошла ошибка!</b> Попробуйте позже.", 
                reply_markup=main_keyboard
            )
        except Exception:
            pass

def run_bot():
    """Запуск бота в отдельной функции"""
    global scheduler_instance
    
    try:
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_callback)
        
        logger.info(f"🚀 Запуск новостного бота @{BOT_USERNAME}...")
        
        # Создаем и запускаем планировщик автопубликации
        logger.info("📅 Инициализация планировщика автопубликации...")
        scheduler_instance = NewsScheduler(BOT_TOKEN, CHANNEL_ID, RealNewsParser)
        scheduler_instance.start()
        
        # Запускаем бота
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        raise
    finally:
        # Останавливаем планировщик при завершении
        if scheduler_instance:
            scheduler_instance.stop()

def main():
    """Главная функция для запуска всех компонентов"""
    try:
        logger.info("🚀 Запуск новостного бота на Replit...")
        
        # Запуск keep-alive сервера в отдельном потоке
        logger.info("📡 Запуск keep-alive сервера...")
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        
        # Небольшая задержка для инициализации сервера
        time.sleep(2)
        
        # Запуск бота (основной поток)
        logger.info("🤖 Запуск новостного бота...")
        run_bot()
        
    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()