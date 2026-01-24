"""
Управление бонусными баллами и запросами на списание
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton  # ДОБАВИТЬ Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from config import ADMIN_IDS
from database import Database

logger = logging.getLogger(__name__)
db = Database()


def is_admin(user_id):
    return user_id in ADMIN_IDS


async def handle_bonus_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать запросы на списание баллов"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    from keyboards.menus import get_admin_main_menu, get_bonus_request_keyboard

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    requests = db.get_pending_requests()

    # Постоянное сообщение с меню управления запросами
    await message_manager.send_message(
        update, context,
        f"📋 Управление запросами на списание\n\n"
        f"📊 Найдено запросов: {len(requests) if requests else 0}\n\n"
        f"Для управления запросами используйте кнопки под сообщением.",
        reply_markup=get_admin_main_menu(),
        is_temporary=False
    )

    if not requests:
        # Временное сообщение - будет удалено
        await message_manager.send_message(
            update, context,
            "📭 Активных запросов на списание нет.",
            is_temporary=True
        )
        return

    # Каждый запрос - постоянное сообщение
    for request in requests:
        message = (
            f"🎁 Запрос на списание баллов\n\n"
            f"👤 Пользователь: {request[5]} {request[6]}\n"
            f"🆔 ID пользователя: {request[1]}\n"
            f"💰 Сумма: {request[2]} баллов\n"
            f"📅 Дата: {request[4]}\n"
            f"🆔 ID запроса: {request[0]}"
        )

        await message_manager.send_message(
            update, context,
            message,
            reply_markup=get_bonus_request_keyboard(request[0]),
            is_temporary=False
        )


async def refresh_bonus_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновить список запросов"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    # Очищаем все временные сообщения
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    # Вызываем основную функцию для показа запросов
    await handle_bonus_requests(update, context)


async def handle_bonus_request_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий с запросами на списание"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    action, request_id = query.data.split('_')
    request_id = int(request_id)

    # Находим запрос
    requests = db.get_pending_requests()
    request_data = None
    for req in requests:
        if req[0] == request_id:
            request_data = req
            break

    if not request_data:
        try:
            await query.edit_message_text("❌ Запрос не найден.")
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при обработке запроса на списание: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    "❌ Запрос не найден.",
                    is_temporary=True
                )
        return

    user_data = db.get_user_by_id(request_data[1])

    if action == 'approve':
        # Проверяем достаточно ли баллов
        if request_data[2] > user_data[5]:
            try:
                await query.edit_message_text("❌ У пользователя недостаточно баллов для списания.")
            except Exception as e:
                if "Message is not modified" not in str(e):
                    logger.error(f"Ошибка при обработке запроса на списание: {e}")
                    from message_manager import message_manager
                    await message_manager.send_message(
                        update, context,
                        "❌ У пользователя недостаточно баллов для списания.",
                        is_temporary=True
                    )
            return

        # Списание баллов
        db.update_user_balance(request_data[1], -request_data[2])
        db.update_bonus_request(request_id, 'approved')
        db.add_transaction(request_data[1], -request_data[2], 'spend', 'Списание по запросу')

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                user_data[1],
                f"✅ Ваш запрос на списание {request_data[2]} бонусных баллов одобрен!\n"
                f"💰 Новый баланс: {user_data[5] - request_data[2]} баллов"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")

        try:
            await query.edit_message_text(
                f"✅ Запрос на списание {request_data[2]} баллов одобрен.\n"
                f"👤 Пользователь: {user_data[2]} {user_data[3]}"
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при одобрении запроса на списание: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    f"✅ Запрос на списание {request_data[2]} баллов одобрен.\n👤 Пользователь: {user_data[2]} {user_data[3]}",
                    is_temporary=False
                )

    else:  # reject
        db.update_bonus_request(request_id, 'rejected')

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                user_data[1],
                f"❌ Ваш запрос на списание {request_data[2]} бонусных баллов отклонен.",
                is_temporary=True
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")

        try:
            await query.edit_message_text(
                f"❌ Запрос на списание {request_data[2]} баллов отклонен.\n"
                f"👤 Пользователь: {user_data[2]} {user_data[3]}"
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при отклонении запроса на списание: {e}")
                from message_manager import message_manager
                await message_manager.send_message(
                    update, context,
                    f"❌ Запрос на списание {request_data[2]} баллов отклонен.\n👤 Пользователь: {user_data[2]} {user_data[3]}",
                    is_temporary=False
                )


def get_bonus_handler():
    """Создать обработчик бонусов"""
    from telegram.ext import ConversationHandler, MessageHandler, filters

    # Импортируем нужные функции из admin_users
    from .admin_users import (
        AWAITING_BONUS_AMOUNT, AWAITING_SPENT_AMOUNT,
        add_bonus_callback, remove_bonus_callback,
        process_remove_bonus, process_spent_amount
    )

    # СОЗДАЕМ ЛОКАЛЬНУЮ ФУНКЦИЮ ДЛЯ ОТМЕНЫ
    async def cancel_bonus_operation(update, context):
        from message_manager import message_manager
        from keyboards.menus import get_admin_main_menu

        context.user_data.clear()
        await message_manager.send_message(
            update, context,
            "❌ Операция отменена.",
            reply_markup=get_admin_main_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_bonus_callback, pattern="^add_bonus_"),
            CallbackQueryHandler(remove_bonus_callback, pattern="^remove_bonus_")
        ],
        states={
            AWAITING_BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_remove_bonus)],
            AWAITING_SPENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_spent_amount)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel_bonus_operation)]
    )