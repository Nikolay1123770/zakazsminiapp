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
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import sqlite3
import hashlib
import hmac

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

# Проверка подписи Telegram WebApp
def verify_telegram_data(init_data: str, bot_token: str) -> bool:
    """
    Проверяет подпись данных от Telegram WebApp
    """
    try:
        # Парсим данные
        data_pairs = init_data.split('&')
        hash_pair = [pair for pair in data_pairs if pair.startswith('hash=')][0]
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

# Создаем папку static, если её нет
STATIC_DIR = Path("static")
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("📁 Создана папка 'static' для MiniApp")

# Создаем базовый index.html, если его нет
INDEX_FILE = STATIC_DIR / "index.html"
if not INDEX_FILE.exists():
    # Сохраняем ваш HTML код
    html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Во Все Тяжкие | Premium Hookah</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* ... ваш существующий CSS остается без изменений ... */
    </style>
</head>
<body>
    <!-- LOADER -->
    <div class="loader-screen" id="loader">
        <!-- ... ваш существующий loader HTML ... -->
    </div>

    <!-- MAIN APP -->
    <div class="app" id="app">
        <!-- Toast -->
        <div class="toast" id="toast">
            <span class="toast-icon">✓</span>
            <span class="toast-message">Сообщение</span>
        </div>

        <!-- Header -->
        <header class="header">
            <div class="header-content">
                <div class="logo">
                    <div class="logo-boxes">
                        <div class="logo-box">Во</div>
                        <div class="logo-box">Т</div>
                    </div>
                    <div class="logo-text">
                        <h1>Во Все Тяжкие</h1>
                        <span>Premium Hookah</span>
                    </div>
                </div>
                <button class="header-btn" onclick="openLink('tel:+79991234567')">📞</button>
            </div>
        </header>

        <div class="container">
            <!-- MENU SECTION -->
            <section class="section active" id="section-menu">
                <!-- Hero -->
                <div class="hero">
                    <div class="hero-badge">Мы открыты до 02:00</div>
                    <h2 class="font-display">Искусство <span>кальяна</span></h2>
                    <p>Погрузитесь в атмосферу премиального отдыха с авторскими миксами</p>
                </div>

                <!-- Stats -->
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-value" id="statsFlavors">50+</div>
                        <div class="stat-label">Вкусов</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="statsExperience">5</div>
                        <div class="stat-label">Лет опыта</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="statsGuests">10K</div>
                        <div class="stat-label">Гостей</div>
                    </div>
                </div>

                <!-- CTA -->
                <div class="cta-section">
                    <button class="cta-btn" onclick="showSection('booking')">
                        <span class="icon">📅</span>
                        Забронировать столик
                    </button>
                </div>

                <!-- Categories -->
                <div class="categories-section">
                    <div class="section-header">
                        <h3 class="section-title">Наше <span>меню</span></h3>
                        <button class="header-btn" onclick="refreshMenu()" style="width: auto; padding: 0 12px;">🔄</button>
                    </div>
                    <div class="categories-scroll">
                        <button class="category-chip active" onclick="filterMenu('all', this)">
                            <span class="icon">✨</span> Всё меню
                        </button>
                        <button class="category-chip" onclick="filterMenu('hookah', this)">
                            <span class="icon">💨</span> Кальяны
                        </button>
                        <button class="category-chip" onclick="filterMenu('signature', this)">
                            <span class="icon">⚗️</span> Авторские
                        </button>
                        <button class="category-chip" onclick="filterMenu('drinks', this)">
                            <span class="icon">🍹</span> Напитки
                        </button>
                        <button class="category-chip" onclick="filterMenu('food', this)">
                            <span class="icon">🍕</span> Кухня
                        </button>
                    </div>
                    <div class="menu-grid" id="menuGrid">
                        <!-- Меню будет загружено динамически -->
                    </div>
                </div>

                <!-- Features -->
                <div class="features">
                    <div class="section-header">
                        <h3 class="section-title">Почему <span>мы</span></h3>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🌿</div>
                        <div class="feature-content">
                            <h4>Премиум табаки</h4>
                            <p>Tangiers, Darkside, MustHave, Element — только лучшие бренды</p>
                        </div>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">👨‍🔬</div>
                        <div class="feature-content">
                            <h4>Мастера своего дела</h4>
                            <p>Наши кальянщики — настоящие алхимики с 5+ лет опыта</p>
                        </div>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🛋️</div>
                        <div class="feature-content">
                            <h4>VIP атмосфера</h4>
                            <p>Приватные комнаты и уютные зоны для вашего комфорта</p>
                        </div>
                    </div>
                </div>

                <!-- Contacts -->
                <div class="section-header">
                    <h3 class="section-title">📍 <span>Контакты</span></h3>
                </div>
                <div class="contacts-card">
                    <div class="contact-item" onclick="openLink('https://maps.google.com/?q=Москва+Химическая+52')">
                        <div class="contact-icon">📍</div>
                        <div class="contact-info">
                            <div class="contact-label">Адрес</div>
                            <div class="contact-value" id="contactAddress">ул. Химическая, 52</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" onclick="openLink('tel:+79991234567')">
                        <div class="contact-icon">📞</div>
                        <div class="contact-info">
                            <div class="contact-label">Телефон</div>
                            <div class="contact-value" id="contactPhone">+7 (999) 123-45-67</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" onclick="openLink('https://instagram.com/vovseTyajkie')">
                        <div class="contact-icon">📸</div>
                        <div class="contact-info">
                            <div class="contact-label">Instagram</div>
                            <div class="contact-value" id="contactInstagram">@vovseTyajkie</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                </div>

                <!-- Schedule -->
                <div class="schedule-card">
                    <div class="schedule-header">
                        <span class="schedule-header-icon">🕐</span>
                        <div>
                            <h4>Время работы</h4>
                            <p>Ждём вас каждый день</p>
                        </div>
                    </div>
                    <div class="schedule-grid">
                        <div class="schedule-item">
                            <div class="schedule-days">Пн — Чт</div>
                            <div class="schedule-time" id="scheduleWeekdays">14:00 — 02:00</div>
                        </div>
                        <div class="schedule-item">
                            <div class="schedule-days">Пт — Вс</div>
                            <div class="schedule-time" id="scheduleWeekend">14:00 — 04:00</div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- BOOKING SECTION -->
            <section class="section" id="section-booking">
                <div class="section-header" style="margin: 24px 0 16px;">
                    <h3 class="section-title">📅 <span>Бронирование</span></h3>
                </div>
                <div class="booking-card">
                    <div class="form-group">
                        <label class="form-label">Ваше имя</label>
                        <input type="text" class="form-input" id="bookingName" placeholder="Введите имя">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Телефон</label>
                        <input type="tel" class="form-input" id="bookingPhone" placeholder="+7 (___) ___-__-__">
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Дата</label>
                            <input type="date" class="form-input" id="bookingDate">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Время</label>
                            <select class="form-input" id="bookingTime">
                                <!-- Времена будут загружены динамически -->
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Количество гостей</label>
                        <select class="form-input" id="bookingGuests">
                            <option value="1-2">1-2 человека</option>
                            <option value="3-4">3-4 человека</option>
                            <option value="5-6">5-6 человек</option>
                            <option value="7+">7+ человек (VIP)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Пожелания</label>
                        <input type="text" class="form-input" id="bookingComment" placeholder="Особые пожелания...">
                    </div>
                    <button class="submit-btn" onclick="submitBooking()">Забронировать столик</button>
                </div>
            </section>

            <!-- GALLERY SECTION -->
            <section class="section" id="section-gallery">
                <!-- ... существующая галерея ... -->
            </section>

            <!-- PROFILE SECTION -->
            <section class="section" id="section-profile">
                <div class="section-header" style="margin: 24px 0 16px;">
                    <h3 class="section-title">👤 <span>Профиль</span></h3>
                </div>
                <div class="profile-card">
                    <div class="profile-avatar" id="profileAvatar">👤</div>
                    <div class="profile-name" id="profileName">Гость</div>
                    <div class="profile-username" id="profileUsername"></div>
                    <div class="profile-balance" style="margin-top: 15px; padding: 10px; background: rgba(168,85,247,0.1); border-radius: 10px;">
                        <div style="font-size: 14px; color: #a855f7;">Ваш баланс:</div>
                        <div style="font-size: 24px; font-weight: 700;" id="profileBalance">0 бонусов</div>
                    </div>
                </div>

                <!-- Quick Actions -->
                <div class="contacts-card" style="margin-top: 20px;">
                    <div class="contact-item" onclick="showSection('booking')">
                        <div class="contact-icon">📅</div>
                        <div class="contact-info">
                            <div class="contact-value">Забронировать столик</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" onclick="openLink('tel:+79991234567')">
                        <div class="contact-icon">📞</div>
                        <div class="contact-info">
                            <div class="contact-value">Позвонить нам</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                    <div class="contact-item" onclick="openLink('https://instagram.com/vovseTyajkie')">
                        <div class="contact-icon">📸</div>
                        <div class="contact-info">
                            <div class="contact-value">Instagram</div>
                        </div>
                        <span class="contact-arrow">→</span>
                    </div>
                </div>
            </section>
        </div>

        <!-- Bottom Navigation -->
        <nav class="bottom-nav">
            <div class="bottom-nav-content">
                <button class="nav-item active" onclick="showSection('menu')">
                    <span class="icon">🏠</span>
                    <span>Меню</span>
                </button>
                <button class="nav-item" onclick="showSection('booking')">
                    <span class="icon">📅</span>
                    <span>Бронь</span>
                </button>
                <button class="nav-item" onclick="showSection('gallery')">
                    <span class="icon">📸</span>
                    <span>Галерея</span>
                </button>
                <button class="nav-item" onclick="showSection('profile')">
                    <span class="icon">👤</span>
                    <span>Профиль</span>
                </button>
            </div>
        </nav>

        <!-- Product Modal -->
        <div class="modal-overlay" id="productModal" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()">
                <div class="modal-handle"></div>
                <div class="modal-image" id="modalImage">💨</div>
                <h3 class="modal-title" id="modalTitle">Название</h3>
                <p class="modal-desc" id="modalDesc">Описание товара</p>
                <div class="modal-price" id="modalPrice">0₽</div>
                <button class="modal-close-btn" onclick="document.getElementById('productModal').classList.remove('active')">Закрыть</button>
            </div>
        </div>
    </div>

    <script>
        const tg = window.Telegram?.WebApp;
        const API_URL = window.location.origin; // Базовый URL API
        
        let menuItems = [];
        let userData = null;
        let currentCategory = 'all';

        // Initialize
        async function init() {
            try {
                // Загружаем все данные параллельно
                await Promise.all([
                    loadMenu(),
                    loadUserData(),
                    loadConfig()
                ]);
                
                setTimeout(() => {
                    document.getElementById('loader').classList.add('hidden');
                    document.getElementById('app').classList.add('visible');
                    showToast('Добро пожаловать!');
                }, 1500);
                
            } catch (error) {
                console.error('Ошибка инициализации:', error);
                showToast('Ошибка загрузки данных');
            }
            
            // Устанавливаем минимальную дату для бронирования
            const today = new Date();
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            document.getElementById('bookingDate').min = tomorrow.toISOString().split('T')[0];
            document.getElementById('bookingDate').value = tomorrow.toISOString().split('T')[0];
            
            // Заполняем времена для бронирования
            populateBookingTimes();
        }

        // Загрузить меню с сервера
        async function loadMenu() {
            try {
                const response = await fetch(`${API_URL}/api/menu`);
                if (!response.ok) throw new Error('Ошибка загрузки меню');
                menuItems = await response.json();
                renderMenu(menuItems);
            } catch (error) {
                console.error('Ошибка загрузки меню:', error);
                // Загружаем fallback данные
                loadFallbackMenu();
            }
        }

        // Загрузить данные пользователя
        async function loadUserData() {
            if (!tg?.initDataUnsafe?.user) return;
            
            try {
                const user = tg.initDataUnsafe.user;
                const response = await fetch(`${API_URL}/api/user/${user.id}`, {
                    headers: {
                        'X-Telegram-Init-Data': JSON.stringify(tg.initDataUnsafe)
                    }
                });
                
                if (response.ok) {
                    userData = await response.json();
                    updateUserProfile(userData);
                } else {
                    // Если пользователь не найден, создаем его
                    await createUser(user);
                }
            } catch (error) {
                console.error('Ошибка загрузки пользователя:', error);
            }
        }

        // Создать нового пользователя
        async function createUser(tgUser) {
            try {
                const response = await fetch(`${API_URL}/api/user/create`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Telegram-Init-Data': JSON.stringify(tg.initDataUnsafe)
                    },
                    body: JSON.stringify({
                        user_id: tgUser.id,
                        first_name: tgUser.first_name,
                        last_name: tgUser.last_name || '',
                        username: tgUser.username || '',
                        language_code: tgUser.language_code || 'ru'
                    })
                });
                
                if (response.ok) {
                    userData = await response.json();
                    updateUserProfile(userData);
                }
            } catch (error) {
                console.error('Ошибка создания пользователя:', error);
            }
        }

        // Обновить профиль пользователя
        function updateUserProfile(data) {
            document.getElementById('profileName').textContent = data.first_name || 'Гость';
            document.getElementById('profileUsername').textContent = data.username ? '@' + data.username : '';
            document.getElementById('profileAvatar').textContent = (data.first_name || 'Г')[0];
            document.getElementById('profileBalance').textContent = `${data.bonus_balance || 0} бонусов`;
            
            // Заполняем форму бронирования данными пользователя
            if (data.phone) {
                document.getElementById('bookingPhone').value = data.phone;
            }
            if (data.first_name) {
                document.getElementById('bookingName').value = data.first_name;
            }
        }

        // Загрузить конфигурацию
        async function loadConfig() {
            try {
                const response = await fetch(`${API_URL}/api/config`);
                if (!response.ok) throw new Error('Ошибка загрузки конфигурации');
                const config = await response.json();
                
                // Обновляем контакты
                if (config.contacts) {
                    document.getElementById('contactAddress').textContent = config.contacts.address || 'ул. Химическая, 52';
                    document.getElementById('contactPhone').textContent = config.contacts.phone || '+7 (999) 123-45-67';
                    document.getElementById('contactInstagram').textContent = config.contacts.instagram || '@vovseTyajkie';
                }
                
                // Обновляем график работы
                if (config.schedule) {
                    document.getElementById('scheduleWeekdays').textContent = config.schedule.weekdays || '14:00 — 02:00';
                    document.getElementById('scheduleWeekend').textContent = config.schedule.weekend || '14:00 — 04:00';
                }
                
                // Обновляем статистику
                if (config.stats) {
                    document.getElementById('statsFlavors').textContent = config.stats.flavors || '50+';
                    document.getElementById('statsExperience').textContent = config.stats.experience || '5';
                    document.getElementById('statsGuests').textContent = config.stats.guests || '10K';
                }
            } catch (error) {
                console.error('Ошибка загрузки конфигурации:', error);
            }
        }

        // Заполнить времена для бронирования
        function populateBookingTimes() {
            const timeSelect = document.getElementById('bookingTime');
            timeSelect.innerHTML = '';
            
            // Генерируем времена с 14:00 до 02:00
            for (let hour = 14; hour <= 23; hour++) {
                const time = `${hour.toString().padStart(2, '0')}:00`;
                const option = document.createElement('option');
                option.value = time;
                option.textContent = time;
                timeSelect.appendChild(option);
            }
            
            // Добавляем ночные часы
            for (let hour = 0; hour <= 2; hour++) {
                const time = `${hour.toString().padStart(2, '0')}:00`;
                const option = document.createElement('option');
                option.value = time;
                option.textContent = time;
                timeSelect.appendChild(option);
            }
            
            // Устанавливаем текущее время + 1 час как значение по умолчанию
            const now = new Date();
            const nextHour = new Date(now.getTime() + 60 * 60 * 1000);
            const defaultTime = nextHour.getHours().toString().padStart(2, '0') + ':00';
            timeSelect.value = defaultTime;
        }

        // Fallback меню (если API недоступно)
        function loadFallbackMenu() {
            menuItems = [
                {id:1, name:'Классический', desc:'Один вкус премиум табака на выбор. Идеален для начинающих', price:1200, old_price:1500, category:'hookah', icon:'💨', badge:'hit'},
                {id:2, name:'Premium', desc:'Tangiers, Darkside, Element — топовые табаки мира', price:1800, category:'hookah', icon:'🔮', badge:'premium'},
                {id:3, name:'VIP Кальян', desc:'Эксклюзивные табаки + фрукты + авторская подача', price:2500, category:'hookah', icon:'👑', badge:'vip'},
                {id:4, name:'Blue Crystal', desc:'Ледяная свежесть с нотками мяты и цитруса', price:2000, category:'signature', icon:'🧊', badge:'hit'},
                {id:5, name:'Heisenberg', desc:'Секретный рецепт шефа. 99.1% чистого наслаждения', price:2200, category:'signature', icon:'⚗️', badge:'signature'},
                {id:6, name:'Los Pollos', desc:'Пряный микс с перцем и тропическими фруктами', price:2000, category:'signature', icon:'🔥', badge:'hot'},
                {id:7, name:'Чай (чайник)', desc:'Чёрный, зелёный, фруктовый или травяной', price:400, category:'drinks', icon:'🍵'},
                {id:8, name:'Лимонады', desc:'Клубничный, цитрусовый, мохито, манго', price:350, category:'drinks', icon:'🍹'},
                {id:9, name:'Кофе', desc:'Эспрессо, американо, капучино, латте, раф', price:250, category:'drinks', icon:'☕'},
                {id:10, name:'Пицца', desc:'Маргарита, Пепперони, 4 сыра, BBQ курица', price:650, category:'food', icon:'🍕'},
                {id:11, name:'Салаты', desc:'Цезарь, Греческий, с креветками', price:450, category:'food', icon:'🥗'},
                {id:12, name:'Закуски', desc:'Картофель фри, наггетсы, сырные палочки', price:350, category:'food', icon:'🍟'}
            ];
            renderMenu(menuItems);
        }

        // Render Menu
        function renderMenu(items) {
            const badgeLabels = {
                hit:'Хит', 
                premium:'Premium', 
                vip:'VIP', 
                signature:'Авторский', 
                hot:'Острое',
                new: 'Новинка'
            };
            
            if (!items || items.length === 0) {
                document.getElementById('menuGrid').innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 40px;">
                        <div style="font-size: 48px; margin-bottom: 20px;">🍽️</div>
                        <p style="color: #888; margin-bottom: 20px;">Меню временно недоступно</p>
                        <button onclick="refreshMenu()" style="padding: 12px 24px; background: var(--primary); border: none; border-radius: 12px; color: white; cursor: pointer;">
                            Обновить
                        </button>
                    </div>
                `;
                return;
            }
            
            document.getElementById('menuGrid').innerHTML = items.map(item => `
                <div class="menu-card" data-category="${item.category}" onclick="openProduct(${item.id})">
                    <div class="menu-card-image">
                        ${item.badge ? `<span class="menu-card-badge badge-${item.badge}">${badgeLabels[item.badge] || item.badge}</span>` : ''}
                        ${item.icon || '🍽️'}
                    </div>
                    <div class="menu-card-content">
                        <h4 class="menu-card-title">${item.name}</h4>
                        <p class="menu-card-desc">${item.description || item.desc}</p>
                        <div class="menu-card-footer">
                            <span class="menu-card-price">${item.price}₽${item.old_price ? `<span class="old">${item.old_price}₽</span>` : ''}</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        // Filter Menu
        function filterMenu(category, btn) {
            document.querySelectorAll('.category-chip').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = category;
            
            const filtered = category === 'all' 
                ? menuItems 
                : menuItems.filter(i => i.category === category);
            
            renderMenu(filtered);
            haptic();
        }

        // Refresh Menu
        async function refreshMenu() {
            showToast('Обновляем меню...');
            await loadMenu();
            showToast('Меню обновлено!');
            haptic();
        }

        // Product Modal
        function openProduct(id) {
            const product = menuItems.find(i => i.id === id);
            if (!product) return;
            
            document.getElementById('modalImage').textContent = product.icon || '🍽️';
            document.getElementById('modalTitle').textContent = product.name;
            document.getElementById('modalDesc').textContent = product.description || product.desc;
            document.getElementById('modalPrice').textContent = product.price + '₽';
            document.getElementById('productModal').classList.add('active');
            haptic();
        }

        function closeModal(e) {
            if (e.target.id === 'productModal') {
                document.getElementById('productModal').classList.remove('active');
            }
        }

        // Booking
        async function submitBooking() {
            const name = document.getElementById('bookingName').value.trim();
            const phone = document.getElementById('bookingPhone').value.trim();
            const date = document.getElementById('bookingDate').value;
            const time = document.getElementById('bookingTime').value;
            const guests = document.getElementById('bookingGuests').value;
            const comment = document.getElementById('bookingComment').value.trim();
            
            if (!name || !phone) {
                showToast('Заполните имя и телефон');
                return;
            }
            
            if (!date) {
                showToast('Выберите дату');
                return;
            }
            
            try {
                const bookingData = {
                    name,
                    phone,
                    date,
                    time,
                    guests,
                    comment,
                    source: 'miniapp'
                };
                
                // Если пользователь авторизован, добавляем его ID
                if (userData) {
                    bookingData.user_id = userData.user_id;
                }
                
                // Отправляем данные на сервер
                const response = await fetch(`${API_URL}/api/booking/create`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Telegram-Init-Data': JSON.stringify(tg?.initDataUnsafe || {})
                    },
                    body: JSON.stringify(bookingData)
                });
                
                if (response.ok) {
                    const result = await response.json();
                    showToast('Заявка отправлена! Мы перезвоним ✓');
                    
                    // Очищаем форму
                    document.getElementById('bookingName').value = '';
                    document.getElementById('bookingPhone').value = '';
                    document.getElementById('bookingComment').value = '';
                    
                    // Показываем меню
                    showSection('menu');
                    
                    // Отправляем данные в Telegram (для бота)
                    if (tg) {
                        tg.sendData(JSON.stringify({
                            type: 'booking_created',
                            booking_id: result.booking_id
                        }));
                    }
                } else {
                    const error = await response.json();
                    showToast(error.message || 'Ошибка при отправке заявки');
                }
            } catch (error) {
                console.error('Ошибка бронирования:', error);
                showToast('Ошибка сети. Проверьте подключение');
            }
            
            haptic();
        }

        // Navigation
        function showSection(id) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById('section-' + id).classList.add('active');
            
            const navIndex = {menu: 0, booking: 1, gallery: 2, profile: 3};
            document.querySelectorAll('.nav-item')[navIndex[id]]?.classList.add('active');
            window.scrollTo({top: 0, behavior: 'smooth'});
            
            // При показе профиля обновляем данные
            if (id === 'profile' && tg?.initDataUnsafe?.user) {
                loadUserData();
            }
            
            haptic();
        }

        // Helpers
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.querySelector('.toast-message').textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        function haptic() {
            if (tg?.HapticFeedback) {
                tg.HapticFeedback.impactOccurred('light');
            }
        }

        function openLink(url) {
            if (tg) {
                tg.openLink(url);
            } else {
                window.open(url, '_blank');
            }
        }

        // Запуск приложения
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>"""
    
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info("📄 Создан index.html в папке static")

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

# Подключаем базу данных
def get_db_connection():
    conn = sqlite3.connect('vovsetyagskie.db')
    conn.row_factory = sqlite3.Row
    return conn

# Middleware для проверки данных Telegram
async def verify_telegram_request(request: Request):
    """Проверяет подпись запроса от Telegram"""
    init_data = request.headers.get('X-Telegram-Init-Data')
    
    if not init_data:
        # Для публичных эндпоинтов пропускаем проверку
        public_endpoints = ['/api/menu', '/api/config', '/health']
        if request.url.path in public_endpoints:
            return None
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
    
    # Парсим данные пользователя
    import urllib.parse
    parsed_data = urllib.parse.parse_qs(init_data)
    user_data = json.loads(parsed_data.get('user', ['{}'])[0])
    
    return user_data

# API эндпоинты
@web_app.get("/api/menu")
async def get_menu():
    """Получить все товары меню"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Получаем все товары
        cursor.execute("""
            SELECT id, name, description, price, old_price, category, icon, badge 
            FROM menu 
            WHERE is_active = 1
            ORDER BY category, position, id
        """)
        
        items = cursor.fetchall()
        menu_data = []
        
        for item in items:
            menu_data.append({
                "id": item[0],
                "name": item[1],
                "description": item[2],
                "price": item[3],
                "old_price": item[4],
                "category": item[5],
                "icon": item[6] or "🍽️",
                "badge": item[7]
            })
        
        return JSONResponse(menu_data)
        
    except Exception as e:
        logger.error(f"Ошибка получения меню: {e}")
        return JSONResponse({"error": "Ошибка загрузки меню"}, status_code=500)
        
    finally:
        conn.close()

