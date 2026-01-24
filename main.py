import logging
import os
import warnings
import json
import hashlib
import hmac
from urllib.parse import parse_qsl
from threading import Thread
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.warnings import PTBUserWarning
from dotenv import load_dotenv
from config import BOT_TOKEN, ADMIN_IDS
from error_logger import setup_error_logging

# Flask imports для Mini App
from flask import Flask, render_template_string, jsonify, request, send_from_directory
from flask_cors import CORS

# Игнорировать предупреждения PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

# Загрузка переменных окружения
load_dotenv()

# ============ MINI APP CONFIGURATION ============
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 5000
WEBAPP_URL = "https://vovsetyagskie.bothost.ru"  # Ваш домен

# ============ FLASK APP FOR MINI APP ============
flask_app = Flask(__name__)
CORS(flask_app)
flask_app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# ============ HTML TEMPLATES ============

BASE_HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{{ title }}</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --tg-theme-bg-color: #ffffff;
            --tg-theme-text-color: #000000;
            --tg-theme-hint-color: #999999;
            --tg-theme-link-color: #2481cc;
            --tg-theme-button-color: #2481cc;
            --tg-theme-button-text-color: #ffffff;
            --tg-theme-secondary-bg-color: #f1f1f1;
            --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --success-gradient: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            --danger-color: #ff3b30;
            --warning-color: #ff9500;
            --success-color: #34c759;
            --radius: 16px;
            --radius-sm: 10px;
            --shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--tg-theme-bg-color);
            color: var(--tg-theme-text-color);
            min-height: 100vh;
            padding-bottom: 90px;
            -webkit-font-smoothing: antialiased;
        }
        
        .container { max-width: 500px; margin: 0 auto; padding: 16px; }
        
        /* Header */
        .header {
            background: var(--primary-gradient);
            padding: 30px 20px;
            border-radius: 0 0 30px 30px;
            color: white;
            text-align: center;
            margin: -16px -16px 20px;
        }
        .header h1 { font-size: 26px; margin-bottom: 5px; }
        .header p { opacity: 0.9; font-size: 14px; }
        
        /* Balance Card */
        .balance-card {
            background: var(--success-gradient);
            padding: 25px;
            border-radius: var(--radius);
            color: white;
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 20px;
            box-shadow: var(--shadow);
        }
        .balance-icon { font-size: 45px; }
        .balance-info { flex: 1; }
        .balance-label { font-size: 13px; opacity: 0.9; }
        .balance-value { font-size: 36px; font-weight: 700; }
        .balance-currency { font-size: 14px; opacity: 0.9; }
        
        /* Quick Actions Grid */
        .actions-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 25px;
        }
        .action-card {
            background: var(--tg-theme-secondary-bg-color);
            padding: 22px 15px;
            border-radius: var(--radius);
            text-align: center;
            text-decoration: none;
            color: var(--tg-theme-text-color);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }
        .action-card:active { transform: scale(0.97); }
        .action-icon { font-size: 36px; margin-bottom: 10px; }
        .action-title { font-size: 13px; font-weight: 600; }
        
        /* Section Card */
        .section { margin-bottom: 20px; }
        .section-title { font-size: 18px; font-weight: 700; margin-bottom: 15px; }
        .section-card {
            background: var(--tg-theme-secondary-bg-color);
            padding: 20px;
            border-radius: var(--radius);
        }
        
        /* Booking Card */
        .booking-card {
            background: var(--tg-theme-secondary-bg-color);
            padding: 16px;
            border-radius: var(--radius-sm);
            margin-bottom: 10px;
            border-left: 4px solid var(--warning-color);
        }
        .booking-card.confirmed { border-left-color: var(--success-color); }
        .booking-card.cancelled { border-left-color: var(--danger-color); }
        .booking-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
        .booking-date { font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .booking-status {
            font-size: 12px; padding: 4px 10px; border-radius: 20px;
            background: rgba(255,149,0,0.2); color: var(--warning-color);
        }
        .booking-status.confirmed { background: rgba(52,199,89,0.2); color: var(--success-color); }
        .booking-status.cancelled { background: rgba(255,59,48,0.2); color: var(--danger-color); }
        .booking-guests { color: var(--tg-theme-hint-color); font-size: 14px; display: flex; align-items: center; gap: 8px; }
        
        /* Menu Items */
        .category-tabs {
            display: flex; gap: 10px; overflow-x: auto;
            padding: 5px 0 15px; margin-bottom: 15px;
            -webkit-overflow-scrolling: touch;
        }
        .category-tabs::-webkit-scrollbar { display: none; }
        .category-tab {
            background: var(--tg-theme-secondary-bg-color);
            border: none; padding: 12px 20px; border-radius: 25px;
            font-size: 14px; font-weight: 500; white-space: nowrap;
            cursor: pointer; color: var(--tg-theme-text-color);
            transition: all 0.2s;
        }
        .category-tab.active { background: var(--tg-theme-button-color); color: white; }
        
        .menu-item {
            background: var(--tg-theme-secondary-bg-color);
            padding: 16px; border-radius: var(--radius-sm);
            margin-bottom: 12px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .item-name { font-weight: 600; margin-bottom: 4px; }
        .item-desc { font-size: 13px; color: var(--tg-theme-hint-color); }
        .item-price { font-size: 18px; font-weight: 700; color: var(--tg-theme-button-color); white-space: nowrap; }
        
        /* Form Styles */
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; font-size: 14px; font-weight: 500; margin-bottom: 8px; }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%; padding: 15px; border: 2px solid transparent;
            border-radius: var(--radius-sm); font-size: 16px;
            background: var(--tg-theme-secondary-bg-color);
            color: var(--tg-theme-text-color);
            transition: border-color 0.2s;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none; border-color: var(--tg-theme-button-color);
        }
        .form-group textarea { min-height: 100px; resize: vertical; }
        
        .guests-selector { display: flex; align-items: center; gap: 20px; }
        .guests-btn {
            width: 50px; height: 50px; border: none; border-radius: 50%;
            background: var(--tg-theme-secondary-bg-color);
            font-size: 26px; cursor: pointer; color: var(--tg-theme-text-color);
            display: flex; align-items: center; justify-content: center;
        }
        .guests-btn:active { background: var(--tg-theme-button-color); color: white; }
        .guests-value { font-size: 28px; font-weight: 700; min-width: 50px; text-align: center; }
        
        .submit-btn {
            width: 100%; background: var(--tg-theme-button-color);
            color: white; border: none; padding: 18px;
            border-radius: var(--radius); font-size: 16px; font-weight: 600;
            cursor: pointer; display: flex; align-items: center;
            justify-content: center; gap: 10px;
            transition: opacity 0.2s;
        }
        .submit-btn:active { opacity: 0.8; }
        .submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        /* Referral Card */
        .referral-card {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 25px; border-radius: var(--radius);
            color: white; margin-bottom: 20px;
        }
        .referral-card h3 { margin-bottom: 8px; }
        .referral-card p { font-size: 14px; opacity: 0.9; margin-bottom: 15px; }
        .referral-code-box {
            background: rgba(255,255,255,0.2);
            padding: 12px 15px; border-radius: var(--radius-sm);
            display: flex; align-items: center; justify-content: space-between;
        }
        .referral-code { font-size: 22px; font-weight: 700; letter-spacing: 2px; }
        .copy-btn {
            background: rgba(255,255,255,0.3);
            border: none; color: white; width: 40px; height: 40px;
            border-radius: 50%; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
        }
        
        /* Contact Buttons */
        .contact-btn {
            display: flex; align-items: center; gap: 15px;
            padding: 18px 20px; border-radius: var(--radius);
            text-decoration: none; color: white;
            margin-bottom: 12px; transition: transform 0.2s;
        }
        .contact-btn:active { transform: scale(0.98); }
        .contact-btn i { font-size: 24px; width: 30px; }
        .contact-btn .text { flex: 1; }
        .contact-btn .title { font-weight: 600; }
        .contact-btn .subtitle { font-size: 13px; opacity: 0.9; }
        .contact-btn.phone { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
        .contact-btn.telegram { background: linear-gradient(135deg, #0088cc 0%, #00a8e8 100%); }
        .contact-btn.maps { background: linear-gradient(135deg, #f12711 0%, #f5af19 100%); }
        
        /* Bottom Navigation */
        .bottom-nav {
            position: fixed; bottom: 0; left: 0; right: 0;
            background: var(--tg-theme-bg-color);
            display: flex; justify-content: space-around;
            padding: 12px 0 25px; border-top: 1px solid rgba(0,0,0,0.1);
            z-index: 1000;
        }
        .nav-item {
            display: flex; flex-direction: column; align-items: center;
            gap: 5px; text-decoration: none;
            color: var(--tg-theme-hint-color);
            font-size: 11px; padding: 5px 15px;
            transition: color 0.2s;
        }
        .nav-item i { font-size: 24px; }
        .nav-item.active { color: var(--tg-theme-button-color); }
        
        /* Modal */
        .modal {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.6); display: none;
            align-items: center; justify-content: center;
            z-index: 2000; padding: 20px;
        }
        .modal.show { display: flex; }
        .modal-content {
            background: var(--tg-theme-bg-color);
            padding: 35px; border-radius: var(--radius);
            text-align: center; max-width: 320px; width: 100%;
        }
        .modal-icon { font-size: 70px; margin-bottom: 20px; }
        .modal-content h2 { margin-bottom: 10px; }
        .modal-content p { color: var(--tg-theme-hint-color); margin-bottom: 25px; }
        
        /* Toast */
        .toast {
            position: fixed; bottom: 100px; left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.85); color: white;
            padding: 14px 28px; border-radius: 30px;
            font-size: 14px; z-index: 3000;
            animation: fadeInUp 0.3s ease;
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translate(-50%, 20px); }
            to { opacity: 1; transform: translate(-50%, 0); }
        }
        
        /* Loading */
        .loading { text-align: center; padding: 40px; color: var(--tg-theme-hint-color); }
        .loading i { font-size: 30px; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        /* No Data */
        .no-data { text-align: center; padding: 30px; color: var(--tg-theme-hint-color); }
        
        /* Page Header */
        .page-header { margin-bottom: 25px; }
        .page-header h1 { font-size: 28px; }
        
        /* Profile */
        .profile-header { text-align: center; padding: 20px 0 30px; }
        .profile-avatar {
            width: 90px; height: 90px;
            background: var(--primary-gradient);
            border-radius: 50%; margin: 0 auto 15px;
            display: flex; align-items: center; justify-content: center;
            color: white; font-size: 40px;
        }
        .profile-name { font-size: 24px; font-weight: 700; }
        .profile-phone { color: var(--tg-theme-hint-color); margin-top: 5px; }
        
        /* Stats */
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }
        .stat-item { text-align: center; padding: 15px; }
        .stat-value { font-size: 32px; font-weight: 700; color: var(--tg-theme-button-color); }
        .stat-label { font-size: 12px; color: var(--tg-theme-hint-color); margin-top: 5px; }
        
        /* Working Hours */
        .hours-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
        .hours-row:last-child { border-bottom: none; }
        
        /* Share Button */
        .share-btn {
            width: 100%; background: var(--primary-gradient);
            color: white; border: none; padding: 16px;
            border-radius: var(--radius-sm); font-size: 15px;
            font-weight: 600; cursor: pointer; margin-top: 15px;
            display: flex; align-items: center; justify-content: center; gap: 10px;
        }
    </style>
</head>
<body>
    {{ content | safe }}
    
    <nav class="bottom-nav">
        <a href="/" class="nav-item {{ 'active' if page == 'home' else '' }}">
            <i class="fas fa-home"></i><span>Главная</span>
        </a>
        <a href="/menu" class="nav-item {{ 'active' if page == 'menu' else '' }}">
            <i class="fas fa-utensils"></i><span>Меню</span>
        </a>
        <a href="/booking" class="nav-item {{ 'active' if page == 'booking' else '' }}">
            <i class="fas fa-calendar-alt"></i><span>Бронь</span>
        </a>
        <a href="/profile" class="nav-item {{ 'active' if page == 'profile' else '' }}">
            <i class="fas fa-user"></i><span>Профиль</span>
        </a>
        <a href="/contacts" class="nav-item {{ 'active' if page == 'contacts' else '' }}">
            <i class="fas fa-phone"></i><span>Контакты</span>
        </a>
    </nav>
    
    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        tg.ready();
        
        // Apply theme
        document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#ffffff');
        document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#000000');
        document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color || '#999999');
        document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#2481cc');
        document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f1f1f1');
        
        // Back button
        if (window.location.pathname !== '/') {
            tg.BackButton.show();
            tg.BackButton.onClick(() => window.history.back());
        }
        
        function getUser() {
            return tg.initDataUnsafe?.user || null;
        }
        
        function getUserId() {
            return getUser()?.id || null;
        }
        
        function showToast(msg) {
            const existing = document.querySelector('.toast');
            if (existing) existing.remove();
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.textContent = msg;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 2500);
        }
        
        function haptic(type = 'light') {
            if (tg.HapticFeedback) {
                if (['success','error','warning'].includes(type)) {
                    tg.HapticFeedback.notificationOccurred(type);
                } else {
                    tg.HapticFeedback.impactOccurred(type);
                }
            }
        }
        
        // Click feedback
        document.addEventListener('click', (e) => {
            if (e.target.closest('button, .action-card, .nav-item, .contact-btn')) {
                haptic('light');
            }
        });
    </script>
    {{ extra_js | safe }}
