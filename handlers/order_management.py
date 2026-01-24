# handlers/order_management.py
"""
Модуль управления существующими заказами
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.order_utils import is_admin, message_manager, menu_manager, db, logger, format_datetime


async def show_active_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные заказы - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    active_orders = db.get_active_orders()

    if not active_orders:
        try:
            await query.edit_message_text(
                "📭 Активных заказов нет.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("➕ Создать заказ", callback_data="create_order"),
                      InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")],
                     [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение активных заказов не требует изменений")
            else:
                logger.error(f"Ошибка при показе активных заказов: {e}")
                await message_manager.send_message(
                    update, context,
                    "📭 Активных заказов нет.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("➕ Создать заказ", callback_data="create_order"),
                          InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")],
                         [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]]),
                    is_temporary=False
                )
        return

    for order in active_orders:
        items = menu_manager.get_order_items(order[0])
        total = menu_manager.calculate_order_total(order[0])

        # ТА ЖЕ ЛОГИКА, ЧТО И В close_shift()
        admin_id = order[2]  # admin_id из orders таблицы
        admin_data = db.get_user_by_id(admin_id)  # Ищем по ID в таблице users

        # Формируем имя администратора как в close_shift()
        if admin_data:
            first_name = admin_data[2] or ""
            last_name = admin_data[3] or ""
            admin_name = f"{first_name} {last_name}".strip()
            if not admin_name:
                admin_name = f"ID: {admin_id}"
        else:
            admin_name = f"ID: {admin_id} (пользователь не найден)"

        message = f"📋 Заказ #{order[0]} | Стол {order[1]}\n"
        message += f"👨‍💼 Админ: {admin_name}\n"
        message += f"💰 Сумма: {total}₽\n"
        message += f"📅 Создан: {format_datetime(order[4])}\n"

        # Добавляем информацию о позициях если они есть
        if items:
            message += "\n🛒 Позиции:\n"
            for item in items[:3]:  # Показываем первые 3 позиции
                message += f"• {item[2]} x{item[4]}\n"
            if len(items) > 3:
                message += f"• ... и еще {len(items) - 3} позиций\n"

        # Кнопки для управления заказом
        keyboard = [
            [InlineKeyboardButton("➕ Добавить позиции", callback_data=f"add_items_{order[0]}")],
            [InlineKeyboardButton("👀 Просмотреть детали", callback_data=f"view_order_{order[0]}")],
            [InlineKeyboardButton("💰 Рассчитать", callback_data=f"calculate_{order[0]}")]
        ]

        await message_manager.send_message(
            update, context,
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            is_temporary=False
        )

    # ИСПРАВЛЕННАЯ КЛАВИАТУРА
    await message_manager.send_message(
        update, context,
        f"📊 Всего активных заказов: {len(active_orders)}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")],
                                           [InlineKeyboardButton("➕ Создать заказ", callback_data="create_order"),
                                            InlineKeyboardButton("⬅️ Назад",
                                                                 callback_data="back_to_order_management")]]),
        is_temporary=False
    )


async def add_items_to_existing_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление позиций к существующему заказу"""
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.replace("add_to_existing_", ""))
    context.user_data['current_order_id'] = order_id

    order = db.get_order_by_id(order_id)
    context.user_data['table_number'] = order[1]

    await query.edit_message_text(
        f"✅ Добавление к заказу #{order_id} для стола {order[1]}\n\n"
        f"Выберите категорию меню:",
        reply_markup=menu_manager.get_category_keyboard()
    )


