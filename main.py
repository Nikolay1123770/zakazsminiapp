import logging
import os
import warnings
import json
import asyncio
from typing import Dict, Any
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

# Ваш домен для WebApp
WEBAPP_URL = "https://vovsetyagskie.bothost.ru:8080/webapp.html"

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


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик данных из WebApp"""
    try:
        if update.message and update.message.web_app_data:
            data = json.loads(update.message.web_app_data.data)
            user_id = update.effective_user.id
            
            logger.info(f"Получены данные из WebApp от пользователя {user_id}: {data}")
            
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
                
                # Отправляем данные обратно в WebApp
                response_data = {
                    'type': 'user_data',
                    'balance': balance,
                    'bookings': bookings_count,
                    'orders': orders_count,
                    'referrals': referrals_count
                }
                
                # Отправляем через WebApp
                await update.message.reply_text(
                    f"🎮 Данные для WebApp обновлены!\n"
                    f"💰 Баланс: {balance} баллов\n"
                    f"📅 Бронирований: {bookings_count}\n"
                    f"🍽️ Заказов: {orders_count}\n"
                    f"🎁 Рефералов: {referrals_count}"
                )
                
                # Отправляем данные в WebApp
                await context.bot.answer_web_app_query(
                    update.message.web_app_data.query_id,
                    json.dumps(response_data)
                )
                
            elif data.get('type') == 'order':
                # Обработка заказа из WebApp
                cart = data.get('cart', [])
                table_number = data.get('tableNumber', '1')
                
                if cart:
                    # Создаем заказ
                    from menu_manager import menu_manager
                    
                    # Проверяем, является ли пользователь администратором
                    if not is_admin(user_id):
                        await update.message.reply_text(
                            "❌ Только администраторы могут создавать заказы через WebApp"
                        )
                        return
                    
                    # Создаем заказ
                    order_id = menu_manager.create_order(table_number, user_id)
                    
                    # Добавляем позиции
                    for item in cart:
                        menu_manager.add_item_to_order(
                            order_id, 
                            item['name'], 
                            item['quantity']
                        )
                    
                    total = menu_manager.calculate_order_total(order_id)
                    
                    await update.message.reply_text(
                        f"✅ Заказ #{order_id} создан!\n"
                        f"📊 Номер стола: {table_number}\n"
                        f"💰 Сумма: {total}₽\n"
                        f"🛒 Позиций: {len(cart)}\n\n"
                        f"Для оплаты перейдите в раздел '🍽️ Управление заказами'"
                    )
            
            elif data.get('type') == 'booking':
                # Обработка бронирования из WebApp
                date = data.get('date', 'сегодня')
                time = data.get('time', '19:00')
                
                await update.message.reply_text(
                    f"📅 Заявка на бронирование принята!\n"
                    f"📅 Дата: {date}\n"
                    f"⏰ Время: {time}\n\n"
                    f"Администратор свяжется с вами для подтверждения."
                )
            
            elif data.get('type') == 'contacts':
                # Показываем контакты
                from handlers.user_handlers import show_contacts
                await show_contacts(update, context)
            
            elif data.get('type') == 'referral':
                # Показываем реферальную программу
                from handlers.user_handlers import show_referral_info
                await show_referral_info(update, context)
            
            elif data.get('type') == 'refresh':
                # Обновление данных
                await update.message.reply_text("🔄 Данные обновлены!")
                
    except Exception as e:
        logger.error(f"Ошибка обработки WebApp данных: {e}")
        await update.message.reply_text("❌ Ошибка обработки данных из WebApp")


async def start_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск WebApp"""
    keyboard = [[
        InlineKeyboardButton(
            text="🎮 Открыть Hookah Lounge App",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]]
    
    await update.message.reply_text(
        "🎮 *Доступ к Hookah Lounge MiniApp*\n\n"
        "Нажмите кнопку ниже для запуска современного приложения с:\n"
        "• 📊 Вашей статистикой\n"
        "• 📋 Интерактивным меню\n"
        "• 🛒 Удобной корзиной заказов\n"
        "• 📅 Быстрым бронированием\n\n"
        "*Функции для администраторов:*\n"
        "• Создание заказов\n"
        "• Управление столами\n"
        "• Просмотр статистики",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def setup_webapp_hosting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка хостинга WebApp"""
    if not is_admin(update.effective_user.id):
        return
    
    html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hookah Lounge App</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 20px;
            font-size: 28px;
        }
        p {
            color: #666;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        .status {
            background: #4CAF50;
            color: white;
            padding: 10px 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            font-weight: bold;
        }
        .btn {
            background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.3s ease;
            margin-top: 20px;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 Hookah Lounge MiniApp</h1>
        <div class="status">✅ Веб-приложение готово к работе</div>
        <p>Это приложение интегрировано с Telegram ботом Hookah Lounge.</p>
        <p>Для использования откройте бота и нажмите "Открыть Hookah Lounge App"</p>
        <button class="btn" onclick="testApp()">Тестировать приложение</button>
    </div>
    <script>
        function testApp() {
            alert('Приложение работает корректно!');
            if (window.Telegram && Telegram.WebApp) {
                Telegram.WebApp.ready();
                Telegram.WebApp.expand();
            }
        }
    </script>
</body>
</html>
    """
    
    await update.message.reply_text(
        f"🌐 *Настройка хостинга WebApp*\n\n"
        f"Ваш домен: `{WEBAPP_URL}`\n\n"
        f"*Инструкция:*\n"
        f"1. Создайте файл `webapp.html` в корне вашего сервера\n"
        f"2. Добавьте следующий HTML код:\n"
        f"```html\n{html_content[:500]}...\n```\n"
        f"3. Убедитесь, что порт 8080 открыт\n"
        f"4. Используйте команду `/start_webapp` для тестирования",
        parse_mode='Markdown'
    )


async def webapp_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестирование WebApp"""
    keyboard = [[
        InlineKeyboardButton("🎮 Тест WebApp", web_app=WebAppInfo(url=WEBAPP_URL))
    ]]
    
    await update.message.reply_text(
        "🔧 *Тестирование WebApp*\n\n"
        "Нажмите кнопку для проверки работы WebApp.\n"
        "Если приложение не открывается, проверьте:\n"
        "• Файл `webapp.html` на сервере\n"
        "• Доступность порта 8080\n"
        "• SSL сертификат (для HTTPS)",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать контакты"""
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


def setup_handlers(application):
    """Настройка всех обработчиков"""

    # Импорты обработчиков пользователя
    from handlers.user_handlers import (
        get_registration_handler, get_spend_bonus_handler,
        show_balance, show_referral_info, show_user_bookings,
        handle_user_pending_bookings_button, handle_user_confirmed_bookings_button,
        handle_user_cancelled_bookings_button, handle_user_all_bookings_button,
        handle_user_back_to_bookings_button, handle_user_cancel_booking,
        handle_back_to_bookings_list, start, back_to_main,
        handle_call_contact, handle_telegram_contact,
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

    # Для совместимости с существующим кодом
    from handlers.order_utils import handle_order_buttons_outside_conversation

    # Утилиты
    from handlers.order_utils import cancel_order_creation, handle_back_to_order_management

    # Импорты обработчиков управления меню
    from handlers.menu_management_handlers import (
        get_menu_management_handlers,
        manage_menu,
        start_edit_item
    )

    # НОВАЯ ФУНКЦИЯ ДЛЯ ОТЛАДКИ
    from database import Database
    db = Database()
    db.add_payment_method_column()  # Добавить эту строку

    async def debug_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для отладки - показать все смены"""
        if not is_admin(update.effective_user.id):
            return

        all_shifts = db.get_all_shifts_debug()

        if not all_shifts:
            await update.message.reply_text("📭 Нет смен в базе данных")
            return

        message = "📊 ВСЕ СМЕНЫ В БАЗЕ:\n\n"
        for shift in all_shifts:
            message += f"Смена #{shift[1]} ({shift[2]})\n"
            message += f"  Открыта: {shift[3]}\n"
            message += f"  Закрыта: {shift[4] if shift[4] else 'Открыта'}\n"
            message += f"  Выручка: {shift[5] or 0}₽\n"
            message += f"  Заказов: {shift[6] or 0}\n"
            message += f"  Статус: {shift[7]}\n"
            message += "-" * 30 + "\n"

        # Разбиваем сообщение если оно слишком длинное
        if len(message) > 4000:
            await update.message.reply_text(message[:4000])
            if len(message) > 8000:
                await update.message.reply_text(message[4000:8000])
                if len(message) > 12000:
                    await update.message.reply_text(message[8000:12000])
            else:
                await update.message.reply_text(message[4000:])
        else:
            await update.message.reply_text(message)

    # НОВАЯ ФУНКЦИЯ ДЛЯ ОБРАБОТКИ ПОИСКА ПОЛЬЗОВАТЕЛЕЙ АДМИНОМ
    async def handle_admin_user_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений админа для поиска пользователей"""
        user_id = update.effective_user.id

        # Проверяем, является ли пользователь администратором
        if not is_admin(user_id):
            return False  # Не админ

        # Проверяем, находится ли админ в режиме поиска пользователей
        if not context.user_data.get('search_users_mode', False):
            # Не в режиме поиска - пропускаем дальше
            return False

        # Игнорируем кнопки меню
        text = update.message.text.strip()
        menu_buttons = ["👥 Список пользователей", "📊 Статистика", "📋 Запросы на списание",
                        "🔄 Обновить список запросов", "📅 Бронирования", "🍽️ Управление заказами",
                        "🍴 Управление меню", "✏️ Редактировать позицию", "⬅️ Назад",
                        "⬅️ В главное меню", "⏳ Ожидающие", "✅ Подтвержденные",
                        "❌ Отмененные", "📋 Все бронирования", "💰 Мой баланс",
                        "🎁 Реферальная программа", "📋 Мои бронирования", "📞 Контакты",
                        "📞 Позвонить", "💬 Написать в Telegram", "📍 Мы на картах"]

        if text in menu_buttons:
            # Это кнопка меню, а не поисковый запрос
            return False

        # Если в режиме поиска - обрабатываем как поисковый запрос
        search_query = text

        if not search_query:
            await update.message.reply_text("❌ Введите текст для поиска (ID, имя или фамилию)")
            return True  # Блокируем цепочку

        logger.info(f"Админ {user_id} ищет пользователя: {search_query}")

        # Ищем пользователей в базе данных
        cursor = db.conn.cursor()

        # Поиск по ID
        if search_query.isdigit():
            cursor.execute('''
                SELECT * FROM users 
                WHERE id = ? AND is_active = TRUE 
                ORDER BY id DESC
            ''', (int(search_query),))
        else:
            # Поиск по имени или фамилии
            search_pattern = f"%{search_query}%"
            cursor.execute('''
                SELECT * FROM users 
                WHERE (first_name LIKE ? OR last_name LIKE ?) AND is_active = TRUE 
                ORDER BY id DESC
            ''', (search_pattern, search_pattern))

        users = cursor.fetchall()

        if not users:
            await update.message.reply_text(
                f"❌ Пользователи по запросу '{search_query}' не найдены.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")],
                    [InlineKeyboardButton("📋 Показать полный список", callback_data="show_full_users_list_0")],
                    [InlineKeyboardButton("❌ Выйти из поиска", callback_data="exit_search_mode")]
                ])
            )
            return True  # Блокируем цепочку

        # Показываем найденных пользователей
        message = f"🔍 Результаты поиска по запросу: '{search_query}'\n\n"
        message += f"Найдено пользователей: {len(users)}\n\n"

        keyboard = []

        for user in users:
            keyboard.append([InlineKeyboardButton(
                f"{user[2]} {user[3]} (ID: {user[0]}) | 💰 {user[5]} баллов",
                callback_data=f"select_user_{user[0]}"
            )])

        keyboard.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")])
        keyboard.append([InlineKeyboardButton("📋 Показать полный список", callback_data="show_full_users_list_0")])
        keyboard.append([InlineKeyboardButton("❌ Выйти из поиска", callback_data="exit_search_mode")])

        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return True  # Блокируем дальнейшую обработку

    # ========== ОБРАБОТЧИК ПОИСКА ПОЛЬЗОВАТЕЛЕЙ АДМИНОМ ==========
    # Создаем UserMessageHandler для обработки отправки сообщений пользователям
    user_message_conversation = get_user_message_handler()

    # Сначала добавляем ConversationHandler для отправки сообщений (более высокий приоритет)
    application.add_handler(user_message_conversation)

    # Затем добавляем обработчик поиска пользователей (низкий приоритет)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & admin_filter,
        handle_admin_user_search_text
    ), group=2)  # group=2 - более низкий приоритет

    # ДОБАВЛЕНЫ ОБРАБОТЧИКИ УПРАВЛЕНИЯ МЕНЮ ПЕРВЫМИ (чтобы избежать конфликтов)
    menu_handlers = get_menu_management_handlers()
    for handler in menu_handlers:
        application.add_handler(handler)

    # ДОБАВЛЕН НОВЫЙ ОБРАБОТЧИК ПОИСКА ПОЛЬЗОВАТЕЛЕЙ
    application.add_handler(get_user_search_handler())

    # ДОБАВЛЕНЫ ОБРАБОТЧИКИ ДЛЯ РЕЖИМА ПОИСКА ПОЛЬЗОВАТЕЛЕЙ
    application.add_handler(CallbackQueryHandler(exit_search_mode, pattern="^exit_search_mode$"))
    application.add_handler(CallbackQueryHandler(back_to_search_mode, pattern="^back_to_search_mode$"))
    application.add_handler(CallbackQueryHandler(new_search, pattern="^new_search$"))
    application.add_handler(CallbackQueryHandler(show_full_users_list, pattern="^show_full_users_list_"))

    # ОБРАБОТЧИКИ WEBAPP (добавляем в начало для приоритета)
    application.add_handler(CommandHandler("start_webapp", start_webapp))
    application.add_handler(CommandHandler("webapp_hosting", setup_webapp_hosting))
    application.add_handler(CommandHandler("webapp_test", webapp_test))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    # ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ (только для обычных пользователей)
    # Основные кнопки меню пользователя
    application.add_handler(MessageHandler(filters.Regex("^💰 Мой баланс$") & user_filter, show_balance))
    application.add_handler(
        MessageHandler(filters.Regex("^🎁 Реферальная программа$") & user_filter, show_referral_info))
    application.add_handler(MessageHandler(filters.Regex("^📋 Мои бронирования$") & user_filter, show_user_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📞 Контакта$") & user_filter, show_contacts))

    # Кнопки фильтрации бронирований пользователя
    application.add_handler(
        MessageHandler(filters.Regex("^⏳ Ожидающие$") & user_filter, handle_user_pending_bookings_button))
    application.add_handler(
        MessageHandler(filters.Regex("^✅ Подтвержденные$") & user_filter, handle_user_confirmed_bookings_button))
    application.add_handler(
        MessageHandler(filters.Regex("^❌ Отмененные$") & user_filter, handle_user_cancelled_bookings_button))
    application.add_handler(
        MessageHandler(filters.Regex("^📋 Все бронирования$") & user_filter, handle_user_all_bookings_button))
    application.add_handler(
        MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_user_back_to_bookings_button))

    # Обработчики контактов
    application.add_handler(MessageHandler(filters.Regex("^📞 Контакты$") & user_filter, show_contacts))
    application.add_handler(MessageHandler(filters.Regex("^📞 Позвонить$") & user_filter, handle_call_contact))
    application.add_handler(
        MessageHandler(filters.Regex("^💬 Написать в Telegram$") & user_filter, handle_telegram_contact))
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

    # ОБРАБОТЧИКИ АДМИНИСТРАТОРА (только для администраторов)
    # Основные кнопки меню администратора
    application.add_handler(MessageHandler(filters.Regex("^👥 Список пользователей$") & admin_filter, show_users_list))
    application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$") & admin_filter, show_statistics))
    application.add_handler(
        MessageHandler(filters.Regex("^📋 Запросы на списание$") & admin_filter, handle_bonus_requests))
    application.add_handler(
        MessageHandler(filters.Regex("^🔄 Обновить список запросов$") & admin_filter, refresh_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^📅 Бронирования$") & admin_filter, show_bookings))
    application.add_handler(
        MessageHandler(filters.Regex("^🍽️ Управление заказами$") & admin_filter, start_order_management))

    # Обработчики управления меню добавляются через get_menu_management_handlers()
    application.add_handler(MessageHandler(filters.Regex("^🍴 Управление меню$") & admin_filter, manage_menu))

    # ДОБАВЛЕН НОВЫЙ ОБРАБОТЧИК ДЛЯ ПАГИНАЦИИ ПОЛЬЗОВАТЕЛЕЙ И ПОИСКА
    application.add_handler(CallbackQueryHandler(handle_users_pagination, pattern="^(users_page_|refresh_users)"))

    # Кнопки фильтрации бронирований администратора
    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & admin_filter, show_pending_bookings))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & admin_filter, show_confirmed_bookings))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & admin_filter, show_cancelled_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & admin_filter, show_all_bookings))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & admin_filter, back_to_main_menu))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ В главное меню$") & admin_filter, back_to_main_menu))

    # Conversation handlers администратора
    application.add_handler(get_broadcast_handler())
    application.add_handler(get_user_message_handler())
    application.add_handler(get_bonus_handler())
    application.add_handler(get_booking_date_handler())
    application.add_handler(get_booking_cancellation_handler())

    # ========== ОБРАБОТЧИКИ УПРАВЛЕНИЯ ЗАКАЗАМИ (БЕЗ CONVERSATIONHANDLER) ==========

    # Основные кнопки управления заказами
    application.add_handler(CallbackQueryHandler(handle_create_order, pattern="^create_order$"))

    # Обработчики категорий и позиций
    application.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(handle_item_selection, pattern="^item_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_categories$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_category_"))
    application.add_handler(CallbackQueryHandler(finish_order, pattern="^finish_order$"))
    application.add_handler(CallbackQueryHandler(cancel_order_creation, pattern="^cancel_order$"))

    # Обработчики управления существующими заказами
    application.add_handler(CallbackQueryHandler(handle_add_items, pattern="^add_items_"))
    application.add_handler(CallbackQueryHandler(view_order_details, pattern="^view_order_"))
    application.add_handler(CallbackQueryHandler(show_payment_selection, pattern="^calculate_"))
    application.add_handler(CallbackQueryHandler(handle_payment_selection, pattern="^payment_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_calculation, pattern="^back_to_calculation_"))
    application.add_handler(CallbackQueryHandler(show_active_orders, pattern="^active_orders$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_admin$"))
    application.add_handler(CallbackQueryHandler(handle_cancel_calculation, pattern="^cancel_calculation$"))
    application.add_handler(CallbackQueryHandler(add_items_to_existing_order, pattern="^add_to_existing_"))

    # Обработчики для редактирования заказа
    application.add_handler(CallbackQueryHandler(show_order_for_editing, pattern="^edit_order_"))
    application.add_handler(CallbackQueryHandler(remove_item_from_order, pattern="^remove_item_"))

    # Обработчики истории заказов
    application.add_handler(CallbackQueryHandler(show_order_history_menu, pattern="^order_history$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_order_management$"))

    # Обработчики новой статистики
    application.add_handler(CallbackQueryHandler(show_shift_history, pattern="^history_shift$"))
    application.add_handler(CallbackQueryHandler(show_year_history, pattern="^history_year$"))
    application.add_handler(CallbackQueryHandler(select_year_for_history, pattern="^history_year_"))
    application.add_handler(CallbackQueryHandler(select_month_for_history, pattern="^history_month_"))
    application.add_handler(CallbackQueryHandler(show_select_shift_menu, pattern="^history_select_shift$"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_"))

    # Обработчики статистики за весь год/месяц
    application.add_handler(CallbackQueryHandler(show_full_year_history, pattern="^history_full_year_"))
    application.add_handler(CallbackQueryHandler(show_full_month_history, pattern="^history_full_month_"))

    # Обработчики пагинации смен
    application.add_handler(CallbackQueryHandler(show_more_shifts, pattern="^history_month_more_"))

    # Обработчики управления сменой
    application.add_handler(CallbackQueryHandler(open_shift, pattern="^open_shift$"))
    application.add_handler(CallbackQueryHandler(close_shift, pattern="^close_shift$"))
    application.add_handler(CallbackQueryHandler(calculate_all_orders, pattern="^calculate_all_orders$"))
    application.add_handler(CallbackQueryHandler(show_shift_status, pattern="^shift_status$"))

    # Callback обработчики администратора
    application.add_handler(CallbackQueryHandler(user_selected_callback, pattern="^select_user_"))
    application.add_handler(CallbackQueryHandler(user_info_callback, pattern="^info_"))
    application.add_handler(CallbackQueryHandler(handle_booking_action, pattern="^(confirm_booking_|cancel_booking_)"))
    application.add_handler(CallbackQueryHandler(handle_bonus_request_action, pattern="^(approve_|reject_)"))
    application.add_handler(CallbackQueryHandler(message_user_callback, pattern="^message_"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_.*_.*"))

    # ДОБАВЛЕН НОВЫЙ ОБРАБОТЧИК ДЛЯ КНОПКИ "НАЗАД К СПИСКУ"
    application.add_handler(CallbackQueryHandler(back_to_users_list, pattern="^back_to_users_list$"))

    # ВАЖНО: Обработчик для кнопки "Редактировать позицию" в меню управления меню
    application.add_handler(MessageHandler(filters.Regex("^✏️ Редактировать позицию$") & admin_filter, start_edit_item))

    # КОМАНДЫ
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset_shift", reset_shift_data))
    application.add_handler(CommandHandler("debug_shifts", debug_shifts))

    # Обработчик кнопки "Назад" для обоих типов пользователей
    async def handle_back_button(update: Update, context):
        user_id = update.effective_user.id
        if is_admin(user_id):
            await back_to_main_menu(update, context)
        else:
            await back_to_main(update, context)

    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$"), handle_back_button))

    # УМНЫЙ ОБРАБОТЧИК ВВОДА НОМЕРА СТОЛА - только когда это действительно нужно
    async def smart_table_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Умный обработчик ввода номера стола - только когда пользователь в процессе создания заказа"""
        user_id = update.effective_user.id

        # Проверяем, является ли пользователь администратором
        if not is_admin(user_id):
            return False

        # КРИТИЧЕСКАЯ ПРОВЕРКА: Если админ в режиме поиска пользователей - НЕ создавать заказ
        if context.user_data.get('search_users_mode', False):
            logger.info(f"Админ {user_id} в режиме поиска, НЕ создаем заказ для: {update.message.text}")
            return False  # Пропускаем, сообщение уже обработано поиском

        # Проверяем, ожидает ли система ввод номера стола
        # Флаг expecting_table_number устанавливается только при нажатии "Создать заказ"
        if not context.user_data.get('expecting_table_number', False):
            logger.info(f"Админ {user_id}: не ожидаем номер стола, пропускаем: {update.message.text}")
            return False  # Не ожидаем номер стола - не обрабатываем

        # Проверяем, является ли ввод числом
        if not update.message.text.isdigit():
            await update.message.reply_text("❌ Номер стола должен быть числом. Попробуйте снова:")
            return True  # Блокируем цепочку

        # Если ожидаем номер стола и это число - обрабатываем
        logger.info(f"Админ {user_id} вводит номер стола: {update.message.text}")
        await handle_table_number(update, context)

        # Сбрасываем флаг ожидания после обработки
        context.user_data.pop('expecting_table_number', None)

        return True  # Блокируем цепочку

    # Этот обработчик должен быть ПОСЛЕ обработчика поиска пользователей
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & admin_filter,
        smart_table_number_handler
    ))

    # Обработчик неизвестных сообщений (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ)
    async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Для администраторов показываем другое сообщение
        if is_admin(update.effective_user.id):
            await update.message.reply_text(
                "❌ Неизвестная команда. Используйте кнопки меню администратора."
            )
        else:
            await update.message.reply_text(
                "❌ Неизвестная команда. Используйте кнопки меню."
            )

    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, unknown_message))


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
        print("🌐 WebApp доступен по команде /start_webapp")
        print("🔧 Настройка хоста: /webapp_hosting")
        print("🧪 Тестирование: /webapp_test")
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
