from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler, \
    CallbackQueryHandler
from database import Database
from keyboards.menus import get_user_main_menu, get_cancel_keyboard, get_calendar_keyboard
from config import ADMIN_IDS
from message_manager import message_manager
import logging
import re
from datetime import datetime, date

logger = logging.getLogger(__name__)

db = Database()

# Состояния для бронирования
BOOKING_DATE, BOOKING_TIME, BOOKING_GUESTS = range(3)


async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало бронирования с календарем"""
    await message_manager.cleanup_all_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await message_manager.send_message(
            update, context,
            "❌ Сначала зарегистрируйтесь с помощью /start",
            is_temporary=True
        )
        return ConversationHandler.END

    # Отправляем календарь
    await message_manager.send_message(
        update, context,
        "📅 Выберите дату бронирования:\n\n"
        "📍 - сегодня\n"
        "✅ - выбранная дата\n"
        "·1· - прошедшая дата",
        reply_markup=get_calendar_keyboard(),
        is_temporary=False
    )
    return BOOKING_DATE


async def handle_calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на календарь"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "cal_cancel":
        await cancel_booking_conversation(update, context)
        return ConversationHandler.END

    if data == "ignore":
        return BOOKING_DATE

    # Обработка выбора дня
    if data.startswith("cal_day_"):
        # Формат: cal_day_YYYY_MM_DD
        parts = data.split('_')
        year = int(parts[2])
        month = int(parts[3])
        day = int(parts[4])

        # Создаем объект даты для проверки
        selected_date_obj = date(year, month, day)

        # Проверяем, что дата не в прошлом
        today = date.today()
        if selected_date_obj < today:
            await query.edit_message_text(
                text="❌ Нельзя выбрать прошедшую дату. Выберите другую дату:",
                reply_markup=get_calendar_keyboard()
            )
            return BOOKING_DATE

        # Форматируем дату в нужный формат
        selected_date = f"{day:02d}.{month:02d}.{year}"

        # Сохраняем дату
        context.user_data['booking_date'] = selected_date
        context.user_data['booking_date_obj'] = selected_date_obj

        # Удаляем сообщение с календарем
        await query.delete_message()

        # Переходим к ручному вводу времени
        await message_manager.send_message(
            update, context,
            f"📅 Выбрана дата: {selected_date}\n\n"
            f"⏰ Введите время бронирования (в формате ЧЧ:ММ):",
            reply_markup=get_cancel_keyboard(),
            is_temporary=False
        )
        return BOOKING_TIME

    # Обработка навигации по месяцам
    elif data.startswith("cal_prev_") or data.startswith("cal_next_"):
        parts = data.split('_')
        year = int(parts[2])
        month = int(parts[3])

        if "prev" in data:
            month -= 1
            if month < 1:
                month = 12
                year -= 1
        else:
            month += 1
            if month > 12:
                month = 1
                year += 1

        # Проверяем, есть ли выбранная дата
        selected_date = context.user_data.get('booking_date')

        # Обновляем календарь
        await query.edit_message_reply_markup(
            reply_markup=get_calendar_keyboard(year, month, selected_date)
        )
        return BOOKING_DATE

    return BOOKING_DATE


async def get_booking_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение времени бронирования (ручной ввод)"""
    if update.message.text == "❌ Отмена":
        await message_manager.cleanup_all_messages(context, update.effective_user.id)
        await message_manager.send_message(
            update, context,
            "❌ Бронирование отменено.",
            reply_markup=get_user_main_menu(),
            is_temporary=False
        )
        return ConversationHandler.END

    time = update.message.text.strip()

    # Проверка формата времени
    time_pattern = r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$'
    if not re.match(time_pattern, time):
        await message_manager.send_message(
            update, context,
            "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 14:30):",
            is_temporary=True
        )
        return BOOKING_TIME

    try:
        hours, minutes = map(int, time.split(':'))

        # Если выбрана сегодняшняя дата, проверяем что время не прошлое
        booking_date_obj = context.user_data.get('booking_date_obj')
        today = date.today()
        now = datetime.now()

        if booking_date_obj == today:
            # Проверяем, не прошло ли уже это время сегодня
            input_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if input_time < now:
                await message_manager.send_message(
                    update, context,
                    "❌ Нельзя выбрать прошедшее время. Введите будущее время:",
                    is_temporary=True
                )
                return BOOKING_TIME

        context.user_data['booking_time'] = time
        await message_manager.send_message(
            update, context,
            "👥 Введите количество гостей:",
            reply_markup=get_cancel_keyboard(),
            is_temporary=False
        )
        return BOOKING_GUESTS

    except Exception as e:
        logger.error(f"Ошибка при обработке времени: {e}")
        await message_manager.send_message(
            update, context,
            "❌ Произошла ошибка. Введите время в формате ЧЧ:ММ:",
            is_temporary=True
        )
        return BOOKING_TIME


