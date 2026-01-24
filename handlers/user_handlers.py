from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler, \
    CallbackQueryHandler
from database import Database
from keyboards.menus import get_user_main_menu, get_phone_keyboard, get_confirmation_keyboard, get_spend_bonus_keyboard, \
    get_cancel_keyboard, get_user_booking_filter_menu, get_user_booking_cancel_keyboard, get_contacts_keyboard
from utils.helpers import validate_phone, validate_name, format_user_data
from config import ADMIN_IDS, REFERRAL_BONUS
from message_manager import message_manager
import logging
import asyncio

logger = logging.getLogger(__name__)

db = Database()

# Состояния для регистрации
FIRST_NAME, LAST_NAME, PHONE, CONFIRMATION = range(4)
# Состояния для списания баллов
SPEND_BONUS = 10


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем только временные сообщения при старте
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if user_data:
        # Показываем разное меню для админов и обычных пользователей
        if user.id in ADMIN_IDS:
            from keyboards.menus import get_admin_main_menu
            await message_manager.send_message(
                update, context,
                f"Добро пожаловать обратно, {user_data[2]}! 🎉",
                reply_markup=get_admin_main_menu(),
                is_temporary=False
            )
        else:
            await message_manager.send_message(
                update, context,
                f"Добро пожаловать обратно, {user_data[2]}! 🎉",
                reply_markup=get_user_main_menu(),
                is_temporary=False
            )
        return ConversationHandler.END
    else:
        # Проверяем реферальный код
        referred_by = None
        if context.args:
            try:
                referred_by = int(context.args[0])
                # Проверяем существование реферера
                referrer_data = db.get_user_by_id(referred_by)
                if not referrer_data:
                    referred_by = None
            except ValueError:
                referred_by = None

        context.user_data['referred_by'] = referred_by

        welcome_text = "👋 Добро пожаловать! Давайте зарегистрируем вас в нашей системе лояльности.\n\n"
        if referred_by:
            welcome_text += "🎁 Вы зарегистрировались по приглашению друга! После регистрации ваш друг получит бонусные баллы.\n\n"

        welcome_text += "Пожалуйста, введите ваше имя:"

        await message_manager.send_message(update, context, welcome_text, is_temporary=True)
        return FIRST_NAME


async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем предыдущие временные сообщения
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    first_name = update.message.text.strip()

    if not validate_name(first_name):
        await message_manager.send_message(
            update, context,
            "❌ Имя должно содержать только буквы и быть не короче 2 символов. Попробуйте еще раз:",
            is_temporary=True
        )
        return FIRST_NAME

    context.user_data['first_name'] = first_name
    await message_manager.send_message(update, context, "Теперь введите вашу фамилию:", is_temporary=False)
    return LAST_NAME


