import logging
import os
import warnings
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.warnings import PTBUserWarning
from dotenv import load_dotenv
from config import BOT_TOKEN, ADMIN_IDS, MINIAPP_URL
from error_logger import setup_error_logging

# Игнорировать предупреждения PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация системы логирования ошибок
setup_error_logging()

async def post_init(application):
    """Функция, выполняемая после инициализации бота"""
    logger.info("🤖 Бот успешно запущен и готов к работе!")

    # Получаем информацию о боте
    bot_info = await application.bot.get_me()
    logger.info(f"🔗 Бот: {bot_info.first_name} (@{bot_info.username})")
    logger.info(f"🆔 ID бота: {bot_info.id}")
    
    # Проверяем настройки MiniApp
    if MINIAPP_URL:
        logger.info(f"🌐 MiniApp настроен: {MINIAPP_URL}")
    else:
        logger.warning("⚠️ MiniApp URL не настроен в конфигурации")

async def post_stop(application):
    """Функция, выполняемая при остановке бота"""
    logger.info("🛑 Бот остановлен")

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

class AdminFilter(filters.MessageFilter):
    def filter(self, message):
        return is_admin(message.from_user.id)

class UserFilter(filters.MessageFilter):
    def filter(self, message):
        return not is_admin(message.from_user.id)

# Создаем экземпляры фильтров
admin_filter = AdminFilter()
user_filter = UserFilter()

