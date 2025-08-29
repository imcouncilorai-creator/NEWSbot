#!/usr/bin/env python3
"""
Планировщик автоматической публикации новостей
Автоматически публикует новости в канал по расписанию
"""

import schedule
import time
import asyncio
import logging
import threading
from datetime import datetime
import pytz
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class NewsScheduler:
    def __init__(self, bot_token: str, channel_id: str, news_parser):
        self.bot = Bot(token=bot_token)
        self.channel_id = channel_id
        self.news_parser = news_parser
        self.is_running = False
        self.scheduler_thread = None
        self.moscow_tz = pytz.timezone('Europe/Moscow')
        
        # Счетчики для статистики
        self.auto_posts_count = 0
        self.last_auto_post = None
        
    def auto_publish_news(self):
        """Автоматическая публикация новостей"""
        try:
            moscow_time = datetime.now(self.moscow_tz)
            logger.info(f"🕐 Запланированная публикация новостей в {moscow_time.strftime('%H:%M')} МСК")
            
            # Запускаем асинхронную функцию в новом event loop
            asyncio.run(self._async_publish_news())
            
        except Exception as e:
            logger.error(f"❌ Ошибка автоматической публикации: {e}")
    
    async def _async_publish_news(self):
        """Асинхронная публикация новостей"""
        try:
            # Создаем фиктивный context для совместимости
            class FakeContext:
                pass
            
            fake_context = FakeContext()
            
            # Получаем новости
            news_items, error_urls = await self.news_parser.fetch_rss_news(fake_context, limit=6)
            
            if not news_items:
                logger.warning("⚠️ Нет новостей для автопубликации")
                return
            
            # Форматируем сообщение
            message = await self.news_parser.format_news_message(news_items)
            
            # Добавляем информацию об автопубликации
            moscow_time = datetime.now(self.moscow_tz)
            # Заменяем окончание сообщения для автопубликации
            if message.endswith("📢 <b>Новостной дайджест составлен с помощью автоматического Telegram-бота</b> 🎉"):
                message = message.replace(
                    "📢 <b>Новостной дайджест составлен с помощью автоматического Telegram-бота</b> 🎉",
                    ""
                ).rstrip("\n")
            
            # Также заменяем заголовок для автопубликации
            if "📰 <b>СВЕЖИЕ НОВОСТИ</b>" in message:
                message = message.replace(
                    "📰 <b>СВЕЖИЕ НОВОСТИ</b>",
                    "🔥 <b>АКТУАЛЬНЫЕ НОВОСТИ</b> 🔥"
                )
            
            auto_message = (
                f"{message}\n\n"
                f"🤖 <b>Автоматическая публикация</b>\n"
                f"🕐 {moscow_time.strftime('%H:%M')} МСК\n\n"
                f"📢 <b>Новостной дайджест составлен с помощью автоматического Telegram-бота</b> 🎉"
            )
            
            # Отправляем в канал
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=auto_message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            self.auto_posts_count += 1
            self.last_auto_post = moscow_time
            
            logger.info(f"✅ Автоматически опубликовано {len(news_items)} новостей в канал")
            
        except TelegramError as e:
            logger.error(f"❌ Ошибка Telegram при автопубликации: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка при автопубликации: {e}")
    
    def setup_schedule(self):
        """Настройка расписания публикаций"""
        # Очищаем существующие задачи
        schedule.clear()
        
        # Расписание: 9:00, 12:00, 15:00, 18:00, 21:00 МСК
        schedule.every().day.at("06:00").do(self.auto_publish_news)  # 9:00 МСК = 6:00 UTC
        schedule.every().day.at("09:00").do(self.auto_publish_news)  # 12:00 МСК = 9:00 UTC  
        schedule.every().day.at("12:00").do(self.auto_publish_news)  # 15:00 МСК = 12:00 UTC
        schedule.every().day.at("15:00").do(self.auto_publish_news)  # 18:00 МСК = 15:00 UTC
        schedule.every().day.at("18:00").do(self.auto_publish_news)  # 21:00 МСК = 18:00 UTC
        
        logger.info("📅 Расписание настроено: публикация в 9:00, 12:00, 15:00, 18:00, 21:00 МСК")
    
    def start(self):
        """Запуск планировщика"""
        if self.is_running:
            logger.warning("⚠️ Планировщик уже запущен")
            return
        
        self.setup_schedule()
        self.is_running = True
        
        def run_scheduler():
            logger.info("🚀 Планировщик автопубликации запущен")
            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Проверяем каждую минуту
                except Exception as e:
                    logger.error(f"❌ Ошибка в планировщике: {e}")
                    time.sleep(60)
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("✅ Планировщик автопубликации активирован")
    
    def stop(self):
        """Остановка планировщика"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("⏹️ Планировщик автопубликации остановлен")
    
    def get_schedule_info(self):
        """Получение информации о расписании"""
        moscow_time = datetime.now(self.moscow_tz)
        
        # Время следующих публикаций в МСК
        schedule_times = ["09:00", "12:00", "15:00", "18:00", "21:00"]
        
        # Находим следующее время публикации
        current_hour = moscow_time.hour
        next_time = None
        
        for time_str in schedule_times:
            hour = int(time_str.split(':')[0])
            if hour > current_hour:
                next_time = time_str
                break
        
        if not next_time:
            next_time = schedule_times[0]  # Следующий день
        
        return {
            'auto_posts_count': self.auto_posts_count,
            'last_auto_post': self.last_auto_post.strftime('%d.%m.%Y %H:%M МСК') if self.last_auto_post else 'Нет',
            'next_auto_post': f"Сегодня в {next_time} МСК" if next_time != schedule_times[0] else f"Завтра в {next_time} МСК",
            'schedule_times': schedule_times,
            'is_running': self.is_running
        }