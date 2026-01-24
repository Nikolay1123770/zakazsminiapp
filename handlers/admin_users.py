"""
Управление пользователями: поиск, просмотр, начисление/списание баллов
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton  # УЖЕ ЕСТЬ
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS
from database import Database
import asyncio

logger = logging.getLogger(__name__)
db = Database()

# Состояния для админских функций
AWAITING_BONUS_AMOUNT, AWAITING_SPENT_AMOUNT, AWAITING_SEARCH_QUERY = range(3)


def is_admin(user_id):
    return user_id in ADMIN_IDS


async def show_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    """Показать список пользователей с поиском"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    # Автоматически запускаем режим поиска!
    await message_manager.send_message(
        update, context,
        "🔍 Режим поиска пользователей активен!\n\n"
        "📌 Просто напишите в чат:\n"
        "• ID пользователя (например: 123)\n"
        "• Имя или фамилию (например: Иван)\n"
        "• Часть имени\n\n"
        "Или нажмите кнопку для просмотра полного списка:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Показать полный список", callback_data="show_full_users_list_0")],
            [InlineKeyboardButton("❌ Выйти из поиска", callback_data="exit_search_mode")]
        ]),
        is_temporary=False
    )

    # Устанавливаем флаг режима поиска
    context.user_data['search_users_mode'] = True
    return


async def start_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать поиск пользователя"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    await query.edit_message_text(
        "🔍 Поиск пользователя\n\n"
        "Введите ID пользователя, имя или фамилию для поиска:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_search")]
        ])
    )
    return AWAITING_SEARCH_QUERY


async def process_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка поиска пользователя"""
    if not is_admin(update.effective_user.id):
        return

    search_query = update.message.text.strip()

    if not search_query:
        from message_manager import message_manager
        await message_manager.send_message(
            update, context,
            "❌ Введите текст для поиска.",
            is_temporary=True
        )
        return AWAITING_SEARCH_QUERY

    # Ищем пользователей в базе данных
    cursor = db.conn.cursor()

    # Поиск по ID
    if search_query.isdigit():
        cursor.execute('''
            SELECT * FROM users 
            WHERE id = ? AND is_active = TRUE 
            ORDER BY id DESC
        ''', (int(search_query),))
    else:
        # Поиск по имени или фамилии
        search_pattern = f"%{search_query}%"
        cursor.execute('''
            SELECT * FROM users 
            WHERE (first_name LIKE ? OR last_name LIKE ?) AND is_active = TRUE 
            ORDER BY id DESC
        ''', (search_pattern, search_pattern))

    users = cursor.fetchall()

    if not users:
        from message_manager import message_manager
        await message_manager.send_message(
            update, context,
            f"❌ Пользователи по запросу '{search_query}' не найдены.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад к списку", callback_data="back_to_users_list")]
            ]),
            is_temporary=False
        )
        return ConversationHandler.END

    # Показываем найденных пользователей
    message = f"🔍 Результаты поиска по запросу: '{search_query}'\n\n"
    message += f"Найдено пользователей: {len(users)}\n\n"

    keyboard = []
    for user in users:
        keyboard.append([InlineKeyboardButton(
            f"{user[2]} {user[3]} (ID: {user[0]}) | 💰 {user[5]} баллов",
            callback_data=f"select_user_{user[0]}"
        )])

    keyboard.append([InlineKeyboardButton("⬅️ Назад к списку", callback_data="back_to_users_list")])

    from message_manager import message_manager
    await message_manager.send_message(
        update, context,
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        is_temporary=False
    )
    return ConversationHandler.END


async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена поиска"""
    query = update.callback_query
    await query.answer()

    await show_users_list(update, context, 0)
    return ConversationHandler.END


