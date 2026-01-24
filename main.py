import logging
import os
import json
import warnings
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.warnings import PTBUserWarning
from dotenv import load_dotenv
from config import BOT_TOKEN, ADMIN_IDS, WEB_APP_URL
from error_logger import setup_error_logging

# Игнорировать предупреждения PTBUserWarning
warnings.filterwarnings("ignore", category=PTBUserWarning)

# Загрузка переменных окружения
load_dotenv()


async def post_init(application):
    """Функция, выполняемая после инициализации бота"""
    logger.info("🤖 Бот успешно запущен и готов к работе!")

    # Получаем информацию о бота
    bot_info = await application.bot.get_me()
    logger.info(f"🔗 Бот: {bot_info.first_name} (@{bot_info.username})")
    logger.info(f"🆔 ID бота: {bot_info.id}")
    logger.info(f"🌐 Web App URL: {WEB_APP_URL}")


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


def setup_handlers(application):
    """Настройка всех обработчиков"""

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

    # Импорты обработчиков администратора (НОВЫЕ ИМПОРТЫ)
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
    from handlers.admin_handlers import reset_shift_data

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

    # Для совместимости с существующим кодом
    from handlers.order_utils import handle_order_buttons_outside_conversation

    # Утилиты
    from handlers.order_utils import cancel_order_creation, handle_back_to_order_management

    # Импорты обработчиков управления меню
    from handlers.menu_management_handlers import (
        get_menu_management_handlers,
        manage_menu,
        start_edit_item
    )

    # НОВАЯ ФУНКЦИЯ ДЛЯ ОТЛАДКИ
    from database import Database
    db = Database()
    db.add_payment_method_column()  # Добавить эту строку

    # НОВАЯ ФУНКЦИЯ: Обработка данных из Web App
    async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка данных из Web App"""
        try:
            if not update.message or not update.message.web_app_data:
                return
                
            # Получаем данные из Web App
            data = json.loads(update.message.web_app_data.data)
            user_id = update.effective_user.id
            
            logger.info(f"📱 Получены данные из Web App от пользователя {user_id}: {data}")
            
            data_type = data.get('type')
            
            if data_type == 'web_app_booking':
                # Обработка бронирования из Web App
                name = data.get('name', '').strip()
                phone = data.get('phone', '').strip()
                date = data.get('date')
                time = data.get('time')
                guests = data.get('guests')
                comment = data.get('comment', '')
                
                if not name or not phone:
                    await update.message.reply_text("❌ Пожалуйста, заполните имя и телефон.")
                    return
                
                # Получаем информацию о пользователе
                user_data = db.get_user(user_id)
                
                if not user_data:
                    # Если пользователь не зарегистрирован в боте, регистрируем
                    db.register_user(
                        user_id=user_id,
                        username=update.effective_user.username,
                        first_name=name.split()[0] if name else update.effective_user.first_name,
                        last_name=' '.join(name.split()[1:]) if len(name.split()) > 1 else '',
                        phone=phone
                    )
                
                # Сохраняем бронирование
                booking_id = db.create_booking(
                    user_id=user_id,
                    date=date,
                    time=time,
                    guests=guests,
                    comment=comment,
                    status='pending',
                    source='web_app'
                )
                
                if booking_id:
                    # Отправляем подтверждение пользователю
                    await update.message.reply_text(
                        f"✅ *Бронирование успешно создано!*\n\n"
                        f"📅 Дата: {date}\n"
                        f"🕐 Время: {time}\n"
                        f"👥 Гостей: {guests}\n"
                        f"💬 Пожелания: {comment if comment else 'Нет'}\n\n"
                        f"Мы свяжемся с вами для подтверждения.",
                        parse_mode='Markdown'
                    )
                    
                    # Уведомляем администраторов
                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"📱 *НОВОЕ БРОНИРОВАНИЕ ИЗ WEB APP*\n\n"
                                     f"👤 Пользователь: {name}\n"
                                     f"📱 Телефон: {phone}\n"
                                     f"📅 Дата: {date}\n"
                                     f"🕐 Время: {time}\n"
                                     f"👥 Гостей: {guests}\n"
                                     f"💬 Пожелания: {comment if comment else 'Нет'}\n"
                                     f"🆔 ID пользователя: {user_id}",
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
                else:
                    await update.message.reply_text("❌ Ошибка при создании бронирования. Попробуйте позже.")
                    
            elif data_type == 'web_app_contact':
                # Обработка запроса контактов
                contact_type = data.get('contact_type')
                
                if contact_type == 'call':
                    await update.message.reply_text(
                        "📞 *Наш телефон:* +7 (999) 123-45-67\n\n"
                        "Мы ждём вашего звонка с 14:00 до 04:00!",
                        parse_mode='Markdown'
                    )
                elif contact_type == 'telegram':
                    await update.message.reply_text(
                        "💬 *Наш Telegram:* @vovseTyajkie\n\n"
                        "Пишите нам в любое время!",
                        parse_mode='Markdown'
                    )
                elif contact_type == 'map':
                    await update.message.reply_text(
                        "📍 *Наш адрес:* ул. Химическая, 52\n\n"
                        "Ждём вас в гости!",
                        parse_mode='Markdown'
                    )
                    
            elif data_type == 'web_app_menu_request':
                # Запрос меню через Web App
                from handlers.menu_management_handlers import get_menu_categories
                
                categories = get_menu_categories()
                if categories:
                    message = "🍽️ *Наше меню:*\n\n"
                    for category in categories:
                        message += f"• {category['name']}\n"
                    
                    await update.message.reply_text(
                        message + "\nВыберите категорию в Web App для просмотра позиций.",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text("🍽️ Меню временно недоступно.")
                    
        except Exception as e:
            logger.error(f"Ошибка обработки Web App данных: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке данных.")

    # НОВАЯ ФУНКЦИЯ ДЛЯ ОТЛАДКИ
    async def debug_shifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для отладки - показать все смены"""
        if not is_admin(update.effective_user.id):
            return

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

    # НОВАЯ ФУНКЦИЯ: Отправка меню с Web App кнопкой
    async def send_web_app_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправка меню с кнопкой Web App"""
        user_id = update.effective_user.id
        
        # Проверяем регистрацию
        user_data = db.get_user(user_id)
        
        if not user_data:
            # Если пользователь не зарегистрирован, показываем приветствие
            keyboard = [
                [InlineKeyboardButton("📱 Открыть меню", web_app=WebAppInfo(url=WEB_APP_URL))],
                [InlineKeyboardButton("📝 Зарегистрироваться", callback_data="register")]
            ]
            
            await update.message.reply_text(
                "🍸 *Добро пожаловать в 'Во Все Тяжкие'!*\n\n"
                "Для полного доступа ко всем функциям пройдите регистрацию.\n"
                "Или откройте меню через Web App:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            # Пользователь зарегистрирован
            keyboard = [
                [InlineKeyboardButton("📱 Открыть меню", web_app=WebAppInfo(url=WEB_APP_URL))],
                [
                    InlineKeyboardButton("💰 Баланс", callback_data="balance"),
                    InlineKeyboardButton("📅 Бронь", callback_data="my_bookings")
                ],
                [
                    InlineKeyboardButton("🎁 Рефералы", callback_data="referrals"),
                    InlineKeyboardButton("📞 Контакты", callback_data="contacts")
                ]
            ]
            
            await update.message.reply_text(
                f"🍸 *С возвращением, {user_data[2]}!*\n\n"
                f"💰 Баланс: *{user_data[5]} баллов*\n"
                f"📱 Используйте Web App для:\n"
                f"• Просмотра меню\n"
                f"• Бронирования столиков\n"
                f"• Просмотра галереи\n\n"
                f"Или используйте кнопки ниже:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    # НОВАЯ ФУНКЦИЯ ДЛЯ ОБРАБОТКИ ПОИСКА ПОЛЬЗОВАТЕЛЕЙ АДМИНОМ
    async def handle_admin_user_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений админа для поиска пользователей"""
        user_id = update.effective_user.id

        # Проверяем, является ли пользователь администратором
        if not is_admin(user_id):
            return False  # Не админ

        # Проверяем, находится ли админ в режиме поиска пользователей
        if not context.user_data.get('search_users_mode', False):
            # Не в режиме поиска - пропускаем дальше
            return False

        # Игнорируем кнопки меню
        text = update.message.text.strip()
        menu_buttons = ["👥 Список пользователей", "📊 Статистика", "📋 Запросы на списание",
                        "🔄 Обновить список запросов", "📅 Бронирования", "🍽️ Управление заказами",
                        "🍴 Управление меню", "✏️ Редактировать позицию", "⬅️ Назад",
                        "⬅️ В главное меню", "⏳ Ожидающие", "✅ Подтвержденные",
                        "❌ Отмененные", "📋 Все бронирования", "💰 Мой баланс",
                        "🎁 Реферальная программа", "📋 Мои бронирования", "📞 Контакты",
                        "📞 Позвонить", "💬 Написать в Telegram", "📍 Мы на картах"]

        if text in menu_buttons:
            # Это кнопка меню, а не поисковый запрос
            return False

        # Если в режиме поиска - обрабатываем как поисковый запрос
        search_query = text

        if not search_query:
            await update.message.reply_text("❌ Введите текст для поиска (ID, имя или фамилию)")
            return True  # Блокируем цепочку

        logger.info(f"Админ {user_id} ищет пользователя: {search_query}")

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
            await update.message.reply_text(
                f"❌ Пользователи по запросу '{search_query}' не найдены.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")],
                    [InlineKeyboardButton("📋 Показать полный список", callback_data="show_full_users_list_0")],
                    [InlineKeyboardButton("❌ Выйти из поиска", callback_data="exit_search_mode")]
                ])
            )
            return True  # Блокируем цепочку

        # Показываем найденных пользователей
        message = f"🔍 Результаты поиска по запросу: '{search_query}'\n\n"
        message += f"Найдено пользователей: {len(users)}\n\n"

        keyboard = []

        for user in users:
            keyboard.append([InlineKeyboardButton(
                f"{user[2]} {user[3]} (ID: {user[0]}) | 💰 {user[5]} баллов",
                callback_data=f"select_user_{user[0]}"
            )])

        keyboard.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")])
        keyboard.append([InlineKeyboardButton("📋 Показать полный список", callback_data="show_full_users_list_0")])
        keyboard.append([InlineKeyboardButton("❌ Выйти из поиска", callback_data="exit_search_mode")])

        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return True  # Блокируем дальнейшую обработку

    # ========== ОБРАБОТЧИК ПОИСКА ПОЛЬЗОВАТЕЛЕЙ АДМИНОМ ==========
    # Создаем UserMessageHandler для обработки отправки сообщений пользователям
    user_message_conversation = get_user_message_handler()

    # Сначала добавляем ConversationHandler для отправки сообщений (более высокий приоритет)
    application.add_handler(user_message_conversation)

    # Затем добавляем обработчик поиска пользователей (низкий приоритет)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & admin_filter,
        handle_admin_user_search_text
    ), group=2)  # group=2 - более низкий приоритет

    # ДОБАВЛЕНЫ ОБРАБОТЧИКИ УПРАВЛЕНИЯ МЕНЮ ПЕРВЫМИ (чтобы избежать конфликтов)
    menu_handlers = get_menu_management_handlers()
    for handler in menu_handlers:
        application.add_handler(handler)

    # ДОБАВЛЕН НОВЫЙ ОБРАБОТЧИК ПОИСКА ПОЛЬЗОВАТЕЛЕЙ
    application.add_handler(get_user_search_handler())

    # ДОБАВЛЕНЫ ОБРАБОТЧИКИ ДЛЯ РЕЖИМА ПОИСКА ПОЛЬЗОВАТЕЛЕЙ
    application.add_handler(CallbackQueryHandler(exit_search_mode, pattern="^exit_search_mode$"))
    application.add_handler(CallbackQueryHandler(back_to_search_mode, pattern="^back_to_search_mode$"))
    application.add_handler(CallbackQueryHandler(new_search, pattern="^new_search$"))
    application.add_handler(CallbackQueryHandler(show_full_users_list, pattern="^show_full_users_list_"))

    # ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ (только для обычных пользователей)
    # Основные кнопки меню пользователя
    application.add_handler(MessageHandler(filters.Regex("^💰 Мой баланс$") & user_filter, show_balance))
    application.add_handler(
        MessageHandler(filters.Regex("^🎁 Реферальная программа$") & user_filter, show_referral_info))
    application.add_handler(MessageHandler(filters.Regex("^📋 Мои бронирования$") & user_filter, show_user_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📞 Контакта$") & user_filter, show_contacts))

    # Кнопки фильтрации бронирований пользователя
    application.add_handler(
        MessageHandler(filters.Regex("^⏳ Ожидающие$") & user_filter, handle_user_pending_bookings_button))
    application.add_handler(
        MessageHandler(filters.Regex("^✅ Подтвержденные$") & user_filter, handle_user_confirmed_bookings_button))
    application.add_handler(
        MessageHandler(filters.Regex("^❌ Отмененные$") & user_filter, handle_user_cancelled_bookings_button))
    application.add_handler(
        MessageHandler(filters.Regex("^📋 Все бронирования$") & user_filter, handle_user_all_bookings_button))
    application.add_handler(
        MessageHandler(filters.Regex("^⬅️ Назад$") & user_filter, handle_user_back_to_bookings_button))

    # Обработчики контактов
    application.add_handler(MessageHandler(filters.Regex("^📞 Контакты$") & user_filter, show_contacts))
    application.add_handler(MessageHandler(filters.Regex("^📞 Позвонить$") & user_filter, handle_call_contact))
    application.add_handler(
        MessageHandler(filters.Regex("^💬 Написать в Telegram$") & user_filter, handle_telegram_contact))
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

    # ОБРАБОТЧИКИ АДМИНИСТРАТОРА (только для администраторов)
    # Основные кнопки меню администратора
    application.add_handler(MessageHandler(filters.Regex("^👥 Список пользователей$") & admin_filter, show_users_list))
    application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$") & admin_filter, show_statistics))
    application.add_handler(
        MessageHandler(filters.Regex("^📋 Запросы на списание$") & admin_filter, handle_bonus_requests))
    application.add_handler(
        MessageHandler(filters.Regex("^🔄 Обновить список запросов$") & admin_filter, refresh_bonus_requests))
    application.add_handler(MessageHandler(filters.Regex("^📅 Бронирования$") & admin_filter, show_bookings))
    application.add_handler(
        MessageHandler(filters.Regex("^🍽️ Управление заказами$") & admin_filter, start_order_management))

    # Обработчики управления меню добавляются через get_menu_management_handlers()
    application.add_handler(MessageHandler(filters.Regex("^🍴 Управление меню$") & admin_filter, manage_menu))

    # ДОБАВЛЕН НОВЫЙ ОБРАБОТЧИК ДЛЯ ПАГИНАЦИИ ПОЛЬЗОВАТЕЛЕЙ И ПОИСКА
    application.add_handler(CallbackQueryHandler(handle_users_pagination, pattern="^(users_page_|refresh_users)"))

    # Кнопки фильтрации бронирований администратора
    application.add_handler(MessageHandler(filters.Regex("^⏳ Ожидающие$") & admin_filter, show_pending_bookings))
    application.add_handler(MessageHandler(filters.Regex("^✅ Подтвержденные$") & admin_filter, show_confirmed_bookings))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отмененные$") & admin_filter, show_cancelled_bookings))
    application.add_handler(MessageHandler(filters.Regex("^📋 Все бронирования$") & admin_filter, show_all_bookings))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$") & admin_filter, back_to_main_menu))
    application.add_handler(MessageHandler(filters.Regex("^⬅️ В главное меню$") & admin_filter, back_to_main_menu))

    # Conversation handlers администратора (НОВЫЕ ИМПОРТЫ)
    application.add_handler(get_broadcast_handler())
    application.add_handler(get_user_message_handler())
    application.add_handler(get_bonus_handler())
    application.add_handler(get_booking_date_handler())
    application.add_handler(get_booking_cancellation_handler())

    # ========== ОБРАБОТЧИКИ УПРАВЛЕНИЯ ЗАКАЗАМИ (БЕЗ CONVERSATIONHANDLER) ==========

    # Основные кнопки управления заказами
    application.add_handler(CallbackQueryHandler(handle_create_order, pattern="^create_order$"))

    # Обработчики категорий и позиций
    application.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(handle_item_selection, pattern="^item_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_categories$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_categories, pattern="^back_to_category_"))
    application.add_handler(CallbackQueryHandler(finish_order, pattern="^finish_order$"))
    application.add_handler(CallbackQueryHandler(cancel_order_creation, pattern="^cancel_order$"))

    # Обработчики управления существующими заказами
    application.add_handler(CallbackQueryHandler(handle_add_items, pattern="^add_items_"))
    application.add_handler(CallbackQueryHandler(view_order_details, pattern="^view_order_"))
    application.add_handler(CallbackQueryHandler(show_payment_selection, pattern="^calculate_"))
    application.add_handler(CallbackQueryHandler(handle_payment_selection, pattern="^payment_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_calculation, pattern="^back_to_calculation_"))
    application.add_handler(CallbackQueryHandler(show_active_orders, pattern="^active_orders$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_admin$"))
    application.add_handler(CallbackQueryHandler(handle_cancel_calculation, pattern="^cancel_calculation$"))
    application.add_handler(CallbackQueryHandler(add_items_to_existing_order, pattern="^add_to_existing_"))

    # Обработчики для редактирования заказа
    application.add_handler(CallbackQueryHandler(show_order_for_editing, pattern="^edit_order_"))
    application.add_handler(CallbackQueryHandler(remove_item_from_order, pattern="^remove_item_"))

    # Обработчики истории заказов
    application.add_handler(CallbackQueryHandler(show_order_history_menu, pattern="^order_history$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_management, pattern="^back_to_order_management$"))

    # Обработчики новой статистики
    application.add_handler(CallbackQueryHandler(show_shift_history, pattern="^history_shift$"))
    application.add_handler(CallbackQueryHandler(show_year_history, pattern="^history_year$"))
    application.add_handler(CallbackQueryHandler(select_year_for_history, pattern="^history_year_"))
    application.add_handler(CallbackQueryHandler(select_month_for_history, pattern="^history_month_"))
    application.add_handler(CallbackQueryHandler(show_select_shift_menu, pattern="^history_select_shift$"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_"))

    # Обработчики статистики за весь год/месяц
    application.add_handler(CallbackQueryHandler(show_full_year_history, pattern="^history_full_year_"))
    application.add_handler(CallbackQueryHandler(show_full_month_history, pattern="^history_full_month_"))

    # Обработчики пагинации смен
    application.add_handler(CallbackQueryHandler(show_more_shifts, pattern="^history_month_more_"))

    # Обработчики управления сменой
    application.add_handler(CallbackQueryHandler(open_shift, pattern="^open_shift$"))
    application.add_handler(CallbackQueryHandler(close_shift, pattern="^close_shift$"))
    application.add_handler(CallbackQueryHandler(calculate_all_orders, pattern="^calculate_all_orders$"))
    application.add_handler(CallbackQueryHandler(show_shift_status, pattern="^shift_status$"))

    # Callback обработчики администратора
    application.add_handler(CallbackQueryHandler(user_selected_callback, pattern="^select_user_"))
    application.add_handler(CallbackQueryHandler(user_info_callback, pattern="^info_"))
    application.add_handler(CallbackQueryHandler(handle_booking_action, pattern="^(confirm_booking_|cancel_booking_)"))
    application.add_handler(CallbackQueryHandler(handle_bonus_request_action, pattern="^(approve_|reject_)"))
    application.add_handler(CallbackQueryHandler(message_user_callback, pattern="^message_"))
    application.add_handler(CallbackQueryHandler(show_selected_shift_history, pattern="^history_shift_.*_.*"))

    # ДОБАВЛЕН НОВЫЙ ОБРАБОТЧИК ДЛЯ КНОПКИ "НАЗАД К СПИСКУ"
    application.add_handler(CallbackQueryHandler(back_to_users_list, pattern="^back_to_users_list$"))

    # ВАЖНО: Обработчик для кнопки "Редактировать позицию" в меню управления меню
    application.add_handler(MessageHandler(filters.Regex("^✏️ Редактировать позицию$") & admin_filter, start_edit_item))

    # КОМАНДЫ
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset_shift", reset_shift_data))
    application.add_handler(CommandHandler("debug_shifts", debug_shifts))  # НОВАЯ КОМАНДА
    
    # НОВАЯ КОМАНДА ДЛЯ WEB APP
    application.add_handler(CommandHandler("menu", send_web_app_menu))
    
    # ОБРАБОТЧИК ДАННЫХ ИЗ WEB APP
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

    # Обработчик кнопки "Назад" для обоих типов пользователей
    async def handle_back_button(update: Update, context):
        user_id = update.effective_user.id
        if is_admin(user_id):
            await back_to_main_menu(update, context)
        else:
            await back_to_main(update, context)

    application.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$"), handle_back_button))

    # УМНЫЙ ОБРАБОТЧИК ВВОДА НОМЕРА СТОЛА - только когда это действительно нужно
    async def smart_table_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Умный обработчик ввода номера стола - только когда пользователь в процессе создания заказа"""
        user_id = update.effective_user.id

        # Проверяем, является ли пользователь администратором
        if not is_admin(user_id):
            return False

        # КРИТИЧЕСКАЯ ПРОВЕРКА: Если админ в режиме поиска пользователей - НЕ создавать заказ
        if context.user_data.get('search_users_mode', False):
            logger.info(f"Админ {user_id} в режиме поиска, НЕ создаем заказ для: {update.message.text}")
            return False  # Пропускаем, сообщение уже обработано поиском

        # Проверяем, ожидает ли система ввод номера стола
        # Флаг expecting_table_number устанавливается только при нажатии "Создать заказ"
        if not context.user_data.get('expecting_table_number', False):
            logger.info(f"Админ {user_id}: не ожидаем номер стола, пропускаем: {update.message.text}")
            return False  # Не ожидаем номер стола - не обрабатываем

        # Проверяем, является ли ввод числом
        if not update.message.text.isdigit():
            await update.message.reply_text("❌ Номер стола должен быть числом. Попробуйте снова:")
            return True  # Блокируем цепочку

        # Если ожидаем номер стола и это число - обрабатываем
        logger.info(f"Админ {user_id} вводит номер стола: {update.message.text}")
        await handle_table_number(update, context)

        # Сбрасываем флаг ожидания после обработки
        context.user_data.pop('expecting_table_number', None)

        return True  # Блокируем цепочку

    # Этот обработчик должен быть ПОСЛЕ обработчика поиска пользователей
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & admin_filter,
        smart_table_number_handler
    ))

    # Обработчик неизвестных сообщений (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ)
    async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Для администраторов показываем другое сообщение
        if is_admin(update.effective_user.id):
            await update.message.reply_text(
                "❌ Неизвестная команда. Используйте кнопки меню администратора.\n"
                f"Или используйте команду /menu для Web App."
            )
        else:
            await update.message.reply_text(
                "❌ Неизвестная команда. Используйте кнопки меню.\n"
                f"Или используйте команду /menu для Web App."
            )

    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, unknown_message))


def main():
    """Основная функция запуска бота"""
    try:
        # Проверка токена
        if not BOT_TOKEN:
            logger.error("❌ Токен бота не найден! Проверьте файл .env")
            return

        # Создание приложения
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).post_stop(post_stop).build()

        # Настройка обработчиков
        logger.info("🔄 Настройка обработчиков...")
        setup_handlers(application)

        # Запуск бота
        logger.info("🚀 Запуск бота...")
        print("=" * 50)
        print("🤖 Бот запущен! Для остановки нажмите Ctrl+C")
        print(f"🌐 Web App доступен по адресу: {WEB_APP_URL}")
        print("📱 Пользователи могут открыть Web App командой /menu")
        print("=" * 50)

        application.run_polling(
            allowed_updates=['message', 'callback_query', 'web_app_data'],
            timeout=60,
            drop_pending_updates=True
        )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    # Базовая настройка логирования перед запуском
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    main()
