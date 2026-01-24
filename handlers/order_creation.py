# handlers/order_creation.py
"""
Модуль создания заказов
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.order_utils import is_admin, message_manager, menu_manager, db, logger


async def handle_create_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки создания заказа"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    # Проверяем, открыта ли смена
    if not context.bot_data.get('shift_open', False):
        await query.edit_message_text(
            "❌ Смена закрыта! Сначала откройте смену.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔓 Открыть смену", callback_data="open_shift"),
                                                InlineKeyboardButton("⬅️ Назад",
                                                                     callback_data="back_to_order_management")]])
        )
        return

    # Устанавливаем флаг, что ожидаем ввод номера стола
    context.user_data['expecting_table_number'] = True

    await message_manager.send_message(
        update, context,
        "Введите номер стола:",
        is_temporary=False
    )


async def handle_table_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода номера стола"""
    if not is_admin(update.effective_user.id):
        return

    # Убираем флаг ожидания номера стола
    context.user_data.pop('expecting_table_number', None)

    try:
        table_number = int(update.message.text.strip())
        context.user_data['table_number'] = table_number

        # Проверяем, нет ли уже активного заказа на этот стол
        existing_order = db.get_active_order_by_table(table_number)
        if existing_order:
            await message_manager.send_message(
                update, context,
                f"⚠️ На столе {table_number} уже есть активный заказ.\n"
                f"Хотите добавить позиции к существующему заказу?",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("✅ Да", callback_data=f"add_to_existing_{existing_order[0]}"),
                      InlineKeyboardButton("❌ Нет", callback_data="cancel_order")]]),
                is_temporary=False
            )
            return

        # ДОБАВЬТЕ ОТЛАДКУ ЗДЕСЬ:
        telegram_id = update.effective_user.id
        print(f"🔄 DEBUG: Ищем пользователя с telegram_id: {telegram_id}")

        user_data = db.get_user(telegram_id)

        if user_data:
            print(f"✅ DEBUG: Найден пользователь: ID={user_data[0]}, Имя={user_data[2]}, Фамилия={user_data[3]}")
        else:
            print(f"❌ DEBUG: Пользователь не найден в базе")

        if not user_data:
            await message_manager.send_message(
                update, context,
                "❌ Пользователь не найден в базе данных. Попробуйте выполнить /start",
                is_temporary=True
            )
            return

        user_id = user_data[0]  # id из таблицы users
        print(f"🔄 DEBUG: Создаем заказ для user_id: {user_id}")

        # Создаем новый заказ с user_id
        order_id = menu_manager.create_order(table_number, user_id)
        print(f"✅ DEBUG: Создан заказ #{order_id} для стола {table_number}, admin_id={user_id}")

        context.user_data['current_order_id'] = order_id

        await message_manager.send_message(
            update, context,
            f"✅ Заказ #{order_id} создан для стола {table_number}\n\n"
            f"Выберите категорию меню:",
            reply_markup=menu_manager.get_category_keyboard(),
            is_temporary=False
        )

    except ValueError:
        await message_manager.send_message(
            update, context,
            "❌ Пожалуйста, введите корректный номер стола:",
            is_temporary=True
        )


