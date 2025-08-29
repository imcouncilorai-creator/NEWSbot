import asyncio
import aiohttp
import feedparser
import logging
from rss_feeds import RSS_SOURCES

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('rss_test.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

async def test_rss_feed(url: str, timeout=10):
    """Тестирует доступность RSS-ленты и наличие записей."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout, headers=headers, ssl=False) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} для {url}")
                    return url, False, f"HTTP {response.status}"
                content = await response.text()
                feed = feedparser.parse(content)
                if not feed.entries:
                    logger.warning(f"Пустая лента: {url}")
                    return url, False, "Пустая лента"
                logger.info(f"Успешно: {url} (записей: {len(feed.entries)})")
                return url, True, f"OK, записей: {len(feed.entries)}"
    except Exception as e:
        logger.error(f"Ошибка загрузки {url}: {e}")
        return url, False, str(e)

async def test_all_feeds():
    """Тестирует все RSS-ленты из RSS_SOURCES."""
    tasks = [test_rss_feed(url) for url in RSS_SOURCES['general']]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\nРезультаты тестирования RSS-лент:")
    print("=" * 50)
    successful = 0
    failed = 0
    for url, status, message in results:
        if status:
            successful += 1
            print(f"✅ {url}: {message}")
        else:
            failed += 1
            print(f"❌ {url}: {message}")
    print("=" * 50)
    print(f"Успешно: {successful}, Ошибок: {failed}")

if __name__ == "__main__":
    asyncio.run(test_all_feeds())