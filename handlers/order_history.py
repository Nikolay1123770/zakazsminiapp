# handlers/order_history.py
"""
Модуль истории заказов и статистики
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from keyboards.menus import PAYMENT_METHOD_NAMES
from handlers.order_utils import (
    is_admin, message_manager, menu_manager, db, logger, format_datetime,
    group_items_by_category, back_to_admin_main
)


# ИСТОРИЯ ЗАКАЗОВ - ОБНОВЛЕННАЯ ВЕРСИЯ
async def show_order_history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню истории заказов - ОБНОВЛЕННАЯ ВЕРСИЯ БЕЗ КНОПКИ 'ЗА МЕСЯЦ'"""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🔄 За смену", callback_data="history_shift")],
        [InlineKeyboardButton("📅 Выбрать смену", callback_data="history_select_shift")],
        [InlineKeyboardButton("📊 За год", callback_data="history_year")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_order_management")]
    ]

    try:
        await query.edit_message_text(
            "📊 История заказов\n\n"
            "Выберите период для просмотра:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение истории заказов не требует изменений")
        else:
            logger.error(f"Ошибка при показе меню истории заказов: {e}")
            await message_manager.send_message(
                update, context,
                "📊 История заказов\n\nВыберите период для просмотра:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def show_shift_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю за текущую смену - ОБНОВЛЕННАЯ ВЕРСИЯ С ПОДРОБНОЙ ИНФОРМАЦИЕЙ О ЗАКАЗАХ И БОНУСАМИ И ОПЛАТОЙ"""
    query = update.callback_query
    await query.answer()

    shift_number = context.bot_data.get('shift_number')
    month_year = context.bot_data.get('shift_month_year')

    if not shift_number or not month_year:
        try:
            await query.edit_message_text(
                "❌ Нет активной смены.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение ошибки смены не требует изменений")
            else:
                logger.error(f"Ошибка при показе истории смены: {e}")
                await message_manager.send_message(
                    update, context,
                    "❌ Нет активной смены.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]]),
                    is_temporary=False
                )
        return

    # Получаем ID текущей смены
    shift = db.get_shift_by_number_and_month(shift_number, month_year)
    if not shift:
        try:
            await query.edit_message_text(
                f"📭 Смена #{shift_number} ({month_year}) не найдена.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия данных не требует изменений")
            else:
                logger.error(f"Ошибка при показе истории смены: {e}")
                await message_manager.send_message(
                    update, context,
                    f"📭 Смена #{shift_number} ({month_year}) не найдена.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]]),
                    is_temporary=False
                )
        return

    shift_id = shift[0]

    # Получаем все заказы текущей смены (активные и закрытые)
    shift_orders = db.get_orders_by_shift_id(shift_id)

    if not shift_orders:
        try:
            await query.edit_message_text(
                f"📭 Нет заказов за текущую смену #{shift_number} ({month_year}).",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия данных не требует изменений")
            else:
                logger.error(f"Ошибка при показе истории смены: {e}")
                await message_manager.send_message(
                    update, context,
                    f"📭 Нет заказов за текущую смену #{shift_number} ({month_year}).",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]]),
                    is_temporary=False
                )
        return

    # Формируем подробный отчет по смене
    total_revenue = 0
    active_orders_count = 0
    closed_orders_count = 0

    message = f"📊 Текущая смена #{shift_number} ({month_year})\n\n"
    message += f"📅 Открыта: {format_datetime(shift[4])}\n"
    message += f"📋 Всего заказов: {len(shift_orders)}\n\n"

    # Получаем сумму списанных бонусов за смену
    spent_bonuses = db.get_spent_bonuses_by_shift(shift_number, month_year)

    # Получаем статистику по оплате за смену
    payment_stats = db.get_payment_statistics_by_shift(shift_number, month_year)

    # Обрабатываем каждый заказ
    for order in shift_orders:
        order_id = order[0]
        table_number = order[1]
        status = order[3]
        created_at = format_datetime(order[4])
        closed_at = format_datetime(order[5]) if order[5] else "Еще не закрыт"

        items = menu_manager.get_order_items(order_id)
        total = menu_manager.calculate_order_total(order_id)
        total_revenue += total

        # Считаем статистику по статусам
        if status == 'active':
            active_orders_count += 1
        elif status == 'closed':
            closed_orders_count += 1

        message += f"🧾 Заказ #{order_id} | Стол {table_number}\n"
        message += f"📊 Статус: {'🟢 Активен' if status == 'active' else '🔴 Закрыт'}\n"
        message += f"💰 Сумма: {total}₽\n"
        message += f"📅 Создан: {created_at}\n"

        if status == 'closed':
            message += f"📅 Закрыт: {closed_at}\n"

        # Добавляем информацию о позициях
        if items:
            message += "🛒 Позиции:\n"
            for item in items:
                item_total = item[3] * item[4]
                message += f"  • {item[2]} - {item[3]}₽ x {item[4]} = {item_total}₽\n"
        else:
            message += "🛒 Позиции: нет\n"

        message += "─" * 30 + "\n\n"

    # Добавляем общую статистику
    message += f"📈 Итоги смены:\n"
    message += f"🟢 Активных заказов: {active_orders_count}\n"
    message += f"🔴 Закрытых заказов: {closed_orders_count}\n"
    message += f"💰 Общая выручка: {total_revenue}₽\n"
    message += f"🎫 Сумма списанных бонусов: {spent_bonuses}₽\n\n"

    # Добавляем статистику по оплате
    if payment_stats:
        message += "💳 Статистика по оплате:\n"
        total_payment_count = 0
        total_payment_amount = 0

        for method, data in payment_stats.items():
            name = PAYMENT_METHOD_NAMES.get(method, method)
            message += f"  {name}: {data['count']} зак. - {data['total_amount']}₽\n"
            total_payment_count += data['count']
            total_payment_amount += data['total_amount']

        message += f"  Всего: {total_payment_count} зак. - {total_payment_amount}₽\n\n"
    else:
        message += "💳 Статистика по оплате: нет данных\n\n"

    keyboard = [
        [InlineKeyboardButton("📊 Другая статистика", callback_data="order_history")],
        [InlineKeyboardButton("⬅️ Назад в управление", callback_data="back_to_order_management")]
    ]

    # Если сообщение слишком длинное, разбиваем на части
    if len(message) > 4000:
        parts = []
        current_part = ""
        lines = message.split('\n')

        for line in lines:
            if len(current_part + line + '\n') < 4000:
                current_part += line + '\n'
            else:
                parts.append(current_part)
                current_part = line + '\n'

        if current_part:
            parts.append(current_part)

        # Отправляем первую часть с клавиатурой
        await query.edit_message_text(
            parts[0],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Остальные части отправляем как новые сообщения
        for part in parts[1:]:
            await message_manager.send_message(
                update, context,
                part,
                is_temporary=False
            )
    else:
        try:
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение истории смены не требует изменений")
            else:
                logger.error(f"Ошибка при показе истории смены: {e}")
                await message_manager.send_message(
                    update, context,
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    is_temporary=False
                )


async def show_month_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику за месяц - ОБНОВЛЕННАЯ ВЕРСИЯ С ГРУППИРОВКОЙ И БОНУСАМИ И ОПЛАТОЙ"""
    query = update.callback_query
    await query.answer()

    # Получаем статистику за месяц
    sales_stats = db.get_sales_statistics_by_period('month')
    total_revenue = db.get_total_revenue_by_period('month')

    if not sales_stats:
        try:
            await query.edit_message_text(
                "📭 Нет данных за текущий месяц.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия данных не требует изменений")
            else:
                logger.error(f"Ошибка при показе статистики месяца: {e}")
                await message_manager.send_message(
                    update, context,
                    "📭 Нет данных за текущий месяц.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]]),
                    is_temporary=False
                )
        return

    current_month = datetime.now().strftime('%B %Y')
    # Считаем общую сумму всех продаж
    total_sales_amount = sum(total_amount for _, _, total_amount in sales_stats)

    # Получаем сумму списанных бонусов за текущий месяц
    current_date = datetime.now()
    spent_bonuses = db.get_spent_bonuses_by_month(current_date.year, current_date.month)

    # Получаем статистику по оплате за месяц
    payment_stats = db.get_payment_statistics_by_period('month')

    # Группируем позиции по категориям
    categories = group_items_by_category(sales_stats)

    message = f"📊 Статистика за {current_month}\n\n"
    message += f"💰 Общая сумма продаж: {total_sales_amount}₽\n"
    message += f"🎫 Сумма списанных бонусов: {spent_bonuses}₽\n\n"

    # Добавляем статистику по оплате
    if payment_stats:
        message += "💳 Статистика по оплате:\n"
        total_payment_count = 0
        total_payment_amount = 0

        for method, data in payment_stats.items():
            name = PAYMENT_METHOD_NAMES.get(method, method)
            message += f"  {name}: {data['count']} зак. - {data['total_amount']}₽\n"
            total_payment_count += data['count']
            total_payment_amount += data['total_amount']

        message += f"  Всего: {total_payment_count} зак. - {total_payment_amount}₽\n\n"
    else:
        message += "💳 Статистика по оплате: нет данных\n\n"

    message += "📈 Продажи по категориям:\n\n"

    # Выводим категории с группировкой
    for category_key in ['Кальяны', 'Чай', 'Коктейли', 'Напитки', 'Другое']:
        category_data = categories[category_key]
        if category_data['total_quantity'] > 0:
            message += f"{category_data['name']}:\n"
            message += f"  Всего: {category_data['total_quantity']} шт. - {category_data['total_amount']}₽\n"

            # Выводим детали по позициям внутри категории
            for item_name, item_data in category_data['items'].items():
                message += f"  • {item_name}: {item_data['quantity']} шт. - {item_data['total_amount']}₽\n"
            message += "\n"

    keyboard = [
        [InlineKeyboardButton("📊 Другая статистика", callback_data="order_history")],
        [InlineKeyboardButton("⬅️ Назад в управление", callback_data="back_to_order_management")]
    ]

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение статистики месяца не требует изменений")
        else:
            logger.error(f"Ошибка при показе статистики месяца: {e}")
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def show_year_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню выбора года для статистики - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    # ИСПРАВЛЕННЫЙ ВЫЗОВ - через экземпляр db
    years = db.get_shift_years()

    if not years:
        try:
            await query.edit_message_text(
                "📭 Нет данных за предыдущие годы.\n\n"
                "Данные появятся после закрытия первой смены.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия данных не требует изменений")
            else:
                logger.error(f"Ошибка при показе статистики года: {e}")
                await message_manager.send_message(
                    update, context,
                    "📭 Нет данных за предыдущие годы.\n\nДанные появятся после закрытия первой смены.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]]),
                    is_temporary=False
                )
        return

    keyboard = []
    for year in years:
        keyboard.append([InlineKeyboardButton(f"📅 {year} год", callback_data=f"history_year_{year}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="order_history")])

    try:
        await query.edit_message_text(
            "📊 Статистика за год\n\n"
            "Выберите год для просмотра:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение выбора года не требует изменений")
        else:
            logger.error(f"Ошибка при показе выбора года: {e}")
            await message_manager.send_message(
                update, context,
                "📊 Статистика за год\n\nВыберите год для просмотра:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def select_year_for_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора года для статистики - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    year = query.data.replace("history_year_", "")
    context.user_data['selected_year'] = year

    # ИСПРАВЛЕННЫЙ ВЫЗОВ - через экземпляр db
    months = db.get_shift_months(year)

    if not months:
        try:
            await query.edit_message_text(
                f"📭 Нет данных за {year} год.\n\n"
                "Данные появятся после закрытия смен в этом году.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="history_year")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия данных не требует изменений")
            else:
                logger.error(f"Ошибка при показе месяцев: {e}")
        return

    keyboard = []

    # Добавляем кнопку "За весь год"
    keyboard.append([InlineKeyboardButton(f"📊 За весь {year} год", callback_data=f"history_full_year_{year}")])
    keyboard.append([InlineKeyboardButton("─" * 20, callback_data="separator")])  # Разделитель

    month_names = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }

    for month in months:
        month_name = month_names.get(month, month)
        # Формируем правильный callback: history_month_2024_01
        keyboard.append([InlineKeyboardButton(f"📆 {month_name}", callback_data=f"history_month_{year}_{month}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="history_year")])

    try:
        await query.edit_message_text(
            f"📊 Статистика за {year} год\n\n"
            "Выберите период:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение выбора месяца не требует изменений")
        else:
            logger.error(f"Ошибка при показе выбора месяца: {e}")
            await message_manager.send_message(
                update, context,
                f"📊 Статистика за {year} год\n\nВыберите период:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def show_full_year_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику за весь год - ОБНОВЛЕННАЯ ВЕРСИЯ С ПРОВЕРКОЙ ДАННЫХ И БОНУСАМИ И ОПЛАТОЙ"""
    query = update.callback_query
    await query.answer()

    # Извлекаем год из callback_data: history_full_year_2024
    year = query.data.replace("history_full_year_", "")
    context.user_data['selected_year'] = year

    # Получаем статистику за весь год
    sales_stats = db.get_sales_statistics_by_year(year)

    if not sales_stats:
        try:
            await query.edit_message_text(
                f"📭 Нет данных за {year} год.\n\n"
                "Данные появятся после закрытия смен в этом году.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Назад", callback_data=f"history_year_{year}")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия данных не требует изменений")
            else:
                logger.error(f"Ошибка при показе статистики года: {e}")
        return

    total_revenue = db.get_total_revenue_by_year(year)

    # Получаем сумму списанных бонусов за год
    spent_bonuses = db.get_spent_bonuses_by_year(year)

    # Получаем статистику по оплате за год
    payment_stats = db.get_payment_statistics_by_year(year)

    # Считаем общую сумму всех продаж
    total_sales_amount = sum(total_amount for _, _, total_amount in sales_stats)

    # Группируем позиции по категориям
    categories = group_items_by_category(sales_stats)

    message = f"📊 Статистика за {year} год\n\n"
    message += f"💰 Общая сумма продаж: {total_sales_amount}₽\n"
    message += f"🎫 Сумма списанных бонусов: {spent_bonuses}₽\n\n"

    # Добавляем статистику по оплате
    if payment_stats:
        message += "💳 Статистика по оплате:\n"
        total_payment_count = 0
        total_payment_amount = 0

        for method, data in payment_stats.items():
            name = PAYMENT_METHOD_NAMES.get(method, method)
            message += f"  {name}: {data['count']} зак. - {data['total_amount']}₽\n"
            total_payment_count += data['count']
            total_payment_amount += data['total_amount']

        message += f"  Всего: {total_payment_count} зак. - {total_payment_amount}₽\n\n"
    else:
        message += "💳 Статистика по оплате: нет данных\n\n"

    # Проверяем, есть ли данные для отображения
    has_data = False
    for category_key in ['Кальяны', 'Чай', 'Коктейли', 'Напитки', 'Другое']:
        category_data = categories[category_key]
        if category_data['total_quantity'] > 0:
            has_data = True
            break

    if not has_data:
        message += "📭 Нет данных о продажах за этот период."
    else:
        message += "📈 Продажи по категориям:\n\n"

        # Выводим категории с группировкой
        for category_key in ['Кальяны', 'Чай', 'Коктейли', 'Напитки', 'Другое']:
            category_data = categories[category_key]
            if category_data['total_quantity'] > 0:
                message += f"{category_data['name']}:\n"
                message += f"  Всего: {category_data['total_quantity']} шт. - {category_data['total_amount']}₽\n"

                # Выводим детали по позиции внутри категории
                for item_name, item_data in category_data['items'].items():
                    message += f"  • {item_name}: {item_data['quantity']} шт. - {item_data['total_amount']}₽\n"
                message += "\n"

    keyboard = [
        [InlineKeyboardButton("📅 Выбрать месяц", callback_data=f"history_year_{year}")],
        [InlineKeyboardButton("📊 Другая статистика", callback_data="order_history")],
        [InlineKeyboardButton("⬅️ Назад в управление", callback_data="back_to_order_management")]
    ]

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение статистики года не требует изменений")
        else:
            logger.error(f"Ошибка при показе статистики года: {e}")
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


# НОВАЯ ФУНКЦИЯ: Показ всех смен в месяце с пагинацией
async def select_month_for_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора месяца для статистики - ОБНОВЛЕННАЯ ВЕРСИЯ СО ВСЕМИ СМЕНАМИ"""
    query = update.callback_query
    await query.answer()

    # Правильный разбор данных: history_month_2024_01
    parts = query.data.split("_")
    if len(parts) != 4:
        try:
            await query.edit_message_text(
                "❌ Ошибка в данных запроса.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="history_year")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение ошибки не требует изменений")
            else:
                logger.error(f"Ошибка при разборе данных месяца: {e}")
        return

    year = parts[2]
    month = parts[3]
    context.user_data['selected_year'] = year
    context.user_data['selected_month'] = month

    # ИСПРАВЛЕННЫЙ ВЫЗОВ - через экземпляр db
    shifts = db.get_shifts_by_year_month(year, month)

    if not shifts:
        try:
            await query.edit_message_text(
                f"📭 Нет смен за выбранный период.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Назад", callback_data=f"history_year_{year}")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия смен не требует изменений")
            else:
                logger.error(f"Ошибка при показе смен: {e}")
        return

    month_names = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    month_name = month_names.get(month, month)

    keyboard = []

    # Добавляем кнопку "За весь месяц"
    keyboard.append(
        [InlineKeyboardButton(f"📊 Весь {month_name} {year}", callback_data=f"history_full_month_{year}_{month}")])
    keyboard.append([InlineKeyboardButton("─" * 20, callback_data="separator")])  # Разделитель

    # ПОКАЗЫВАЕМ ВСЕ СМЕНЫ (не только 10)
    for shift in shifts:
        shift_number = shift[1]
        month_year = shift[2]

        # Получаем информацию об администраторе
        admin_id = shift[3]  # admin_id
        admin_data = db.get_user_by_id(admin_id)

        # Формируем имя администратора
        if admin_data:
            first_name = admin_data[2] or ""
            last_name = admin_data[3] or ""
            admin_name = f"{first_name} {last_name}".strip()
            if len(admin_name) > 10:  # Обрезаем длинные имена
                admin_name = admin_name[:8] + ".."
            if not admin_name:
                admin_name = f"ID:{admin_id}"
        else:
            admin_name = f"ID:{admin_id}"

        revenue = shift[6] or 0

        # ИСПРАВЛЕННЫЙ ФОРМАТ: #{shift_number} | {admin_name} | {revenue}₽
        button_text = f"#{shift_number} | {admin_name} | {revenue}₽"

        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"history_shift_{month_year}_{shift_number}"  # Новый формат с месяцем и номером
        )])

    # Добавляем пагинацию если смен больше 50
    if len(shifts) > 50:
        keyboard.append(
            [InlineKeyboardButton("📄 Показать еще...", callback_data=f"history_month_more_{year}_{month}_2")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"history_year_{year}")])

    try:
        await query.edit_message_text(
            f"📊 Смены за {month_name} {year} года:\n\n"
            f"📋 Найдено смен: {len(shifts)}\n"
            f"👆 Выберите смену для просмотра детальной статистики",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение списка смен не требует изменений")
        else:
            logger.error(f"Ошибка при показе списка смен: {e}")


async def show_more_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать следующие смены (пагинация) - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    # Формат: history_month_more_2024_01_2
    parts = query.data.split("_")
    if len(parts) != 6:
        await query.edit_message_text("❌ Ошибка в данных запроса.")
        return

    year = parts[3]
    month = parts[4]
    page = int(parts[5])

    # ИСПРАВЛЕННЫЙ ВЫЗОВ - через экземпляр db
    shifts = db.get_shifts_by_year_month(year, month)

    if not shifts:
        await query.edit_message_text("📭 Нет смен за выбранный период.")
        return

    month_names = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    month_name = month_names.get(month, month)

    keyboard = []

    # Вычисляем диапазон для текущей страницы
    items_per_page = 50
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page

    for shift in shifts[start_idx:end_idx]:
        shift_number = shift[1]
        month_year = shift[2]

        # Получаем информацию об администраторе
        admin_id = shift[3]  # admin_id
        admin_data = db.get_user_by_id(admin_id)

        # Формируем имя администратора
        if admin_data:
            first_name = admin_data[2] or ""
            last_name = admin_data[3] or ""
            admin_name = f"{first_name} {last_name}".strip()
            if len(admin_name) > 10:  # Обрезаем длинные имена
                admin_name = admin_name[:8] + ".."
            if not admin_name:
                admin_name = f"ID:{admin_id}"
        else:
            admin_name = f"ID:{admin_id}"

        revenue = shift[6] or 0

        # ИСПРАВЛЕННЫЙ ФОРМАТ: #{shift_number} | {admin_name} | {revenue}₽
        button_text = f"#{shift_number} | {admin_name} | {revenue}₽"

        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"history_shift_{month_year}_{shift_number}"  # Новый формат
        )])

    # Добавляем навигацию по страницам
    navigation = []
    if page > 1:
        navigation.append(
            InlineKeyboardButton("⬅️ Предыдущие", callback_data=f"history_month_more_{year}_{month}_{page - 1}"))

    if end_idx < len(shifts):
        navigation.append(
            InlineKeyboardButton("Следующие ➡️", callback_data=f"history_month_more_{year}_{month}_{page + 1}"))

    if navigation:
        keyboard.append(navigation)

    keyboard.append([InlineKeyboardButton("⬅️ Назад к выбору", callback_data=f"history_year_{year}")])

    await query.edit_message_text(
        f"📊 Смены за {month_name} {year} года (стр. {page}):\n\n"
        f"📋 Всего смен: {len(shifts)}\n"
        f"👆 Выберите смену для просмотра детальной статистики",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_full_month_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику за весь месяц - ОБНОВЛЕННАЯ ВЕРСИЯ С ГРУППИРОВКОЙ И БОНУСАМИ И ОПЛАТОЙ"""
    query = update.callback_query
    await query.answer()

    year = context.user_data.get('selected_year')
    month = context.user_data.get('selected_month')

    if not year or not month:
        try:
            await query.edit_message_text(
                "❌ Год или месяц не выбран.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="history_year")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение ошибки не требует изменений")
            else:
                logger.error(f"Ошибка при показе статистики месяца: {e}")
        return

    # Получаем статистику за весь месяц
    sales_stats = db.get_sales_statistics_by_year_month(year, month)
    total_revenue = db.get_total_revenue_by_year_month(year, month)

    if not sales_stats:
        try:
            await query.edit_message_text(
                f"📭 Нет данных за выбранный период.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Назад", callback_data=f"history_year_{year}")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия данных не требует изменений")
            else:
                logger.error(f"Ошибка при показе статистики месяца: {e}")
        return

    month_names = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }
    month_name = month_names.get(month, month)

    # Получаем сумму списанных бонусов за месяц
    spent_bonuses = db.get_spent_bonuses_by_month(year, month)

    # Получаем статистику по оплате за месяц
    payment_stats = db.get_payment_statistics_by_month(year, month)

    # Считаем общую сумму всех продаж
    total_sales_amount = sum(total_amount for _, _, total_amount in sales_stats)

    # Группируем позиции по категориям
    categories = group_items_by_category(sales_stats)

    message = f"📊 Статистика за {month_name} {year} года\n\n"
    message += f"💰 Общая сумма продаж: {total_sales_amount}₽\n"
    message += f"🎫 Сумма списанных бонусов: {spent_bonuses}₽\n\n"

    # Добавляем статистику по оплате
    if payment_stats:
        message += "💳 Статистика по оплате:\n"
        total_payment_count = 0
        total_payment_amount = 0

        for method, data in payment_stats.items():
            name = PAYMENT_METHOD_NAMES.get(method, method)
            message += f"  {name}: {data['count']} зак. - {data['total_amount']}₽\n"
            total_payment_count += data['count']
            total_payment_amount += data['total_amount']

        message += f"  Всего: {total_payment_count} зак. - {total_payment_amount}₽\n\n"
    else:
        message += "💳 Статистика по оплате: нет данных\n\n"

    message += "📈 Продажи по категориям:\n\n"

    # Выводим категории с группировкой
    for category_key in ['Кальяны', 'Чай', 'Коктейли', 'Напитки', 'Другое']:
        category_data = categories[category_key]
        if category_data['total_quantity'] > 0:
            message += f"{category_data['name']}:\n"
            message += f"  Всего: {category_data['total_quantity']} шт. - {category_data['total_amount']}₽\n"

            # Выводим детали по позициям внутри категории
            for item_name, item_data in category_data['items'].items():
                message += f"  • {item_name}: {item_data['quantity']} шт. - {item_data['total_amount']}₽\n"
            message += "\n"

    keyboard = [
        [InlineKeyboardButton("📅 Выбрать смену", callback_data=f"history_year_{year}")],
        [InlineKeyboardButton("📊 Другая статистика", callback_data="order_history")],
        [InlineKeyboardButton("⬅️ Назад в управление", callback_data="back_to_order_management")]
    ]

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение статистики месяца не требует изменений")
        else:
            logger.error(f"Ошибка при показе статистики месяца: {e}")
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def show_selected_shift_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю выбранной смены - ИСПРАВЛЕННАЯ ВЕРСИЯ С ГРУППИРОВКОЙ И БОНУСАМИ И ОПЛАТОЙ"""
    query = update.callback_query
    await query.answer()

    # Формат: history_shift_2024-11_30
    if "_" in query.data:
        parts = query.data.split("_")
        if len(parts) == 4:  # Формат: history_shift_2024-11_30
            month_year = parts[2]
            shift_number = int(parts[3])
        else:  # Старый формат: history_shift_30 (для обратной совместимости)
            shift_number = int(query.data.replace("history_shift_", ""))
            # Пытаемся найти смену по номеру
            shift = db.get_shift_by_number(shift_number)
            if not shift:
                await query.edit_message_text(f"📭 Нет данных по смене #{shift_number}.")
                return
            month_year = shift[2]
    else:
        await query.edit_message_text("❌ Неверный формат данных.")
        return

    # Получаем статистику по выбранной смене
    shift_sales = db.get_shift_sales(shift_number, month_year)
    shift_info = db.get_shift_by_number_and_month(shift_number, month_year)

    if not shift_sales or not shift_info:
        try:
            await query.edit_message_text(
                f"📭 Нет данных по смене #{shift_number} ({month_year}).",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Назад", callback_data="history_select_shift")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия данных не требует изменений")
            else:
                logger.error(f"Ошибка при показе выбранной смены: {e}")
                await message_manager.send_message(
                    update, context,
                    f"📭 Нет данных по смене #{shift_number} ({month_year}).",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Назад", callback_data="history_select_shift")]]),
                    is_temporary=False
                )
        return

    # Получаем информацию об администраторе
    admin_id = shift_info[3]
    admin_data = db.get_user_by_id(admin_id)
    admin_name = f"{admin_data[2]} {admin_data[3]}" if admin_data else f"ID: {admin_id}"

    total_revenue = shift_info[6] or 0
    total_orders = shift_info[7] or 0

    # Получаем сумму списанных бонусов за смену
    spent_bonuses = db.get_spent_bonuses_by_shift(shift_number, month_year)

    # Получаем статистику по оплате за смену
    payment_stats = db.get_payment_statistics_by_shift(shift_number, month_year)

    # Считаем общую сумму всех проданных позиций за смену
    total_sales_amount = sum(total_amount for _, _, total_amount in shift_sales)

    # Группируем позиции по категориям
    categories = group_items_by_category(shift_sales)

    message = f"📊 Статистика за смену #{shift_number} ({month_year})\n\n"
    message += f"👨‍💼 Администратор: {admin_name}\n"
    message += f"📅 Открыта: {format_datetime(shift_info[4])}\n"
    if shift_info[5]:
        message += f"📅 Закрыта: {format_datetime(shift_info[5])}\n"
    message += f"📋 Заказов: {total_orders}\n"
    message += f"💰 Сумма всех продаж: {total_sales_amount}₽\n"
    message += f"🎫 Сумма списанных бонусов: {spent_bonuses}₽\n\n"

    # Добавляем статистику по оплате
    if payment_stats:
        message += "💳 Статистика по оплате:\n"
        total_payment_count = 0
        total_payment_amount = 0

        for method, data in payment_stats.items():
            name = PAYMENT_METHOD_NAMES.get(method, method)
            message += f"  {name}: {data['count']} зак. - {data['total_amount']}₽\n"
            total_payment_count += data['count']
            total_payment_amount += data['total_amount']

        message += f"  Всего: {total_payment_count} зак. - {total_payment_amount}₽\n\n"
    else:
        message += "💳 Статистика по оплате: нет данных\n\n"

    message += "📈 Продажи по категориям:\n\n"

    # Выводим категории с группировкой
    for category_key in ['Кальяны', 'Чай', 'Коктейли', 'Напитки', 'Другое']:
        category_data = categories[category_key]
        if category_data['total_quantity'] > 0:
            message += f"{category_data['name']}:\n"
            message += f"  Всего: {category_data['total_quantity']} шт. - {category_data['total_amount']}₽\n"

            # Выводим детали по позициям внутри категории
            for item_name, item_data in category_data['items'].items():
                message += f"  • {item_name}: {item_data['quantity']} шт. - {item_data['total_amount']}₽\n"
            message += "\n"

    keyboard = [
        [InlineKeyboardButton("📅 Выбрать другую смену", callback_data="history_select_shift")],
        [InlineKeyboardButton("⬅️ Назад в историю", callback_data="order_history")]
    ]

    try:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение выбранной смены не требует изменений")
        else:
            logger.error(f"Ошибка при показе выбранной смены: {e}")
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def show_select_shift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню выбора смены - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    # Получаем список всех закрытых смен
    shifts = db.get_all_shifts_sorted()

    if not shifts:
        try:
            await query.edit_message_text(
                "📭 Нет закрытых смен для просмотра.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия смен не требует изменений")
            else:
                logger.error(f"Ошибка при показе меню выбора смены: {e}")
                await message_manager.send_message(
                    update, context,
                    "📭 Нет закрытых смен для просмотра.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]]),
                    is_temporary=False
                )
        return

    keyboard = []
    for shift in shifts[:15]:  # Показываем последние 15 смен
        shift_number = shift[1]
        month_year = shift[2]

        # Получаем информацию об администраторе
        admin_id = shift[3]  # admin_id
        admin_data = db.get_user_by_id(admin_id)

        # Формируем имя администратора
        if admin_data:
            first_name = admin_data[2] or ""
            last_name = admin_data[3] or ""
            admin_name = f"{first_name} {last_name}".strip()
            if len(admin_name) > 10:  # Обрезаем длинные имена
                admin_name = admin_name[:8] + ".."
            if not admin_name:
                admin_name = f"ID:{admin_id}"
        else:
            admin_name = f"ID:{admin_id}"

        revenue = shift[6] or 0

        # ИСПРАВЛЕННЫЙ ФОРМАТ: #{shift_number} ({month_year}) | {admin_name} | {revenue}₽
        button_text = f"#{shift_number} ({month_year}) | {admin_name} | {revenue}₽"

        keyboard.append([InlineKeyboardButton(
            button_text,
            callback_data=f"history_shift_{month_year}_{shift_number}"  # Новый формат с месяцем
        )])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="order_history")])

    try:
        await query.edit_message_text(
            "📅 Выберите смену для просмотра:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение выбора смены не требует изменений")
        else:
            logger.error(f"Ошибка при показе меню выбора смены: {e}")
            await message_manager.send_message(
                update, context,
                "📅 Выберите смену для просмотра:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


# Остальные функции истории заказов
async def show_today_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать заказы за сегодня - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    today = datetime.now().strftime('%Y-%m-%d')
    orders = db.get_orders_by_date(today, status='closed')

    await show_orders_history(update, context, orders, f"за сегодня ({today})")


async def show_yesterday_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать заказы за вчера"""
    query = update.callback_query
    await query.answer()

    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    orders = db.get_orders_by_date(yesterday, status='closed')

    await show_orders_history(update, context, orders, f"за вчера ({yesterday})")