@web_app.get("/api/user/{user_id}")
async def get_user(user_id: int, user_data: dict = Depends(verify_telegram_request)):
    """Получить информацию о пользователе"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT user_id, first_name, username, phone, balance, bonus_balance, total_spent, total_orders
            FROM users 
            WHERE user_id = ?
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {
            "user_id": user[0],
            "first_name": user[1],
            "username": user[2],
            "phone": user[3] or "",
            "balance": user[4] or 0,
            "bonus_balance": user[5] or 0,
            "total_spent": user[6] or 0,
            "total_orders": user[7] or 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    finally:
        conn.close()

@web_app.post("/api/user/create")
async def create_user(user: UserCreate, user_data: dict = Depends(verify_telegram_request)):
    """Создать нового пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли пользователь
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.user_id,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            return JSONResponse({"message": "Пользователь уже существует", "user_id": user.user_id})
        
        # Создаем нового пользователя
        cursor.execute("""
            INSERT INTO users (user_id, first_name, last_name, username, registration_date, balance, bonus_balance)
            VALUES (?, ?, ?, ?, datetime('now'), 0, 0)
        """, (user.user_id, user.first_name, user.last_name, user.username))
        
        conn.commit()
        
        logger.info(f"🆕 Создан новый пользователь из MiniApp: {user.user_id}, {user.first_name}")
        
        return {
            "message": "Пользователь создан",
            "user_id": user.user_id,
            "first_name": user.first_name
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания пользователя: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания пользователя")
    finally:
        conn.close()

@web_app.post("/api/booking/create")
async def create_booking(booking: BookingCreate, user_data: dict = Depends(verify_telegram_request)):
    """Создать бронирование из MiniApp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Если указан user_id, проверяем пользователя
        if booking.user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (booking.user_id,))
            if not cursor.fetchone():
                # Создаем пользователя, если его нет
                cursor.execute("""
                    INSERT INTO users (user_id, first_name, registration_date, balance, bonus_balance)
                    VALUES (?, ?, datetime('now'), 0, 0)
                """, (booking.user_id, booking.name))
                conn.commit()
                logger.info(f"🆕 Автоматически создан пользователь для бронирования: {booking.user_id}")
        
        # Создаем бронирование
        cursor.execute("""
            INSERT INTO bookings (
                user_id, booking_date, booking_time, guests, comment, 
                status, created_at, source, customer_name, customer_phone
            )
            VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'), ?, ?, ?)
        """, (
            booking.user_id,
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
                logger.error(f"Ошибка уведомления админа {admin_id}: {e}")
        
        return {
            "message": "Бронирование создано",
            "booking_id": booking_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания бронирования: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания бронирования")
    finally:
        conn.close()

@web_app.get("/api/config")
async def get_config():
    """Получить конфигурацию для MiniApp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Получаем конфигурацию из базы или используем значения по умолчанию
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
        
        # Здесь можно добавить получение реальных данных из базы
        cursor.execute("SELECT key, value FROM config WHERE section = 'miniapp'")
        db_config = cursor.fetchall()
        
        for item in db_config:
            key = item[0]
            value = item[1]
            # Обновляем конфиг из базы данных
            if key.startswith("contacts."):
                _, field = key.split(".")
                config["contacts"][field] = value
            elif key.startswith("schedule."):
                _, field = key.split(".")
                config["schedule"][field] = value
            elif key.startswith("stats."):
                _, field = key.split(".")
                config["stats"][field] = value
        
        return JSONResponse(config)
        
    except Exception as e:
        logger.error(f"Ошибка получения конфигурации: {e}")
        return JSONResponse(config)  # Возвращаем конфиг по умолчанию
    finally:
        conn.close()

@web_app.get("/api/booking/user/{user_id}")
async def get_user_bookings(user_id: int, user_data: dict = Depends(verify_telegram_request)):
    """Получить бронирования пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                id, booking_date, booking_time, guests, comment, 
                status, created_at, source, customer_name
            FROM bookings 
            WHERE user_id = ?
            ORDER BY booking_date DESC, booking_time DESC
            LIMIT 20
        """, (user_id,))
        
        bookings = cursor.fetchall()
        
        result = []
        for booking in bookings:
            result.append({
                "id": booking[0],
                "date": booking[1],
                "time": booking[2],
                "guests": booking[3],
                "comment": booking[4] or "",
                "status": booking[5],
                "created_at": booking[6],
                "source": booking[7],
                "customer_name": booking[8]
            })
        
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Ошибка получения бронирований пользователя {user_id}: {e}")
        return JSONResponse([], status_code=500)
    finally:
        conn.close()

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
    return JSONResponse({"status": "ok", "service": "miniapp", "port": 3000})

