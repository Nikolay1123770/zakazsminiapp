# handlers/order_shift.py
"""
Модуль управления сменами
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from message_manager import message_manager
from menu_manager import menu_manager
from database import Database
import logging
from datetime import datetime
from handlers.order_utils import is_admin, format_datetime, db, logger

# СИСТЕМА УПРАВЛЕНИЯ СМЕНОЙ
async def open_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открытие смены - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    # Находим user_id по telegram_id
    user_data = db.get_user(query.from_user.id)
    if not user_data:
        await query.edit_message_text("❌ Пользователь не найден в базе данных.")
        return

    user_id = user_data[0]  # id из таблицы users

    # Проверяем, не открыта ли уже смена
    active_orders = db.get_active_orders()
    if active_orders:
        try:
            await query.edit_message_text(
                "⚠️ Смена уже открыта! Есть активные заказы.\n\n"
                "Для закрытия смены сначала закройте все активные заказы.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders"),
                      InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение открытия смены не требует изменений")
            else:
                logger.error(f"Ошибка при открытии смены: {e}")
                await message_manager.send_message(
                    update, context,
                    "⚠️ Смена уже открыта! Есть активные заказы.\n\nДля закрытия смены сначала закройте все активные заказы.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders"),
                          InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]]),
                    is_temporary=False
                )
        return

    # Создаем новую смену в базе данных с текущим месяцем
    current_month = datetime.now().strftime('%Y-%m')
    shift_number = db.create_shift(user_id, current_month)  # Используем user_id, а не telegram_id

    # Сохраняем в context для текущей сессии
    context.bot_data['shift_open'] = True
    context.bot_data['shift_number'] = shift_number
    context.bot_data['shift_month_year'] = current_month  # Добавляем месяц
    context.bot_data['shift_opened_at'] = db.get_moscow_time()
    context.bot_data['shift_admin'] = user_id  # Сохраняем user_id, а не telegram_id

    try:
        await query.edit_message_text(
            f"✅ Смена #{shift_number} ({current_month}) открыта!\n\n"
            f"⏰ Время открытия: {format_datetime(context.bot_data['shift_opened_at'])}\n\n"
            "Теперь вы можете создавать заказы и управлять ими.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Создать заказ", callback_data="create_order"),
                                                InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders")
                                                ],
                                               [InlineKeyboardButton("📊 История заказов",
                                                                     callback_data="order_history"),
                                                InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")
                                                ],
                                               [InlineKeyboardButton("⬅️ Назад",
                                                                     callback_data="back_to_order_management")
                                                ]])
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение открытия смены не требует изменений")
        else:
            logger.error(f"Ошибка при открытии смены: {e}")
            await message_manager.send_message(
                update, context,
                f"✅ Смена #{shift_number} ({current_month}) открыта!\n\nТеперь вы можете создавать заказы и управлять ими.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("➕ Создать заказ", callback_data="create_order"),
                      InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders")
                      ],
                     [InlineKeyboardButton("📊 История заказов", callback_data="order_history"),
                      InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")
                      ],
                     [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")
                      ]]),
                is_temporary=False
            )


async def close_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрытие смены - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    # Проверяем, есть ли активные заказы
    active_orders = db.get_active_orders()
    if active_orders:
        try:
            await query.edit_message_text(
                f"⚠️ Нельзя закрыть смену! Есть активные заказы: {len(active_orders)}\n\n"
                "Пожалуйста, закройте все заказы перед закрытием смены.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders")],
                     [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение закрытия смены не требует изменений")
            else:
                logger.error(f"Ошибка при закрытии смены: {e}")
                await message_manager.send_message(
                    update, context,
                    f"⚠️ Нельзя закрыть смену! Есть активные заказы: {len(active_orders)}\n\nПожалуйста, закройте все заказы перед закрытием смены.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders")],
                         [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]]),
                    is_temporary=False
                )
        return

    shift_number = context.bot_data.get('shift_number')
    month_year = context.bot_data.get('shift_month_year')

    if not shift_number or not month_year:
        try:
            await query.edit_message_text("❌ Ошибка: данные смены не найдены.")
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение ошибки смены не требует изменений")
            else:
                logger.error(f"Ошибка при закрытии смены: {e}")
                await message_manager.send_message(
                    update, context,
                    "❌ Ошибка: данные смены не найдены.",
                    is_temporary=True
                )
        return

    # Получаем ID текущей смены
    shift = db.get_shift_by_number_and_month(shift_number, month_year)
    if not shift:
        await query.edit_message_text("❌ Смена не найдена в базе данных.")
        return

    shift_id = shift[0]

    # Получаем информацию об администраторе
    admin_id = shift[3]  # shift[3] = admin_id
    admin_data = db.get_user_by_id(admin_id)

    # Формируем имя администратора
    if admin_data:
        first_name = admin_data[2] or ""
        last_name = admin_data[3] or ""
        admin_name = f"{first_name} {last_name}".strip()
        if not admin_name:
            admin_name = f"ID: {admin_id}"
    else:
        admin_name = f"ID: {admin_id} (пользователь не найден)"

    # Получаем заказы за смену
    shift_orders = db.get_orders_by_shift_id(shift_id)

    # Правильно считаем общую сумму всех продаж
    total_sales_amount = 0
    sales_data = {}

    for order in shift_orders:
        items = menu_manager.get_order_items(order[0])
        for item in items:
            item_name = item[2]
            quantity = item[4]
            price = item[3]
            item_total_amount = price * quantity

            # Суммируем общую сумму продаж
            total_sales_amount += item_total_amount

            if item_name not in sales_data:
                sales_data[item_name] = {'quantity': 0, 'total_amount': 0}

            sales_data[item_name]['quantity'] += quantity
            sales_data[item_name]['total_amount'] += item_total_amount

    # Сохраняем статистику в базу
    db.close_shift(shift_number, month_year, total_sales_amount, len(shift_orders))
    db.save_shift_sales(shift_number, month_year, sales_data)

    # Закрываем смену в context
    context.bot_data['shift_open'] = False
    context.bot_data['shift_closed_at'] = db.get_moscow_time()

    # Формируем сообщение со статистикой - ДОБАВЛЕНО ИМЯ АДМИНИСТРАТОРА
    message = (
        f"🔒 Смена #{shift_number} ({month_year}) закрыта!\n\n"
        f"👨‍💼 Администратор: {admin_name}\n"
        f"📅 Открыта: {format_datetime(shift[4])}\n"  # shift[4] = opened_at
        f"📅 Закрыта: {format_datetime(context.bot_data['shift_closed_at'])}\n"
        f"💰 Сумма всех продаж: {total_sales_amount}₽\n"
        f"📋 Количество заказов: {len(shift_orders)}\n\n"
    )

    # Добавляем все проданные позиции
    if sales_data:
        message += "📈 Продажи по позициям:\n"
        sorted_sales = sorted(sales_data.items(), key=lambda x: x[1]['total_amount'], reverse=True)
        for i, (item_name, data) in enumerate(sorted_sales, 1):
            message += f"{i}. {item_name}: {data['quantity']} шт. - {data['total_amount']}₽\n"

    message += "\nСпасибо за работу! 🏮"

    keyboard = [
        [InlineKeyboardButton("📊 История заказов", callback_data="order_history")],
        [InlineKeyboardButton("🍽️ Управление заказов", callback_data="back_to_order_management")]
    ]

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение закрытия смены не требует изменений")
        else:
            logger.error(f"Ошибка при закрытии смены: {e}")
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def calculate_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассчитать все активные заказы - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    active_orders = db.get_active_orders()
    if not active_orders:
        await query.edit_message_text("📭 Нет активных заказов для расчета.")
        return

    total_revenue = 0
    calculated_count = 0

    # Сначала показываем сообщение о начале расчета
    await query.edit_message_text(
        f"🔄 Начинаю расчет {len(active_orders)} заказов...",
        reply_markup=None
    )

    # Рассчитываем каждый заказ
    for order in active_orders:
        order_id = order[0]
        items = menu_manager.get_order_items(order_id)

        if items and len(items) > 0:  # Проверяем что есть позиции
            try:
                total = menu_manager.calculate_order_total(order_id)
                total_revenue += total

                # Закрываем заказ напрямую через базу
                cursor = db.conn.cursor()
                cursor.execute('''
                    UPDATE orders SET status = 'closed', closed_at = ? WHERE id = ?
                ''', (db.get_moscow_time(), order_id))
                db.conn.commit()

                calculated_count += 1

                # Показываем прогресс
                if calculated_count % 3 == 0:  # Обновляем каждые 3 заказа
                    await query.edit_message_text(
                        f"🔄 Рассчитано {calculated_count}/{len(active_orders)} заказов...",
                        reply_markup=None
                    )

            except Exception as e:
                logger.error(f"Ошибка при расчете заказа {order_id}: {e}")
                continue

    # Финальное сообщение
    if calculated_count > 0:
        message = (
            f"✅ Расчет завершен!\n\n"
            f"📊 Результаты:\n"
            f"✅ Успешно: {calculated_count} заказов\n"
            f"❌ Не удалось: {len(active_orders) - calculated_count} заказов\n"
            f"💰 Общая выручка: {total_revenue}₽\n\n"
        )

        remaining_orders = db.get_active_orders()
        if remaining_orders:
            message += f"⚠️ Осталось активных заказов: {len(remaining_orders)}\n\n"
            keyboard = [
                [InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders")],
                [InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]
            ]
        else:
            message += "✅ Все заказы рассчитаны! Теперь можно закрыть смену.\n\n"
            keyboard = [
                [InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]
            ]

        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_shift_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус смены - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    shift_open = context.bot_data.get('shift_open', False)
    active_orders = db.get_active_orders()

    if shift_open:
        shift_number = context.bot_data.get('shift_number', 'Неизвестно')
        month_year = context.bot_data.get('shift_month_year', 'Неизвестно')
        shift_opened_at = context.bot_data.get('shift_opened_at', 'Неизвестно')
        message = (
            f"🟢 Смена #{shift_number} ({month_year}) открыта\n\n"
            f"📅 Время открытия: {shift_opened_at}\n"
            f"📋 Активных заказов: {len(active_orders)}\n"
            f"👨‍💼 Администратор: ID {context.bot_data.get('shift_admin', 'Неизвестно')}"
        )
    else:
        message = "🔴 Смена закрыта\n\nДля начала работы откройте смену."

    keyboard = [
        [InlineKeyboardButton("📊 История заказов", callback_data="order_history")],
        [InlineKeyboardButton("🍽️ Управление заказами", callback_data="back_to_order_management")]
    ]

    if shift_open:
        keyboard[0].insert(0, InlineKeyboardButton("➕ Создать заказ", callback_data="create_order"))
        keyboard[0].insert(1, InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders"))
        keyboard.append([InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")])
    else:
        keyboard.insert(0, [InlineKeyboardButton("🔓 Открыть смену", callback_data="open_shift")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")])

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение статуса смены не требует изменений")
        else:
            logger.error(f"Ошибка при показе статуса смены: {e}")
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def start_order_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало управления заказами с отображением статуса смены - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    if not is_admin(update.effective_user.id):
        await message_manager.send_message(update, context, "❌ У вас нет доступа к этой команде.", is_temporary=True)
        return

    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    shift_open = context.bot_data.get('shift_open', False)
    active_orders = db.get_active_orders()

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    if shift_open:
        # Меню когда смена открыта
        shift_number = context.bot_data.get('shift_number', 'Неизвестно')
        month_year = context.bot_data.get('shift_month_year', 'Неизвестно')
        keyboard = [
            [InlineKeyboardButton("➕ Создать заказ", callback_data="create_order")],
            [InlineKeyboardButton("📋 Активные заказы", callback_data="active_orders")],
            [InlineKeyboardButton("📊 История заказов", callback_data="order_history")],
            [InlineKeyboardButton("🔒 Закрыть смену", callback_data="close_shift")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin")]
        ]

        shift_opened_at = context.bot_data.get('shift_opened_at', 'Неизвестно')
        message = (
            f"🍽️ Управление заказами | Смена #{shift_number} ({month_year})\n\n"
            f"🟢 Смена открыта\n"
            f"⏰ Открыта: {format_datetime(shift_opened_at)}\n"
            f"📋 Активных заказов: {len(active_orders)}\n\n"
            "Выберите действие:"
        )
    else:
        # Меню когда смена закрыта
        keyboard = [
            [InlineKeyboardButton("🔓 Открыть смену", callback_data="open_shift")],
            [InlineKeyboardButton("📊 История заказов", callback_data="order_history")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin")]
        ]

        message = (
            "🍽️ Управление заказами\n\n"
            "🔴 Смена закрыта\n\n"
            "Для начала работы откройте смену."
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            # Пытаемся редактировать сообщение
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
        except Exception as e:
            if "Message is not modified" in str(e):
                # Если сообщение не изменилось, просто игнорируем ошибку
                logger.debug("Сообщение не требует изменений")
            else:
                # Для других ошибок показываем новое сообщение
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                await message_manager.send_message(
                    update, context,
                    message,
                    reply_markup=reply_markup,
                    is_temporary=False
                )
    else:
        await message_manager.send_message(
            update, context,
            message,
            reply_markup=reply_markup,
            is_temporary=False
        )