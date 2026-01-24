# handlers/order_utils.py
"""
Базовые утилиты для модулей управления заказами
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from config import ADMIN_IDS
from message_manager import message_manager
from menu_manager import menu_manager
from database import Database
import logging
from datetime import datetime, timedelta
from keyboards.menus import PAYMENT_METHOD_NAMES

logger = logging.getLogger(__name__)

# Убедитесь, что db инициализирован правильно
db = Database()

# Состояния для управления заказами (теперь не используются в ConversationHandler)
AWAITING_TABLE_NUMBER, SELECTING_CATEGORY, SELECTING_ITEMS, SELECTING_DATE_FOR_HISTORY = range(4)


def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


def format_datetime(datetime_str):
    """Форматирует дату и время для красивого отображения"""
    if not datetime_str:
        return "Неизвестно"
    try:
        if isinstance(datetime_str, str):
            dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d.%m.%Y %H:%M')
        else:
            return str(datetime_str)
    except Exception as e:
        logger.error(f"Ошибка форматирования даты {datetime_str}: {e}")
        return str(datetime_str)


def group_items_by_category(items_data):
    """Группирует позиции по категориям из базы данных и подсчитывает общие суммы - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    categories = {
        'Кальяны': {'name': '🍁 Кальяны', 'items': {}, 'total_quantity': 0, 'total_amount': 0},
        'Чай': {'name': '🍵 Чай', 'items': {}, 'total_quantity': 0, 'total_amount': 0},
        'Коктейли': {'name': '🍹 Коктейли', 'items': {}, 'total_quantity': 0, 'total_amount': 0},
        'Напитки': {'name': '🥤 Напитки', 'items': {}, 'total_quantity': 0, 'total_amount': 0},
        'Другое': {'name': '📦 Другое', 'items': {}, 'total_quantity': 0, 'total_amount': 0}
    }

    # Получаем все позиции меню с их категориями из базы данных
    menu_items = menu_manager.get_all_items_with_categories()

    # Создаем словарь для быстрого поиска категории по названию позиции
    item_category_map = {}
    for name, price, category in menu_items:
        item_category_map[name] = category

    for item_name, quantity, total_amount in items_data:
        # Определяем категорию позиции из базы данных - ПЕРВООЧЕРЕДНО ИСПОЛЬЗУЕМ ДАННЫЕ ИЗ БАЗЫ
        category = item_category_map.get(item_name, 'Другое')

        # Если категория не найдена в базе, используем эвристику для определения
        if category == 'Другое':
            item_lower = item_name.lower()
            if any(keyword in item_lower for keyword in
                   ['кальян', 'hookah', 'calyan', 'пенсионный', 'стандарт', 'премиум', 'фруктовая', 'сигарный',
                    'парфюм']):
                category = 'Кальяны'
            elif any(keyword in item_lower for keyword in
                     ['чай', 'tea', 'chai', 'пуэр', 'габа', 'гречишный', 'медовая', 'малина', 'мята', 'наглый', 'фрукт',
                      'вишневый', 'марроканский', 'голубика', 'смородиновый', 'клубничный', 'облепиховый']):
                category = 'Чай'
            elif any(keyword in item_lower for keyword in
                     ['коктейль', 'cocktail', 'кокт', 'пробирки', 'в/кола', 'санрайз', 'лагуна', 'фиеро']):
                category = 'Коктейли'
            elif any(keyword in item_lower for keyword in
                     ['напиток', 'drink', 'сок', 'вода', 'газировка', 'кола', 'пиво', 'энергетик', 'фанта', 'спрайт']):
                category = 'Напитки'

        # Добавляем позицию в категорию
        if item_name not in categories[category]['items']:
            categories[category]['items'][item_name] = {
                'quantity': 0,
                'total_amount': 0
            }

        categories[category]['items'][item_name]['quantity'] += quantity
        categories[category]['items'][item_name]['total_amount'] += total_amount
        categories[category]['total_quantity'] += quantity
        categories[category]['total_amount'] += total_amount

    return categories


