"""
Главный файл административных обработчиков - импортирует все функции из подмодулей
"""
import logging
from telegram import Update  # ДОБАВИТЬ ЭТОТ ИМПОРТ
from telegram.ext import ContextTypes  # ДОБАВИТЬ ЭТОТ ИМПОРТ
from database import Database

# Импортируем все функции из подмодулей
from .admin_utils import (
    is_admin,
    admin_panel,
    back_to_main_menu,
    cancel_operation,
    show_statistics
)

from .admin_users import (
    show_users_list,
    start_user_search,
    process_user_search,
    cancel_search,
    back_to_users_list,
    handle_users_pagination,
    user_selected_callback,
    user_info_callback,
    exit_search_mode,
    show_full_users_list,
    back_to_search_mode,
    new_search,
    add_bonus_callback,
    process_spent_amount,
    remove_bonus_callback,
    process_remove_bonus,
    get_user_search_handler
)

from .admin_bookings import (
    show_bookings,
    show_pending_bookings,
    show_confirmed_bookings,
    show_cancelled_bookings,
    show_all_bookings,
    show_dates_for_filter,
    select_year_for_filter,
    select_month_for_filter,
    show_bookings_by_selected_date,
    back_to_booking_menu,
    handle_booking_action,
    handle_booking_cancellation_with_reason,
    process_cancellation_reason,
    get_booking_date_handler,
    get_booking_cancellation_handler
)

from .admin_bonuses import (
    handle_bonus_requests,
    refresh_bonus_requests,
    handle_bonus_request_action,
    get_bonus_handler
)

from .admin_messages import (
    broadcast_message,
    process_broadcast_media,
    start_user_message,
    user_selected_for_message,
    process_user_message,
    message_user_callback,
    get_broadcast_handler,
    get_user_message_handler
)

logger = logging.getLogger(__name__)
db = Database()

# Сброс данных смены
async def reset_shift_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить данные смены в памяти"""
    if not is_admin(update.effective_user.id):
        return

    # Сброс данных в памяти
    context.bot_data.clear()

    await update.message.reply_text("✅ Данные смены в памяти сброшены! Бот нужно перезапустить.")

# Отладочные функции
def debug_booking_dates():
    """Отладочная функция для проверки данных бронирований"""
    cursor = db.conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(bookings)")
        columns = cursor.fetchall()
        logger.info("🔍 Структура таблицы bookings:")
        for col in columns:
            logger.info(f"   {col}")

        cursor.execute('''
            SELECT id, booking_date, status 
            FROM bookings 
            ORDER BY booking_date DESC 
            LIMIT 10
        ''')
        recent_bookings = cursor.fetchall()
        logger.info("🔍 Последние 10 бронирований:")
        for booking in recent_bookings:
            logger.info(f"   ID: {booking[0]}, Дата: {booking[1]}, Статус: {booking[2]}")

        cursor.execute('''
            SELECT DISTINCT booking_date 
            FROM bookings 
            WHERE booking_date IS NOT NULL 
            ORDER BY booking_date DESC
        ''')
        unique_dates = cursor.fetchall()
        logger.info("🔍 Уникальные даты бронирований:")
        for date in unique_dates:
            logger.info(f"   Дата: {date[0]}")

        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при отладке бронирований: {e}")
        return False


def create_test_bookings():
    """Создать тестовые бронирования для проверки фильтрации"""
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT id FROM users LIMIT 1")
        user = cursor.fetchone()

        if not user:
            logger.info("❌ Нет пользователей для создания тестовых бронирований")
            return False

        user_id = user[0]
        test_dates = [
            '2024-11-15', '2024-11-16', '2024-12-01',
            '2025-01-10', '2025-02-15', '2025-03-20'
        ]

        for date in test_dates:
            cursor.execute('''
                INSERT INTO bookings (user_id, booking_date, booking_time, guests, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, date, '19:00', 2, db.get_moscow_time(), 'confirmed'))

        db.conn.commit()
        logger.info(f"✅ Создано {len(test_dates)} тестовых бронирований")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при создании тестовых бронирований: {e}")
        return False