# Маршрут для проверки API
@web_app.get("/api/health")
async def api_health():
    return JSONResponse({
        "status": "ok", 
        "api": "vovsetyagskie_miniapp", 
        "version": "1.0",
        "endpoints": {
            "menu": "/api/menu",
            "user": "/api/user/{user_id}",
            "booking": "/api/booking/create",
            "config": "/api/config"
        }
    })

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
        logger.info("📡 API доступно по адресу: http://0.0.0.0:3000")
        logger.info("🔗 Основные эндпоинты:")
        logger.info("   - /api/menu - получить меню")
        logger.info("   - /api/user/{id} - информация о пользователе")
        logger.info("   - /api/booking/create - создать бронирование")
        logger.info("   - /api/config - конфигурация MiniApp")
        loop.run_until_complete(server.serve())
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")

# ... остальная часть вашего main.py остается без изменений ...

# В функции main() добавьте создание необходимых таблиц:
def create_miniapp_tables():
    """Создание таблиц для MiniApp"""
    from database import Database
    db = Database()
    
    # Создаем таблицу конфигурации если её нет
    db.cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(section, key)
        )
    """)
    
    # Добавляем базовую конфигурацию
    default_config = [
        ('miniapp', 'contacts.address', 'ул. Химическая, 52', 'Адрес заведения'),
        ('miniapp', 'contacts.phone', '+7 (999) 123-45-67', 'Телефон для связи'),
        ('miniapp', 'contacts.instagram', '@vovseTyajkie', 'Instagram профиль'),
        ('miniapp', 'schedule.weekdays', '14:00 — 02:00', 'Время работы Пн-Чт'),
        ('miniapp', 'schedule.weekend', '14:00 — 04:00', 'Время работы Пт-Вс'),
        ('miniapp', 'stats.flavors', '50+', 'Количество вкусов'),
        ('miniapp', 'stats.experience', '5', 'Лет опыта'),
        ('miniapp', 'stats.guests', '10K', 'Количество гостей')
    ]
    
    for config_item in default_config:
        try:
            db.cursor.execute("""
                INSERT OR IGNORE INTO config (section, key, value, description)
                VALUES (?, ?, ?, ?)
            """, config_item)
        except:
            pass
    
    db.conn.commit()
    logger.info("✅ Таблицы для MiniApp созданы/проверены")

# Обновите функцию main():
def main():
    """Основная функция запуска бота"""
    try:
        # Проверка токена
        if not BOT_TOKEN:
            logger.error("❌ Токен бота не найден! Проверьте файл .env")
            return

        # Создаем таблицы для MiniApp
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
        print("🔧 Отладка MiniApp: /debug_miniapp")
        print("🔧 Отладка смен: /debug_shifts")
        print("🔄 Сброс смены: /reset_shift")
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
