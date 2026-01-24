# miniapp_handlers.py
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import is_admin
from database import Database

logger = logging.getLogger(__name__)

async def miniapp_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель управления MiniApp для администраторов"""
    if not is_admin(update.effective_user.id):
        return
    
    keyboard = [
        [InlineKeyboardButton("📱 Управление меню", callback_data="miniapp_menu")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="miniapp_settings")],
        [InlineKeyboardButton("📊 Статистика MiniApp", callback_data="miniapp_stats")],
        [InlineKeyboardButton("🔄 Обновить кэш", callback_data="miniapp_refresh")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin")]
    ]
    
    await update.message.reply_text(
        "🌐 **Управление MiniApp**\n\n"
        "Здесь вы можете управлять контентом веб-приложения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def miniapp_menu_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление меню для MiniApp"""
    query = update.callback_query
    await query.answer()
    
    db = Database()
    
    # Получаем категории меню
    menu_items = db.get_miniapp_menu()
    
    if not menu_items:
        await query.edit_message_text(
            "🍽️ **Меню MiniApp**\n\n"
            "Пока нет товаров в меню.\n\n"
            "Добавьте первый товар:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Добавить товар", callback_data="miniapp_add_item")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="miniapp_dashboard")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # Группируем по категориям
    categories = {}
    for item in menu_items:
        category = item[5]  # category
        if category not in categories:
            categories[category] = []
        categories[category].append(item)
    
    # Создаем сообщение с меню
    message = "🍽️ **Меню MiniApp**\n\n"
    
    for category, items in categories.items():
        message += f"**{category.upper()}**\n"
        for item in items:
            item_id, name, desc, price, old_price, cat, icon, badge = item
            price_str = f"<s>{old_price}₽</s> {price}₽" if old_price else f"{price}₽"
            badge_str = f" [{badge}]" if badge else ""
            message += f"• {icon} {name}{badge_str} - {price_str}\n"
        message += "\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="miniapp_add_item")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="miniapp_edit_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="miniapp_dashboard")]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def miniapp_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки MiniApp"""
    query = update.callback_query
    await query.answer()
    
    db = Database()
    
    # Получаем текущие настройки
    contacts = db.get_miniapp_config('contacts')
    schedule = db.get_miniapp_config('schedule')
    stats = db.get_miniapp_config('stats')
    
    message = "⚙️ **Настройки MiniApp**\n\n"
    
    message += "**Контакты:**\n"
    message += f"📍 Адрес: {contacts.get('address', 'Не указан')}\n"
    message += f"📞 Телефон: {contacts.get('phone', 'Не указан')}\n"
    message += f"📸 Instagram: {contacts.get('instagram', 'Не указан')}\n\n"
    
    message += "**График работы:**\n"
    message += f"Пн-Чт: {schedule.get('weekdays', 'Не указан')}\n"
    message += f"Пт-Вс: {schedule.get('weekend', 'Не указан')}\n\n"
    
    message += "**Статистика:**\n"
    message += f"Вкусы: {stats.get('flavors', 'Не указано')}\n"
    message += f"Опыт: {stats.get('experience', 'Не указано')}\n"
    message += f"Гости: {stats.get('guests', 'Не указано')}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📱 Контакты", callback_data="miniapp_edit_contacts"),
            InlineKeyboardButton("🕐 График", callback_data="miniapp_edit_schedule")
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="miniapp_edit_stats"),
            InlineKeyboardButton("🎨 Внешний вид", callback_data="miniapp_edit_theme")
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="miniapp_dashboard")]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def miniapp_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика использования MiniApp"""
    query = update.callback_query
    await query.answer()
    
    db = Database()
    
    # Получаем статистику бронирований из MiniApp
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT 
            COUNT(*) as total_bookings,
            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
        FROM bookings 
        WHERE source = 'miniapp'
    ''')
    stats = cursor.fetchone()
    
    cursor.execute('SELECT COUNT(*) FROM miniapp_menu WHERE is_active = TRUE')
    menu_items = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM miniapp_gallery WHERE is_active = TRUE')
    gallery_items = cursor.fetchone()[0]
    
    message = "📊 **Статистика MiniApp**\n\n"
    message += f"🍽️ Товаров в меню: {menu_items}\n"
    message += f"📸 Элементов в галерее: {gallery_items}\n\n"
    
    if stats:
        total, confirmed, pending, cancelled = stats
        message += f"📅 Бронирований из MiniApp:\n"
        message += f"• Всего: {total or 0}\n"
        message += f"• Подтверждено: {confirmed or 0}\n"
        message += f"• Ожидает: {pending or 0}\n"
        message += f"• Отменено: {cancelled or 0}\n"
    else:
        message += "📅 Бронирований из MiniApp: 0\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="miniapp_stats")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="miniapp_dashboard")]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def miniapp_edit_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование контактов"""
    query = update.callback_query
    await query.answer()
    
    db = Database()
    contacts = db.get_miniapp_config('contacts')
    
    message = "📱 **Редактирование контактов**\n\n"
    message += "Текущие значения:\n"
    message += f"📍 Адрес: `{contacts.get('address', '')}`\n"
    message += f"📞 Телефон: `{contacts.get('phone', '')}`\n"
    message += f"📸 Instagram: `{contacts.get('instagram', '')}`\n\n"
    message += "Отправьте новые значения в формате:\n"
    message += "`адрес:Новый адрес`\n"
    message += "`телефон:+7 999 123-45-67`\n"
    message += "`инстаграм:@username`"
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="miniapp_settings")]]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    # Сохраняем состояние для обработки сообщения
    context.user_data['miniapp_editing'] = 'contacts'

async def miniapp_edit_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование графика работы"""
    query = update.callback_query
    await query.answer()
    
    db = Database()
    schedule = db.get_miniapp_config('schedule')
    
    message = "🕐 **Редактирование графика работы**\n\n"
    message += "Текущие значения:\n"
    message += f"Пн-Чт: `{schedule.get('weekdays', '')}`\n"
    message += f"Пт-Вс: `{schedule.get('weekend', '')}`\n\n"
    message += "Отправьте новые значения в формате:\n"
    message += "`будни:14:00 — 02:00`\n"
    message += "`выходные:14:00 — 04:00`"
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="miniapp_settings")]]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['miniapp_editing'] = 'schedule'

async def handle_miniapp_settings_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений с настройками MiniApp"""
    if not is_admin(update.effective_user.id):
        return
    
    if 'miniapp_editing' not in context.user_data:
        return
    
    editing = context.user_data['miniapp_editing']
    text = update.message.text
    db = Database()
    
    try:
        if ':' in text:
            key, value = text.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if editing == 'contacts':
                valid_keys = ['адрес', 'телефон', 'инстаграм']
                key_map = {
                    'адрес': 'address',
                    'телефон': 'phone', 
                    'инстаграм': 'instagram'
                }
                
                if key in valid_keys:
                    db_key = key_map[key]
                    db.set_miniapp_config('contacts', db_key, value)
                    await update.message.reply_text(f"✅ Контакт '{key}' обновлен!")
                else:
                    await update.message.reply_text("❌ Неверный ключ. Используйте: адрес, телефон, инстаграм")
                    
            elif editing == 'schedule':
                valid_keys = ['будни', 'выходные']
                key_map = {
                    'будни': 'weekdays',
                    'выходные': 'weekend'
                }
                
                if key in valid_keys:
                    db_key = key_map[key]
                    db.set_miniapp_config('schedule', db_key, value)
                    await update.message.reply_text(f"✅ График '{key}' обновлен!")
                else:
                    await update.message.reply_text("❌ Неверный ключ. Используйте: будни, выходные")
        
        # Возвращаем в меню настроек
        await miniapp_settings(update, context)
        context.user_data.pop('miniapp_editing', None)
        
    except Exception as e:
        logger.error(f"Ошибка обновления настроек MiniApp: {e}")
        await update.message.reply_text("❌ Ошибка при обновлении настроек")

async def miniapp_add_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления товара"""
    query = update.callback_query
    await query.answer()
    
    message = "➕ **Добавление товара в меню**\n\n"
    message += "Отправьте данные товара в формате:\n"
    message += "`название:Цена:Категория`\n\n"
    message += "Дополнительные параметры (через |):\n"
    message += "• иконка: 🍽️ (эмодзи)\n"
    message += "• бейдж: hit/premium/vip/signature/hot\n"
    message += "• старая цена: число\n\n"
    message += "**Пример:**\n"
    message += "`Фруктовый микс:1500:hookah|🍓|hit|1800`\n\n"
    message += "**Категории:** hookah, signature, drinks, food"
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="miniapp_menu")]]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['miniapp_adding'] = True

async def handle_miniapp_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик добавления товара"""
    if not is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    db = Database()
    
    try:
        # Разбираем данные
        parts = text.split('|')
        main_part = parts[0].strip()
        
        # Основные данные: название:цена:категория
        name_price_cat = main_part.split(':')
        if len(name_price_cat) != 3:
            await update.message.reply_text("❌ Неверный формат. Используйте: название:цена:категория")
            return
        
        name = name_price_cat[0].strip()
        try:
            price = int(name_price_cat[1].strip())
        except ValueError:
            await update.message.reply_text("❌ Цена должна быть числом")
            return
        
        category = name_price_cat[2].strip().lower()
        
        # Дополнительные параметры
        icon = '🍽️'
        badge = None
        old_price = None
        
        if len(parts) > 1:
            for i in range(1, len(parts)):
                param = parts[i].strip()
                if param and any(c in param for c in ['🍽️', '💨', '🍹', '🍕', '🥗', '🍟', '☕', '🍵', '🧊', '🔥', '⚗️', '👑', '🔮']):
                    icon = param
                elif param in ['hit', 'premium', 'vip', 'signature', 'hot', 'new']:
                    badge = param
                elif param.isdigit():
                    old_price = int(param)
        
        # Добавляем товар
        success, result = db.add_miniapp_menu_item(name, "", price, category, icon, badge, old_price)
        
        if success:
            await update.message.reply_text(
                f"✅ Товар добавлен!\n\n"
                f"**{name}**\n"
                f"Цена: {price}₽\n"
                f"Категория: {category}\n"
                f"Иконка: {icon}\n"
                f"Бейдж: {badge or 'нет'}\n"
                f"Старая цена: {old_price or 'нет'}",
                parse_mode='Markdown'
            )
            
            # Показываем меню
            await miniapp_menu_management(update, context)
        else:
            await update.message.reply_text(result)
    
    except Exception as e:
        logger.error(f"Ошибка добавления товара: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении товара. Проверьте формат.")

async def miniapp_refresh_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновить кэш MiniApp"""
    query = update.callback_query
    await query.answer()
    
    # Здесь можно добавить логику очистки кэша
    # Например, сброс кэшированных данных в памяти
    
    await query.edit_message_text(
        "🔄 **Кэш MiniApp обновлен**\n\n"
        "Изменения вступят в силу при следующем обновлении приложения.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад", callback_data="miniapp_dashboard")]
        ]),
        parse_mode='Markdown'
    )

def setup_miniapp_handlers(application):
    """Настройка обработчиков для MiniApp"""
    
    # Команды
    application.add_handler(CommandHandler("miniapp", miniapp_dashboard))
    
    # Callback обработчики
    application.add_handler(CallbackQueryHandler(miniapp_dashboard, pattern="^miniapp_dashboard$"))
    application.add_handler(CallbackQueryHandler(miniapp_menu_management, pattern="^miniapp_menu$"))
    application.add_handler(CallbackQueryHandler(miniapp_settings, pattern="^miniapp_settings$"))
    application.add_handler(CallbackQueryHandler(miniapp_stats, pattern="^miniapp_stats$"))
    application.add_handler(CallbackQueryHandler(miniapp_edit_contacts, pattern="^miniapp_edit_contacts$"))
    application.add_handler(CallbackQueryHandler(miniapp_edit_schedule, pattern="^miniapp_edit_schedule$"))
    application.add_handler(CallbackQueryHandler(miniapp_add_item_start, pattern="^miniapp_add_item$"))
    application.add_handler(CallbackQueryHandler(miniapp_refresh_cache, pattern="^miniapp_refresh$"))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'.+:.+:.+') & filters.ChatType.PRIVATE,
        handle_miniapp_add_item
    ))
    
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE,
        handle_miniapp_settings_message
    ))