async def show_order_for_editing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать заказ для редактирования (удаления позиций)"""
    query = update.callback_query
    await query.answer()

    # Правильно извлекаем order_id из callback_data
    if query.data.startswith("edit_order_"):
        order_id = int(query.data.replace("edit_order_", ""))
    elif query.data.startswith("remove_item_"):
        # Если вызываем из remove_item, берем order_id из context или из данных
        parts = query.data.split("_")
        if len(parts) >= 3:
            order_id = int(parts[2])
        else:
            await query.edit_message_text("❌ Ошибка: неверный формат данных.")
            return
    else:
        await query.edit_message_text("❌ Ошибка: неизвестная команда.")
        return

    order = db.get_order_by_id(order_id)
    if not order:
        await query.edit_message_text("❌ Заказ не найден.")
        return

    items = menu_manager.get_order_items(order_id)
    total = menu_manager.calculate_order_total(order_id)

    message = f"✏️ Редактирование заказа #{order_id}\n"
    message += f"🍽️ Стол: {order[1]}\n"
    message += f"💰 Текущая сумма: {total}₽\n\n"

    if not items:
        message += "🛒 В заказе нет позиций\n"
    else:
        message += "🛒 Позиции (нажмите чтобы удалить):\n"

    keyboard = []
    for item in items:
        item_total = item[3] * item[4]
        keyboard.append([InlineKeyboardButton(
            f"❌ {item[2]} - {item[3]}₽ x {item[4]} = {item_total}₽",
            callback_data=f"remove_item_{order_id}_{item[2].replace(' ', '_')}"  # Заменяем пробелы на подчеркивания
        )])

    keyboard.append([InlineKeyboardButton("➕ Добавить позиции", callback_data=f"add_items_{order_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад к заказу", callback_data=f"view_order_{order_id}")])
    keyboard.append([InlineKeyboardButton("📋 К списку заказов", callback_data="active_orders")])

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка при показе заказа для редактирования: {e}")
        await message_manager.send_message(
            update, context,
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            is_temporary=False
        )


async def remove_item_from_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить позицию из заказа"""
    query = update.callback_query
    await query.answer()

    # Формат: remove_item_{order_id}_{item_name}
    parts = query.data.split("_")
    if len(parts) < 4:
        await query.edit_message_text("❌ Ошибка в данных запроса.")
        return

    order_id = int(parts[2])
    item_name = "_".join(parts[3:])  # Название может содержать подчеркивания

    # Заменяем обратно подчеркивания на пробелы в названии товара
    item_name = item_name.replace('_', ' ')

    # Удаляем позицию
    success, message = menu_manager.remove_item_from_order(order_id, item_name)

    if success:
        # Показываем обновленный заказ
        await show_order_for_editing(update, context)
    else:
        await query.edit_message_text(
            f"❌ {message}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data=f"edit_order_{order_id}")
            ]])
        )


async def view_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр деталей заказа - ОБНОВЛЕННАЯ ВЕРСИЯ С КНОПКОЙ РЕДАКТИРОВАНИЯ"""
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.replace("view_order_", ""))
    order = db.get_order_by_id(order_id)
    items = menu_manager.get_order_items(order_id)
    total = menu_manager.calculate_order_total(order_id)

    message = f"📋 Детали заказа #{order_id}\n"
    message += f"🍽️ Стол: {order[1]}\n"
    message += f"📅 Создан: {format_datetime(order[4])}\n"
    message += f"📊 Статус: {order[3]}\n\n"
    message += "🛒 Позиции:\n"

    for item in items:
        item_total = item[3] * item[4]
        message += f"• {item[2]} - {item[3]}₽ x {item[4]} = {item_total}₽\n"

    message += f"\n💰 Общая сумма: {total}₽"

    # ОБНОВЛЕННАЯ КЛАВИАТУРА - добавлена кнопка редактирования
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать заказ", callback_data=f"edit_order_{order_id}")],
        [InlineKeyboardButton("➕ Добавить позиции", callback_data=f"add_items_{order_id}")],
        [InlineKeyboardButton("💰 Рассчитать", callback_data=f"calculate_{order_id}")],
        [InlineKeyboardButton("⬅️ Назад к заказам", callback_data="active_orders")]
    ]

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение деталей заказа не требует изменений")
        else:
            logger.error(f"Ошибка при просмотре деталей заказа: {e}")
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def handle_add_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки добавления позиций"""
    query = update.callback_query
    await query.answer()

    order_id = int(query.data.replace("add_items_", ""))
    context.user_data['current_order_id'] = order_id

    order = db.get_order_by_id(order_id)
    context.user_data['table_number'] = order[1]

    await query.edit_message_text(
        f"✅ Добавление позиций к заказу #{order_id} для стола {order[1]}\n\n"
        f"Выберите категорию меню:",
        reply_markup=menu_manager.get_category_keyboard()
    )