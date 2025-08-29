import logging
import asyncio
import aiohttp
import feedparser
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TimedOut, TelegramError
from bs4 import BeautifulSoup
import re
import random
import telegram
import os
import datetime
from rss_feeds import RSS_SOURCES

if telegram.__version__ != '21.4':
    print(f"❌ Требуется python-telegram-bot==21.4, установлена {telegram.__version__}")
    exit()

try:
    from config import BOT_TOKEN, CHANNEL_ID
except ImportError:
    print("❌ Создайте config.py с BOT_TOKEN, CHANNEL_ID!")
    exit()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

main_keyboard = ReplyKeyboardMarkup([
    ['📰 Свежие новости на сегодня', '📢 Опубликовать в канал'],
    ['📊 Статистика', '🆘 Поддержка']
], resize_keyboard=True)

# Глобальные счётчики
news_fetched = 0
news_posted = 0

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
        desc = BeautifulSoup(summary[:600], 'lxml').get_text(strip=True)
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
        return f"📰 <b>{title}</b>\n{description}\n<a href=\"{link}\">👉 link</a>"

    @staticmethod
    async def fetch_rss_news(context: ContextTypes.DEFAULT_TYPE, limit: int = 6):
        global news_fetched
        news_items = []
        error_urls = []
        debug_info = []
        seen_links_file = 'seen_links.txt'
        seen_links = set()
        used_sources = set()

        if os.path.exists(seen_links_file):
            with open(seen_links_file, 'r') as f:
                seen_links = set(f.read().splitlines())

        random.shuffle(RSS_SOURCES['general'])
        for rss_url in RSS_SOURCES['general']:
            if len(news_items) >= limit:
                break
            logger.info(f"Загружаю RSS: {rss_url}")
            rss_content, error = await RealNewsParser.fetch_rss_content(rss_url)
            if not rss_content:
                error_urls.append(f"{rss_url} ({error})")
                debug_info.append(f"{rss_url}: Ошибка - {error}")
                continue
            feed = feedparser.parse(rss_content)
            if not feed.entries:
                error_urls.append(f"{rss_url} (пустая лента)")
                debug_info.append(f"{rss_url}: Пустая лента")
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
                            debug_info.append(f"{rss_url}: {title}")
                            news_fetched += 1
                            break
                except Exception as e:
                    debug_info.append(f"{rss_url}: Ошибка записи {entry.get('link', 'unknown')}: {e}")

        with open(seen_links_file, 'a') as f:
            f.write('\n'.join(seen_links))

        return news_items[:limit], error_urls, debug_info

    @staticmethod
    async def format_news_message(news_items):
        message = f"📰 <b>СВЕЖИЕ НОВОСТИ</b>\n\n"
        for item in news_items:
            processed = await RealNewsParser.process_news_item(
                item['title'], item['summary'], item['link']
            )
            message += processed + "\n\n—\n\n"
        message += "📢 <b>Новостной дайджест составлен с применением Telegram-бота</b> 🎉"
        channel_message = f"📰 <b>СВЕЖИЕ НОВОСТИ</b>\n\n" + \
                         "\n\n—\n\n".join([await RealNewsParser.process_news_item(item['title'], item['summary'], item['link']) for item in news_items]) + \
                         "\n\n📢 <b>Новостной дайджест составлен с применением Telegram-бота</b> 🎉"
        return message, channel_message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"Вызов функции start для пользователя {user.id}")
    seen_links_file = 'seen_links.txt'
    if os.path.exists(seen_links_file):
        os.remove(seen_links_file)
    logger.info(f"Пользователь {user.id} запустил /start")
    try:
        await update.message.reply_html(
            f"👋 <b>Добро пожаловать!</b> 🎉\nВыберите действие ниже:",
            reply_markup=main_keyboard
        )
        logger.info(f"Приветственное сообщение отправлено пользователю {user.id}")
    except TelegramError as e:
        logger.error(f"Ошибка Telegram при отправке приветствия пользователю {user.id}: {e}")
        await update.message.reply_html(f"❌ <b>Ошибка!</b> Проверьте права бота. 😞", reply_markup=main_keyboard)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Вызов функции test для пользователя {update.effective_user.id}")
    logger.info(f"Пользователь {update.effective_user.id} запросил /test")
    try:
        await update.message.reply_text("✅ Бот работает! 😊", reply_markup=main_keyboard)
        logger.info(f"Тестовое сообщение отправлено пользователю {update.effective_user.id}")
    except TelegramError as e:
        logger.error(f"Ошибка Telegram при отправке тестового сообщения пользователю {update.effective_user.id}: {e}")
        await update.message.reply_html(f"❌ <b>Ошибка!</b> Проверьте права бота. 😞", reply_markup=main_keyboard)