# НОВАЯ ФУНКЦИЯ: Обработчик для кнопки MiniApp
async def open_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открыть MiniApp"""
    user_id = update.effective_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    from database import Database
    db = Database()
    user_data = db.get_user(user_id)
    
    if not user_data:
        await update.message.reply_text(
            "❌ Сначала зарегистрируйтесь с помощью /start",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Зарегистрироваться", callback_data="start_registration")]
            ])
        )
        return
    
    if not MINIAPP_URL:
        await update.message.reply_text(
            "❌ MiniApp временно недоступен. Используйте бота для доступа ко всем функциям."
        )
        return
    
    # Создаем кнопку для открытия MiniApp
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🌐 Открыть веб-приложение",
            web_app=WebAppInfo(url=MINIAPP_URL)
        )
    ]])
    
    await update.message.reply_text(
        "🌐 **Vovsetyagskie - Веб-приложение**\n\n"
        "Откройте веб-приложение для удобного доступа к:\n"
        "• 🍽️ Меню с ценами\n"
        "• 📅 Бронированию столов\n"
        "• 💰 Вашему балансу баллов\n"
        "• 📋 История бронирований\n\n"
        "Нажмите кнопку ниже, чтобы открыть:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# НОВАЯ ФУНКЦИЯ: Команда для администраторов чтобы протестировать MiniApp
async def test_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестирование MiniApp (только для администраторов)"""
    if not is_admin(update.effective_user.id):
        return
    
    if not MINIAPP_URL:
        await update.message.reply_text(
            "❌ MiniApp URL не настроен в конфигурации.\n"
            "Добавьте MINIAPP_URL = 'https://vovsetyagskie.bothost.ru' в config.py"
        )
        return
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🧪 Тест MiniApp",
            web_app=WebAppInfo(url=MINIAPP_URL)
        )
    ]])
    
    await update.message.reply_text(
        "🧪 **Тестирование MiniApp**\n\n"
        f"URL: {MINIAPP_URL}\n\n"
        "Нажмите кнопку для открытия веб-приложения:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# Упрощенные версии обработчиков (без удаления сообщений)

async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных сообщений"""
    if update.message:
        if is_admin(update.effective_user.id):
            await update.message.reply_text(
                "❌ Неизвестная команда. Используйте кнопки меню администратора."
            )
        else:
            # Предлагаем открыть MiniApp или показать меню
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 Открыть веб-приложение", callback_data="open_miniapp"),
                InlineKeyboardButton("📋 Показать меню", callback_data="show_menu")
            ]])
            await update.message.reply_text(
                "Я не понимаю эту команду. Хотите открыть веб-приложение или увидеть меню?",
                reply_markup=keyboard
            )

async def handle_back_button(update: Update, context):
    """Обработчик кнопки 'Назад' для обоих типов пользователей"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        from handlers.admin_utils import back_to_main_menu
        await back_to_main_menu(update, context)
    else:
        from handlers.user_handlers import back_to_main
        await back_to_main(update, context)

# Функции для отладки
async def debug_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки - показать все смены"""
    if not is_admin(update.effective_user.id):
        return

    from database import Database
    db = Database()
    all_shifts = db.get_all_shifts_debug()

    if not all_shifts:
        await update.message.reply_text("📭 Нет смен в базе данных")
        return

    message = "📊 ВСЕ СМЕНЫ В БАЗЕ:\n\n"
    for shift in all_shifts:
        message += f"Смена #{shift[1]} ({shift[2]})\n"
        message += f"  Открыта: {shift[3]}\n"
        message += f"  Закрыта: {shift[4] if shift[4] else 'Открыта'}\n"
        message += f"  Выручка: {shift[5] or 0}₽\n"
        message += f"  Заказов: {shift[6] or 0}\n"
        message += f"  Статус: {shift[7]}\n"
        message += "-" * 30 + "\n"

    # Разбиваем сообщение если оно слишком длинное
    if len(message) > 4000:
        await update.message.reply_text(message[:4000])
        if len(message) > 8000:
            await update.message.reply_text(message[4000:8000])
            if len(message) > 12000:
                await update.message.reply_text(message[8000:12000])
        else:
            await update.message.reply_text(message[4000:])
    else:
        await update.message.reply_text(message)

async def reset_shift_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить данные смены в памяти"""
    if not is_admin(update.effective_user.id):
        return

    # Сброс данных в памяти
    context.bot_data.clear()

    await update.message.reply_text("✅ Данные смены в памяти сброшены!")

def setup_handlers(application):
    """Настройка всех обработчиков"""
    
    # ДОБАВЛЯЕМ КОЛОНКУ payment_method ЕСЛИ ЕЁ НЕТ
    from database import Database
    db = Database()
    db.add_payment_method_column()
    
    # ========== ИМПОРТЫ ОБРАБОТЧИКОВ ==========
    
    # Импорты обработчиков пользователя
    from handlers.user_handlers import (
        get_registration_handler, get_spend_bonus_handler,
        show_balance, show_referral_info, show_user_bookings,
        handle_user_pending_bookings_button, handle_user_confirmed_bookings_button,
        handle_user_cancelled_bookings_button, handle_user_all_bookings_button,
        handle_user_back_to_bookings_button, handle_user_cancel_booking,
        handle_back_to_bookings_list, start, back_to_main,
        show_contacts, handle_call_contact, handle_telegram_contact,
        handle_open_maps, handle_back_from_contacts, handle_back_to_contacts_callback
    )

    # Импорты обработчиков бронирования
    from handlers.booking_handlers import get_booking_handler

    # Импорты обработчиков администратора
    from handlers.admin_utils import admin_panel, back_to_main_menu, show_statistics
    from handlers.admin_users import (
        show_users_list, user_selected_callback, user_info_callback,
        handle_users_pagination, get_user_search_handler,
        back_to_users_list, exit_search_mode, show_full_users_list,
        back_to_search_mode, new_search
    )
    from handlers.admin_bookings import (
        show_bookings, show_pending_bookings, show_confirmed_bookings,
        show_cancelled_bookings, show_all_bookings, handle_booking_action,
        get_booking_date_handler, get_booking_cancellation_handler
    )
    from handlers.admin_bonuses import (
        handle_bonus_requests, refresh_bonus_requests, handle_bonus_request_action,
        get_bonus_handler
    )
    from handlers.admin_messages import (
        get_broadcast_handler, get_user_message_handler,
        message_user_callback
    )

    # Импорты обработчиков заказов
    from handlers.order_shift import (
        start_order_management,
        open_shift, close_shift,
        calculate_all_orders, show_shift_status
    )

    from handlers.order_creation import (
        handle_create_order, handle_table_number,
        handle_category_selection, handle_item_selection,
        handle_back_to_categories, finish_order
    )

    from handlers.order_management import (
        show_active_orders, add_items_to_existing_order,
        show_order_for_editing, remove_item_from_order,
        view_order_details, handle_add_items
    )

    from handlers.order_payment import (
        calculate_order, handle_cancel_calculation,
        show_payment_selection, handle_payment_selection,
        handle_back_to_calculation
    )

    from handlers.order_history import (
        show_order_history_menu, show_today_orders, show_yesterday_orders,
        show_all_closed_orders, show_select_date_menu, show_orders_by_date,
        show_shift_history, show_year_history,
        show_select_shift_menu, show_selected_shift_history,
        select_year_for_history, select_month_for_history,
        show_full_year_history, show_full_month_history,
        show_more_shifts
    )

    # Утилиты заказов
    from handlers.order_utils import cancel_order_creation, handle_back_to_order_management

    # Импорты обработчиков управления меню
    from handlers.menu_management_handlers import (
        get_menu_management_handlers,
        manage_menu,
        start_edit_item
    )

    # ========== НАСТРОЙКА ОБРАБОТЧИКОВ ==========
    
    # 1. НОВЫЕ ОБРАБОТЧИКИ ДЛЯ MINIAPP
    application.add_handler(MessageHandler(filters.Regex("^🌐 Веб-приложение$") & user_filter, open_miniapp))
    application.add_handler(CallbackQueryHandler(open_miniapp, pattern="^open_miniapp$"))
    
    # 2. Сначала добавляем ConversationHandler'ы
    application.add_handler(get_user_message_handler())
    application.add_handler(get_broadcast_handler())
    application.add_handler(get_bonus_handler())
    application.add_handler(get_booking_date_handler())
    application.add_handler(get_booking_cancellation_handler())
    application.add_handler(get_user_search_handler())
    
    # 3. Обработчики управления меню
    menu_handlers = get_menu_management_handlers()
    for handler in menu_handlers:
        application.add_handler(handler)

    # 4. ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ
    # Обновляем меню пользователя (добавляем кнопку MiniApp)
    application.add_handler(MessageHandler(filters.Regex("^💰 Мой баланс$") & user_filter, show_balance))
    application.add_handler(MessageHandler(filters.Regex("^🎁 Реферальная программа$") & user_filter, show_referral_info))
    application.add_handler(MessageHandler(filters.Regex("^📋 Мои бронирования$") & user_filter, show_user_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📞 Контакты$") & user_filter, show_contacts))

    # Кнопки фильтрации бронирований пользователя
    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & user_filter, handle_user_pending_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & user_filter, handle_user_confirmed_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & user_filter, handle_user_cancelled_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & user_filter, handle_user_all_bookings_button))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_user_back_to_bookings_button))

    # Обработчики контактов
    application.add_handler(MessageHandler(filters.Regex("^📞 Позвонить$") & user_filter, handle_call_contact))
    application.add_handler(MessageHandler(filters.Regex("^💬 Написать в Telegram$") & user_filter, handle_telegram_contact))
    application.add_handler(MessageHandler(filters.Regex("^📍 Мы на картах$") & user_filter, handle_open_maps))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_back_from_contacts))

    # Callback обработчики пользователя
    application.add_handler(CallbackQueryHandler(handle_user_cancel_booking, pattern="^user_cancel_booking_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_bookings_list, pattern="^back_to_bookings_list$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_contacts_callback, pattern="^back_to_contacts$"))

    # Conversation handlers пользователя
    application.add_handler(get_registration_handler())
    application.add_handler(get_spend_bonus_handler())
    application.add_handler(get_booking_handler())

    # 5. ОБРАБОТЧИКИ АДМИНИСТРАТОРА
    application.add_handler(MessageHandler(filters.Regex("^👥 Список пользователей$") & admin_filter, show_users_list))
    application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$") & admin_filter, show_statistics))
    application.add_handler(MessageHandler(filters.Regex("^📋 Запросы на списание$") & admin_filter, handle_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^🔄 Обновить список запросов$") & admin_filter, refresh_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^📅 Бронирования$") & admin_filter, show_bookings))
    application.add_handler(MessageHandler(filters.Regex("^🍽️ Управление заказами$") & admin_filter, start_order_management))
    application.add_handler(MessageHandler(filters.Regex("^🍴 Управление меню$") & admin_filter, manage_menu))

    # Кнопки фильтрации бронирований администратора
    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & admin_filter, show_pending_bookings))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & admin_filter, show_confirmed_bookings))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & admin_filter, show_cancelled_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & admin_filter, show_all_bookings))

    # Callback обработчики администратора для пользователей
    application.add_handler(CallbackQueryHandler(handle_users_pagination, pattern="^(users_page_|refresh_users)"))
    application.add_handler(CallbackQueryHandler(user_selected_callback, pattern="^select_user_"))
    application.add_handler(CallbackQueryHandler(user_info_callback, pattern="^info_"))
    application.add_handler(CallbackQueryHandler(message_user_callback, pattern="^message_"))
    application.add_handler(CallbackQueryHandler(exit_search_mode, pattern="^exit_search_mode$"))
    application.add_handler(CallbackQueryHandler(back_to_search_mode, pattern="^back_to_search_mode$"))
    application.add_handler(CallbackQueryHandler(new_search, pattern="^new_search$"))
    application.add_handler(CallbackQueryHandler(show_full_users_list, pattern="^show_full_users_list_"))
    application.add_handler(CallbackQueryHandler(back_to_users_list, pattern="^back_to_users_list$"))

    # Callback обработчики бронирований
    application.add_handler(CallbackQueryHandler(handle_booking_action, pattern="^(confirm_booking_|cancel_booking_)"))
    application.add_handler(CallbackQueryHandler(handle_bonus_request_action, pattern="^(approve_|reject_)"))

    # 6. ОБРАБОТЧИКИ УПРАВЛЕНИЯ ЗАКАЗАМИ
    # (оставляем без изменений, как в предыдущей версии)
    application.add_handler(CallbackQueryHandler(handle_create_order, pattern="^create_order$"))
    application.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(handle_item_selection, pattern="^item_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_categories$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_category_"))
    application.add_handler(CallbackQueryHandler(finish_order, pattern="^finish_order$"))
    application.add_handler(CallbackQueryHandler(cancel_order_creation, pattern="^cancel_order$"))
    application.add_handler(CallbackQueryHandler(handle_add_items, pattern="^add_items_"))
    application.add_handler(CallbackQueryHandler(view_order_details, pattern="^view_order_"))
    application.add_handler(CallbackQueryHandler(show_payment_selection, pattern="^calculate_"))
    application.add_handler(CallbackQueryHandler(handle_payment_selection, pattern="^payment_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_calculation, pattern="^back_to_calculation_"))
    application.add_handler(CallbackQueryHandler(show_active_orders, pattern="^active_orders$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_admin$"))
    application.add_handler(CallbackQueryHandler(handle_cancel_calculation, pattern="^cancel_calculation$"))
    application.add_handler(CallbackQueryHandler(add_items_to_existing_order, pattern="^add_to_existing_"))
    application.add_handler(CallbackQueryHandler(show_order_for_editing, pattern="^edit_order_"))
    application.add_handler(CallbackQueryHandler(remove_item_from_order, pattern="^remove_item_"))
    application.add_handler(CallbackQueryHandler(show_order_history_menu, pattern="^order_history$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_order_management$"))
    application.add_handler(CallbackQueryHandler(show_shift_history, pattern="^history_shift$"))
    application.add_handler(CallbackQueryHandler(show_year_history, pattern="^history_year$"))
    application.add_handler(CallbackQueryHandler(select_year_for_history, pattern="^history_year_"))
    application.add_handler(CallbackQueryHandler(select_month_for_history, pattern="^history_month_"))
    application.add_handler(CallbackQueryHandler(show_select_shift_menu, pattern="^history_select_shift$"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_.*_.*"))
    application.add_handler(CallbackQueryHandler(show_full_year_history, pattern="^history_full_year_"))
    application.add_handler(CallbackQueryHandler(show_full_month_history, pattern="^history_full_month_"))
    application.add_handler(CallbackQueryHandler(show_more_shifts, pattern="^history_month_more_"))
    application.add_handler(CallbackQueryHandler(open_shift, pattern="^open_shift$"))
    application.add_handler(CallbackQueryHandler(close_shift, pattern="^close_shift$"))
    application.add_handler(CallbackQueryHandler(calculate_all_orders, pattern="^calculate_all_orders$"))
    application.add_handler(CallbackQueryHandler(show_shift_status, pattern="^shift_status$"))

    # 7. КОМАНДЫ (ДОБАВЛЯЕМ НОВЫЕ ДЛЯ MINIAPP)
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset_shift", reset_shift_data))
    application.add_handler(CommandHandler("debug_shifts", debug_shifts))
    application.add_handler(CommandHandler("webapp", open_miniapp))  # НОВАЯ КОМАНДА
    application.add_handler(CommandHandler("test_miniapp", test_miniapp))  # НОВАЯ КОМАНДА ТЕСТА

    # 8. СПЕЦИАЛЬНЫЕ ОБРАБОТЧИКИ
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$"), handle_back_button))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ В главное меню$"), handle_back_button))

    # 9. ОБРАБОТЧИК НЕИЗВЕСТНЫХ СООБЩЕНИЙ (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_unknown_message))

def main():
    """Основная функция запуска бота"""
    try:
        # Проверка токена
        if not BOT_TOKEN:
            logger.error("❌ Токен бота не найден! Проверьте файл .env")
            return

        # Создание приложения
        application = Application.builder() \
            .token(BOT_TOKEN) \
            .post_init(post_init) \
            .post_stop(post_stop) \
            .build()

        # Настройка обработчиков
        logger.info("🔄 Настройка обработчиков...")
        setup_handlers(application)

        # Запуск бота
        logger.info("🚀 Запуск бота...")
        print("=" * 50)
        print("🤖 Бот запущен! Для остановки нажмите Ctrl+C")
        print("🌐 MiniApp доступен по команде /webapp")
        print("=" * 50)

        application.run_polling(
            allowed_updates=['message', 'callback_query'],
            timeout=60,
            drop_pending_updates=True,
            poll_interval=0.5
        )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    main()