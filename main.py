import logging
import os
import warnings
import json
import base64
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.warnings import PTBUserWarning
from dotenv import load_dotenv
from config import BOT_TOKEN, ADMIN_IDS
from error_logger import setup_error_logging

# Игнорировать предупреждения PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

# Загрузка переменных окружения
load_dotenv()

logger = logging.getLogger(__name__)


async def post_init(application):
    """Функция, выполняемая после инициализации бота"""
    logger.info("🤖 Бот успешно запущен и готов к работе!")

    # Получаем информацию о бота
    bot_info = await application.bot.get_me()
    logger.info(f"🔗 Бот: {bot_info.first_name} (@{bot_info.username})")
    logger.info(f"🆔 ID бота: {bot_info.id}")


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


# HTML MiniApp полностью встроенный
MINIAPP_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hookah Lounge MiniApp</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 100%;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .logo {
            font-size: 60px;
            margin-bottom: 10px;
            text-shadow: 0 0 20px rgba(0, 247, 255, 0.5);
        }
        
        .title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
            background: linear-gradient(90deg, #00dbde 0%, #fc00ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .subtitle {
            font-size: 14px;
            opacity: 0.8;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.15);
            border-color: #00dbde;
        }
        
        .stat-value {
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 5px;
            text-shadow: 0 0 10px rgba(0, 247, 255, 0.5);
        }
        
        .stat-label {
            font-size: 12px;
            opacity: 0.8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .menu-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .menu-item {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .menu-item:hover {
            transform: translateY(-3px);
            border-color: #00dbde;
            box-shadow: 0 10px 20px rgba(0, 219, 222, 0.2);
        }
        
        .menu-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
            transition: 0.5s;
        }
        
        .menu-item:hover::before {
            left: 100%;
        }
        
        .menu-name {
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #fff;
        }
        
        .menu-price {
            font-size: 20px;
            font-weight: bold;
            color: #00dbde;
        }
        
        .menu-category {
            font-size: 12px;
            opacity: 0.6;
            margin-top: 5px;
        }
        
        .actions-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .action-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 15px;
            padding: 20px;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 10px;
            text-align: center;
        }
        
        .action-btn:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }
        
        .action-btn.secondary {
            background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
        }
        
        .action-btn.danger {
            background: linear-gradient(135deg, #f44336 0%, #c62828 100%);
        }
        
        .action-btn .icon {
            font-size: 30px;
        }
        
        .cart-section {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .cart-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .cart-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .cart-item:last-child {
            border-bottom: none;
        }
        
        .cart-item-name {
            flex: 1;
            font-size: 16px;
        }
        
        .cart-item-quantity {
            background: rgba(255, 255, 255, 0.1);
            padding: 5px 15px;
            border-radius: 20px;
            margin: 0 10px;
        }
        
        .cart-item-price {
            font-weight: bold;
            color: #00dbde;
            min-width: 80px;
            text-align: right;
        }
        
        .cart-total {
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 2px solid rgba(255, 255, 255, 0.2);
        }
        
        .total-amount {
            color: #00dbde;
            text-shadow: 0 0 10px rgba(0, 219, 222, 0.5);
        }
        
        .notification {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%);
            color: white;
            padding: 15px 25px;
            border-radius: 10px;
            z-index: 1000;
            animation: slideDown 0.3s ease;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            max-width: 90%;
            text-align: center;
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translate(-50%, -20px);
            }
            to {
                opacity: 1;
                transform: translate(-50%, 0);
            }
        }
        
        .loader {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 1001;
        }
        
        .spinner {
            width: 60px;
            height: 60px;
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            border-top-color: #00dbde;
            animation: spin 1s linear infinite;
            margin-bottom: 20px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .loader-text {
            font-size: 16px;
            opacity: 0.8;
        }
        
        .tab-navigation {
            display: flex;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 5px;
            margin-bottom: 20px;
        }
        
        .tab-btn {
            flex: 1;
            padding: 15px;
            text-align: center;
            background: transparent;
            border: none;
            color: rgba(255, 255, 255, 0.6);
            font-weight: bold;
            cursor: pointer;
            border-radius: 10px;
            transition: all 0.3s ease;
        }
        
        .tab-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        
        .tab-content {
            display: none;
            animation: fadeIn 0.3s ease;
        }
        
        .tab-content.active {
            display: block;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .category-filter {
            display: flex;
            overflow-x: auto;
            gap: 10px;
            margin-bottom: 20px;
            padding-bottom: 10px;
        }
        
        .category-btn {
            white-space: nowrap;
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .category-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-color: transparent;
        }
        
        .quantity-control {
            display: flex;
            align-items: center;
            gap: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 5px 15px;
        }
        
        .quantity-btn {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: white;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .quantity-value {
            font-weight: bold;
            min-width: 30px;
            text-align: center;
        }
        
        .order-btn {
            background: linear-gradient(135deg, #00dbde 0%, #fc00ff 100%);
            border: none;
            border-radius: 15px;
            padding: 20px;
            color: white;
            font-size: 18px;
            font-weight: bold;
            width: 100%;
            cursor: pointer;
            margin-top: 20px;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .order-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0, 219, 222, 0.4);
        }
        
        .order-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            opacity: 0.5;
        }
        
        .empty-state .icon {
            font-size: 60px;
            margin-bottom: 20px;
            opacity: 0.3;
        }
        
        .empty-state p {
            font-size: 16px;
        }
        
        .history-item {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .history-date {
            font-size: 12px;
            opacity: 0.6;
            margin-bottom: 5px;
        }
        
        .history-amount {
            font-size: 20px;
            font-weight: bold;
            color: #00dbde;
        }
        
        .history-items {
            font-size: 14px;
            opacity: 0.8;
            margin-top: 5px;
        }
        
        /* Адаптивность */
        @media (max-width: 480px) {
            .stats-grid,
            .menu-grid,
            .actions-grid {
                grid-template-columns: 1fr;
            }
            
            .menu-name {
                font-size: 14px;
            }
            
            .menu-price {
                font-size: 18px;
            }
        }
    </style>
</head>
<body>
    <div class="loader" id="loader">
        <div class="spinner"></div>
        <div class="loader-text">Загрузка Hookah Lounge...</div>
    </div>
    
    <div class="container" id="app" style="display: none;">
        <!-- Заголовок -->
        <div class="header">
            <div class="logo">🍹</div>
            <div class="title">HOOKAH LOUNGE</div>
            <div class="subtitle">Ваш премиум кальян-бар</div>
        </div>
        
        <!-- Навигация по табам -->
        <div class="tab-navigation">
            <button class="tab-btn active" data-tab="main">🏠 Главная</button>
            <button class="tab-btn" data-tab="menu">📋 Меню</button>
            <button class="tab-btn" data-tab="cart">🛒 Корзина</button>
            <button class="tab-btn" data-tab="history">📊 История</button>
        </div>
        
        <!-- Основной контент -->
        <div class="tab-content active" id="tab-main">
            <!-- Статистика -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="stat-balance">0</div>
                    <div class="stat-label">Баллов</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-bookings">0</div>
                    <div class="stat-label">Бронирований</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-orders">0</div>
                    <div class="stat-label">Заказов</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-referrals">0</div>
                    <div class="stat-label">Рефералов</div>
                </div>
            </div>
            
            <!-- Быстрые действия -->
            <div class="actions-grid">
                <button class="action-btn" onclick="showMenuTab()">
                    <span class="icon">📋</span>
                    <span>Меню</span>
                </button>
                <button class="action-btn secondary" onclick="bookTable()">
                    <span class="icon">📅</span>
                    <span>Бронь</span>
                </button>
                <button class="action-btn" onclick="showCartTab()">
                    <span class="icon">🛒</span>
                    <span>Корзина</span>
                </button>
                <button class="action-btn secondary" onclick="showContacts()">
                    <span class="icon">📞</span>
                    <span>Контакты</span>
                </button>
            </div>
            
            <!-- Популярные позиции -->
            <h3 style="margin: 20px 0 15px 0; font-size: 18px;">🔥 Популярное</h3>
            <div class="menu-grid" id="popular-items">
                <!-- Загружается динамически -->
            </div>
        </div>
        
        <!-- Меню -->
        <div class="tab-content" id="tab-menu">
            <div class="category-filter" id="category-filter">
                <!-- Категории загружаются динамически -->
            </div>
            
            <div class="menu-grid" id="menu-items">
                <!-- Меню загружается динамически -->
            </div>
        </div>
        
        <!-- Корзина -->
        <div class="tab-content" id="tab-cart">
            <div class="cart-section">
                <div class="cart-title">
                    <span>🛒 Ваш заказ</span>
                </div>
                
                <div id="cart-items">
                    <div class="empty-state">
                        <div class="icon">🛒</div>
                        <p>Корзина пуста</p>
                    </div>
                </div>
                
                <div class="cart-total">
                    Итого: <span class="total-amount" id="cart-total">0</span> ₽
                </div>
                
                <button class="order-btn" id="order-btn" onclick="sendOrder()" disabled>
                    🚀 Оформить заказ
                </button>
            </div>
        </div>
        
        <!-- История -->
        <div class="tab-content" id="tab-history">
            <div id="history-list">
                <div class="empty-state">
                    <div class="icon">📊</div>
                    <p>История заказов пуста</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Telegram WebApp API
        const tg = window.Telegram.WebApp;
        
        // Инициализация
        tg.expand();
        tg.MainButton.setText("🔄 Обновить");
        tg.MainButton.onClick(refreshData);
        tg.MainButton.show();
        
        // Данные приложения
        let appData = {
            user: {},
            menu: [],
            cart: [],
            orders: [],
            categories: []
        };
        
        // Уведомления
        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = 'notification';
            notification.textContent = message;
            notification.style.background = type === 'error' ? 'linear-gradient(135deg, #f44336 0%, #c62828 100%)' :
                               type === 'success' ? 'linear-gradient(135deg, #00b09b 0%, #96c93d 100%)' :
                               'linear-gradient(135deg, #2196F3 0%, #21CBF3 100%)';
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.style.animation = 'slideDown 0.3s ease reverse';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }
        
        // Работа с табами
        function switchTab(tabName) {
            // Деактивируем все табы
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Активируем выбранный таб
            document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add('active');
            document.getElementById(`tab-${tabName}`).classList.add('active');
        }
        
        // Привязка событий к табам
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                switchTab(btn.dataset.tab);
            });
        });
        
        function showMenuTab() {
            switchTab('menu');
        }
        
        function showCartTab() {
            switchTab('cart');
            updateCartDisplay();
        }
        
        // Обновление данных
        function refreshData() {
            tg.sendData(JSON.stringify({
                type: 'refresh',
                timestamp: Date.now()
            }));
            showNotification('🔄 Обновление данных...');
        }
        
        // Бронирование стола
        function bookTable() {
            const date = new Date();
            const today = date.toLocaleDateString('ru-RU');
            const tomorrow = new Date(date.getTime() + 86400000).toLocaleDateString('ru-RU');
            
            tg.showPopup({
                title: '📅 Бронирование стола',
                message: 'Выберите дату бронирования:',
                buttons: [
                    {id: 'today', type: 'default', text: `Сегодня (${today})`},
                    {id: 'tomorrow', type: 'default', text: `Завтра (${tomorrow})`},
                    {id: 'cancel', type: 'cancel', text: '❌ Отмена'}
                ]
            }, function(btnId) {
                if (btnId === 'today' || btnId === 'tomorrow') {
                    const dateStr = btnId === 'today' ? 'сегодня' : 'завтра';
                    const time = prompt('Введите время (например, 19:00):', '19:00');
                    
                    if (time && time.match(/^\d{1,2}:\d{2}$/)) {
                        tg.sendData(JSON.stringify({
                            type: 'booking',
                            date: dateStr,
                            time: time,
                            user_id: tg.initDataUnsafe.user?.id
                        }));
                        showNotification(`✅ Бронь на ${dateStr} в ${time} отправлена!`, 'success');
                    } else {
                        showNotification('❌ Введите корректное время', 'error');
                    }
                }
            });
        }
        
        // Показать контакты
        function showContacts() {
            tg.sendData(JSON.stringify({
                type: 'contacts',
                user_id: tg.initDataUnsafe.user?.id
            }));
        }
        
        // Работа с меню
        function loadMenu() {
            // Популярные позиции
            const popularContainer = document.getElementById('popular-items');
            if (appData.menu.length > 0) {
                const popular = appData.menu.slice(0, 4);
                popularContainer.innerHTML = popular.map(item => `
                    <div class="menu-item" onclick="addToCart(${item.id})">
                        <div class="menu-name">${item.name}</div>
                        <div class="menu-price">${item.price} ₽</div>
                        <div class="menu-category">${item.category}</div>
                    </div>
                `).join('');
            } else {
                popularContainer.innerHTML = '<div class="empty-state"><p>Меню загружается...</p></div>';
            }
            
            // Категории
            const categoryContainer = document.getElementById('category-filter');
            if (appData.categories.length > 0) {
                categoryContainer.innerHTML = appData.categories.map(cat => `
                    <button class="category-btn" onclick="filterMenu('${cat}')">${cat}</button>
                `).join('');
            }
            
            // Все позиции меню
            const menuContainer = document.getElementById('menu-items');
            if (appData.menu.length > 0) {
                menuContainer.innerHTML = appData.menu.map(item => `
                    <div class="menu-item" onclick="addToCart(${item.id})">
                        <div class="menu-name">${item.name}</div>
                        <div class="menu-price">${item.price} ₽</div>
                        <div class="menu-category">${item.category}</div>
                    </div>
                `).join('');
            }
        }
        
        // Фильтрация меню
        function filterMenu(category) {
            const buttons = document.querySelectorAll('.category-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            const menuContainer = document.getElementById('menu-items');
            const filtered = category === 'all' ? appData.menu : 
                           appData.menu.filter(item => item.category === category);
            
            menuContainer.innerHTML = filtered.map(item => `
                <div class="menu-item" onclick="addToCart(${item.id})">
                    <div class="menu-name">${item.name}</div>
                    <div class="menu-price">${item.price} ₽</div>
                    <div class="menu-category">${item.category}</div>
                </div>
            `).join('');
        }
        
        // Работа с корзиной
        function addToCart(itemId) {
            const item = appData.menu.find(m => m.id === itemId);
            if (!item) return;
            
            const existing = appData.cart.find(c => c.id === itemId);
            if (existing) {
                existing.quantity += 1;
            } else {
                appData.cart.push({
                    ...item,
                    quantity: 1
                });
            }
            
            updateCartDisplay();
            showNotification(`✅ ${item.name} добавлен в корзину`, 'success');
        }
        
        function updateCartDisplay() {
            const container = document.getElementById('cart-items');
            const totalElement = document.getElementById('cart-total');
            const orderBtn = document.getElementById('order-btn');
            
            if (appData.cart.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">🛒</div>
                        <p>Корзина пуста</p>
                    </div>
                `;
                totalElement.textContent = '0';
                orderBtn.disabled = true;
                orderBtn.textContent = '🚀 Оформить заказ';
                return;
            }
            
            let total = 0;
            container.innerHTML = appData.cart.map(item => {
                const itemTotal = item.price * item.quantity;
                total += itemTotal;
                
                return `
                    <div class="cart-item">
                        <div class="cart-item-name">${item.name}</div>
                        <div class="quantity-control">
                            <button class="quantity-btn" onclick="updateQuantity(${item.id}, -1)">-</button>
                            <span class="quantity-value">${item.quantity}</span>
                            <button class="quantity-btn" onclick="updateQuantity(${item.id}, 1)">+</button>
                        </div>
                        <div class="cart-item-price">${itemTotal} ₽</div>
                    </div>
                `;
            }).join('');
            
            totalElement.textContent = total;
            orderBtn.disabled = false;
            orderBtn.textContent = `🚀 Оформить заказ (${total} ₽)`;
        }
        
        function updateQuantity(itemId, delta) {
            const item = appData.cart.find(c => c.id === itemId);
            if (!item) return;
            
            item.quantity += delta;
            if (item.quantity <= 0) {
                appData.cart = appData.cart.filter(c => c.id !== itemId);
            }
            
            updateCartDisplay();
        }
        
        function sendOrder() {
            if (appData.cart.length === 0) return;
            
            tg.showPopup({
                title: 'Подтверждение заказа',
                message: `Вы уверены, что хотите оформить заказ на ${document.getElementById('cart-total').textContent} ₽?`,
                buttons: [
                    {id: 'cancel', type: 'cancel', text: '❌ Отмена'},
                    {id: 'confirm', type: 'default', text: '✅ Подтвердить'}
                ]
            }, function(btnId) {
                if (btnId === 'confirm') {
                    const tableNumber = prompt('Введите номер стола:', '1');
                    if (tableNumber) {
                        tg.sendData(JSON.stringify({
                            type: 'order',
                            cart: appData.cart,
                            table_number: tableNumber,
                            total: document.getElementById('cart-total').textContent,
                            user_id: tg.initDataUnsafe.user?.id
                        }));
                        
                        showNotification('✅ Заказ отправлен! Ожидайте подтверждения.', 'success');
                        appData.cart = [];
                        updateCartDisplay();
                    }
                }
            });
        }
        
        // Загрузка истории заказов
        function loadHistory() {
            const container = document.getElementById('history-list');
            
            if (appData.orders.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📊</div>
                        <p>История заказов пуста</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = appData.orders.map(order => `
                <div class="history-item">
                    <div class="history-date">${order.date}</div>
                    <div class="history-amount">${order.total} ₽</div>
                    <div class="history-items">${order.items}</div>
                </div>
            `).join('');
        }
        
        // Обработка данных от бота
        tg.onEvent('webAppDataReceived', function(event) {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'user_data') {
                    // Обновление данных пользователя
                    appData.user = data;
                    
                    document.getElementById('stat-balance').textContent = data.balance || 0;
                    document.getElementById('stat-bookings').textContent = data.bookings || 0;
                    document.getElementById('stat-orders').textContent = data.orders || 0;
                    document.getElementById('stat-referrals').textContent = data.referrals || 0;
                    
                    // Показываем основное приложение
                    document.getElementById('loader').style.display = 'none';
                    document.getElementById('app').style.display = 'block';
                    
                    showNotification('✅ Данные успешно загружены', 'success');
                }
                else if (data.type === 'menu_data') {
                    // Обновление меню
                    appData.menu = data.menu || [];
                    appData.categories = data.categories || ['Все', ...new Set(appData.menu.map(item => item.category))];
                    
                    loadMenu();
                }
                else if (data.type === 'order_history') {
                    // Обновление истории заказов
                    appData.orders = data.orders || [];
                    loadHistory();
                }
                
            } catch (e) {
                console.error('Error parsing data:', e);
                showNotification('❌ Ошибка загрузки данных', 'error');
            }
        });
        
        // Инициализация при загрузке
        tg.ready();
        
        // Запрашиваем данные при запуске
        tg.sendData(JSON.stringify({
            type: 'init',
            version: '1.0',
            platform: navigator.platform
        }));
        
        // Автоматическое скрытие загрузчика через 5 секунд
        setTimeout(() => {
            if (document.getElementById('loader').style.display !== 'none') {
                document.getElementById('loader').style.display = 'none';
                document.getElementById('app').style.display = 'block';
                showNotification('⚠️ Используются демо-данные', 'info');
                
                // Демо-данные
                appData.user = {
                    balance: 1500,
                    bookings: 3,
                    orders: 12,
                    referrals: 5
                };
                
                appData.menu = [
                    {id: 1, name: 'Пенсионный', price: 800, category: 'Кальяны'},
                    {id: 2, name: 'Стандарт', price: 1000, category: 'Кальяны'},
                    {id: 3, name: 'Премиум', price: 1200, category: 'Кальяны'},
                    {id: 4, name: 'Вода', price: 100, category: 'Напитки'},
                    {id: 5, name: 'Кола 0,5л', price: 100, category: 'Напитки'},
                    {id: 6, name: 'Да Хун Пао', price: 400, category: 'Чай'},
                    {id: 7, name: 'Пробирки', price: 600, category: 'Коктейли'}
                ];
                
                appData.categories = ['Все', 'Кальяны', 'Напитки', 'Чай', 'Коктейли'];
                appData.orders = [
                    {date: 'Сегодня, 19:30', total: '2400', items: 'Премиум ×2'},
                    {date: 'Вчера, 21:15', total: '1800', items: 'Стандарт, Вода ×2'},
                    {date: '15.11.2023, 20:00', total: '3200', items: 'Пенсионный, Премиум, Кола'}
                ];
                
                // Обновляем интерфейс
                document.getElementById('stat-balance').textContent = appData.user.balance;
                document.getElementById('stat-bookings').textContent = appData.user.bookings;
                document.getElementById('stat-orders').textContent = appData.user.orders;
                document.getElementById('stat-referrals').textContent = appData.user.referrals;
                
                loadMenu();
                loadHistory();
            }
        }, 5000);
    </script>
</body>
</html>"""


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик данных из WebApp"""
    try:
        if update.message and update.message.web_app_data:
            data = json.loads(update.message.web_app_data.data)
            user_id = update.effective_user.id
            
            logger.info(f"WebApp данные от {user_id}: {data.get('type')}")
            
            if data.get('type') == 'init':
                # Отправляем данные пользователя
                from database import Database
                db = Database()
                
                # Получаем данные пользователя
                cursor = db.conn.cursor()
                cursor.execute('SELECT balance FROM users WHERE id = ?', (user_id,))
                user = cursor.fetchone()
                
                balance = user[0] if user else 0
                
                # Считаем бронирования
                cursor.execute('SELECT COUNT(*) FROM bookings WHERE user_id = ?', (user_id,))
                bookings_count = cursor.fetchone()[0]
                
                # Считаем заказы
                cursor.execute('SELECT COUNT(*) FROM orders WHERE admin_id = ?', (user_id,))
                orders_count = cursor.fetchone()[0] if is_admin(user_id) else 0
                
                # Считаем рефералов
                cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = ?', (user_id,))
                referrals_count = cursor.fetchone()[0]
                
                # Получаем меню
                cursor.execute('SELECT id, name, price, category FROM menu_items WHERE is_active = 1')
                menu_items = cursor.fetchall()
                menu = [{'id': item[0], 'name': item[1], 'price': item[2], 'category': item[3]} 
                       for item in menu_items]
                
                # Получаем категории
                categories = list(set([item[3] for item in menu_items]))
                
                # Получаем историю заказов
                if is_admin(user_id):
                    cursor.execute('''
                        SELECT o.created_at, SUM(oi.price * oi.quantity), 
                               GROUP_CONCAT(oi.item_name || '×' || oi.quantity)
                        FROM orders o
                        JOIN order_items oi ON o.id = oi.order_id
                        WHERE o.admin_id = ? AND o.status = 'closed'
                        GROUP BY o.id
                        ORDER BY o.created_at DESC
                        LIMIT 10
                    ''', (user_id,))
                else:
                    cursor.execute('''
                        SELECT o.created_at, SUM(oi.price * oi.quantity),
                               GROUP_CONCAT(oi.item_name || '×' || oi.quantity)
                        FROM orders o
                        JOIN order_items oi ON o.id = oi.order_id
                        WHERE o.table_number = ? AND o.status = 'closed'
                        GROUP BY o.id
                        ORDER BY o.created_at DESC
                        LIMIT 10
                    ''', (user_id % 100,))  # Демо-номер стола
                
                orders_data = cursor.fetchall()
                orders = []
                for order in orders_data:
                    orders.append({
                        'date': order[0][:16].replace('T', ' '),
                        'total': order[1] or 0,
                        'items': order[2] or ''
                    })
                
                # Отправляем данные обратно
                response_data = {
                    'type': 'user_data',
                    'balance': balance,
                    'bookings': bookings_count,
                    'orders': orders_count,
                    'referrals': referrals_count
                }
                
                await context.bot.answer_web_app_query(
                    update.message.web_app_data.query_id,
                    json.dumps(response_data)
                )
                
                # Отправляем меню
                menu_data = {
                    'type': 'menu_data',
                    'menu': menu,
                    'categories': categories
                }
                
                await context.bot.send_message(
                    user_id,
                    f"🎮 *Hookah Lounge MiniApp*\n\n"
                    f"✅ Данные успешно загружены!\n"
                    f"💰 Ваш баланс: *{balance}* баллов\n"
                    f"📅 Бронирований: *{bookings_count}*\n"
                    f"🍽️ Заказов: *{orders_count}*\n"
                    f"🎁 Рефералов: *{referrals_count}*\n\n"
                    f"Доступно позиций в меню: *{len(menu)}*",
                    parse_mode='Markdown'
                )
                
                # Отправляем историю
                history_data = {
                    'type': 'order_history',
                    'orders': orders
                }
                
                # Ждем немного и отправляем остальные данные
                import asyncio
                await asyncio.sleep(0.5)
                
                try:
                    await context.bot.send_message(
                        user_id,
                        json.dumps(menu_data),
                        disable_notification=True
                    )
                except:
                    pass
                    
            elif data.get('type') == 'order':
                # Обработка заказа
                cart = data.get('cart', [])
                table_number = data.get('table_number', '1')
                
                if cart and is_admin(user_id):
                    from menu_manager import menu_manager
                    
                    order_id = menu_manager.create_order(table_number, user_id)
                    
                    for item in cart:
                        menu_manager.add_item_to_order(
                            order_id,
                            item['name'],
                            item['quantity']
                        )
                    
                    total = sum(item['price'] * item['quantity'] for item in cart)
                    
                    await update.message.reply_text(
                        f"✅ *Заказ #{order_id} создан!*\n\n"
                        f"📊 Номер стола: *{table_number}*\n"
                        f"💰 Сумма: *{total}₽*\n"
                        f"🛒 Позиций: *{len(cart)}*\n\n"
                        f"Для оплаты перейдите в раздел '🍽️ Управление заказами'",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "❌ *Только администраторы могут создавать заказы*\n\n"
                        "Обратитесь к администратору для создания заказа.",
                        parse_mode='Markdown'
                    )
                    
            elif data.get('type') == 'booking':
                # Обработка бронирования
                date = data.get('date', 'сегодня')
                time = data.get('time', '19:00')
                
                await update.message.reply_text(
                    f"📅 *Заявка на бронирование принята!*\n\n"
                    f"📅 Дата: *{date}*\n"
                    f"⏰ Время: *{time}*\n\n"
                    f"Администратор свяжется с вами для подтверждения.",
                    parse_mode='Markdown'
                )
                
            elif data.get('type') == 'contacts':
                # Отправляем контакты
                await update.message.reply_text(
                    "📞 *Контакты Hookah Lounge*\n\n"
                    "*Телефон:* +7 (XXX) XXX-XX-XX\n"
                    "*Telegram:* @hookahlounge\n"
                    "*Адрес:* Ваш адрес\n\n"
                    "*Режим работы:*\n"
                    "Пн-Чт: 18:00 - 02:00\n"
                    "Пт-Сб: 18:00 - 04:00\n"
                    "Вс: 18:00 - 02:00",
                    parse_mode='Markdown'
                )
                
            elif data.get('type') == 'refresh':
                # Обновление данных
                await update.message.reply_text(
                    "🔄 *Данные обновлены!*\n\n"
                    "MiniApp получит актуальные данные при следующем открытии.",
                    parse_mode='Markdown'
                )
                
    except Exception as e:
        logger.error(f"Ошибка WebApp: {e}")
        try:
            await update.message.reply_text(
                "❌ *Ошибка обработки запроса*\n\n"
                "Попробуйте перезагрузить MiniApp или обратитесь к администратору.",
                parse_mode='Markdown'
            )
        except:
            pass


async def start_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск MiniApp"""
    # Кодируем HTML в base64 для data URL
    html_bytes = MINIAPP_HTML.encode('utf-8')
    html_base64 = base64.b64encode(html_bytes).decode('utf-8')
    webapp_url = f"data:text/html;base64,{html_base64}"
    
    keyboard = [[
        InlineKeyboardButton(
            text="🚀 Открыть Hookah Lounge App",
            web_app=WebAppInfo(url=webapp_url)
        )
    ]]
    
    await update.message.reply_text(
        "🎮 *Добро пожаловать в Hookah Lounge MiniApp!*\n\n"
        "Это современное веб-приложение с:\n"
        "• 📊 Вашей статистикой и балансом\n"
        "• 📋 Полным меню с категориями\n"
        "• 🛒 Умной корзиной заказов\n"
        "• 📅 Быстрым бронированием столов\n"
        "• 📊 Историей заказов\n\n"
        "*Для администраторов:*\n"
        "• Создание и управление заказами\n"
        "• Просмотр статистики продаж\n\n"
        "Нажмите кнопку ниже для запуска 👇",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def miniapp_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о MiniApp"""
    await update.message.reply_text(
        "ℹ️ *О MiniApp*\n\n"
        "*Hookah Lounge MiniApp* — это современное веб-приложение, "
        "встроенное прямо в Telegram.\n\n"
        "*Возможности:*\n"
        "✅ Полностью работает без внешнего сервера\n"
        "✅ Красивый современный интерфейс\n"
        "✅ Автоматическая синхронизация с ботом\n"
        "✅ Поддержка заказов и бронирований\n"
        "✅ История и статистика\n"
        "✅ Работает на любом устройстве\n\n"
        "*Команды:*\n"
        "`/miniapp` — открыть приложение\n"
        "`/miniapp_help` — справка по использованию",
        parse_mode='Markdown'
    )


async def miniapp_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по MiniApp"""
    await update.message.reply_text(
        "📖 *Справка по MiniApp*\n\n"
        "*Как использовать:*\n"
        "1. Нажмите `/miniapp` для запуска\n"
        "2. Используйте табы для навигации\n"
        "3. Добавляйте товары в корзину\n"
        "4. Оформляйте заказы\n\n"
        "*Табы:*\n"
        "🏠 *Главная* — статистика и быстрые действия\n"
        "📋 *Меню* — полный список товаров\n"
        "🛒 *Корзина* — ваш текущий заказ\n"
        "📊 *История* — предыдущие заказы\n\n"
        "*Для администраторов:*\n"
        "• Можно создавать заказы через MiniApp\n"
        "• Указывайте номер стола при оформлении\n"
        "• Заказы появляются в основном боте\n\n"
        "Проблемы? Пишите администратору.",
        parse_mode='Markdown'
    )


# Остальной код остается БЕЗ ИЗМЕНЕНИЙ - включая setup_handlers и main
# Добавьте обработчики WebApp в setup_handlers:

def setup_handlers(application):
    """Настройка всех обработчиков"""
    
    # ... ВСЕ остальные импорты и код как было ...
    
    # ДОБАВЛЯЕМ WEBAPP ОБРАБОТЧИКИ В НАЧАЛО:
    
    # WebApp команды
    application.add_handler(CommandHandler("miniapp", start_miniapp))
    application.add_handler(CommandHandler("miniapp_info", miniapp_info))
    application.add_handler(CommandHandler("miniapp_help", miniapp_help))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    
    # ... ВСЕ остальные обработчики как были ...
    
    # Замените старый start_webapp на новый:
    async def start_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await start_miniapp(update, context)
    
    application.add_handler(CommandHandler("start_webapp", start_webapp))
    
    # ... Остальной код без изменений ...


def main():
    """Основная функция запуска бота"""
    try:
        # Проверка токена
        if not BOT_TOKEN:
            logger.error("❌ Токен бота не найден! Проверьте файл .env")
            return

        # Создание приложения
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).post_stop(post_stop).build()

        # Настройка обработчиков
        logger.info("🔄 Настройка обработчиков...")
        setup_handlers(application)

        # Запуск бота
        logger.info("🚀 Запуск бота...")
        print("=" * 50)
        print("🤖 Бот запущен! Для остановки нажмите Ctrl+C")
        print("🎮 MiniApp: /miniapp")
        print("ℹ️ Инфо: /miniapp_info")
        print("📖 Помощь: /miniapp_help")
        print("=" * 50)

        application.run_polling(
            allowed_updates=['message', 'callback_query', 'web_app_data'],
            timeout=60,
            drop_pending_updates=True
        )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    # Базовая настройка логирования перед запуском
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    main()