async def back_to_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к списку пользователей"""
    query = update.callback_query
    await query.answer()

    try:
        await query.edit_message_text(
            "🔄 Загружаю список пользователей...",
            reply_markup=None
        )
        await asyncio.sleep(0.5)
        await show_users_list(update, context, 0)
    except Exception as e:
        logger.error(f"Ошибка при возврате к списку пользователей: {e}")
        await show_users_list(update, context, 0)
    return ConversationHandler.END


async def handle_users_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка пагинации списка пользователей"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    if query.data.startswith("users_page_"):
        page = int(query.data.split("_")[2])
        await show_users_list(update, context, page)
    elif query.data == "refresh_users":
        await show_users_list(update, context, 0)


async def user_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора пользователя"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(query.data.split('_')[-1])
    user_data = db.get_user_by_id(user_id)

    if user_data:
        # Получаем информацию о рефералах
        referral_stats = db.get_referrer_stats(user_id)
        total_referrals = referral_stats[0] if referral_stats else 0

        message = (
            f"👤 Пользователь:\n\n"
            f"🆔 ID: {user_data[0]}\n"
            f"👤 Имя: {user_data[2]} {user_data[3]}\n"
            f"📱 Телефон: {user_data[4]}\n"
            f"💰 Баланс: {user_data[5]} баллов\n"
            f"📅 Дата регистрации: {user_data[6]}\n"
            f"👥 Приглашено друзей: {total_referrals}\n"
            f"🔗 Telegram ID: {user_data[1]}"
        )

        from keyboards.menus import get_user_actions_keyboard
        try:
            await query.edit_message_text(
                message,
                reply_markup=get_user_actions_keyboard(user_id)
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при показе пользователя: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    message,
                    reply_markup=get_user_actions_keyboard(user_id),
                    is_temporary=False
                )
    else:
        try:
            await query.edit_message_text("❌ Пользователь не найден.")
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при показе пользователя: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    "❌ Пользователь не найден.",
                    is_temporary=True
                )


async def user_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки информации о пользователе"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(query.data.split('_')[-1])
    user_data = db.get_user_by_id(user_id)

    if user_data:
        message = (
            f"👤 Информация о пользователе:\n\n"
            f"🆔 ID: {user_data[0]}\n"
            f"👤 Имя: {user_data[2]}\n"
            f"📝 Фамилия: {user_data[3]}\n"
            f"📱 Телефон: {user_data[4]}\n"
            f"💰 Баланс: {user_data[5]} баллов\n"
            f"📅 Регистрация: {user_data[6]}\n"
            f"🔗 Telegram ID: {user_data[1]}"
        )

        from keyboards.menus import get_user_actions_keyboard
        try:
            await query.edit_message_text(
                message,
                reply_markup=get_user_actions_keyboard(user_id)
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при показе информации о пользователе: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    message,
                    reply_markup=get_user_actions_keyboard(user_id),
                    is_temporary=False
                )
    else:
        try:
            await query.edit_message_text("❌ Пользователь не найден.")
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при показе информации о пользователе: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    "❌ Пользователь не найден.",
                    is_temporary=True
                )


async def exit_search_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выйти из режима поиска пользователей"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    context.user_data.pop('search_users_mode', None)
    from handlers.admin_utils import back_to_main_menu
    await back_to_main_menu(update, context)


async def show_full_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать полный список пользователей"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    page = 0
    if query.data.startswith("show_full_users_list_"):
        try:
            page = int(query.data.split("_")[-1])
        except:
            page = 0

    context.user_data.pop('search_users_mode', None)
    users = db.get_all_users()

    if not users:
        await query.edit_message_text("📭 Пользователи не найдены.")
        return

    users_per_page = 20
    total_pages = (len(users) + users_per_page - 1) // users_per_page

    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    start_index = page * users_per_page
    end_index = min(start_index + users_per_page, len(users))
    users_page = users[start_index:end_index]

    message = f"👥 Список пользователей (стр. {page + 1}/{total_pages}, всего: {len(users)})\n\n"
    message += "Выберите пользователя:"

    keyboard = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Предыдущая", callback_data=f"show_full_users_list_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Следующая ➡️", callback_data=f"show_full_users_list_{page + 1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    for user in users_page:
        keyboard.append([InlineKeyboardButton(
            f"{user[2]} {user[3]} (ID: {user[0]}) | 💰 {user[5]} баллов",
            callback_data=f"select_user_{user[0]}"
        )])

    keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="refresh_users")])
    keyboard.append([InlineKeyboardButton("🔍 Вернуться к поиску", callback_data="back_to_search_mode")])
    keyboard.append([InlineKeyboardButton("❌ Выйти из поиска", callback_data="exit_search_mode")])

    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def back_to_search_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в режим поиска"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    context.user_data['search_users_mode'] = True

    await query.edit_message_text(
        "🔍 Режим поиска пользователей активен!\n\n"
        "📌 Просто напишите в чат:\n"
        "• ID пользователя (например: 123)\n"
        "• Имя или фамилию (например: Иван)\n"
        "• Часть имени\n\n"
        "Или нажмите кнопку для просмотра полного списка:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Показать полный список", callback_data="show_full_users_list_0")],
            [InlineKeyboardButton("❌ Выйти из поиска", callback_data="exit_search_mode")]
        ])
    )


async def new_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать новый поиск"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    context.user_data['search_users_mode'] = True

    await query.edit_message_text(
        "🔍 Введите новый поисковый запрос:\n"
        "• ID пользователя\n"
        "• Имя или фамилию\n"
        "• Часть имени\n\n"
        "Или нажмите кнопку для просмотра полного списка:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Показать полный список", callback_data="show_full_users_list_0")],
            [InlineKeyboardButton("❌ Выйти из поиска", callback_data="exit_search_mode")]
        ])
    )


# Начисление баллов (5% от суммы)
async def add_bonus_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать начисление баллов пользователю"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(query.data.split('_')[-1])
    context.user_data['selected_user'] = user_id
    context.user_data['action'] = 'add_bonus_percent'

    user_data = db.get_user_by_id(user_id)

    from keyboards.menus import get_cancel_keyboard
    from message_manager import message_manager
    await message_manager.send_message(
        update, context,
        f"💰 Начисление баллов пользователю:\n"
        f"👤 {user_data[2]} {user_data[3]}\n"
        f"💰 Текущий баланс: {user_data[5]} баллов\n\n"
        f"Введите сумму, которую потратил пользователь (рубли):",
        reply_markup=get_cancel_keyboard(),
        is_temporary=False
    )
    return AWAITING_SPENT_AMOUNT


async def process_spent_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка суммы потраченных денег для начисления баллов"""
    if update.message.text == "❌ Отмена":
        context.user_data.clear()
        from handlers.admin_utils import cancel_operation
        await cancel_operation(update, context)
        return ConversationHandler.END

    if not is_admin(update.effective_user.id):
        return

    try:
        spent_amount = int(update.message.text)
        user_id = context.user_data.get('selected_user')
        action = context.user_data.get('action')

        if spent_amount <= 0:
            from message_manager import message_manager
            await message_manager.send_message(
                update, context,
                "❌ Сумма должна быть положительной.",
                is_temporary=True
            )
            return AWAITING_SPENT_AMOUNT

        user_data = db.get_user_by_id(user_id)

        if action == 'add_bonus_percent':
            bonus_amount = int(spent_amount * 0.05)
            db.update_user_balance(user_id, bonus_amount)
            db.add_transaction(user_id, bonus_amount, 'earn', f'Начисление 5% от суммы {spent_amount} руб')

            # Уведомляем пользователя о начислении
            try:
                await context.bot.send_message(
                    user_data[1],
                    f"🎉 Вам начислены бонусные баллы!\n\n"
                    f"💰 Начислено: {bonus_amount} баллов (5% от {spent_amount} руб)\n"
                    f"💳 Новый баланс: {user_data[5] + bonus_amount} баллов\n\n"
                    f"Мы будем рады если вы оставите свой отзыв:\n"
                    f"📍 [Оставить отзыв на Яндекс Картах](https://yandex.ru/maps/org/vovsetyazhkiye/57633254342)\n\n"
                    f"Спасибо за посещение нашего заведения! 🏪",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя о начислении: {e}")

            from keyboards.menus import get_admin_main_menu
            from message_manager import message_manager
            await message_manager.send_message(
                update, context,
                f"✅ Пользователю {user_data[2]} {user_data[3]} начислено {bonus_amount} бонусных баллов (5% от {spent_amount} руб).\n"
                f"💰 Новый баланс: {user_data[5] + bonus_amount} баллов",
                reply_markup=get_admin_main_menu(),
                is_temporary=False
            )

        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        from message_manager import message_manager
        await message_manager.send_message(
            update, context,
            "❌ Пожалуйста, введите корректную сумму:",
            is_temporary=True
        )
        return AWAITING_SPENT_AMOUNT


# Списание баллов администратором
async def remove_bonus_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать списание баллов у пользователя"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(query.data.split('_')[-1])
    context.user_data['selected_user'] = user_id
    context.user_data['action'] = 'remove_bonus'

    user_data = db.get_user_by_id(user_id)

    from keyboards.menus import get_cancel_keyboard
    from message_manager import message_manager
    await message_manager.send_message(
        update, context,
        f"📊 Списание баллов у пользователя:\n"
        f"👤 {user_data[2]} {user_data[3]}\n"
        f"💰 Текущий баланс: {user_data[5]} баллов\n\n"
        f"Введите сумму для списания:",
        reply_markup=get_cancel_keyboard(),
        is_temporary=False
    )
    return AWAITING_BONUS_AMOUNT


async def process_remove_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка списания баллов"""
    if update.message.text == "❌ Отмена":
        context.user_data.clear()
        from handlers.admin_utils import cancel_operation
        await cancel_operation(update, context)
        return ConversationHandler.END

    if not is_admin(update.effective_user.id):
        return

    try:
        amount = int(update.message.text)
        user_id = context.user_data.get('selected_user')

        if amount <= 0:
            from message_manager import message_manager
            await message_manager.send_message(
                update, context,
                "❌ Сумма должна быть положительной.",
                is_temporary=True
            )
            return AWAITING_BONUS_AMOUNT

        user_data = db.get_user_by_id(user_id)

        if amount > user_data[5]:
            from message_manager import message_manager
            await message_manager.send_message(
                update, context,
                "❌ Недостаточно баллов для списания.",
                is_temporary=True
            )
            return AWAITING_BONUS_AMOUNT

        db.update_user_balance(user_id, -amount)
        db.add_transaction(user_id, -amount, 'spend', 'Списание администратором')

        # Уведомляем пользователя о списании
        try:
            await context.bot.send_message(
                user_data[1],
                f"📊 С вашего счета списано {amount} бонусных баллов.\n"
                f"💰 Новый баланс: {user_data[5] - amount} баллов"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя о списании: {e}")

        from keyboards.menus import get_admin_main_menu
        from message_manager import message_manager
        await message_manager.send_message(
            update, context,
            f"✅ У пользователя {user_data[2]} {user_data[3]} списано {amount} бонусных баллов.\n"
            f"💰 Новый баланс: {user_data[5] - amount} баллов",
            reply_markup=get_admin_main_menu(),
            is_temporary=False
        )

        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        from message_manager import message_manager
        await message_manager.send_message(
            update, context,
            "❌ Пожалуйста, введите корректное число:",
            is_temporary=True
        )
        return AWAITING_BONUS_AMOUNT


def get_user_search_handler():
    """Создать обработчик поиска пользователей"""
    from telegram.ext import ConversationHandler, MessageHandler, filters, CallbackQueryHandler
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_user_search, pattern="^search_user$"),
        ],
        states={
            AWAITING_SEARCH_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_search),
                CallbackQueryHandler(cancel_search, pattern="^cancel_search$")
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_search),
            CallbackQueryHandler(back_to_users_list, pattern="^back_to_users_list$")
        ]
    )