</body>
</html>
'''

HOME_CONTENT = '''
<div class="container">
    <header class="header">
        <h1>🍽️ Во все тяжкие</h1>
        <p>Добро пожаловать!</p>
    </header>
    
    <div class="balance-card" id="balance-card">
        <div class="balance-icon">💰</div>
        <div class="balance-info">
            <div class="balance-label">Ваш баланс</div>
            <div><span class="balance-value" id="balance">0</span> <span class="balance-currency">баллов</span></div>
        </div>
    </div>
    
    <div class="actions-grid">
        <a href="/booking" class="action-card">
            <div class="action-icon">📅</div>
            <div class="action-title">Забронировать столик</div>
        </a>
        <a href="/menu" class="action-card">
            <div class="action-icon">🍴</div>
            <div class="action-title">Посмотреть меню</div>
        </a>
        <a href="/profile" class="action-card">
            <div class="action-icon">🎁</div>
            <div class="action-title">Мои бонусы</div>
        </a>
        <a href="/contacts" class="action-card">
            <div class="action-icon">📞</div>
            <div class="action-title">Контакты</div>
        </a>
    </div>
    
    <div class="section">
        <div class="section-title">📋 Ваши бронирования</div>
        <div id="bookings-container">
            <div class="loading"><i class="fas fa-spinner"></i><br>Загрузка...</div>
        </div>
    </div>
    
    <div class="referral-card">
        <h3>🎁 Приглашайте друзей!</h3>
        <p>Получайте 100 бонусов за каждого приглашенного друга</p>
        <div class="referral-code-box">
            <span class="referral-code" id="referral-code">---</span>
            <button class="copy-btn" onclick="copyCode()"><i class="fas fa-copy"></i></button>
        </div>
    </div>
