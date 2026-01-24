"""
Управление бронированиями: фильтрация, подтверждение, отмена
"""
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton  # УЖЕ ЕСТЬ
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_IDS
from database import Database

logger = logging.getLogger(__name__)
db = Database()

# Состояния для фильтрации бронирований
SELECTING_YEAR, SELECTING_MONTH, SELECTING_DATE, AWAITING_CANCELLATION_REASON = range(4)


def is_admin(user_id):
    return user_id in ADMIN_IDS


def _format_booking_message(booking):
    """Форматирует сообщение о бронировании"""
    status_emoji = {
        'pending': '⏳',
        'confirmed': '✅',
        'cancelled': '❌'
    }

    status_text = {
        'pending': 'Ожидание',
        'confirmed': 'Подтверждено',
        'cancelled': 'Отменено'
    }

    return (
        f"{status_emoji.get(booking[5], '📅')} Бронирование #{booking[0]}\n"
        f"👤 {booking[7]} {booking[8]}\n"
        f"📱 {booking[9]}\n"
        f"📅 Дата: {booking[2]}\n"
        f"⏰ Время: {booking[3]}\n"
        f"👥 Гостей: {booking[4]}\n"
        f"📊 Статус: {status_text.get(booking[5], booking[5])}\n"
        f"🆔 ID брони: {booking[0]}"
    )


async def show_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню управления бронированиями"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    from keyboards.menus import get_booking_filter_menu

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    # Получаем статистику бронирований
    stats = db.get_booking_stats()

    message = (
        "📅 Управление бронированиями\n\n"
        f"📊 Статистика:\n"
        f"⏳ Ожидающие: {stats.get('pending', 0)}\n"
        f"✅ Подтвержденные: {stats.get('confirmed', 0)}\n"
        f"❌ Отмененные: {stats.get('cancelled', 0)}\n"
        f"📋 Всего: {stats.get('total', 0)}\n\n"
        "Выберите тип фильтрации:"
    )

    # Меню фильтрации - постоянное сообщение
    await message_manager.send_message(
        update, context,
        message,
        reply_markup=get_booking_filter_menu(),
        is_temporary=False
    )


