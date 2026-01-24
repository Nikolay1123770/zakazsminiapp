"""
Утилиты и базовые функции для администраторов
"""
import logging
from telegram import Update  # ДОБАВИТЬ ЭТОТ ИМПОРТ
from telegram.ext import ContextTypes
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная панель администратора"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return

    from keyboards.menus import get_admin_main_menu
    from message_manager import message_manager

    # Полная очистка всех сообщений при входе в админ-панель
    await message_manager.cleanup_all_messages(context, update.effective_user.id)

    # Главное меню - постоянное сообщение
    await message_manager.send_message(
        update, context,
        "👨‍💼 Панель администратора",
        reply_markup=get_admin_main_menu(),
        is_temporary=False
    )


async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню администратора с полной очисткой чата"""
    from message_manager import message_manager
    from keyboards.menus import get_admin_main_menu
    import asyncio

    user = update.effective_user
    if not is_admin(user.id):
        return

    try:
        # Полная очистка всех сообщений при возврате в главное меню
        await message_manager.cleanup_all_messages(context, user.id)

        # Небольшая задержка для завершения очистки
        await asyncio.sleep(0.5)

        # Показываем главное меню администратора
        await message_manager.send_message(
            update, context,
            "👨‍💼 Панель администратора",
            reply_markup=get_admin_main_menu(),
            is_temporary=False
        )

        # Логируем действие
        from error_logger import log_admin_action
        log_admin_action("Возврат в главное меню", user.id)

    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню администратора: {e}")
        await message_manager.send_message(
            update, context,
            "👨‍💼 Панель администратора",
            reply_markup=get_admin_main_menu(),
            is_temporary=False
        )


async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    from message_manager import message_manager
    from keyboards.menus import get_admin_main_menu

    context.user_data.clear()
    await message_manager.send_message(
        update, context,
        "❌ Операция отменена.",
        reply_markup=get_admin_main_menu(),
        is_temporary=True
    )
    return True  # Для ConversationHandler.END


async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику системы"""
    if not is_admin(update.effective_user.id):
        return

    from database import Database
    from message_manager import message_manager
    from keyboards.menus import get_admin_main_menu

    db = Database()

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    users = db.get_all_users()
    total_users = len(users)
    total_bonuses = sum(user[5] for user in users)

    # Получаем статистику бронирований
    booking_stats = db.get_booking_stats()

    # Получаем статистику запросов
    requests = db.get_pending_requests()
    pending_requests_count = len(requests)

    message = (
        f"📊 Статистика системы:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💰 Всего бонусных баллов: {total_bonuses}\n"
        f"🏆 Средний баланс: {total_bonuses // total_users if total_users > 0 else 0} баллов\n\n"
        f"📅 Бронирования:\n"
        f"⏳ Ожидающие: {booking_stats.get('pending', 0)}\n"
        f"✅ Подтвержденные: {booking_stats.get('confirmed', 0)}\n"
        f"❌ Отмененные: {booking_stats.get('cancelled', 0)}\n\n"
        f"📋 Запросы на списание: {pending_requests_count}"
    )

    # Статистика - постоянное сообщение
    await message_manager.send_message(
        update, context,
        message,
        reply_markup=get_admin_main_menu(),
        is_temporary=False
    )