async def send_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Вызов функции send_news для пользователя {update.effective_user.id}")
    try:
        logger.info(f"Пользователь {update.effective_user.id} запросил новости")
        await update.message.reply_html(f"📡 <b>Загружаю свежие новости...</b>", reply_markup=main_keyboard)
        all_news, error_urls, debug_info = await RealNewsParser.fetch_rss_news(context)
        if not all_news:
            error_msg = f"⚠️ <b>Нет новостей!</b> 😔"
            if error_urls:
                error_msg += f"\nПроблемы: {', '.join(error_urls[:3])}"
            logger.warning(f"Не удалось загрузить новости: {error_urls}")
            await update.message.reply_html(error_msg, reply_markup=main_keyboard)
            return
        message, channel_message = await RealNewsParser.format_news_message(all_news)
        context.user_data['last_news'] = {
            'items': all_news,
            'message': message,
            'channel_message': channel_message
        }
        await update.message.reply_html(message, disable_web_page_preview=True, reply_markup=main_keyboard)
        logger.info(f"Новости отправлены пользователю {update.effective_user.id}")
    except TelegramError as e:
        logger.error(f"Ошибка Telegram при отправке новостей пользователю {update.effective_user.id}: {e}")
        await update.message.reply_html(f"❌ <b>Ошибка загрузки!</b> Проверьте права бота. 😞", reply_markup=main_keyboard)
    except Exception as e:
        logger.error(f"Ошибка загрузки новостей: {e}", exc_info=True)
        await update.message.reply_html(f"❌ <b>Ошибка загрузки!</b> Попробуйте позже. 😞", reply_markup=main_keyboard)