async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора категории меню - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("category_"):
        category = query.data.replace("category_", "")
        context.user_data['current_category'] = category

        try:
            await query.edit_message_text(
                f"🍽️ Категория: {category}\n\n"
                f"Выберите позицию:",
                reply_markup=menu_manager.get_items_keyboard(category)
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение выбора категории не требует изменений")
            else:
                logger.error(f"Ошибка при выборе категории: {e}")
                await message_manager.send_message(
                    update, context,
                    f"🍽️ Категория: {category}\n\nВыберите позицию:",
                    reply_markup=menu_manager.get_items_keyboard(category),
                    is_temporary=False
                )

    elif query.data == "back_to_categories":
        try:
            await query.edit_message_text(
                "Выберите категорию меню:",
                reply_markup=menu_manager.get_category_keyboard()
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение категорий не требует изменений")
            else:
                logger.error(f"Ошибка при возврате к категориям: {e}")
                await message_manager.send_message(
                    update, context,
                    "Выберите категорию меню:",
                    reply_markup=menu_manager.get_category_keyboard(),
                    is_temporary=False
                )

    elif query.data == "cancel_order":
        from handlers.order_utils import cancel_order_creation
        await cancel_order_creation(update, context)


async def handle_item_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора позиции меню - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("item_"):
        item_name = query.data.replace("item_", "")
        order_id = context.user_data['current_order_id']

        # Добавляем позицию в заказ
        success = menu_manager.add_item_to_order(order_id, item_name)

        if success:
            item = menu_manager.get_item_by_name(item_name)
            try:
                await query.edit_message_text(
                    f"✅ Добавлено: {item_name} - {item[1]}₽\n\n"
                    f"Продолжайте выбирать позиции или нажмите 'Готово'",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                        "➕ Добавить еще",
                        callback_data=f"back_to_category_{context.user_data['current_category']}"),
                        InlineKeyboardButton("✅ Готово", callback_data="finish_order")
                    ]])
                )
            except Exception as e:
                if "Message is not modified" in str(e):
                    logger.debug("Сообщение добавления позиции не требует изменений")
                else:
                    logger.error(f"Ошибка при добавлении позиции: {e}")
                    await message_manager.send_message(
                        update, context,
                        f"✅ Добавлено: {item_name} - {item[1]}₽\n\nПродолжайте выбирать позиции или нажмите 'Готово'",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                            "➕ Добавить еще",
                            callback_data=f"back_to_category_{context.user_data['current_category']}"),
                            InlineKeyboardButton("✅ Готово", callback_data="finish_order")
                        ]]),
                        is_temporary=False
                    )
        else:
            try:
                await query.edit_message_text(
                    "❌ Ошибка при добавлении позиции",
                    reply_markup=menu_manager.get_category_keyboard()
                )
            except Exception as e:
                if "Message is not modified" in str(e):
                    logger.debug("Сообщение ошибки добавления не требует изменений")
                else:
                    logger.error(f"Ошибка при добавлении позиции: {e}")
                    await message_manager.send_message(
                        update, context,
                        "❌ Ошибка при добавлении позиции",
                        reply_markup=menu_manager.get_category_keyboard(),
                        is_temporary=False
                    )

    elif query.data.startswith("back_to_category_"):
        category = query.data.replace("back_to_category_", "")
        try:
            await query.edit_message_text(
                f"🍽️ Категория: {category}\n\nВыберите позицию:",
                reply_markup=menu_manager.get_items_keyboard(category)
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение возврата к категории не требует изменений")
            else:
                logger.error(f"Ошибка при возврате к категории: {e}")
                await message_manager.send_message(
                    update, context,
                    f"🍽️ Категория: {category}\n\nВыберите позицию:",
                    reply_markup=menu_manager.get_items_keyboard(category),
                    is_temporary=False
                )

    elif query.data == "back_to_categories":
        try:
            await query.edit_message_text(
                "Выберите категорию меню:",
                reply_markup=menu_manager.get_category_keyboard()
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение категорий не требует изменений")
            else:
                logger.error(f"Ошибка при возврате к категориям: {e}")
                await message_manager.send_message(
                    update, context,
                    "Выберите категорию меню:",
                    reply_markup=menu_manager.get_category_keyboard(),
                    is_temporary=False
                )

    elif query.data == "finish_order":
        await finish_order(update, context)

    elif query.data == "cancel_order":
        from handlers.order_utils import cancel_order_creation
        await cancel_order_creation(update, context)


async def finish_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение создания заказа - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    order_id = context.user_data['current_order_id']
    table_number = context.user_data['table_number']

    # Получаем все позиции заказа
    items = menu_manager.get_order_items(order_id)
    total = menu_manager.calculate_order_total(order_id)

    from handlers.order_utils import format_datetime
    message = f"✅ Заказ #{order_id} для стола {table_number} завершен!\n\n"
    message += "📋 Состав заказа:\n"
    for item in items:
        message += f"• {item[2]} - {item[3]}₽ x {item[4]} = {item[3] * item[4]}₽\n"
    message += f"\n💰 Общая сумма: {total}₽"

    try:
        await query.edit_message_text(message)
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение завершения заказа не требует изменений")
        else:
            logger.error(f"Ошибка при завершении заказа: {e}")
            await message_manager.send_message(
                update, context,
                message,
                is_temporary=False
            )

    # Очищаем данные
    context.user_data.clear()


async def handle_back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки возврата к категориям - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    try:
        await query.edit_message_text(
            "Выберите категорию меню:",
            reply_markup=menu_manager.get_category_keyboard()
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение категорий не требует изменений")
        else:
            logger.error(f"Ошибка при возврате к категориям: {e}")
            await message_manager.send_message(
                update, context,
                "Выберите категорию меню:",
                reply_markup=menu_manager.get_category_keyboard(),
                is_temporary=False
            )