async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    last_name = update.message.text.strip()

    if not validate_name(last_name):
        await message_manager.send_message(
            update, context,
            "❌ Фамилия должна содержать только буквы и быть не короче 2 символов. Попробуйте еще раз:",
            is_temporary=True
        )
        return LAST_NAME

    context.user_data['last_name'] = last_name
    await message_manager.send_message(
        update, context,
        "Теперь введите ваш номер телефона:",
        reply_markup=get_phone_keyboard(),
        is_temporary=False
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()

    if not validate_phone(phone):
        await message_manager.send_message(
            update, context,
            "❌ Неверный формат номера телефона. Попробуйте еще раз:",
            is_temporary=True
        )
        return PHONE

    context.user_data['phone'] = phone

    await message_manager.send_message(
        update, context,
        format_user_data(context.user_data),
        reply_markup=get_confirmation_keyboard(),
        is_temporary=False
    )
    return CONFIRMATION


async def confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user_data = context.user_data
    user = update.effective_user

    user_id = db.add_user(
        user.id,
        user_data['first_name'],
        user_data['last_name'],
        user_data['phone'],
        user_data.get('referred_by')
    )

    if user_id:
        db.add_transaction(user_id, 100, 'earn', 'Приветственные бонусы')

        # Начисляем реферальный бонус если есть
        referrer_id, bonus_amount = db.award_referral_bonus(user_id)

        success_message = "🎉 Благодарим за регистрацию! Вам начислено 100 бонусных баллов.\n\n"

        if referrer_id:
            referrer_data = db.get_user_by_id(referrer_id)
            success_message += f"🎁 Вы зарегистрировались по приглашению {referrer_data[2]} {referrer_data[3]}! "
            success_message += f"Ваш друг получил {bonus_amount} бонусных баллов.\n\n"

        success_message += f"Ваш ID: {user_id}\n\n"
        success_message += "💡 Приглашайте друзей и получайте бонусы!"

        # Показываем разное меню для админов и обычных пользователей
        if user.id in ADMIN_IDS:
            from keyboards.menus import get_admin_main_menu
            await message_manager.send_message(
                update, context,
                success_message,
                reply_markup=get_admin_main_menu(),
                is_temporary=False
            )
        else:
            await message_manager.send_message(
                update, context,
                success_message,
                reply_markup=get_user_main_menu(),
                is_temporary=False
            )

        # Отправляем уведомление администраторам о новой регистрации
        for admin_id in ADMIN_IDS:
            try:
                referral_info = ""
                if referrer_id:
                    referral_info = f"\n👥 Зарегистрирован по приглашению пользователя ID: {referrer_id}"

                await message_manager.send_message_to_chat(
                    context, admin_id,
                    f"🆕 Новый пользователь зарегистрирован!\n\n"
                    f"👤 {user_data['first_name']} {user_data['last_name']}\n"
                    f"📱 {user_data['phone']}\n"
                    f"🆔 ID: {user_id}\n"
                    f"🔗 Telegram ID: {user.id}{referral_info}",
                    is_temporary=False  # Постоянное сообщение
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")

        context.user_data.clear()
        return ConversationHandler.END
    else:
        await message_manager.send_message(
            update, context,
            "❌ Произошла ошибка при регистрации. Попробуйте еще раз.",
            is_temporary=True
        )
        return ConversationHandler.END


async def change_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await message_manager.cleanup_user_messages(context, update.effective_user.id)
    await message_manager.send_message(update, context, "Введите ваше имя:", is_temporary=False)
    return FIRST_NAME


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await message_manager.cleanup_user_messages(context, update.effective_user.id)
    context.user_data.clear()
    await message_manager.send_message(
        update, context,
        "Регистрация отменена. Используйте /start чтобы начать заново.",
        is_temporary=True
    )
    return ConversationHandler.END


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем только временные сообщения при переходе
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if user_data:
        # Получаем статистику рефералов
        referral_stats = db.get_referrer_stats(user_data[0])
        total_referrals = referral_stats[0] if referral_stats else 0
        awarded_referrals = referral_stats[1] if referral_stats else 0

        message = (
            f"💰 Ваш баланс: {user_data[5]} бонусных баллов\n"
            f"👤 Ваш ID: {user_data[0]}\n"
        )

        if total_referrals > 0:
            message += f"👥 Приглашено друзей: {total_referrals}\n"
            message += f"🎁 Получено бонусов: {awarded_referrals * REFERRAL_BONUS} баллов\n\n"
            message += "💡 Используйте /referral чтобы пригласить больше друзей!"

        await message_manager.send_message(
            update, context,
            message,
            reply_markup=get_user_main_menu(),
            is_temporary=False
        )
    else:
        await message_manager.send_message(
            update, context,
            "❌ Вы не зарегистрированы. Используйте /start для регистрации.",
            is_temporary=True
        )


async def show_referral_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем только временные сообщения при переходе
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await message_manager.send_message(
            update, context,
            "❌ Вы не зарегистрированы. Используйте /start для регистрации.",
            is_temporary=True
        )
        return

    referral_stats = db.get_referrer_stats(user_data[0])
    total_referrals = referral_stats[0] if referral_stats else 0
    awarded_referrals = referral_stats[1] if referral_stats else 0

    # Исправление ошибки: проверяем, что awarded_referrals не None
    if awarded_referrals is None:
        awarded_referrals = 0

    # Получаем username бота для создания ссылки
    try:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_data[0]}"
    except Exception as e:
        logger.error(f"Ошибка при получении username бота: {e}")
        referral_link = f"Используйте команду: /start {user_data[0]}"

    message = (
        f"🎁 Реферальная программа\n\n"
        f"💎 За каждого приглашенного друга вы получаете {REFERRAL_BONUS} бонусных баллов!\n\n"
        f"📊 Ваша статистика:\n"
        f"👥 Приглашено друзей: {total_referrals}\n"
        f"🎁 Получено бонусов: {awarded_referrals * REFERRAL_BONUS} баллов\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"`{referral_link}`\n\n"
        f"📢 Просто отправьте эту ссылку друзьям!"
    )

    await message_manager.send_message(
        update, context,
        message,
        parse_mode='Markdown',
        reply_markup=get_user_main_menu(),
        is_temporary=False
    )


async def show_user_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню фильтрации бронирований пользователя"""
    # Очищаем только временные сообщения при переходе
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await message_manager.send_message(
            update, context,
            "❌ Сначала зарегистрируйтесь с помощью /start",
            is_temporary=True
        )
        return

    # Получаем статистику бронирований пользователя
    all_bookings = db.get_user_bookings(user_data[0])
    pending_count = len([b for b in all_bookings if b[5] == 'pending'])
    confirmed_count = len([b for b in all_bookings if b[5] == 'confirmed'])
    cancelled_count = len([b for b in all_bookings if b[5] == 'cancelled'])

    # ОТЛАДОЧНАЯ ИНФОРМАЦИЯ
    logger.info(f"👤 Пользователь {user_data[0]} открыл фильтрацию бронирований")
    logger.info(
        f"📊 Статистика: ожидающие={pending_count}, подтвержденные={confirmed_count}, отмененные={cancelled_count}")

    message = (
        "📋 Фильтрация бронирований\n\n"
        f"📊 Ваша статистика:\n"
        f"⏳ Ожидающие: {pending_count}\n"
        f"✅ Подтвержденные: {confirmed_count}\n"
        f"❌ Отмененные: {cancelled_count}\n"
        f"📋 Всего: {len(all_bookings)}\n\n"
        "Выберите тип бронирований для просмотра:"
    )

    await message_manager.send_message(
        update, context,
        message,
        reply_markup=get_user_booking_filter_menu(),
        is_temporary=False
    )


async def show_user_pending_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ожидающие бронирования пользователя"""
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await message_manager.send_message(
            update, context,
            "❌ Сначала зарегистрируйтесь с помощью /start",
            is_temporary=True
        )
        return

    bookings = db.get_user_bookings(user_data[0])
    pending_bookings = [b for b in bookings if b[5] == 'pending']

    if not pending_bookings:
        await message_manager.send_message(
            update, context,
            "⏳ У вас нет ожидающих бронирований.",
            reply_markup=get_user_booking_filter_menu(),
            is_temporary=False
        )
        return

    await message_manager.send_message(
        update, context,
        f"⏳ Ваши ожидающие бронирования ({len(pending_bookings)}):",
        reply_markup=get_user_booking_filter_menu(),
        is_temporary=False
    )

    for booking in pending_bookings:
        message = _format_user_booking_message(booking)
        await message_manager.send_message(
            update, context,
            message,
            reply_markup=get_user_booking_cancel_keyboard(booking[0]),
            is_temporary=False
        )


async def show_user_confirmed_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подтвержденные бронирования пользователя"""
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await message_manager.send_message(
            update, context,
            "❌ Сначала зарегистрируйтесь с помощью /start",
            is_temporary=True
        )
        return

    bookings = db.get_user_bookings(user_data[0])
    confirmed_bookings = [b for b in bookings if b[5] == 'confirmed']

    if not confirmed_bookings:
        await message_manager.send_message(
            update, context,
            "✅ У вас нет подтвержденных бронирований.",
            reply_markup=get_user_booking_filter_menu(),
            is_temporary=False
        )
        return

    await message_manager.send_message(
        update, context,
        f"✅ Ваши подтвержденные бронирования ({len(confirmed_bookings)}):",
        reply_markup=get_user_booking_filter_menu(),
        is_temporary=False
    )

    for booking in confirmed_bookings:
        message = _format_user_booking_message(booking)
        await message_manager.send_message(
            update, context,
            message,
            reply_markup=get_user_booking_cancel_keyboard(booking[0]),
            is_temporary=False
        )


async def show_user_cancelled_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать отмененные бронирования пользователя"""
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await message_manager.send_message(
            update, context,
            "❌ Сначала зарегистрируйтесь с помощью /start",
            is_temporary=True
        )
        return

    bookings = db.get_user_bookings(user_data[0])
    cancelled_bookings = [b for b in bookings if b[5] == 'cancelled']

    if not cancelled_bookings:
        await message_manager.send_message(
            update, context,
            "❌ У вас нет отмененных бронирований.",
            reply_markup=get_user_booking_filter_menu(),
            is_temporary=False
        )
        return

    await message_manager.send_message(
        update, context,
        f"❌ Ваши отмененные бронирования ({len(cancelled_bookings)}):",
        reply_markup=get_user_booking_filter_menu(),
        is_temporary=False
    )

    for booking in cancelled_bookings:
        message = _format_user_booking_message(booking)
        await message_manager.send_message(
            update, context,
            message,
            is_temporary=False
        )


async def show_user_all_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все бронирования пользователя"""
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await message_manager.send_message(
            update, context,
            "❌ Сначала зарегистрируйтесь с помощью /start",
            is_temporary=True
        )
        return

    bookings = db.get_user_bookings(user_data[0])

    if not bookings:
        await message_manager.send_message(
            update, context,
            "📭 У вас нет бронирований.",
            reply_markup=get_user_booking_filter_menu(),
            is_temporary=False
        )
        return

    await message_manager.send_message(
        update, context,
        f"📋 Все ваши бронирования ({len(bookings)}):",
        reply_markup=get_user_booking_filter_menu(),
        is_temporary=False
    )

    for booking in bookings:
        message = _format_user_booking_message(booking)

        # Для активных бронирований показываем кнопку отмены
        if booking[5] in ['pending', 'confirmed']:
            await message_manager.send_message(
                update, context,
                message,
                reply_markup=get_user_booking_cancel_keyboard(booking[0]),
                is_temporary=False
            )
        else:
            await message_manager.send_message(
                update, context,
                message,
                is_temporary=False
            )


def _format_user_booking_message(booking):
    """Форматирует сообщение о бронировании для пользователя"""
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
        f"📅 Дата: {booking[2]}\n"
        f"⏰ Время: {booking[3]}\n"
        f"👥 Гостей: {booking[4]}\n"
        f"📊 Статус: {status_text.get(booking[5], booking[5])}\n"
        f"🆔 ID брони: {booking[0]}"
    )


# ОТМЕНА БРОНИРОВАНИЯ ПОЛЬЗОВАТЕЛЕМ
async def handle_user_cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отмены бронирования пользователем"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await query.edit_message_text("❌ Вы не зарегистрированы.")
        return

    # Получаем ID бронирования из callback данных
    booking_id = int(query.data.split('_')[-1])

    # Находим бронирование
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT b.*, u.first_name, u.last_name, u.telegram_id
        FROM bookings b 
        JOIN users u ON b.user_id = u.id 
        WHERE b.id = ? AND u.id = ?
    ''', (booking_id, user_data[0]))
    booking = cursor.fetchone()

    if not booking:
        await query.edit_message_text("❌ Бронирование не найдено.")
        return

    # Проверяем, что бронирование принадлежит пользователю
    if booking[1] != user_data[0]:
        await query.edit_message_text("❌ Это не ваше бронирование.")
        return

    # Проверяем статус бронирования
    if booking[5] == 'cancelled':
        await query.edit_message_text("❌ Это бронирование уже отменено.")
        return

    # Отменяем бронирование
    cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', ('cancelled', booking_id))
    db.conn.commit()

    # Форматируем информацию о бронировании
    booking_date = booking[2]
    booking_time = booking[3]
    guests = booking[4]

    # Обновляем сообщение
    await query.edit_message_text(
        f"❌ Бронирование отменено\n\n"
        f"📅 Дата: {booking_date}\n"
        f"⏰ Время: {booking_time}\n"
        f"👥 Гостей: {guests}\n\n"
        f"Если у вас есть вопросы, свяжитесь с нами."
    )

    # Уведомляем администраторов об отмене бронирования пользователем
    for admin_id in ADMIN_IDS:
        try:
            await message_manager.send_message_to_chat(
                context, admin_id,
                f"❌ Пользователь отменил бронирование!\n\n"
                f"👤 Пользователь: {user_data[2]} {user_data[3]}\n"
                f"📱 Телефон: {user_data[4]}\n"
                f"📅 Дата: {booking_date}\n"
                f"⏰ Время: {booking_time}\n"
                f"👥 Гостей: {guests}\n"
                f"🆔 ID брони: {booking_id}",
                is_temporary=False
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить администратора {admin_id}: {e}")


async def handle_back_to_bookings_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к списку бронирований"""
    query = update.callback_query
    await query.answer()

    await show_user_bookings(update, context)


# СПИСАНИЕ БАЛЛОВ
async def start_spend_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем только временные сообщения при переходе
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    user = update.effective_user
    user_data = db.get_user(user.id)

    if not user_data:
        await message_manager.send_message(update, context, "❌ Вы не зарегистрированы.", is_temporary=True)
        return ConversationHandler.END

    if user_data[5] <= 0:
        await message_manager.send_message(
            update, context,
            "❌ У вас недостаточно баллов для списания.",
            reply_markup=get_user_main_menu(),
            is_temporary=False
        )
        return ConversationHandler.END

    await message_manager.send_message(
        update, context,
        f"🎁 Списание бонусных баллов\n\n"
        f"💰 Ваш текущий баланс: {user_data[5]} баллов\n\n"
        f"Выберите сумму для списания или введите свою:",
        reply_markup=get_spend_bonus_keyboard(),
        is_temporary=False
    )
    return SPEND_BONUS


async def process_spend_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Отмена":
        await message_manager.cleanup_user_messages(context, update.effective_user.id)
        await message_manager.send_message(
            update, context,
            "❌ Списание отменено.",
            reply_markup=get_user_main_menu(),
            is_temporary=False
        )
        return ConversationHandler.END

    user = update.effective_user
    user_data = db.get_user(user.id)

    try:
        if update.message.text in ["50 баллов", "100 баллов", "200 баллов", "500 баллов"]:
            amount = int(update.message.text.split()[0])
        else:
            amount = int(update.message.text)

        if amount <= 0:
            await message_manager.send_message(
                update, context,
                "❌ Сумма должна быть положительной.",
                is_temporary=True
            )
            return SPEND_BONUS

        if amount > user_data[5]:
            await message_manager.send_message(
                update, context,
                "❌ Недостаточно баллов для списания.",
                is_temporary=True
            )
            return SPEND_BONUS

        # Создаем запрос на списание
        request_id = db.create_bonus_request(user_data[0], amount)

        # Уведомляем администратора
        from config import ADMIN_IDS
        for admin_id in ADMIN_IDS:
            try:
                await message_manager.send_message_to_chat(
                    context, admin_id,
                    f"🎁 Новый запрос на списание баллов!\n\n"
                    f"👤 Пользователь: {user_data[2]} {user_data[3]}\n"
                    f"📱 Телефон: {user_data[4]}\n"
                    f"💰 Сумма: {amount} баллов\n"
                    f"🆔 ID запроса: {request_id}",
                    is_temporary=False
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору: {e}")

        # Уведомление пользователю о создании запроса - НЕ очищается
        await message_manager.send_message(
            update, context,
            f"✅ Запрос на списание {amount} баллов отправлен администратору.\n"
            f"Ожидайте подтверждения.",
            reply_markup=get_user_main_menu(),
            is_temporary=False,
            is_notification=True  # Уведомление не будет очищено
        )

        return ConversationHandler.END

    except ValueError:
        await message_manager.send_message(
            update, context,
            "❌ Пожалуйста, введите корректное число:",
            is_temporary=True
        )
        return SPEND_BONUS


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню пользователя с очисткой временных сообщений"""
    user = update.effective_user

    try:
        # Очищаем только временные сообщения при возврате в главное меню
        await message_manager.cleanup_user_messages(context, user.id)

        # Показываем разное меню для админов и обычных пользователей
        if user.id in ADMIN_IDS:
            from keyboards.menus import get_admin_main_menu
            await message_manager.send_message(
                update, context,
                "👨‍💼 Панель администратора",
                reply_markup=get_admin_main_menu(),
                is_temporary=False
            )
        else:
            await message_manager.send_message(
                update, context,
                "Главное меню:",
                reply_markup=get_user_main_menu(),
                is_temporary=False
            )

        # Логируем действие
        from error_logger import log_user_action
        log_user_action("Возврат в главное меню", user.id)

    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню пользователя: {e}")
        # В случае ошибки все равно пытаемся показать меню
        if user.id in ADMIN_IDS:
            from keyboards.menus import get_admin_main_menu
            await message_manager.send_message(
                update, context,
                "👨‍💼 Панель администратора",
                reply_markup=get_admin_main_menu(),
                is_temporary=False
            )
        else:
            await message_manager.send_message(
                update, context,
                "Главное меню:",
                reply_markup=get_user_main_menu(),
                is_temporary=False
            )


async def back_to_booking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в меню фильтрации бронирований"""
    await show_user_bookings(update, context)


# ОБРАБОТЧИКИ КНОПОК ФИЛЬТРАЦИИ БРОНИРОВАНИЙ
async def handle_user_pending_bookings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки '⏳ Ожидающие'"""
    await show_user_pending_bookings(update, context)


async def handle_user_confirmed_bookings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки '✅ Подтвержденные'"""
    await show_user_confirmed_bookings(update, context)


async def handle_user_cancelled_bookings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки '❌ Отмененные'"""
    await show_user_cancelled_bookings(update, context)


async def handle_user_all_bookings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки '📋 Все бронирования'"""
    await show_user_all_bookings(update, context)


async def handle_user_back_to_bookings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки '⬅️ Назад' в меню бронирований"""
    await back_to_main(update, context)


# ОБРАБОТЧИКИ КОНТАКТОВ
async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать контакты кальянной"""
    # Очищаем только временные сообщения при переходе
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    contacts_message = (
        "<b>🌟 Добро пожаловать в #ВОВСЕТЯЖКИЕ! 🌟</b>\n\n"
        "<i>Твое место для идеального отдыха</i>\n\n"
        "<b>🕐 Режим работы:</b>\n"
        "Вс-Чт: 19:00 - 01:00\n\n"
        "Пт-Сб: 19:00 - 02:00\n\n"
        "<b>📞 Свяжитесь с нами:</b>\n"
        "💬 Telegram: @vo_vsetyazhkie\n"
        "📱 Телефон: +7 (962) 304-85-88\n\n"
        "<b>📍 Найдите нас на картах</b>\n"
        "Приходите отдохнуть и насладиться качественными кальянами! 🏮\n\n"
        "<b>Выберите действие:</b>"
    )

    await message_manager.send_message(
        update, context,
        contacts_message,
        reply_markup=get_contacts_keyboard(),
        is_temporary=False,
        parse_mode='HTML'
    )


async def handle_call_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки звонка"""
    phone_number = "+79623048588"

    await message_manager.send_message(
        update, context,
        f"📞 *Позвоните нам!*\n\n"
        f"Мы с радостью ответим на все ваши вопросы и поможем с бронированием!\n\n"
        f"*Наш номер:* [{phone_number}](tel:{phone_number})\n\n"
        f"📅 *Мы ждем вашего звонка!*",
        parse_mode='Markdown',
        is_temporary=False
    )


async def handle_telegram_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки Telegram"""
    telegram_username = "vo_vsetyazhkie"

    # Создаем инлайн-кнопку для перехода в чат
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = [
        [InlineKeyboardButton("💬 Написать в Telegram", url=f"https://t.me/{telegram_username}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_contacts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message_manager.send_message(
        update, context,
        "<b>💬 Напишите нам в Telegram!</b>\n\n"
        "Мы всегда на связи и готовы ответить на ваши вопросы!\n\n"
        "<b>Наш Telegram:</b> @vo_vsetyazhkie\n\n"
        "<b>📲 Нажмите кнопку ниже чтобы перейти в чат:</b>\n\n"
        "<b>⏰ Отвечаем в течение 15 минут!</b>",
        reply_markup=reply_markup,
        parse_mode='HTML',
        is_temporary=False
    )


async def handle_open_maps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки карт"""
    map_url = "https://yandex.ru/maps/org/vovsetyazhkiye/57633254342"

    await message_manager.send_message(
        update, context,
        f"📍 *Мы на картах!* 🗺️\n\n"
        f"*Кальянная 'ВОВСЕТЯЖКИЕ'*\n\n"
        f"🍽️ *Найдите нас на Яндекс Картах:*\n"
        f"[📍 Открыть в Яндекс Картах]({map_url})\n\n"
        f"✨ *Ждем вас в гости!*\n"
        f"Приходите за вкусными кальянами и теплой атмосферой!",
        parse_mode='Markdown',
        disable_web_page_preview=False,
        is_temporary=False
    )


async def handle_back_from_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат из меню контактов с очисткой сообщений - ТОЛЬКО при нажатии 'Назад'"""
    user = update.effective_user

    try:
        print(f"🔍 DEBUG: Нажата кнопка 'Назад' в контактах пользователем {user.id}")

        # Очищаем ВСЕ сообщения при нажатии "Назад"
        await message_manager.cleanup_all_messages(context, user.id)

        print(f"🔍 DEBUG: Сообщения очищены, показываем главное меню")

        # Небольшая задержка для завершения очистки
        await asyncio.sleep(0.5)

        # Показываем главное меню
        await message_manager.send_message(
            update, context,
            "Главное меню:",
            reply_markup=get_user_main_menu(),
            is_temporary=False
        )

        logger.info(f"✅ Очищены сообщения контактов для пользователя {user.id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при очистке сообщений контактов: {e}")
        print(f"❌ DEBUG: Ошибка очистки: {e}")
        # В случае ошибки все равно показываем меню
        await message_manager.send_message(
            update, context,
            "Главное меню:",
            reply_markup=get_user_main_menu(),
            is_temporary=False
        )


async def handle_back_to_contacts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки 'Назад' из инлайн-клавиатуры"""
    query = update.callback_query
    await query.answer()

    # Возвращаемся в меню контактов
    await show_contacts(update, context)


# Создаем обработчик регистрации
def get_registration_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
            LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_name)],
            PHONE: [MessageHandler(filters.TEXT | filters.CONTACT, get_phone)],
            CONFIRMATION: [
                MessageHandler(filters.Regex("^✅ Подтвердить$"), confirm_registration),
                MessageHandler(filters.Regex("^✏️ Изменить данные$"), change_data),
                MessageHandler(filters.Regex("^❌ Отмена$"), cancel_registration)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel_registration)]
    )


# Создаем обработчик списания баллов
def get_spend_bonus_handler():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 Списать баллы$"), start_spend_bonus)],
        states={
            SPEND_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_spend_bonus)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), back_to_main)]
    )