async def get_booking_guests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение количества гостей (ручной ввод)"""
    if update.message.text == "❌ Отмена":
        await message_manager.cleanup_all_messages(context, update.effective_user.id)
        await message_manager.send_message(
            update, context,
            "❌ Бронирование отменено.",
            reply_markup=get_user_main_menu(),
            is_temporary=False
        )
        return ConversationHandler.END

    try:
        guests = int(update.message.text.strip())

        if guests <= 0 or guests > 50:  # Увеличил лимит до 50
            await message_manager.send_message(
                update, context,
                "❌ Количество гостей должно быть от 1 до 50:",
                is_temporary=True
            )
            return BOOKING_GUESTS

        user = update.effective_user
        user_data = db.get_user(user.id)

        # Создаем бронирование
        booking_id = db.create_booking(
            user_data[0],
            context.user_data['booking_date'],
            context.user_data['booking_time'],
            guests
        )

        # Отправляем уведомление администраторам
        for admin_id in ADMIN_IDS:
            try:
                await message_manager.send_message_to_chat(
                    context, admin_id,
                    f"📅 Новое бронирование!\n\n"
                    f"👤 Пользователь: {user_data[2]} {user_data[3]}\n"
                    f"📱 Телефон: {user_data[4]}\n"
                    f"📅 Дата: {context.user_data['booking_date']}\n"
                    f"⏰ Время: {context.user_data['booking_time']}\n"
                    f"👥 Гостей: {guests}\n"
                    f"🆔 ID брони: {booking_id}",
                    is_temporary=False
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

        await message_manager.send_message(
            update, context,
            f"✅ Бронирование создано!\n\n"
            f"📅 Дата: {context.user_data['booking_date']}\n"
            f"⏰ Время: {context.user_data['booking_time']}\n"
            f"👥 Гостей: {guests}\n\n"
            f"Мы ждем вас! Ожидайте подтверждения от администратора.",
            reply_markup=get_user_main_menu(),
            is_temporary=False
        )

        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        await message_manager.send_message(
            update, context,
            "❌ Пожалуйста, введите корректное число гостей:",
            is_temporary=True
        )
        return BOOKING_GUESTS


async def cancel_booking_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена бронирования"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()

    await message_manager.cleanup_all_messages(context, update.effective_user.id)
    context.user_data.clear()

    await message_manager.send_message(
        update, context,
        "❌ Бронирование отменено.",
        reply_markup=get_user_main_menu(),
        is_temporary=False
    )
    return ConversationHandler.END


def get_booking_handler():
    """Создает обработчик бронирования с календарем и ручным вводом"""
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📅 Забронировать стол$"), start_booking)],
        states={
            BOOKING_DATE: [
                CallbackQueryHandler(handle_calendar_callback, pattern="^cal_"),
                CallbackQueryHandler(cancel_booking_conversation, pattern="^cal_cancel$")
            ],
            BOOKING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_booking_time)
            ],
            BOOKING_GUESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_booking_guests)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_booking_conversation),
            CommandHandler('cancel', cancel_booking_conversation),
            CallbackQueryHandler(cancel_booking_conversation, pattern="^cal_cancel$")
        ]
    )