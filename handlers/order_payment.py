# handlers/order_payment.py
"""
Модуль оплаты и расчета заказов
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from keyboards.menus import PAYMENT_METHOD_NAMES
from handlers.order_utils import is_admin, message_manager, menu_manager, db, logger, format_datetime


async def show_active_orders_for_calculation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные заказы для расчета"""
    query = update.callback_query
    await query.answer()

    active_orders = db.get_active_orders()

    if not active_orders:
        await query.edit_message_text("📭 Активных заказов для расчета нет.")
        return

    keyboard = []
    for order in active_orders:
        total = menu_manager.calculate_order_total(order[0])
        keyboard.append([InlineKeyboardButton(
            f"Стол {order[1]} - {total}₽ (Заказ #{order[0]})",
            callback_data=f"calculate_{order[0]}"
        )])

    keyboard.append([InlineKeyboardButton("💰 Рассчитать все", callback_data="calculate_all_orders")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_calculation")])

    await query.edit_message_text(
        "Выберите заказ для расчета:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор способа оплаты"""
    query = update.callback_query
    await query.answer()

    try:
        order_id = int(query.data.replace("calculate_", ""))
    except ValueError:
        await query.edit_message_text("❌ Неверный ID заказа.")
        return

    order = db.get_order_by_id(order_id)
    if not order:
        await query.edit_message_text("❌ Заказ не найден.")
        return

    items = menu_manager.get_order_items(order_id)
    total = menu_manager.calculate_order_total(order_id)

    if not items:
        await query.edit_message_text("❌ В заказе нет позиций.")
        return

    # Формируем чек
    message = f"🧾 Чек для стола {order[1]}\n"
    message += f"🆔 Заказ #{order_id}\n"
    message += f"📅 Время: {format_datetime(order[4])}\n\n"
    message += "📋 Позиции:\n"

    for item in items:
        item_total = item[3] * item[4]
        message += f"• {item[2]} - {item[3]}₽ x {item[4]} = {item_total}₽\n"

    message += f"\n💰 Итого: {total}₽\n"
    message += f"💵 К оплате: {total}₽\n\n"
    message += "Выберите способ оплаты:"

    from keyboards.menus import get_payment_method_keyboard
    await query.edit_message_text(
        message,
        reply_markup=get_payment_method_keyboard(order_id)
    )


async def handle_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора способа оплаты"""
    query = update.callback_query
    await query.answer()

    # Формат: payment_method_orderid
    parts = query.data.split("_")
    if len(parts) < 3:
        await query.edit_message_text("❌ Ошибка в данных запроса.")
        return

    payment_method = parts[1]  # qr, card, cash, transfer
    order_id = int(parts[2])

    # Обновляем метод оплаты в базе данных
    db.update_order_payment_method(order_id, payment_method)

    # Закрываем заказ
    menu_manager.close_order(order_id)

    # Показываем финальное сообщение
    order = db.get_order_by_id(order_id)
    total = menu_manager.calculate_order_total(order_id)

    message = f"✅ Заказ #{order_id} закрыт!\n"
    message += f"🍽️ Стол: {order[1]}\n"
    message += f"💰 Сумма: {total}₽\n"
    message += f"💳 Способ оплаты: {PAYMENT_METHOD_NAMES.get(payment_method, payment_method)}\n"
    message += f"📅 Время: {format_datetime(db.get_moscow_time())}\n\n"
    message += "Спасибо за посещение! 🏮"

    # Обновляем сообщение с клавиатурой оплаты
    await query.edit_message_text(message)

    # Отправляем дополнительное сообщение с клавиатурой для возврата
    keyboard = [
        [InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders")],
        [InlineKeyboardButton("🍽️ Управление заказами", callback_data="back_to_order_management")]
    ]

    await query.message.reply_text(
        "Что дальше?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_back_to_calculation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к расчету заказа"""
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.replace("back_to_calculation_", ""))

    # Показываем активные заказы с расчетом
    active_orders = db.get_active_orders()

    keyboard = []
    for order in active_orders:
        total = menu_manager.calculate_order_total(order[0])
        keyboard.append([InlineKeyboardButton(
            f"Стол {order[1]} - {total}₽ (Заказ #{order[0]})",
            callback_data=f"calculate_{order[0]}"
        )])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="active_orders")])

    await query.edit_message_text(
        "Выберите заказ для расчета:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def calculate_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перенаправление на выбор оплаты"""
    query = update.callback_query
    await query.answer()

    # Просто вызываем новую функцию выбора оплаты
    await show_payment_selection(update, context)


async def handle_cancel_calculation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена расчета заказа - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    try:
        await query.edit_message_text("❌ Расчет заказа отменен.")
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение отмены расчета не требует изменений")
        else:
            logger.error(f"Ошибка при отмене расчета: {e}")
            await message_manager.send_message(
                update, context,
                "❌ Расчет заказа отменен.",
                is_temporary=True
            )


async def handle_back_to_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к списку заказов"""
    query = update.callback_query
    await query.answer()

    from handlers.order_management import show_active_orders
    await show_active_orders(update, context)