async def show_pending_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ожидающие бронирования"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    from keyboards.menus import get_booking_filter_menu, get_booking_actions_keyboard

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    bookings = db.get_bookings_by_status('pending')

    if not bookings:
        await message_manager.send_message(
            update, context,
            "⏳ Нет ожидающих бронирований.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return

    await message_manager.send_message(
        update, context,
        f"⏳ Ожидающие бронирования ({len(bookings)}):",
        reply_markup=get_booking_filter_menu(),
        is_temporary=False
    )

    for booking in bookings:
        message = _format_booking_message(booking)
        await message_manager.send_message(
            update, context,
            message,
            reply_markup=get_booking_actions_keyboard(booking[0]),
            is_temporary=False
        )


async def show_confirmed_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подтвержденные бронирования"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    from keyboards.menus import get_booking_filter_menu

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    bookings = db.get_bookings_by_status('confirmed')

    if not bookings:
        await message_manager.send_message(
            update, context,
            "✅ Нет подтвержденных бронирований.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return

    await message_manager.send_message(
        update, context,
        f"✅ Подтвержденные бронирования ({len(bookings)}):",
        reply_markup=get_booking_filter_menu(),
        is_temporary=False
    )

    for booking in bookings:
        message = _format_booking_message(booking)
        await message_manager.send_message(
            update, context,
            message,
            is_temporary=False
        )


async def show_cancelled_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать отмененные бронирования"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    from keyboards.menus import get_booking_filter_menu

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    bookings = db.get_bookings_by_status('cancelled')

    if not bookings:
        await message_manager.send_message(
            update, context,
            "❌ Нет отмененных бронирований.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return

    await message_manager.send_message(
        update, context,
        f"❌ Отмененные бронирования ({len(bookings)}):",
        reply_markup=get_booking_filter_menu(),
        is_temporary=False
    )

    for booking in bookings:
        message = _format_booking_message(booking)
        await message_manager.send_message(
            update, context,
            message,
            is_temporary=False
        )


async def show_all_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все бронирования"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    from keyboards.menus import get_booking_filter_menu, get_booking_actions_keyboard

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    bookings = db.get_all_bookings_sorted()

    if not bookings:
        await message_manager.send_message(
            update, context,
            "📭 Бронирования не найдены.",
            is_temporary=True
        )
        return

    await message_manager.send_message(
        update, context,
        f"📋 Все бронирования ({len(bookings)}):",
        is_temporary=False
    )

    for booking in bookings:
        message = _format_booking_message(booking)

        # Для ожидающих бронирований показываем кнопки действий
        if booking[5] == 'pending':
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=get_booking_actions_keyboard(booking[0]),
                is_temporary=False
            )
        else:
            await message_manager.send_message(
                update, context,
                message,
                is_temporary=False
            )


# Функции для фильтрации бронирований по году/месяцу/дате
def get_booking_years():
    """Получить список годов, в которых есть бронирования"""
    cursor = db.conn.cursor()
    try:
        cursor.execute('''
            SELECT DISTINCT booking_date 
            FROM bookings 
            WHERE booking_date IS NOT NULL AND booking_date != ''
            ORDER BY booking_date DESC
        ''')
        dates = cursor.fetchall()

        years_set = set()
        for date_tuple in dates:
            date_str = date_tuple[0]
            if date_str and '.' in date_str:
                try:
                    day, month, year = date_str.split('.')
                    if len(year) == 4 and year.isdigit():
                        years_set.add(year)
                except ValueError:
                    continue

        years = sorted(years_set, reverse=True)
        logger.info(f"🔍 Найдено годов с бронированиями: {years}")
        return years

    except Exception as e:
        logger.error(f"❌ Ошибка при получении годов бронирований: {e}")
        return []


def get_booking_months(year):
    """Получить список месяцев для указанного года"""
    cursor = db.conn.cursor()
    try:
        cursor.execute('''
            SELECT DISTINCT booking_date 
            FROM bookings 
            WHERE booking_date IS NOT NULL AND booking_date != ''
            ORDER BY booking_date DESC
        ''')
        dates = cursor.fetchall()

        months_set = set()
        for date_tuple in dates:
            date_str = date_tuple[0]
            if date_str and '.' in date_str:
                try:
                    day, month, date_year = date_str.split('.')
                    if date_year == year and len(month) == 2 and month.isdigit():
                        months_set.add(month)
                except ValueError:
                    continue

        months = sorted(months_set, reverse=True)
        logger.info(f"🔍 Найдено месяцев за {year} год: {months}")
        return months

    except Exception as e:
        logger.error(f"❌ Ошибка при получении месяцев бронирований: {e}")
        return []


def get_booking_dates_by_year_month(year, month):
    """Получить список дат для указанного года и месяца"""
    cursor = db.conn.cursor()
    try:
        cursor.execute('''
            SELECT DISTINCT booking_date 
            FROM bookings 
            WHERE booking_date IS NOT NULL AND booking_date != ''
            ORDER BY booking_date DESC
        ''')
        dates = cursor.fetchall()

        filtered_dates = []
        for date_tuple in dates:
            date_str = date_tuple[0]
            if date_str and '.' in date_str:
                try:
                    day, date_month, date_year = date_str.split('.')
                    if date_year == year and date_month == month:
                        filtered_dates.append(date_str)
                except ValueError:
                    continue

        logger.info(f"🔍 Найдено дат за {month}.{year}: {filtered_dates}")
        return filtered_dates

    except Exception as e:
        logger.error(f"❌ Ошибка при получении дат бронирований: {e}")
        return []


async def show_dates_for_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список годов для фильтрации"""
    if not is_admin(update.effective_user.id):
        return

    years = get_booking_years()

    if not years:
        from message_manager import message_manager
        from keyboards.menus import get_booking_filter_menu
        await message_manager.send_message(
            update, context,
            "📭 Нет доступных годов для фильтрации.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return

    keyboard = []
    for year in years:
        keyboard.append([KeyboardButton(f"📅 {year} год")])
    keyboard.append([KeyboardButton("❌ Отмена")])

    from message_manager import message_manager
    await message_manager.send_message(
        update, context,
        "📅 Выберите год для просмотра бронирований:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
        is_temporary=False
    )
    return SELECTING_YEAR


async def select_year_for_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора года"""
    if update.message.text == "❌ Отмена":
        from message_manager import message_manager
        from keyboards.menus import get_booking_filter_menu
        await message_manager.send_message(
            update, context,
            "❌ Поиск по дате отменен.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    if not is_admin(update.effective_user.id):
        return

    year = update.message.text.replace("📅 ", "").replace(" год", "").strip()
    context.user_data['selected_year'] = year

    months = get_booking_months(year)

    if not months:
        from message_manager import message_manager
        from keyboards.menus import get_booking_filter_menu
        await message_manager.send_message(
            update, context,
            f"📭 Нет бронирований за {year} год.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    keyboard = []
    month_names = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель',
        '05': 'Май', '06': 'Июнь', '07': 'Июль', '08': 'Август',
        '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    }

    for month in months:
        month_name = month_names.get(month, month)
        keyboard.append([KeyboardButton(f"📆 {month_name}")])
    keyboard.append([KeyboardButton("❌ Отмена")])

    from message_manager import message_manager
    await message_manager.send_message(
        update, context,
        f"📅 Выберите месяц {year} года:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
        is_temporary=False
    )
    return SELECTING_MONTH


async def select_month_for_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора месяца"""
    if update.message.text == "❌ Отмена":
        from message_manager import message_manager
        from keyboards.menus import get_booking_filter_menu
        await message_manager.send_message(
            update, context,
            "❌ Поиск по дате отменен.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    if not is_admin(update.effective_user.id):
        return

    month_text = update.message.text.replace("📆 ", "").strip()
    month_names = {
        'Январь': '01', 'Февраль': '02', 'Март': '03', 'Апрель': '04',
        'Май': '05', 'Июнь': '06', 'Июль': '07', 'Август': '08',
        'Сентябрь': '09', 'Октябрь': '10', 'Ноябрь': '11', 'Декабрь': '12'
    }

    month = month_names.get(month_text)
    if not month:
        from message_manager import message_manager
        await message_manager.send_message(
            update, context,
            "❌ Неверный месяц.",
            is_temporary=True
        )
        return SELECTING_MONTH

    year = context.user_data['selected_year']
    context.user_data['selected_month'] = month

    dates = get_booking_dates_by_year_month(year, month)

    if not dates:
        from message_manager import message_manager
        from keyboards.menus import get_booking_filter_menu
        await message_manager.send_message(
            update, context,
            f"📭 Нет бронирований за {month_text} {year} года.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    keyboard = []
    for date in dates:
        keyboard.append([KeyboardButton(date)])
    keyboard.append([KeyboardButton("❌ Отмена")])

    from message_manager import message_manager
    await message_manager.send_message(
        update, context,
        f"📅 Выберите дату ({month_text} {year}):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
        is_temporary=False
    )
    return SELECTING_DATE


async def show_bookings_by_selected_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать бронирования по выбранной дате"""
    if update.message.text == "❌ Отмена":
        from message_manager import message_manager
        from keyboards.menus import get_booking_filter_menu
        await message_manager.send_message(
            update, context,
            "❌ Поиск по дате отменен.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    if not is_admin(update.effective_user.id):
        return

    selected_date = update.message.text.strip()
    formatted_date = selected_date

    bookings = db.get_bookings_by_date(formatted_date)

    if not bookings:
        from message_manager import message_manager
        from keyboards.menus import get_booking_filter_menu
        await message_manager.send_message(
            update, context,
            f"📭 На {selected_date} бронирований не найдено.",
            reply_markup=get_booking_filter_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    from message_manager import message_manager
    from keyboards.menus import get_booking_filter_menu, get_booking_actions_keyboard

    await message_manager.send_message(
        update, context,
        f"📅 Бронирования на {selected_date} ({len(bookings)}):",
        reply_markup=get_booking_filter_menu(),
        is_temporary=False
    )

    for booking in bookings:
        message = _format_booking_message(booking)

        # Для ожидающих бронирований показываем кнопки действий
        if booking[5] == 'pending':
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=get_booking_actions_keyboard(booking[0]),
                is_temporary=False
            )
        else:
            await message_manager.send_message(
                update, context,
                message,
                is_temporary=False
            )

    return ConversationHandler.END


async def back_to_booking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в меню фильтрации бронирований"""
    if not is_admin(update.effective_user.id):
        return

    await show_bookings(update, context)
    return ConversationHandler.END


# Обработка действий с бронированиями
async def handle_booking_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий с бронированиями"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    parts = query.data.split('_')
    if len(parts) < 3:
        try:
            await query.edit_message_text("❌ Ошибка в данных запроса.")
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при обработке бронирования: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    "❌ Ошибка в данных запроса.",
                    is_temporary=True
                )
        return

    action = parts[0] + '_' + parts[1]
    booking_id = parts[2]

    try:
        booking_id = int(booking_id)
    except ValueError:
        try:
            await query.edit_message_text("❌ Неверный ID бронирования.")
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при обработке бронирования: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    "❌ Неверный ID бронирования.",
                    is_temporary=True
                )
        return

    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT b.*, u.first_name, u.last_name, u.telegram_id
        FROM bookings b 
        JOIN users u ON b.user_id = u.id 
        WHERE b.id = ?
    ''', (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        try:
            await query.edit_message_text("❌ Бронирование не найдено.")
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при обработке бронирования: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    "❌ Бронирование не найдено.",
                    is_temporary=True
                )
        return

    booking_id = booking[0]
    booking_date = booking[2]
    booking_time = booking[3]
    guests = booking[4]
    user_first_name = booking[7]
    user_last_name = booking[8]
    user_telegram_id = booking[9]

    if action == 'confirm_booking':
        cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', ('confirmed', booking_id))
        db.conn.commit()

        try:
            await context.bot.send_message(
                user_telegram_id,
                f"✅ Ваше бронирование подтверждено!\n\n"
                f"📅 Дата: {booking_date}\n"
                f"⏰ Время: {booking_time}\n"
                f"👥 Гостей: {guests}\n\n"
                f"Ждем вас в нашем заведении!"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")

        try:
            await query.edit_message_text(
                f"✅ Бронирование #{booking_id} подтверждено.\n"
                f"👤 Пользователь: {user_first_name} {user_last_name}"
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при подтверждении бронирования: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    f"✅ Бронирование #{booking_id} подтверждено.\n👤 Пользователь: {user_first_name} {user_last_name}",
                    is_temporary=False
                )

    elif action == 'cancel_booking':
        cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', ('cancelled', booking_id))
        db.conn.commit()

        try:
            await context.bot.send_message(
                user_telegram_id,
                f"❌ Ваше бронирование отменено.\n\n"
                f"📅 Дата: {booking_date}\n"
                f"⏰ Время: {booking_time}\n"
                f"👥 Гостей: {guests}\n\n"
                f"Если у вас есть вопросы, свяжитесь с нами."
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")

        try:
            await query.edit_message_text(
                f"❌ Бронирование #{booking_id} отменено.\n"
                f"👤 Пользователь: {user_first_name} {user_last_name}"
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при отмене бронирования: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    f"❌ Бронирование #{booking_id} отменено.\n👤 Пользователь: {user_first_name} {user_last_name}",
                    is_temporary=False
                )
    else:
        try:
            await query.edit_message_text("❌ Неизвестное действие.")
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при обработке бронирования: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    "❌ Неизвестное действие.",
                    is_temporary=True
                )


async def handle_booking_cancellation_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отмены бронирования с запросом причины"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    booking_id = int(query.data.split('_')[-1])
    context.user_data['cancelling_booking_id'] = booking_id

    from keyboards.menus import get_cancel_keyboard
    try:
        await query.edit_message_text(
            "📝 Укажите причину отмены бронирования:",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Ошибка при запросе причины отмены: {e}")
            from message_manager import message_manager
            await message_manager.send_message(
                update, context,
                "📝 Укажите причину отмены бронирования:",
                reply_markup=get_cancel_keyboard(),
                is_temporary=False
            )
    return AWAITING_CANCELLATION_REASON


async def process_cancellation_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка причины отмены бронирования"""
    if update.message.text == "❌ Отмена":
        context.user_data.pop('cancelling_booking_id', None)
        from message_manager import message_manager
        await message_manager.send_message(
            update, context,
            "❌ Отмена бронирования отменена.",
            is_temporary=True
        )
        from handlers.admin_utils import back_to_main_menu
        await back_to_main_menu(update, context)
        return ConversationHandler.END

    if not is_admin(update.effective_user.id) or 'cancelling_booking_id' not in context.user_data:
        return

    reason = update.message.text
    booking_id = context.user_data['cancelling_booking_id']

    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT b.*, u.first_name, u.last_name, u.telegram_id
        FROM bookings b 
        JOIN users u ON b.user_id = u.id 
        WHERE b.id = ?
    ''', (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        from message_manager import message_manager
        await message_manager.send_message(update, context, "❌ Бронирование не найдено.", is_temporary=True)
        from handlers.admin_utils import back_to_main_menu
        await back_to_main_menu(update, context)
        return ConversationHandler.END

    cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', ('cancelled', booking_id))
    db.conn.commit()

    try:
        await context.bot.send_message(
            booking[9],
            f"❌ Ваше бронирование отменено.\n\n"
            f"📅 Дата: {booking[2]}\n"
            f"⏰ Время: {booking[3]}\n"
            f"👥 Гостей: {booking[4]}\n\n"
            f"📝 Причина отмена: {reason}\n\n"
            f"Если у вас есть вопросы, свяжитесь с нами."
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя: {e}")

    from message_manager import message_manager
    await message_manager.send_message(
        update, context,
        f"❌ Бронирование #{booking_id} отменено.\n"
        f"👤 Пользователь: {booking[7]} {booking[8]}\n"
        f"📝 Причина: {reason}",
        is_temporary=False
    )

    context.user_data.pop('cancelling_booking_id', None)
    import asyncio
    await asyncio.sleep(2)
    from handlers.admin_utils import back_to_main_menu
    await back_to_main_menu(update, context)
    return ConversationHandler.END


def get_booking_date_handler():
    """Создать обработчик фильтрации по дате"""
    from telegram.ext import ConversationHandler, MessageHandler, filters
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📅 По дате$"), show_dates_for_filter)],
        states={
            SELECTING_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_year_for_filter)],
            SELECTING_MONTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_month_for_filter)],
            SELECTING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_bookings_by_selected_date)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), back_to_booking_menu)]
    )


def get_booking_cancellation_handler():
    """Создать обработчик отмены бронирования с причиной"""
    from telegram.ext import ConversationHandler, MessageHandler, filters
    from .admin_utils import cancel_operation  # ИЛИ из handlers.admin_utils

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_booking_cancellation_with_reason, pattern="^cancel_booking_reason_")
        ],
        states={
            AWAITING_CANCELLATION_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_cancellation_reason)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel_operation)]
    )