async def post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global news_posted
    logger.debug(f"Вызов функции post_to_channel для пользователя {update.effective_user.id}")
    try:
        logger.info(f"Пользователь {update.effective_user.id} запросил публикацию в канал")
        if 'last_news' not in context.user_data:
            await update.message.reply_html(f"❌ <b>Сначала загрузите новости!</b> 😔", reply_markup=main_keyboard)
            return
        news_data = context.user_data['last_news']
        await update.message.reply_html(f"📢 <b>Публикую новости в канал...</b>", reply_markup=main_keyboard)
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=news_data['channel_message'],
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        await update.message.reply_html(f"✅ <b>Новости опубликованы!</b> 🎉", reply_markup=main_keyboard)
        news_posted += len(news_data['items'])
        logger.info(f"Новости опубликованы в канал {CHANNEL_ID}")
    except TelegramError as e:
        logger.error(f"Ошибка Telegram при публикации в канал: {e}")
        await update.message.reply_html(f"❌ <b>Ошибка публикации!</b> Проверьте права бота в канале. 😞", reply_markup=main_keyboard)
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}", exc_info=True)
        await update.message.reply_html(f"❌ <b>Ошибка публикации!</b> Попробуйте позже. 😞", reply_markup=main_keyboard)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"Вызов функции show_stats для пользователя {update.effective_user.id}")
    try:
        logger.info(f"Пользователь {update.effective_user.id} запросил статистику")
        subscriber_count = await context.bot.get_chat_member_count(CHANNEL_ID)
        subscribers_file = 'subscribers.txt'
        subscriber_history = []
        if os.path.exists(subscribers_file):
            with open(subscribers_file, 'r') as f:
                subscriber_history = [line.split(',') for line in f.read().splitlines()]
                subscriber_history = [(datetime.datetime.fromisoformat(date), int(count)) for date, count in subscriber_history]

        with open(subscribers_file, 'a') as f:
            f.write(f"{datetime.datetime.now().isoformat()},{subscriber_count}\n")

        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        recent_history = [(date, count) for date, count in subscriber_history if date >= week_ago]
        new_subscribers = 0
        left_subscribers = 0
        if recent_history:
            oldest_count = recent_history[0][1]
            new_subscribers = max(0, subscriber_count - oldest_count)
            left_subscribers = max(0, oldest_count - subscriber_count)

        stats_message = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"Получено новостей: {news_fetched}\n"
            f"Отправлено в канал: {news_posted}\n"
            f"Новых подписчиков за неделю: {new_subscribers}\n"
            f"Ушедших подписчиков за неделю: {left_subscribers}\n"
            f"Текущее число подписчиков: {subscriber_count}"
        )
        await update.message.reply_html(stats_message, reply_markup=main_keyboard)
        logger.info(f"Статистика отправлена пользователю {update.effective_user.id}")
    except TelegramError as e:
        logger.error(f"Ошибка Telegram при отправке статистики пользователю {update.effective_user.id}: {e}")
        await update.message.reply_html(f"❌ <b>Ошибка загрузки статистики!</b> Проверьте права бота. 😞", reply_markup=main_keyboard)
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", exc_info=True)
        await update.message.reply_html(f"❌ <b>Ошибка загрузки статистики!</b> Попробуйте позже. 😞", reply_markup=main_keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    update_id = update.update_id
    logger.debug(f"Получено обновление {update_id} от {update.effective_user.id}: {text}")
    try:
        if text == '📰 Свежие новости на сегодня':
            await send_news(update, context)
        elif text == '📢 Опубликовать в канал':
            await post_to_channel(update, context)
        elif text == '📊 Статистика':
            await show_stats(update, context)
        elif text == '🆘 Поддержка':
            await update.message.reply_text("Связь с разработчиком бота @imcouncilor, imcouncilor@gmail.com", reply_markup=main_keyboard)
        else:
            await update.message.reply_html(f"📝 <b>Используйте кнопки меню!</b> 😊", reply_markup=main_keyboard)
    except TelegramError as e:
        logger.error(f"Ошибка Telegram в handle_message для пользователя {update.effective_user.id}: {e}")
        await update.message.reply_html(f"❌ <b>Ошибка!</b> Проверьте права бота. 😞", reply_markup=main_keyboard)
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}", exc_info=True)
        await update.message.reply_html(f"❌ <b>Произошла ошибка!</b> Попробуйте позже. 😞", reply_markup=main_keyboard)

async def error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка в polling: {context.error}", exc_info=True)
    if update and hasattr(update, 'message'):
        try:
            await update.message.reply_html(f"❌ <b>Произошла ошибка!</b> Попробуйте позже. 😞", reply_markup=main_keyboard)
        except TelegramError as e:
            logger.error(f"Ошибка Telegram при отправке сообщения об ошибке: {e}")

async def main():
    application = Application.builder().token(BOT_TOKEN).read_timeout(60).get_updates_read_timeout(60).write_timeout(60).connect_timeout(60).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_callback)
    
    logger.info("🎯 Бот запущен")
    await application.initialize()
    
    for _ in range(5):
        try:
            updates = await application.bot.get_updates(offset=-1, timeout=30)
            logger.info(f"Очередь обновлений очищена, получено {len(updates)} обновлений")
            for update in updates:
                logger.debug(f"Получено обновление при очистке: {update.to_dict()}")
            break
        except TelegramError as e:
            logger.error(f"Ошибка Telegram при очистке очереди: {e}")
            await asyncio.sleep(2)
    
    await application.start()
    logger.info("🚀 Polling начат")
    try:
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            poll_interval=0.5,
            timeout=30
        )
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановка бота...")
    finally:
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("Бот полностью остановлен")
        except Exception as e:
            logger.error(f"Ошибка при остановке: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Программа завершена пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)