async def show_all_closed_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все закрытые заказы - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    orders = db.get_all_closed_orders()

    await show_orders_history(update, context, orders, "все закрытые")


async def show_select_date_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню выбора даты - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    # Получаем список дат, по которым есть закрытые заказы
    dates = db.get_order_dates()

    if not dates:
        try:
            await query.edit_message_text(
                "📭 Нет доступных дат для просмотра.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]])
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                logger.debug("Сообщение отсутствия дат не требует изменений")
            else:
                logger.error(f"Ошибка при показе меню дат: {e}")
                await message_manager.send_message(
                    update, context,
                    "📭 Нет доступных дат для просмотра.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]]),
                    is_temporary=False
                )
        return

    keyboard = []
    row = []
    for i, date in enumerate(dates):
        row.append(InlineKeyboardButton(date, callback_data=f"history_date_{date}"))
        if len(row) == 2 or i == len(dates) - 1:
            keyboard.append(row)
            row = []

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="order_history")])

    try:
        await query.edit_message_text(
            "📅 Выберите дату для просмотра заказов:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        if "Message is not modified" in str(e):
            logger.debug("Сообщение меню дат не требует изменений")
        else:
            logger.error(f"Ошибка при показе меню дат: {e}")
            await message_manager.send_message(
                update, context,
                "📅 Выберите дату для просмотра заказов:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                is_temporary=False
            )


async def show_orders_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать заказы по выбранной дате - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()

    date = query.data.replace("history_date_", "")
    orders = db.get_orders_by_date(date, status='closed')

    await show_orders_history(update, context, orders, f"за {date}")


async def show_orders_history(update: Update, context: ContextTypes.DEFAULT_TYPE, orders, period_text):
    """Показать историю заказов с полной информацией"""
    query = update.callback_query

    if not orders:
        await query.edit_message_text(
            f"📭 Нет закрытых заказов {period_text}.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="order_history")]])
        )
        return

    total_revenue = 0
    total_orders = len(orders)

    message = f"📊 История заказов ({period_text})\n\n"
    message += f"📋 Всего заказов: {total_orders}\n"

    for order in orders:
        items = menu_manager.get_order_items(order[0])
        total = menu_manager.calculate_order_total(order[0])
        total_revenue += total

        # Получаем информацию об администраторе
        admin_info = "Неизвестный администратор"
        if order[2]:  # admin_id
            admin_data = db.get_user_by_id(order[2])
            if admin_data:
                admin_info = f"{admin_data[2]} {admin_data[3]} (ID: {admin_data[0]})"

        message += f"\n🧾 Заказ #{order[0]} | Стол {order[1]}\n"
        message += f"💰 Сумма: {total}₽\n"
        message += f"👨‍💼 Админ: {admin_info}\n"
        message += f"📅 Создан: {format_datetime(order[4])}\n"

        # Добавляем время закрытия если заказ закрыт
        if order[5]:  # closed_at
            message += f"📅 Закрыт: {format_datetime(order[5])}\n"

        # Показываем ВЕСЬ список товаров
        if items:
            message += "🛒 Позиции:\n"
            for item in items:
                item_total = item[3] * item[4]
                message += f"  • {item[2]} - {item[3]}₽ x {item[4]} = {item_total}₽\n"
        message += "─" * 30 + "\n"

    message += f"\n💰 Общая выручка: {total_revenue}₽"

    keyboard = [
        [InlineKeyboardButton("📊 Другая дата", callback_data="order_history")],
        [InlineKeyboardButton("⬅️ Назад в управление", callback_data="back_to_order_management")]
    ]

    # Если сообщение слишком длинное, разбиваем на части
    if len(message) > 4000:
        parts = []
        current_part = ""
        lines = message.split('\n')

        for line in lines:
            if len(current_part + line + '\n') < 4000:
                current_part += line + '\n'
            else:
                parts.append(current_part)
                current_part = line + '\n'

        if current_part:
            parts.append(current_part)

        # Отправляем первую часть с клавиатурой
        await query.edit_message_text(
            parts[0],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Остальные части отправляем как новые сообщения
        for part in parts[1:]:
            await message_manager.send_message(
                update, context,
                part,
                is_temporary=False
            )
    else:
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )