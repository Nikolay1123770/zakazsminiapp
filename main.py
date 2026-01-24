import logging
import os
import warnings
import threading
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.warnings import PTBUserWarning
from dotenv import load_dotenv
from config import BOT_TOKEN, ADMIN_IDS, MINIAPP_URL
from error_logger import setup_error_logging

# Импорт для веб-сервера
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import sqlite3
import hashlib
import hmac
import urllib.parse

# Игнорировать предупреждения PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация системы логирования ошибок
setup_error_logging()

# Модели данных для API
class UserCreate(BaseModel):
    user_id: int
    first_name: str
    last_name: str = ""
    username: str = ""
    language_code: str = "ru"

class BookingCreate(BaseModel):
    name: str
    phone: str
    date: str
    time: str
    guests: str
    comment: str = ""
    user_id: int = None
    source: str = "miniapp"

# Создаем папку static, если её нет
STATIC_DIR = Path("static")
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("📁 Создана папка 'static' для MiniApp")

# Создаем базовый index.html, если его нет
INDEX_FILE = STATIC_DIR / "index.html"
if not INDEX_FILE.exists():
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        # Базовый HTML будет создан позже
        f.write("""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Во Все Тяжкие | Premium Hookah</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: #050505; color: #fff; min-height: 100vh; overflow-x: hidden; }
        .loader-screen { position: fixed; inset: 0; background: #050505; z-index: 9999; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .loader-screen.hidden { opacity: 0; visibility: hidden; pointer-events: none; }
        .app { display: none; }
        .app.visible { display: block; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; text-align: center; }
        h1 { color: #a855f7; margin-bottom: 20px; }
        p { color: #888; margin-bottom: 30px; }
        .btn { background: #a855f7; color: white; border: none; padding: 15px 30px; border-radius: 12px; font-size: 16px; cursor: pointer; }
        .btn:hover { background: #7c3aed; }
    </style>
</head>
<body>
    <div class="loader-screen" id="loader">
        <div class="container">
            <h1>Во Все Тяжкие</h1>
            <p>Загрузка приложения...</p>
        </div>
    </div>
    
    <div class="app" id="app">
        <div class="container">
            <h1>🌐 MiniApp</h1>
            <p>Веб-приложение для кальянной "Во Все Тяжкие"</p>
            <p>Приложение загружается...</p>
            <button class="btn" onclick="location.reload()">🔄 Обновить</button>
        </div>
    </div>
    
    <script>
        setTimeout(() => {
            document.getElementById('loader').classList.add('hidden');
            document.getElementById('app').classList.add('visible');
        }, 2000);
    </script>
</body>
</html>""")
    logger.info("📄 Создан index.html в папке static")

# Подключаем базу данных
def get_db_connection():
    conn = sqlite3.connect('vovsetyagskie.db')
    conn.row_factory = sqlite3.Row
    return conn

# Проверка подписи Telegram WebApp
def verify_telegram_data(init_data: str, bot_token: str) -> bool:
    """Проверяет подпись данных от Telegram WebApp"""
    try:
        if not init_data:
            return False
            
        # Парсим данные
        data_pairs = init_data.split('&')
        hash_pair = [pair for pair in data_pairs if pair.startswith('hash=')][0] if any(pair.startswith('hash=') for pair in data_pairs) else None
        
        if not hash_pair:
            return False
            
        hash_value = hash_pair.split('=')[1]
        
        # Удаляем хэш из данных
        data_without_hash = [pair for pair in data_pairs if not pair.startswith('hash=')]
        data_str = '&'.join(sorted(data_without_hash))
        
        # Вычисляем секретный ключ
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Вычисляем хэш
        computed_hash = hmac.new(
            key=secret_key,
            msg=data_str.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return computed_hash == hash_value
    except Exception as e:
        logger.error(f"Ошибка проверки подписи Telegram: {e}")
        return False

# Создаем FastAPI приложение для MiniApp
web_app = FastAPI(title="Vovsetyagskie MiniApp API")

# Настройка CORS для работы с Telegram
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware для проверки данных Telegram
async def verify_telegram_request(request: Request):
    """Проверяет подпись запроса от Telegram"""
    init_data = request.headers.get('X-Telegram-Init-Data')
    
    if not init_data:
        # Для публичных эндпоинтов пропускаем проверку
        public_endpoints = ['/api/menu', '/api/config', '/health', '/api/health', '/', '/index.html']
        if request.url.path in public_endpoints:
            return None
        
        # Для остальных возвращаем ошибку
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация Telegram"
        )
    
    # Проверяем подпись
    if not verify_telegram_data(init_data, BOT_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверная подпись Telegram"
        )
    
    try:
        # Парсим данные пользователя
        parsed_data = urllib.parse.parse_qs(init_data)
        user_str = parsed_data.get('user', ['{}'])[0]
        user_data = json.loads(user_str) if user_str else {}
        
        return user_data
    except Exception as e:
        logger.error(f"Ошибка парсинга данных пользователя: {e}")
        return {}

# Создаем таблицы для MiniApp
def create_miniapp_tables():
    """Создать таблицы для MiniApp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Таблица для конфигурации MiniApp
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(section, key)
            )
        ''')
        
        # Таблица для меню MiniApp
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                old_price INTEGER DEFAULT NULL,
                category TEXT NOT NULL,
                icon TEXT DEFAULT '🍽️',
                badge TEXT DEFAULT NULL,
                position INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name)
            )
        ''')
        
        # Таблица для галереи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_gallery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                emoji TEXT DEFAULT '📸',
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        
        # Добавляем базовую конфигурацию
        default_config = [
            ('contacts', 'address', 'ул. Химическая, 52', 'Адрес заведения'),
            ('contacts', 'phone', '+7 (999) 123-45-67', 'Телефон для связи'),
            ('contacts', 'instagram', '@vovseTyajkie', 'Instagram профиль'),
            ('schedule', 'weekdays', '14:00 — 02:00', 'Время работы Пн-Чт'),
            ('schedule', 'weekend', '14:00 — 04:00', 'Время работы Пт-Вс'),
            ('stats', 'flavors', '50+', 'Количество вкусов'),
            ('stats', 'experience', '5', 'Лет опыта'),
            ('stats', 'guests', '10K', 'Количество гостей'),
            ('miniapp', 'welcome_message', 'Добро пожаловать в Во Все Тяжкие!', 'Приветственное сообщение'),
            ('miniapp', 'theme', 'dark', 'Тема приложения'),
            ('miniapp', 'primary_color', '#a855f7', 'Основной цвет')
        ]
        
        for config_item in default_config:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_config (section, key, value, description)
                    VALUES (?, ?, ?, ?)
                ''', config_item)
            except Exception as e:
                logger.error(f"Ошибка добавления конфигурации {config_item}: {e}")
        
        # Добавляем базовые товары для MiniApp
        default_menu = [
            ('Классический', 'Один вкус премиум табака на выбор. Идеален для начинающих', 1200, 1500, 'hookah', '💨', 'hit', 1),
            ('Premium', 'Tangiers, Darkside, Element — топовые табаки мира', 1800, None, 'hookah', '🔮', 'premium', 2),
            ('VIP Кальян', 'Эксклюзивные табаки + фрукты + авторская подача', 2500, None, 'hookah', '👑', 'vip', 3),
            ('Blue Crystal', 'Ледяная свежесть с нотками мяты и цитруса', 2000, None, 'signature', '🧊', 'hit', 1),
            ('Heisenberg', 'Секретный рецепт шефа. 99.1% чистого наслаждения', 2200, None, 'signature', '⚗️', 'signature', 2),
            ('Los Pollos', 'Пряный микс с перцем и тропическими фруктами', 2000, None, 'signature', '🔥', 'hot', 3),
            ('Чай (чайник)', 'Чёрный, зелёный, фруктовый или травяной', 400, None, 'drinks', '🍵', None, 1),
            ('Лимонады', 'Клубничный, цитрусовый, мохито, манго', 350, None, 'drinks', '🍹', None, 2),
            ('Кофе', 'Эспрессо, американо, капучино, латте, раф', 250, None, 'drinks', '☕', None, 3),
            ('Пицца', 'Маргарита, Пепперони, 4 сыра, BBQ курица', 650, None, 'food', '🍕', None, 1),
            ('Салаты', 'Цезарь, Греческий, с креветками', 450, None, 'food', '🥗', None, 2),
            ('Закуски', 'Картофель фри, наггетсы, сырные палочки', 350, None, 'food', '🍟', None, 3)
        ]
        
        for menu_item in default_menu:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_menu (name, description, price, old_price, category, icon, badge, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', menu_item)
            except Exception as e:
                logger.error(f"Ошибка добавления товара {menu_item[0]}: {e}")
        
        # Добавляем галерею
        default_gallery = [
            ('Лаборатория вкусов', '🧪', 'Авторские миксы и эксперименты', 1),
            ('Премиум кальяны', '💨', 'Эксклюзивные табаки и оборудование', 2),
            ('VIP зона', '🛋️', 'Уютная атмосфера для отдыха', 3),
            ('Коктейли', '🍹', 'Авторские напитки и лимонады', 4),
            ('Вечерние посиделки', '🔥', 'Атмосферные вечера с друзьями', 5),
            ('Кухня', '⚗️', 'Вкусные закуски и десерты', 6)
        ]
        
        for gallery_item in default_gallery:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_gallery (title, emoji, description, position)
                    VALUES (?, ?, ?, ?)
                ''', gallery_item)
            except Exception as e:
                logger.error(f"Ошибка добавления галереи {gallery_item[0]}: {e}")
        
        conn.commit()
        logger.info("✅ Таблицы для MiniApp созданы/проверены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц MiniApp: {e}")
    finally:
        conn.close()

# API эндпоинты
@web_app.get("/api/menu")
async def get_miniapp_menu():
    """Получить все товары меню для MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, description, price, old_price, category, icon, badge 
            FROM miniapp_menu 
            WHERE is_active = TRUE 
            ORDER BY category, position, name
        ''')
        
        items = cursor.fetchall()
        menu_data = []
        
        for item in items:
            menu_data.append({
                "id": item[0],
                "name": item[1],
                "description": item[2] or "",
                "price": item[3],
                "old_price": item[4],
                "category": item[5],
                "icon": item[6] or "🍽️",
                "badge": item[7]
            })
        
        return JSONResponse(menu_data)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения меню: {e}")
        return JSONResponse({"error": "Ошибка загрузки меню"}, status_code=500)
    finally:
        conn.close()

@web_app.get("/api/config")
async def get_miniapp_config():
    """Получить конфигурацию для MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Получаем всю конфигурацию
        cursor.execute('SELECT section, key, value FROM miniapp_config')
        config_items = cursor.fetchall()
        
        # Структурируем конфигурацию
        config = {
            "contacts": {
                "address": "ул. Химическая, 52",
                "phone": "+7 (999) 123-45-67",
                "instagram": "@vovseTyajkie"
            },
            "schedule": {
                "weekdays": "14:00 — 02:00",
                "weekend": "14:00 — 04:00"
            },
            "stats": {
                "flavors": "50+",
                "experience": "5",
                "guests": "10K"
            }
        }
        
        # Обновляем значения из базы данных
        for section, key, value in config_items:
            if section == 'contacts' and key in config['contacts']:
                config['contacts'][key] = value
            elif section == 'schedule' and key in config['schedule']:
                config['schedule'][key] = value
            elif section == 'stats' and key in config['stats']:
                config['stats'][key] = value
        
        return JSONResponse(config)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения конфигурации: {e}")
        # Возвращаем значения по умолчанию
        return JSONResponse({
            "contacts": {
                "address": "ул. Химическая, 52",
                "phone": "+7 (999) 123-45-67",
                "instagram": "@vovseTyajkie"
            },
            "schedule": {
                "weekdays": "14:00 — 02:00",
                "weekend": "14:00 — 04:00"
            },
            "stats": {
                "flavors": "50+",
                "experience": "5",
                "guests": "10K"
            }
        })
    finally:
        conn.close()

@web_app.get("/api/user/{telegram_id}")
async def get_miniapp_user(telegram_id: int, user_data: dict = Depends(verify_telegram_request)):
    """Получить информацию о пользователе для MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Получаем пользователя из таблицы users
        cursor.execute('''
            SELECT id, telegram_id, first_name, last_name, phone, bonus_balance, registration_date
            FROM users 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return JSONResponse({
                "error": "Пользователь не найден",
                "code": "USER_NOT_FOUND"
            }, status_code=404)
        
        return JSONResponse({
            "user_id": user[0],
            "telegram_id": user[1],
            "first_name": user[2],
            "last_name": user[3] or "",
            "phone": user[4] or "",
            "bonus_balance": user[5] or 0,
            "registration_date": user[6]
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователя: {e}")
        return JSONResponse({"error": "Внутренняя ошибка сервера"}, status_code=500)
    finally:
        conn.close()

@web_app.post("/api/user/create")
async def create_miniapp_user(user: UserCreate, user_data: dict = Depends(verify_telegram_request)):
    """Создать нового пользователя из MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (user.user_id,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            return JSONResponse({
                "message": "Пользователь уже существует",
                "user_id": existing_user[0]
            })
        
        # Создаем нового пользователя
        cursor.execute('''
            INSERT INTO users (telegram_id, first_name, last_name, registration_date, balance, bonus_balance)
            VALUES (?, ?, ?, datetime('now'), 0, 100)
        ''', (user.user_id, user.first_name, user.last_name))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        logger.info(f"🆕 Создан новый пользователь из MiniApp: {user.user_id}, {user.first_name}")
        
        return JSONResponse({
            "message": "Пользователь создан",
            "user_id": user_id,
            "first_name": user.first_name
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания пользователя: {e}")
        return JSONResponse({"error": "Ошибка создания пользователя"}, status_code=500)
    finally:
        conn.close()

@web_app.post("/api/booking/create")
async def create_miniapp_booking(booking: BookingCreate, user_data: dict = Depends(verify_telegram_request)):
    """Создать бронирование из MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Если указан user_id, проверяем пользователя
        user_exists = True
        if booking.user_id:
            cursor.execute('SELECT id FROM users WHERE id = ?', (booking.user_id,))
            if not cursor.fetchone():
                user_exists = False
        
        # Создаем бронирование
        cursor.execute('''
            INSERT INTO bookings (
                user_id, booking_date, booking_time, guests, comment, 
                status, created_at, source, customer_name, customer_phone
            )
            VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'), ?, ?, ?)
        ''', (
            booking.user_id if user_exists else None,
            booking.date,
            booking.time,
            booking.guests,
            booking.comment,
            booking.source,
            booking.name,
            booking.phone
        ))
        
        booking_id = cursor.lastrowid
        conn.commit()
        
        logger.info(f"✅ Бронирование #{booking_id} создано из MiniApp")
        
        # Отправляем уведомление администраторам
        try:
            from telegram import Bot
            bot = Bot(token=BOT_TOKEN)
            
            booking_message = f"""
🆕 НОВАЯ БРОНЬ ИЗ MINIAPP!

📋 ID: #{booking_id}
👤 Имя: {booking.name}
📞 Телефон: {booking.phone}
📅 Дата: {booking.date}
⏰ Время: {booking.time}
👥 Гостей: {booking.guests}
💬 Комментарий: {booking.comment or 'нет'}
🎯 Источник: MiniApp
"""
            
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=booking_message
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка уведомления админа {admin_id}: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")
        
        return JSONResponse({
            "message": "Бронирование создано",
            "booking_id": booking_id,
            "status": "pending"
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания бронирования: {e}")
        return JSONResponse({"error": "Ошибка создания бронирования"}, status_code=500)
    finally:
        conn.close()

@web_app.get("/api/gallery")
async def get_miniapp_gallery():
    """Получить галерею для MiniApp"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, title, emoji, description 
            FROM miniapp_gallery 
            WHERE is_active = TRUE 
            ORDER BY position
        ''')
        
        items = cursor.fetchall()
        gallery_data = []
        
        for item in items:
            gallery_data.append({
                "id": item[0],
                "title": item[1] or "",
                "emoji": item[2] or "📸",
                "description": item[3] or ""
            })
        
        return JSONResponse(gallery_data)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения галереи: {e}")
        return JSONResponse([], status_code=500)
    finally:
        conn.close()

@web_app.get("/api/bookings/{user_id}")
async def get_miniapp_bookings(user_id: int, user_data: dict = Depends(verify_telegram_request)):
    """Получить бронирования пользователя"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, booking_date, booking_time, guests, comment, status, created_at
            FROM bookings 
            WHERE user_id = ? 
            ORDER BY booking_date DESC, booking_time DESC
            LIMIT 10
        ''', (user_id,))
        
        bookings = cursor.fetchall()
        booking_data = []
        
        for booking in bookings:
            booking_data.append({
                "id": booking[0],
                "date": booking[1],
                "time": booking[2],
                "guests": booking[3],
                "comment": booking[4] or "",
                "status": booking[5],
                "created_at": booking[6]
            })
        
        return JSONResponse(booking_data)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения бронирований: {e}")
        return JSONResponse([], status_code=500)
    finally:
        conn.close()

@web_app.get("/api/health")
async def api_health():
    """Проверка здоровья API"""
    return JSONResponse({
        "status": "ok", 
        "api": "vovsetyagskie_miniapp", 
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "menu": "/api/menu",
            "config": "/api/config",
            "user": "/api/user/{telegram_id}",
            "booking": "/api/booking/create",
            "gallery": "/api/gallery"
        }
    })

# Настраиваем раздачу статики
web_app.mount("/static", StaticFiles(directory="static"), name="static")

# Основной маршрут для MiniApp
@web_app.get("/")
async def serve_miniapp():
    """Основной маршрут для MiniApp"""
    return FileResponse("static/index.html")

@web_app.get("/index.html")
async def serve_miniapp_html():
    """Альтернативный маршрут для MiniApp"""
    return FileResponse("static/index.html")

# Маршрут для проверки здоровья
@web_app.get("/health")
async def health_check():
    return JSONResponse({"status": "ok", "service": "miniapp", "port": 3000, "timestamp": datetime.now().isoformat()})

# Функция для запуска веб-сервера в отдельном потоке
def run_web_server():
    """Запуск веб-сервера в отдельном потоке"""
    try:
        # Устанавливаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        config = uvicorn.Config(
            web_app, 
            host="0.0.0.0", 
            port=3000,
            log_level="info",
            access_log=True,
            reload=False
        )
        server = uvicorn.Server(config)
        logger.info("🌐 Веб-сервер MiniApp запущен на порту 3000")
        loop.run_until_complete(server.serve())
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")

async def post_init(application):
    """Функция, выполняемая после инициализации бота"""
    logger.info("🤖 Бот успешно запущен и готов к работе!")

    # Получаем информацию о боте
    bot_info = await application.bot.get_me()
    logger.info(f"🔗 Бот: {bot_info.first_name} (@{bot_info.username})")
    logger.info(f"🆔 ID бота: {bot_info.id}")
    
    # Проверяем настройки MiniApp
    if MINIAPP_URL:
        logger.info(f"🌐 MiniApp настроен: {MINIAPP_URL}")
    else:
        logger.warning("⚠️ MiniApp URL не настроен в конфигурации")

async def post_stop(application):
    """Функция, выполняемая при остановке бота"""
    logger.info("🛑 Бот остановлен")

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

class AdminFilter(filters.MessageFilter):
    def filter(self, message):
        return is_admin(message.from_user.id)

class UserFilter(filters.MessageFilter):
    def filter(self, message):
        return not is_admin(message.from_user.id)

# Создаем экземпляры фильтров
admin_filter = AdminFilter()
user_filter = UserFilter()

# ФУНКЦИЯ: Обработчик для кнопки MiniApp
async def open_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть MiniApp"""
    user_id = update.effective_user.id
    
    if not MINIAPP_URL:
        await update.message.reply_text(
            "❌ MiniApp временно недоступен. Используйте бота для доступа ко всем функциям."
        )
        return
    
    # Создаем кнопку для открытия MiniApp
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🌐 Открыть веб-приложение",
            web_app=WebAppInfo(url=MINIAPP_URL)
        )
    ]])
    
    await update.message.reply_text(
        "🌐 **Во Все Тяжкие | Premium Hookah**\n\n"
        "Откройте веб-приложение для удобного доступа к:\n"
        "• 💨 Премиум кальянам\n"
        "• 📅 Бронированию столиков\n"
        "• 🍽️ Меню с ценами\n"
        "• 📸 Галерее заведения\n"
        "• 👤 Вашему профилю\n\n"
        "Нажмите кнопку ниже, чтобы открыть:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# ФУНКЦИЯ: Обработчик данных из WebApp
async def handle_miniapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик данных из WebApp"""
    try:
        if not update.effective_message or not update.effective_message.web_app_data:
            return
            
        data = update.effective_message.web_app_data.data
        user_id = update.effective_user.id
        logger.info(f"📱 Данные от MiniApp от пользователя {user_id}: {data}")
        
        try:
            parsed_data = json.loads(data)
            
            if parsed_data.get('type') == 'booking':
                # Обработка бронирования через бота
                from database import Database
                db = Database()
                
                # Получаем пользователя
                user = db.get_user(user_id)
                
                # Обновляем данные пользователя, если они изменились
                new_name = parsed_data.get('name', '').strip()
                new_phone = parsed_data.get('phone', '').strip()
                
                if user:
                    # user[3] - first_name, user[4] - phone
                    if new_name and new_name != user[3]:
                        db.update_user_name(user_id, new_name)
                        logger.info(f"🔄 Обновлено имя пользователя {user_id}: {new_name}")
                    
                    if new_phone and new_phone != user[4]:
                        db.update_user_phone(user_id, new_phone)
                        logger.info(f"🔄 Обновлен телефон пользователя {user_id}: {new_phone}")
                
                # Преобразуем количество гостей
                guests_str = parsed_data.get('guests', '1-2')
                if "-" in guests_str:
                    guests_num = int(guests_str.split("-")[-1].replace("+", "").strip())
                elif "+" in guests_str:
                    guests_num = int(guests_str.replace("+", "").strip())
                else:
                    guests_num = int(guests_str)
                
                # Создаем бронирование
                booking_id = db.create_booking(
                    user_id=user_id,
                    booking_date=parsed_data.get('date'),
                    booking_time=parsed_data.get('time'),
                    guests=guests_num,
                    comment=parsed_data.get('comment', ''),
                    status='pending'
                )
                
                if booking_id:
                    # Отправляем подтверждение пользователю
                    await update.effective_message.reply_text(
                        "✅ **Бронирование создано!**\n\n"
                        f"📅 Дата: {parsed_data.get('date')}\n"
                        f"⏰ Время: {parsed_data.get('time')}\n"
                        f"👥 Гостей: {guests_num}\n\n"
                        "Мы свяжемся с вами для подтверждения. Спасибо!",
                        parse_mode='Markdown'
                    )
                    
                    # Уведомляем администраторов
                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"🆕 НОВАЯ БРОНЬ ИЗ MINIAPP (через бота)!\n\n"
                                     f"👤 Пользователь: {new_name}\n"
                                     f"📱 ID: {user_id}\n"
                                     f"📞 Телефон: {new_phone}\n"
                                     f"📅 Дата: {parsed_data.get('date')}\n"
                                     f"⏰ Время: {parsed_data.get('time')}\n"
                                     f"👥 Гостей: {guests_num}\n"
                                     f"💬 Комментарий: {parsed_data.get('comment', 'нет')}\n\n"
                                     f"ID брони: #{booking_id}"
                            )
                        except Exception as e:
                            logger.error(f"❌ Ошибка уведомления админа {admin_id}: {e}")
                    
                    logger.info(f"✅ Бронирование #{booking_id} создано для пользователя {user_id}")
                else:
                    await update.effective_message.reply_text(
                        "❌ Произошла ошибка при создании бронирования. Попробуйте позже."
                    )
            
            elif parsed_data.get('type') == 'booking_created':
                # Подтверждение создания бронирования через API
                booking_id = parsed_data.get('booking_id')
                await update.effective_message.reply_text(
                    f"✅ Бронирование #{booking_id} успешно создано через веб-приложение!\n\n"
                    "Мы свяжемся с вами для подтверждения.",
                    parse_mode='Markdown'
                )
            
            else:
                logger.warning(f"Неизвестный тип данных от MiniApp: {parsed_data.get('type')}")
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка декодирования JSON из MiniApp: {e}")
            await update.effective_message.reply_text(
                "❌ Ошибка обработки данных. Попробуйте еще раз."
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки данных от MiniApp: {e}", exc_info=True)

# КОМАНДА ДЛЯ ОТЛАДКИ MiniApp
async def debug_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отладочная информация о MiniApp"""
    if not is_admin(update.effective_user.id):
        return
    
    # Проверяем, запущен ли веб-сервер
    web_server_running = False
    for thread in threading.enumerate():
        if thread.name == 'web_server_thread':
            web_server_running = thread.is_alive()
            break
    
    # Проверяем таблицы
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем существование таблиц
    tables = ['miniapp_menu', 'miniapp_config', 'miniapp_gallery']
    table_status = {}
    
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        table_status[table] = "✅ существует" if cursor.fetchone() else "❌ отсутствует"
    
    # Получаем количество записей
    menu_count = cursor.execute("SELECT COUNT(*) FROM miniapp_menu").fetchone()[0]
    config_count = cursor.execute("SELECT COUNT(*) FROM miniapp_config").fetchone()[0]
    gallery_count = cursor.execute("SELECT COUNT(*) FROM miniapp_gallery").fetchone()[0]
    
    conn.close()
    
    status_info = {
        "web_server": "✅ running" if web_server_running else "❌ stopped",
        "mini_app_url": MINIAPP_URL or "Не настроен",
        "static_dir": str(STATIC_DIR.absolute()),
        "index_file_exists": "✅ да" if INDEX_FILE.exists() else "❌ нет",
        "port": 3000,
        "threads": threading.active_count(),
        "tables": "\n".join([f"  • {table}: {status}" for table, status in table_status.items()]),
        "records": f"Меню: {menu_count}, Конфиг: {config_count}, Галерея: {gallery_count}"
    }
    
    message = "🔧 **Отладка MiniApp**\n\n"
    for key, value in status_info.items():
        if key == 'tables':
            message += f"• **tables**:\n{value}\n"
        elif key == 'records':
            message += f"• **records**: {value}\n"
        else:
            message += f"• {key}: `{value}`\n"
    
    message += f"\n🌐 API: {MINIAPP_URL}/api/health"
    message += f"\n📊 Меню: {MINIAPP_URL}/api/menu"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# Упрощенные версии обработчиков (без удаления сообщений)
async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных сообщений"""
    if update.message:
        if is_admin(update.effective_user.id):
            await update.message.reply_text(
                "❌ Неизвестная команда. Используйте кнопки меню администратора."
            )
        else:
            # Предлагаем открыть MiniApp или показать меню
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 Открыть веб-приложение", callback_data="open_miniapp"),
                InlineKeyboardButton("📋 Показать меню", callback_data="show_menu")
            ]])
            await update.message.reply_text(
                "Я не понимаю эту команду. Хотите открыть веб-приложение или увидеть меню?",
                reply_markup=keyboard
            )

async def handle_back_button(update: Update, context):
    """Обработчик кнопки 'Назад' для обоих типов пользователей"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        from handlers.admin_utils import back_to_main_menu
        await back_to_main_menu(update, context)
    else:
        from handlers.user_handlers import back_to_main
        await back_to_main(update, context)

def setup_handlers(application):
    """Настройка всех обработчиков"""
    
    # ========== ИМПОРТЫ ОБРАБОТЧИКОВ ==========
    
    # Импорты обработчиков пользователя
    from handlers.user_handlers import (
        get_registration_handler, get_spend_bonus_handler,
        show_balance, show_referral_info, show_user_bookings,
        handle_user_pending_bookings_button, handle_user_confirmed_bookings_button,
        handle_user_cancelled_bookings_button, handle_user_all_bookings_button,
        handle_user_back_to_bookings_button, handle_user_cancel_booking,
        handle_back_to_bookings_list, start, back_to_main,
        show_contacts, handle_call_contact, handle_telegram_contact,
        handle_open_maps, handle_back_from_contacts, handle_back_to_contacts_callback
    )

    # Импорты обработчиков бронирования
    from handlers.booking_handlers import get_booking_handler

    # Импорты обработчиков администратора
    from handlers.admin_utils import admin_panel, back_to_main_menu, show_statistics
    from handlers.admin_users import (
        show_users_list, user_selected_callback, user_info_callback,
        handle_users_pagination, get_user_search_handler,
        back_to_users_list, exit_search_mode, show_full_users_list,
        back_to_search_mode, new_search
    )
    from handlers.admin_bookings import (
        show_bookings, show_pending_bookings, show_confirmed_bookings,
        show_cancelled_bookings, show_all_bookings, handle_booking_action,
        get_booking_date_handler, get_booking_cancellation_handler
    )
    from handlers.admin_bonuses import (
        handle_bonus_requests, refresh_bonus_requests, handle_bonus_request_action,
        get_bonus_handler
    )
    from handlers.admin_messages import (
        get_broadcast_handler, get_user_message_handler,
        message_user_callback
    )

    # Импорты обработчиков заказов
    from handlers.order_shift import (
        start_order_management,
        open_shift, close_shift,
        calculate_all_orders, show_shift_status
    )

    from handlers.order_creation import (
        handle_create_order, handle_table_number,
        handle_category_selection, handle_item_selection,
        handle_back_to_categories, finish_order
    )

    from handlers.order_management import (
        show_active_orders, add_items_to_existing_order,
        show_order_for_editing, remove_item_from_order,
        view_order_details, handle_add_items
    )

    from handlers.order_payment import (
        calculate_order, handle_cancel_calculation,
        show_payment_selection, handle_payment_selection,
        handle_back_to_calculation
    )

    from handlers.order_history import (
        show_order_history_menu, show_today_orders, show_yesterday_orders,
        show_all_closed_orders, show_select_date_menu, show_orders_by_date,
        show_shift_history, show_year_history,
        show_select_shift_menu, show_selected_shift_history,
        select_year_for_history, select_month_for_history,
        show_full_year_history, show_full_month_history,
        show_more_shifts
    )

    # Утилиты заказов
    from handlers.order_utils import cancel_order_creation, handle_back_to_order_management

    # Импорты обработчиков управления меню
    from handlers.menu_management_handlers import (
        get_menu_management_handlers,
        manage_menu,
        start_edit_item
    )

    # ========== НАСТРОЙКА ОБРАБОТЧИКОВ ==========
    
    # 1. НОВЫЕ ОБРАБОТЧИКИ ДЛЯ MINIAPP
    application.add_handler(MessageHandler(filters.Regex("^🌐 Веб-приложение$") & user_filter, open_miniapp))
    application.add_handler(CallbackQueryHandler(open_miniapp, pattern="^open_miniapp$"))
    
    # 2. Обработчик данных из WebApp
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_miniapp_data))
    
    # 3. Сначала добавляем ConversationHandler'ы
    application.add_handler(get_user_message_handler())
    application.add_handler(get_broadcast_handler())
    application.add_handler(get_bonus_handler())
    application.add_handler(get_booking_date_handler())
    application.add_handler(get_booking_cancellation_handler())
    application.add_handler(get_user_search_handler())
    
    # 4. Обработчики управления меню
    menu_handlers = get_menu_management_handlers()
    for handler in menu_handlers:
        application.add_handler(handler)

    # 5. ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ
    application.add_handler(MessageHandler(filters.Regex("^💰 Мой баланс$") & user_filter, show_balance))
    application.add_handler(MessageHandler(filters.Regex("^🎁 Реферальная программа$") & user_filter, show_referral_info))
    application.add_handler(MessageHandler(filters.Regex("^📋 Мои бронирования$") & user_filter, show_user_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📞 Контакты$") & user_filter, show_contacts))

    # Кнопки фильтрации бронирований пользователя
    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & user_filter, handle_user_pending_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & user_filter, handle_user_confirmed_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & user_filter, handle_user_cancelled_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & user_filter, handle_user_all_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_user_back_to_bookings_button))

    # Обработчики контактов
    application.add_handler(MessageHandler(filters.Regex("^📞 Позвонить$") & user_filter, handle_call_contact))
    application.add_handler(MessageHandler(filters.Regex("^💬 Написать в Telegram$") & user_filter, handle_telegram_contact))
    application.add_handler(MessageHandler(filters.Regex("^📍 Мы на картах$") & user_filter, handle_open_maps))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_back_from_contacts))

    # Callback обработчики пользователя
    application.add_handler(CallbackQueryHandler(handle_user_cancel_booking, pattern="^user_cancel_booking_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_bookings_list, pattern="^back_to_bookings_list$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_contacts_callback, pattern="^back_to_contacts$"))

    # Conversation handlers пользователя
    application.add_handler(get_registration_handler())
    application.add_handler(get_spend_bonus_handler())
    application.add_handler(get_booking_handler())

    # 6. ОБРАБОТЧИКИ АДМИНИСТРАТОРА
    application.add_handler(MessageHandler(filters.Regex("^👥 Список пользователей$") & admin_filter, show_users_list))
    application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$") & admin_filter, show_statistics))
    application.add_handler(MessageHandler(filters.Regex("^📋 Запросы на списание$") & admin_filter, handle_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^🔄 Обновить список запросов$") & admin_filter, refresh_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^📅 Бронирования$") & admin_filter, show_bookings))
    application.add_handler(MessageHandler(filters.Regex("^🍽️ Управление заказами$") & admin_filter, start_order_management))
    application.add_handler(MessageHandler(filters.Regex("^🍴 Управление меню$") & admin_filter, manage_menu))

    # Кнопки фильтрации бронирований администратора
    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & admin_filter, show_pending_bookings))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & admin_filter, show_confirmed_bookings))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & admin_filter, show_cancelled_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & admin_filter, show_all_bookings))

    # Callback обработчики администратора для пользователей
    application.add_handler(CallbackQueryHandler(handle_users_pagination, pattern="^(users_page_|refresh_users)"))
    application.add_handler(CallbackQueryHandler(user_selected_callback, pattern="^select_user_"))
    application.add_handler(CallbackQueryHandler(user_info_callback, pattern="^info_"))
    application.add_handler(CallbackQueryHandler(message_user_callback, pattern="^message_"))
    application.add_handler(CallbackQueryHandler(exit_search_mode, pattern="^exit_search_mode$"))
    application.add_handler(CallbackQueryHandler(back_to_search_mode, pattern="^back_to_search_mode$"))
    application.add_handler(CallbackQueryHandler(new_search, pattern="^new_search$"))
    application.add_handler(CallbackQueryHandler(show_full_users_list, pattern="^show_full_users_list_"))
    application.add_handler(CallbackQueryHandler(back_to_users_list, pattern="^back_to_users_list$"))

    # Callback обработчики бронирований
    application.add_handler(CallbackQueryHandler(handle_booking_action, pattern="^(confirm_booking_|cancel_booking_)"))
    application.add_handler(CallbackQueryHandler(handle_bonus_request_action, pattern="^(approve_|reject_)"))

    # 7. ОБРАБОТЧИКИ УПРАВЛЕНИЯ ЗАКАЗАМИ
    application.add_handler(CallbackQueryHandler(handle_create_order, pattern="^create_order$"))
    application.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(handle_item_selection, pattern="^item_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_categories$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_category_"))
    application.add_handler(CallbackQueryHandler(finish_order, pattern="^finish_order$"))
    application.add_handler(CallbackQueryHandler(cancel_order_creation, pattern="^cancel_order$"))
    application.add_handler(CallbackQueryHandler(handle_add_items, pattern="^add_items_"))
    application.add_handler(CallbackQueryHandler(view_order_details, pattern="^view_order_"))
    application.add_handler(CallbackQueryHandler(show_payment_selection, pattern="^calculate_"))
    application.add_handler(CallbackQueryHandler(handle_payment_selection, pattern="^payment_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_calculation, pattern="^back_to_calculation_"))
    application.add_handler(CallbackQueryHandler(show_active_orders, pattern="^active_orders$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_admin$"))
    application.add_handler(CallbackQueryHandler(handle_cancel_calculation, pattern="^cancel_calculation$"))
    application.add_handler(CallbackQueryHandler(add_items_to_existing_order, pattern="^add_to_existing_"))
    application.add_handler(CallbackQueryHandler(show_order_for_editing, pattern="^edit_order_"))
    application.add_handler(CallbackQueryHandler(remove_item_from_order, pattern="^remove_item_"))
    application.add_handler(CallbackQueryHandler(show_order_history_menu, pattern="^order_history$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_order_management$"))
    application.add_handler(CallbackQueryHandler(show_shift_history, pattern="^history_shift$"))
    application.add_handler(CallbackQueryHandler(show_year_history, pattern="^history_year$"))
    application.add_handler(CallbackQueryHandler(select_year_for_history, pattern="^history_year_"))
    application.add_handler(CallbackQueryHandler(select_month_for_history, pattern="^history_month_"))
    application.add_handler(CallbackQueryHandler(show_select_shift_menu, pattern="^history_select_shift$"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_.*_.*"))
    application.add_handler(CallbackQueryHandler(show_full_year_history, pattern="^history_full_year_"))
    application.add_handler(CallbackQueryHandler(show_full_month_history, pattern="^history_full_month_"))
    application.add_handler(CallbackQueryHandler(show_more_shifts, pattern="^history_month_more_"))
    application.add_handler(CallbackQueryHandler(open_shift, pattern="^open_shift$"))
    application.add_handler(CallbackQueryHandler(close_shift, pattern="^close_shift$"))
    application.add_handler(CallbackQueryHandler(calculate_all_orders, pattern="^calculate_all_orders$"))
    application.add_handler(CallbackQueryHandler(show_shift_status, pattern="^shift_status$"))

    # 8. КОМАНДЫ (ДОБАВЛЯЕМ НОВЫЕ ДЛЯ MINIAPP)
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("webapp", open_miniapp))
    application.add_handler(CommandHandler("miniapp", debug_miniapp))

    # 9. СПЕЦИАЛЬНЫЕ ОБРАБОТЧИКИ
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$"), handle_back_button))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ В главное меню$"), handle_back_button))

    # 10. ОБРАБОТЧИК НЕИЗВЕСТНЫХ СООБЩЕНИЙ (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_unknown_message))

def main():
    """Основная функция запуска бота"""
    try:
        # Проверка токена
        if not BOT_TOKEN:
            logger.error("❌ Токен бота не найден! Проверьте файл .env")
            return

        # Создаем таблицы для MiniApp
        logger.info("🔄 Создание/проверка таблиц MiniApp...")
        create_miniapp_tables()
        
        # Запуск веб-сервера в отдельном потоке
        web_thread = threading.Thread(
            target=run_web_server, 
            daemon=True,
            name="web_server_thread"
        )
        web_thread.start()
        logger.info("🌐 Веб-сервер MiniApp запущен в отдельном потоке")
        
        # Даем веб-серверу время на запуск
        import time
        time.sleep(2)

        # Создание приложения бота
        application = Application.builder() \
            .token(BOT_TOKEN) \
            .post_init(post_init) \
            .post_stop(post_stop) \
            .build()

        # Настройка обработчиков
        logger.info("🔄 Настройка обработчиков...")
        setup_handlers(application)

        # Запуск бота
        logger.info("🚀 Запуск бота...")
        print("=" * 60)
        print("🤖 Бот запущен! Для остановки нажмите Ctrl+C")
        print("🌐 MiniApp доступен по команде /webapp")
        print("🌐 Веб-сервер работает на: http://localhost:3000")
        print("🌐 API Health: http://localhost:3000/api/health")
        print("🌐 Статический HTML: http://localhost:3000/static/index.html")
        if MINIAPP_URL:
            print(f"🌐 Внешний доступ: {MINIAPP_URL}")
        else:
            print("⚠️  MiniApp URL не настроен. Настройте MINIAPP_URL в config.py")
        print("🔧 Отладка MiniApp: /miniapp")
        print("=" * 60)

        # Запуск бота (синхронный метод)
        application.run_polling(
            allowed_updates=['message', 'callback_query', 'web_app_data'],
            timeout=60,
            drop_pending_updates=True,
            poll_interval=0.5
        )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    main()
