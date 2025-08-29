#!/usr/bin/env python3
"""
Keep-alive сервер для поддержания работы бота на Replit
Создает простой Flask веб-сервер для мониторинга
"""

import os
import logging
from flask import Flask, jsonify
from datetime import datetime
import threading

# Настройка логирования
logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)

# Глобальная переменная для хранения времени запуска
start_time = datetime.now()

@app.route('/')
def home():
    """Главная страница с информацией о боте"""
    uptime = datetime.now() - start_time
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Telegram Bot - Keep Alive</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .status {{
                background: #d4edda;
                color: #155724;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .info {{
                background: #d1ecf1;
                color: #0c5460;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            h1 {{ color: #333; }}
            .emoji {{ font-size: 1.2em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1><span class="emoji">🤖</span> Telegram Bot Keep-Alive Server</h1>
            
            <div class="status">
                <strong><span class="emoji">🟢</span> Статус: Активен</strong>
            </div>
            
            <div class="info">
                <h3><span class="emoji">📊</span> Информация о сервере:</h3>
                <ul>
                    <li><strong>Время запуска:</strong> {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                    <li><strong>Время работы:</strong> {str(uptime).split('.')[0]}</li>
                    <li><strong>Платформа:</strong> Replit</li>
                    <li><strong>Порт:</strong> 5000</li>
                </ul>
            </div>
            
            <div class="info">
                <h3><span class="emoji">🔧</span> Как использовать:</h3>
                <ol>
                    <li>Этот сервер поддерживает бота в активном состоянии 24/7</li>
                    <li>Используйте UptimeRobot или аналогичный сервис для пинга этой страницы</li>
                    <li>Рекомендуемый интервал: каждые 5 минут</li>
                    <li>URL для мониторинга: <code>https://ваш-домен.repl.co/health</code></li>
                </ol>
            </div>
            
            <div class="info">
                <h3><span class="emoji">📱</span> API Endpoints:</h3>
                <ul>
                    <li><code>/</code> - Эта страница</li>
                    <li><code>/health</code> - JSON статус для мониторинга</li>
                    <li><code>/ping</code> - Простая проверка доступности</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    """API endpoint для проверки здоровья бота"""
    uptime = datetime.now() - start_time
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'uptime_seconds': int(uptime.total_seconds()),
        'uptime_human': str(uptime).split('.')[0],
        'start_time': start_time.isoformat(),
        'service': 'telegram_bot_keep_alive'
    })

@app.route('/ping')
def ping():
    """Простой endpoint для пинга"""
    return 'pong', 200

@app.errorhandler(404)
def not_found(error):
    """Обработчик 404 ошибок"""
    return jsonify({
        'error': 'Not Found',
        'message': 'Эта страница не существует',
        'available_endpoints': ['/', '/health', '/ping']
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Обработчик 500 ошибок"""
    logger.error(f"Внутренняя ошибка сервера: {error}")
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'Произошла внутренняя ошибка сервера'
    }), 500

def keep_alive():
    """Функция для запуска keep-alive сервера"""
    try:
        # Настройка Flask для production
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        
        # Отключаем логи Flask в production (только ошибки)
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        logger.info("🌐 Keep-alive сервер запускается на порту 5000")
        
        # Запускаем сервер
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка keep-alive сервера: {e}")
        raise

def start_keep_alive_thread():
    """Запуск keep-alive сервера в отдельном потоке"""
    thread = threading.Thread(target=keep_alive, daemon=True)
    thread.start()
    logger.info("✅ Keep-alive сервер запущен в фоновом режиме")
    return thread

if __name__ == "__main__":
    keep_alive()