async def back_to_admin_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню администратора"""
    from handlers.admin_handlers import back_to_main_menu
    await back_to_main_menu(update, context)


async def cancel_order_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания заказа - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    if 'current_order_id' in context.user_data:
        order_id = context.user_data['current_order_id']
        # Можно добавить логику удаления заказа если нужно
        pass

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text("❌ Создание заказа отменено.")
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отмены заказа не требует изменений")
            else:
                logger.error(f"Ошибка при отмене заказа: {e}")
                await message_manager.send_message(
                    update, context,
                    "❌ Создание заказа отменено.",
                    is_temporary=True
                )
    else:
        await message_manager.send_message(
            update, context,
            "❌ Создание заказа отменено.",
            is_temporary=True
        )
    context.user_data.clear()


async def handle_back_to_order_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в управление заказами - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    try:
        await start_order_management(update, context)
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение не требует изменений при возврате в управление заказами")
        else:
            logger.error(f"Ошибка при возврате в управление заказами: {e}")
            await message_manager.send_message(
                update, context,
                "🍽️ Управление заказами",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔓 Открыть смену", callback_data="open_shift"),
                    InlineKeyboardButton("📊 История заказов", callback_data="order_history")
                ], [
                    InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin")
                ]]),
                is_temporary=False
            )
async def handle_order_buttons_outside_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок заказов вне ConversationHandler - ОБНОВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    # ПРИНУДИТЕЛЬНАЯ ОТЛАДКА - ДОБАВЬТЕ ЭТО
    print(f"🎯 DEBUG: Получен callback_data: '{query.data}'")
    print(f"🎯 DEBUG: User: {query.from_user.id}, Message: {query.message.message_id}")

    if query.data.startswith("add_items_"):
        from handlers.order_management import handle_add_items
        return await handle_add_items(update, context)
    elif query.data.startswith("view_order_"):
        from handlers.order_management import view_order_details
        return await view_order_details(update, context)
    elif query.data.startswith("calculate_"):
        from handlers.order_payment import calculate_order
        return await calculate_order(update, context)
    elif query.data.startswith("edit_order_"):  # НОВЫЙ ОБРАБОТЧИК
        from handlers.order_management import show_order_for_editing
        return await show_order_for_editing(update, context)
    elif query.data.startswith("remove_item_"):  # НОВЫЙ ОБРАБОТЧИК
        from handlers.order_management import remove_item_from_order
        return await remove_item_from_order(update, context)
    elif query.data == "active_orders":
        from handlers.order_management import show_active_orders
        return await show_active_orders(update, context)
    elif query.data == "back_to_admin":
        return await back_to_admin_main(update, context)
    elif query.data == "cancel_calculation":
        from handlers.order_payment import handle_cancel_calculation
        return await handle_cancel_calculation(update, context)
    elif query.data == "order_history":
        from handlers.order_history import show_order_history_menu
        return await show_order_history_menu(update, context)
    elif query.data == "history_today":
        from handlers.order_history import show_today_orders
        return await show_today_orders(update, context)
    elif query.data == "history_shift":
        from handlers.order_history import show_shift_history
        return await show_shift_history(update, context)
    elif query.data == "history_month":
        from handlers.order_history import show_month_history
        return await show_month_history(update, context)
    elif query.data == "history_year":
        from handlers.order_history import show_year_history
        return await show_year_history(update, context)
    elif query.data == "history_select_shift":
        from handlers.order_history import show_select_shift_menu
        return await show_select_shift_menu(update, context)
    elif query.data.startswith("history_shift_"):  # Обработка нового формата
        from handlers.order_history import show_selected_shift_history
        return await show_selected_shift_history(update, context)
    elif query.data == "history_all":
        from handlers.order_history import show_all_closed_orders
        return await show_all_closed_orders(update, context)
    elif query.data == "history_select_date":
        from handlers.order_history import show_select_date_menu
        return await show_select_date_menu(update, context)
    elif query.data.startswith("history_date_"):
        from handlers.order_history import show_orders_by_date
        return await show_orders_by_date(update, context)
    elif query.data == "back_to_order_management":
        return await handle_back_to_order_management(update, context)
    # Добавляем обработчики управления сменой
    elif query.data == "open_shift":
        from handlers.order_shift import open_shift
        return await open_shift(update, context)
    elif query.data == "close_shift":
        from handlers.order_shift import close_shift
        return await close_shift(update, context)
    elif query.data == "calculate_all_orders":
        from handlers.order_shift import calculate_all_orders
        return await calculate_all_orders(update, context)
    elif query.data == "shift_status":
        from handlers.order_shift import show_shift_status
        return await show_shift_status(update, context)
    # Добавляем обработчики новой статистики
    elif query.data.startswith("history_full_year_"):
        from handlers.order_history import show_full_year_history
        return await show_full_year_history(update, context)
    elif query.data.startswith("history_full_month_"):
        from handlers.order_history import show_full_month_history
        return await show_full_month_history(update, context)
    elif query.data.startswith("history_month_more_"):  # НОВЫЙ ОБРАБОТЧИК ПАГИНАЦИИ
        from handlers.order_history import show_more_shifts
        return await show_more_shifts(update, context)
    elif query.data.startswith("history_month_"):  # Обработка выбора месяца
        from handlers.order_history import select_month_for_history
        return await select_month_for_history(update, context)
    elif query.data.startswith("history_year_"):  # Обработка выбора года
        from handlers.order_history import select_year_for_history
        return await select_year_for_history(update, context)
    else:
        await query.edit_message_text("❌ Неизвестная команда")