</div>
'''

HOME_JS = '''
<script>
document.addEventListener('DOMContentLoaded', async () => {
    const userId = getUserId();
    if (!userId) return;
    
    try {
        const res = await fetch('/api/user/' + userId);
        const data = await res.json();
        if (data.success) {
            document.getElementById('balance').textContent = data.user.bonus_balance || 0;
            document.getElementById('referral-code').textContent = data.user.referral_code || '---';
        }
    } catch(e) { console.error(e); }
    
    try {
        const res = await fetch('/api/bookings/' + userId);
        const data = await res.json();
        const container = document.getElementById('bookings-container');
        
        if (data.success && data.bookings.length > 0) {
            container.innerHTML = data.bookings.slice(0, 3).map(b => `
                <div class="booking-card ${b.status}">
                    <div class="booking-header">
                        <div class="booking-date"><i class="fas fa-calendar"></i> ${b.date} в ${b.time}</div>
                        <div class="booking-status ${b.status}">${getStatus(b.status)}</div>
                    </div>
                    <div class="booking-guests"><i class="fas fa-users"></i> ${b.guests} гостей</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="no-data">У вас пока нет бронирований</div>';
        }
    } catch(e) {
        document.getElementById('bookings-container').innerHTML = '<div class="no-data">Ошибка загрузки</div>';
    }
});

function getStatus(s) {
    return {pending: '⏳ Ожидает', confirmed: '✅ Подтверждено', cancelled: '❌ Отменено'}[s] || s;
}

function copyCode() {
    const code = document.getElementById('referral-code').textContent;
    if (code && code !== '---') {
        navigator.clipboard.writeText(code);
        showToast('Код скопирован!');
        haptic('success');
    }
}
</script>
'''

MENU_CONTENT = '''
<div class="container">
    <div class="page-header"><h1>🍴 Меню</h1></div>
    <div class="category-tabs" id="tabs"><div class="loading"><i class="fas fa-spinner"></i></div></div>
    <div id="menu-items"><div class="loading"><i class="fas fa-spinner"></i></div></div>
</div>
'''

MENU_JS = '''
<script>
let menuData = [];
let activeCategory = null;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('/api/menu');
        const data = await res.json();
        if (data.success) {
            menuData = data.menu;
            renderTabs();
            if (menuData.length > 0) selectCategory(menuData[0].id);
        }
    } catch(e) {
        document.getElementById('menu-items').innerHTML = '<div class="no-data">Ошибка загрузки меню</div>';
    }
});

function renderTabs() {
    document.getElementById('tabs').innerHTML = menuData.map(c => 
        `<button class="category-tab" data-id="${c.id}" onclick="selectCategory(${c.id})">${c.name}</button>`
    ).join('');
}

function selectCategory(id) {
    activeCategory = id;
    document.querySelectorAll('.category-tab').forEach(t => 
        t.classList.toggle('active', parseInt(t.dataset.id) === id)
    );
    const cat = menuData.find(c => c.id === id);
    const container = document.getElementById('menu-items');
    if (cat && cat.items.length) {
        container.innerHTML = cat.items.map(i => `
            <div class="menu-item">
                <div>
                    <div class="item-name">${i.name}</div>
                    <div class="item-desc">${i.description || ''}</div>
                </div>
                <div class="item-price">${i.price} ₽</div>
            </div>
        `).join('');
    } else {
        container.innerHTML = '<div class="no-data">В этой категории пока нет блюд</div>';
    }
}
</script>
'''

BOOKING_CONTENT = '''
<div class="container">
    <div class="page-header"><h1>📅 Бронирование</h1></div>
    
    <form id="booking-form">
        <div class="form-group">
            <label>Дата</label>
            <input type="date" id="date" required>
        </div>
        <div class="form-group">
            <label>Время</label>
            <select id="time" required>
                <option value="">Выберите время</option>
                <option value="12:00">12:00</option>
                <option value="13:00">13:00</option>
                <option value="14:00">14:00</option>
                <option value="15:00">15:00</option>
                <option value="16:00">16:00</option>
                <option value="17:00">17:00</option>
                <option value="18:00">18:00</option>
                <option value="19:00">19:00</option>
                <option value="20:00">20:00</option>
                <option value="21:00">21:00</option>
                <option value="22:00">22:00</option>
            </select>
        </div>
        <div class="form-group">
            <label>Количество гостей</label>
            <div class="guests-selector">
                <button type="button" class="guests-btn" onclick="changeGuests(-1)">−</button>
                <div class="guests-value" id="guests">2</div>
                <button type="button" class="guests-btn" onclick="changeGuests(1)">+</button>
            </div>
        </div>
        <div class="form-group">
            <label>Комментарий</label>
            <textarea id="comment" placeholder="Особые пожелания..."></textarea>
        </div>
        <button type="submit" class="submit-btn" id="submit-btn">
            <i class="fas fa-check"></i> Забронировать
        </button>
    </form>
</div>

<div class="modal" id="modal">
    <div class="modal-content">
        <div class="modal-icon">✅</div>
        <h2>Бронирование создано!</h2>
        <p>Ожидайте подтверждения от администратора</p>
        <button class="submit-btn" onclick="closeModal()">OK</button>
    </div>
</div>
'''

BOOKING_JS = '''
<script>
let guestsCount = 2;

document.addEventListener('DOMContentLoaded', () => {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('date').min = today;
    document.getElementById('date').value = today;
});

function changeGuests(d) {
    guestsCount = Math.max(1, Math.min(20, guestsCount + d));
    document.getElementById('guests').textContent = guestsCount;
    haptic('light');
}

document.getElementById('booking-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const userId = getUserId();
    if (!userId) { showToast('Ошибка авторизации'); return; }
    
    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
    
    try {
        const res = await fetch('/api/booking', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: userId,
                date: document.getElementById('date').value,
                time: document.getElementById('time').value,
                guests: guestsCount,
                comment: document.getElementById('comment').value
            })
        });
        const data = await res.json();
        if (data.success) {
            haptic('success');
            document.getElementById('modal').classList.add('show');
            tg.sendData(JSON.stringify({action: 'booking_created', id: data.booking_id}));
        } else {
            showToast('Ошибка: ' + data.error);
            haptic('error');
        }
    } catch(e) {
        showToast('Ошибка отправки');
        haptic('error');
    }
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-check"></i> Забронировать';
});

function closeModal() {
    document.getElementById('modal').classList.remove('show');
    document.getElementById('booking-form').reset();
    guestsCount = 2;
    document.getElementById('guests').textContent = 2;
}
</script>
'''

PROFILE_CONTENT = '''
<div class="container">
    <div class="profile-header">
        <div class="profile-avatar"><i class="fas fa-user"></i></div>
        <div class="profile-name" id="name">Загрузка...</div>
        <div class="profile-phone" id="phone"></div>
    </div>
    
    <div class="balance-card" style="justify-content: center; flex-direction: column; text-align: center;">
        <div class="balance-label">💰 Бонусный баланс</div>
        <div style="margin: 10px 0;"><span class="balance-value" id="balance" style="font-size: 48px;">0</span></div>
        <div class="balance-currency">баллов</div>
    </div>
    
    <div class="section-card">
        <div class="section-title">📊 Статистика</div>
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-value" id="total-bookings">0</div>
                <div class="stat-label">Бронирований</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="referrals">0</div>
                <div class="stat-label">Приглашено</div>
            </div>
        </div>
    </div>
    
    <div class="referral-card">
        <h3>🎁 Реферальная программа</h3>
        <p>Приглашайте друзей и получайте 100 бонусов!</p>
        <div class="referral-code-box">
            <span class="referral-code" id="ref-code">---</span>
            <button class="copy-btn" onclick="copyCode()"><i class="fas fa-copy"></i></button>
        </div>
        <button class="share-btn" onclick="shareRef()"><i class="fas fa-share-alt"></i> Поделиться</button>
    </div>
    
    <div class="section">
        <div class="section-title">📋 Мои бронирования</div>
        <div id="bookings"><div class="loading"><i class="fas fa-spinner"></i></div></div>
    </div>
</div>
'''

PROFILE_JS = '''
<script>
document.addEventListener('DOMContentLoaded', async () => {
    const user = getUser();
    if (user) {
        document.getElementById('name').textContent = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Пользователь';
    }
    
    const userId = getUserId();
    if (!userId) return;
    
    try {
        const res = await fetch('/api/user/' + userId);
        const data = await res.json();
        if (data.success) {
            document.getElementById('balance').textContent = data.user.bonus_balance || 0;
            document.getElementById('phone').textContent = data.user.phone || '';
            document.getElementById('ref-code').textContent = data.user.referral_code || '---';
            document.getElementById('total-bookings').textContent = data.user.total_bookings || 0;
        }
    } catch(e) {}
    
    try {
        const res = await fetch('/api/bookings/' + userId);
        const data = await res.json();
        const container = document.getElementById('bookings');
        if (data.success && data.bookings.length) {
            container.innerHTML = data.bookings.map(b => `
                <div class="booking-card ${b.status}">
                    <div class="booking-header">
                        <div class="booking-date"><i class="fas fa-calendar"></i> ${b.date} в ${b.time}</div>
                        <div class="booking-status ${b.status}">${getStatus(b.status)}</div>
                    </div>
                    <div class="booking-guests"><i class="fas fa-users"></i> ${b.guests} гостей</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="no-data">Нет бронирований</div>';
        }
    } catch(e) {}
});

function getStatus(s) {
    return {pending: '⏳ Ожидает', confirmed: '✅ Подтверждено', cancelled: '❌ Отменено'}[s] || s;
}

function copyCode() {
    const code = document.getElementById('ref-code').textContent;
    if (code && code !== '---') {
        navigator.clipboard.writeText(code);
        showToast('Код скопирован!');
        haptic('success');
    }
}

function shareRef() {
    const code = document.getElementById('ref-code').textContent;
    if (code && code !== '---') {
        const text = `Приглашаю в ресторан "Во все тяжкие"! Мой код: ${code} 🎁`;
        tg.openTelegramLink('https://t.me/share/url?text=' + encodeURIComponent(text));
    }
}
</script>
'''

CONTACTS_CONTENT = '''
<div class="container">
    <div class="page-header"><h1>📞 Контакты</h1></div>
    
    <div class="section-card" style="text-align: center; margin-bottom: 25px;">
        <div style="font-size: 60px; margin-bottom: 15px;">🍽️</div>
        <h2>Во все тяжкие</h2>
        <p style="color: var(--tg-theme-hint-color);">Ресторан с душой</p>
    </div>
    
    <a href="tel:+79991234567" class="contact-btn phone">
        <i class="fas fa-phone"></i>
        <div class="text">
            <div class="title">Позвонить</div>
            <div class="subtitle">+7 (999) 123-45-67</div>
        </div>
    </a>
    
    <a href="https://t.me/your_restaurant" class="contact-btn telegram" target="_blank">
        <i class="fab fa-telegram-plane"></i>
        <div class="text">
            <div class="title">Telegram</div>
            <div class="subtitle">@your_restaurant</div>
        </div>
    </a>
    
    <a href="https://yandex.ru/maps/-/..." class="contact-btn maps" target="_blank">
        <i class="fas fa-map-marker-alt"></i>
        <div class="text">
            <div class="title">Мы на карте</div>
            <div class="subtitle">г. Москва, ул. Примерная, 123</div>
        </div>
    </a>
    
    <div class="section-card">
        <div class="section-title">🕐 Время работы</div>
        <div class="hours-row"><span>Пн - Чт</span><span>12:00 - 23:00</span></div>
        <div class="hours-row"><span>Пт - Сб</span><span>12:00 - 02:00</span></div>
        <div class="hours-row"><span>Воскресенье</span><span>12:00 - 22:00</span></div>
    </div>
</div>
'''

# ============ FLASK ROUTES ============

@flask_app.route('/')
def webapp_home():
    return render_template_string(BASE_HTML, title="Во все тяжкие", page="home", 
                                  content=HOME_CONTENT, extra_js=HOME_JS)

@flask_app.route('/menu')
def webapp_menu():
    return render_template_string(BASE_HTML, title="Меню", page="menu",
                                  content=MENU_CONTENT, extra_js=MENU_JS)

@flask_app.route('/booking')
def webapp_booking():
    return render_template_string(BASE_HTML, title="Бронирование", page="booking",
                                  content=BOOKING_CONTENT, extra_js=BOOKING_JS)

@flask_app.route('/profile')
def webapp_profile():
    return render_template_string(BASE_HTML, title="Профиль", page="profile",
                                  content=PROFILE_CONTENT, extra_js=PROFILE_JS)

@flask_app.route('/contacts')
def webapp_contacts():
    return render_template_string(BASE_HTML, title="Контакты", page="contacts",
                                  content=CONTACTS_CONTENT, extra_js="")

# ============ API ENDPOINTS ============

@flask_app.route('/api/user/<int:user_id>')
def api_get_user(user_id):
    from database import Database
    db = Database()
    user = db.get_user(user_id)
    if user:
        return jsonify({
            'success': True,
            'user': {
                'id': user[0],
                'telegram_id': user[1],
                'first_name': user[2],
                'last_name': user[3],
                'phone': user[4],
                'bonus_balance': user[5],
                'referral_code': user[6],
                'total_bookings': user[8] if len(user) > 8 else 0
            }
        })
    return jsonify({'success': False, 'error': 'User not found'}), 404

@flask_app.route('/api/menu')
def api_get_menu():
    from database import Database
    db = Database()
    try:
        categories = db.get_all_categories()
        menu_data = []
        for cat in categories:
            items = db.get_items_by_category(cat[0])
            menu_data.append({
                'id': cat[0],
                'name': cat[1],
                'items': [{'id': i[0], 'name': i[1], 'price': i[2], 
                          'description': i[3] if len(i) > 3 else ''} for i in items]
            })
        return jsonify({'success': True, 'menu': menu_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@flask_app.route('/api/bookings/<int:user_id>')
def api_get_bookings(user_id):
    from database import Database
    db = Database()
    try:
        bookings = db.get_user_bookings(user_id)
        return jsonify({
            'success': True,
            'bookings': [{'id': b[0], 'date': b[1], 'time': b[2], 'guests': b[3], 
                         'status': b[4], 'comment': b[5] if len(b) > 5 else ''} for b in bookings]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@flask_app.route('/api/booking', methods=['POST'])
def api_create_booking():
    from database import Database
    db = Database()
    try:
        data = request.json
        if not all([data.get('user_id'), data.get('date'), data.get('time'), data.get('guests')]):
            return jsonify({'success': False, 'error': 'Missing fields'}), 400
        booking_id = db.create_booking(
            data['user_id'], data['date'], data['time'], 
            data['guests'], data.get('comment', '')
        )
        return jsonify({'success': True, 'booking_id': booking_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ RUN FLASK IN THREAD ============

def run_flask():
    flask_app.run(host=WEBAPP_HOST, port=WEBAPP_PORT, debug=False, use_reloader=False)

# ============ TELEGRAM BOT CODE ============

async def post_init(application):
    """Функция, выполняемая после инициализации бота"""
    logger.info("🤖 Бот успешно запущен и готов к работе!")
    bot_info = await application.bot.get_me()
    logger.info(f"🔗 Бот: {bot_info.first_name} (@{bot_info.username})")
    logger.info(f"🆔 ID бота: {bot_info.id}")
    logger.info(f"🌐 Mini App URL: {WEBAPP_URL}")


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


def setup_handlers(application):
    """Настройка всех обработчиков"""

    # Импорты обработчиков пользователя
    from handlers.user_handlers import (
        get_registration_handler, get_spend_bonus_handler,
        show_balance, show_referral_info, show_user_bookings,
        handle_user_pending_bookings_button, handle_user_confirmed_bookings_button,
        handle_user_cancelled_bookings_button, handle_user_all_bookings_button,
        handle_user_back_to_bookings_button, handle_user_cancel_booking,
        handle_back_to_bookings_list, back_to_main,
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
    from handlers.admin_handlers import reset_shift_data

    from handlers.order_shift import (
        start_order_management, open_shift, close_shift,
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

    from handlers.order_utils import handle_order_buttons_outside_conversation
    from handlers.order_utils import cancel_order_creation, handle_back_to_order_management

    from handlers.menu_management_handlers import (
        get_menu_management_handlers, manage_menu, start_edit_item
    )

    from database import Database
    db = Database()
    db.add_payment_method_column()

    # ========== START COMMAND WITH MINI APP BUTTON ==========
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start с кнопкой Mini App"""
        user_id = update.effective_user.id
        
        if is_admin(user_id):
            keyboard = [
                [KeyboardButton("👥 Список пользователей"), KeyboardButton("📊 Статистика")],
                [KeyboardButton("📋 Запросы на списание"), KeyboardButton("📅 Бронирования")],
                [KeyboardButton("🍽️ Управление заказами"), KeyboardButton("🍴 Управление меню")],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "👋 Добро пожаловать в панель администратора!",
                reply_markup=reply_markup
            )
        else:
            keyboard = [
                [KeyboardButton("💰 Мой баланс"), KeyboardButton("🎁 Реферальная программа")],
                [KeyboardButton("📋 Мои бронирования"), KeyboardButton("📞 Контакты")],
                [KeyboardButton(
                    "🌐 Открыть приложение",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "👋 Добро пожаловать в ресторан «Во все тяжкие»!\n\n"
                "🌐 Нажмите «Открыть приложение» для удобного доступа ко всем функциям:\n"
                "• Просмотр меню\n"
                "• Бронирование столика\n"
                "• Управление бонусами\n"
                "• И многое другое!",
                reply_markup=reply_markup
            )

    # ========== WEBAPP DATA HANDLER ==========
    async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик данных от Mini App"""
        try:
            data = json.loads(update.effective_message.web_app_data.data)
            action = data.get('action')
            
            if action == 'booking_created':
                booking_id = data.get('id')
                await update.message.reply_text(
                    f"✅ Бронирование #{booking_id} создано через приложение!\n"
                    "Ожидайте подтверждения от администратора."
                )
                
                # Уведомление админам
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"🔔 Новое бронирование #{booking_id} через Mini App!"
                        )
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error handling webapp data: {e}")

    # Добавляем обработчик данных от WebApp
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    # ... (все остальные обработчики из вашего оригинального кода)

    # ДОБАВЛЕНЫ ОБРАБОТЧИКИ УПРАВЛЕНИЯ МЕНЮ
    menu_handlers = get_menu_management_handlers()
    for handler in menu_handlers:
        application.add_handler(handler)

    application.add_handler(get_user_search_handler())
    
    application.add_handler(CallbackQueryHandler(exit_search_mode, pattern="^exit_search_mode$"))
    application.add_handler(CallbackQueryHandler(back_to_search_mode, pattern="^back_to_search_mode$"))
    application.add_handler(CallbackQueryHandler(new_search, pattern="^new_search$"))
    application.add_handler(CallbackQueryHandler(show_full_users_list, pattern="^show_full_users_list_"))

    # ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ
    application.add_handler(MessageHandler(filters.Regex("^💰 Мой баланс$") & user_filter, show_balance))
    application.add_handler(MessageHandler(filters.Regex("^🎁 Реферальная программа$") & user_filter, show_referral_info))
    application.add_handler(MessageHandler(filters.Regex("^📋 Мои бронирования$") & user_filter, show_user_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📞 Контакты$") & user_filter, show_contacts))

    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & user_filter, handle_user_pending_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & user_filter, handle_user_confirmed_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & user_filter, handle_user_cancelled_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & user_filter, handle_user_all_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_user_back_to_bookings_button))

    application.add_handler(MessageHandler(filters.Regex("^📞 Позвонить$") & user_filter, handle_call_contact))
    application.add_handler(MessageHandler(filters.Regex("^💬 Написать в Telegram$") & user_filter, handle_telegram_contact))
    application.add_handler(MessageHandler(filters.Regex("^📍 Мы на картах$") & user_filter, handle_open_maps))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_back_from_contacts))

    application.add_handler(CallbackQueryHandler(handle_user_cancel_booking, pattern="^user_cancel_booking_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_bookings_list, pattern="^back_to_bookings_list$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_contacts_callback, pattern="^back_to_contacts$"))

    application.add_handler(get_registration_handler())
    application.add_handler(get_spend_bonus_handler())
    application.add_handler(get_booking_handler())

    # ОБРАБОТЧИКИ АДМИНИСТРАТОРА
    application.add_handler(MessageHandler(filters.Regex("^👥 Список пользователей$") & admin_filter, show_users_list))
    application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$") & admin_filter, show_statistics))
    application.add_handler(MessageHandler(filters.Regex("^📋 Запросы на списание$") & admin_filter, handle_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^🔄 Обновить список запросов$") & admin_filter, refresh_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^📅 Бронирования$") & admin_filter, show_bookings))
    application.add_handler(MessageHandler(filters.Regex("^🍽️ Управление заказами$") & admin_filter, start_order_management))
    application.add_handler(MessageHandler(filters.Regex("^🍴 Управление меню$") & admin_filter, manage_menu))

    application.add_handler(CallbackQueryHandler(handle_users_pagination, pattern="^(users_page_|refresh_users)"))

    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & admin_filter, show_pending_bookings))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & admin_filter, show_confirmed_bookings))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & admin_filter, show_cancelled_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & admin_filter, show_all_bookings))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & admin_filter, back_to_main_menu))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ В главное меню$") & admin_filter, back_to_main_menu))

    application.add_handler(get_broadcast_handler())
    application.add_handler(get_user_message_handler())
    application.add_handler(get_bonus_handler())
    application.add_handler(get_booking_date_handler())
    application.add_handler(get_booking_cancellation_handler())

    # Обработчики заказов
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

    # История заказов
    application.add_handler(CallbackQueryHandler(show_order_history_menu, pattern="^order_history$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_order_management$"))
    application.add_handler(CallbackQueryHandler(show_shift_history, pattern="^history_shift$"))
    application.add_handler(CallbackQueryHandler(show_year_history, pattern="^history_year$"))
    application.add_handler(CallbackQueryHandler(select_year_for_history, pattern="^history_year_"))
    application.add_handler(CallbackQueryHandler(select_month_for_history, pattern="^history_month_"))
    application.add_handler(CallbackQueryHandler(show_select_shift_menu, pattern="^history_select_shift$"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_"))
    application.add_handler(CallbackQueryHandler(show_full_year_history, pattern="^history_full_year_"))
    application.add_handler(CallbackQueryHandler(show_full_month_history, pattern="^history_full_month_"))
    application.add_handler(CallbackQueryHandler(show_more_shifts, pattern="^history_month_more_"))

    # Управление сменой
    application.add_handler(CallbackQueryHandler(open_shift, pattern="^open_shift$"))
    application.add_handler(CallbackQueryHandler(close_shift, pattern="^close_shift$"))
    application.add_handler(CallbackQueryHandler(calculate_all_orders, pattern="^calculate_all_orders$"))
    application.add_handler(CallbackQueryHandler(show_shift_status, pattern="^shift_status$"))

    # Callback обработчики
    application.add_handler(CallbackQueryHandler(user_selected_callback, pattern="^select_user_"))
    application.add_handler(CallbackQueryHandler(user_info_callback, pattern="^info_"))
    application.add_handler(CallbackQueryHandler(handle_booking_action, pattern="^(confirm_booking_|cancel_booking_)"))
    application.add_handler(CallbackQueryHandler(handle_bonus_request_action, pattern="^(approve_|reject_)"))
    application.add_handler(CallbackQueryHandler(message_user_callback, pattern="^message_"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_.*_.*"))
    application.add_handler(CallbackQueryHandler(back_to_users_list, pattern="^back_to_users_list$"))

    application.add_handler(MessageHandler(filters.Regex("^✏️ Редактировать позицию$") & admin_filter, start_edit_item))

    # КОМАНДЫ
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset_shift", reset_shift_data))

    # Обработчик кнопки "Назад"
    async def handle_back_button(update: Update, context):
        user_id = update.effective_user.id
        if is_admin(user_id):
            await back_to_main_menu(update, context)
        else:
            await back_to_main(update, context)

    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$"), handle_back_button))

    # Умный обработчик ввода номера стола
    async def smart_table_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            return False
        if context.user_data.get('search_users_mode', False):
            return False
        if not context.user_data.get('expecting_table_number', False):
            return False
        if not update.message.text.isdigit():
            await update.message.reply_text("❌ Номер стола должен быть числом. Попробуйте снова:")
            return True
        await handle_table_number(update, context)
        context.user_data.pop('expecting_table_number', None)
        return True

    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & admin_filter,
        smart_table_number_handler
    ))

    # Обработчик неизвестных сообщений
    async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Неизвестная команда. Используйте кнопки меню.")
        else:
            await update.message.reply_text("❌ Неизвестная команда. Используйте кнопки меню.")

    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, unknown_message))


def main():
    """Основная функция запуска бота и Mini App"""
    try:
        if not BOT_TOKEN:
            logger.error("❌ Токен бота не найден!")
            return

        # Запускаем Flask в отдельном потоке
        logger.info(f"🌐 Запуск Mini App на {WEBAPP_HOST}:{WEBAPP_PORT}")
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info(f"✅ Mini App запущен: {WEBAPP_URL}")

        # Создаем приложение бота
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).post_stop(post_stop).build()

        # Настройка обработчиков
        logger.info("🔄 Настройка обработчиков...")
        setup_handlers(application)

        # Запуск бота
        logger.info("🚀 Запуск бота...")
        print("=" * 50)
        print("🤖 Бот запущен!")
        print(f"🌐 Mini App: {WEBAPP_URL}")
        print("Для остановки нажмите Ctrl+C")
        print("=" * 50)

        application.run_polling(
            allowed_updates=['message', 'callback_query'],
            timeout=60,
            drop_pending_updates=True
        )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    main()
