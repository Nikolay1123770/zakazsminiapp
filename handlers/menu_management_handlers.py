from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from config import ADMIN_IDS
from database import Database
from keyboards.menus import (
    get_menu_management_keyboard, get_categories_keyboard,
    get_menu_items_keyboard, get_menu_item_actions_keyboard,
    get_edit_confirmation_keyboard, get_back_to_menu_management_keyboard,
    get_admin_main_menu, get_cancel_keyboard
)
import logging

logger = logging.getLogger(__name__)

db = Database()

# Состояния для управления меню
AWAITING_ITEM_NAME, AWAITING_ITEM_PRICE = range(2)
AWAITING_EDIT_NAME, AWAITING_EDIT_PRICE = range(2, 4)


def is_admin(user_id):
    return user_id in ADMIN_IDS


async def manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню управления меню"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return

    await update.message.reply_text(
        "🍴 Управление меню\n\n"
        "Выберите действие:",
        reply_markup=get_menu_management_keyboard()
    )


async def view_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр всего меню"""
    if not is_admin(update.effective_user.id):
        return

    categories = db.get_all_menu_categories()

    if not categories:
        await update.message.reply_text(
            "📭 Меню пусто. Добавьте позиции в меню.",
            reply_markup=get_menu_management_keyboard()
        )
        return

    message = "📋 Текущее меню:\n\n"

    for category in categories:
        items = db.get_menu_items_by_category(category)
        if items:
            message += f"🍽️ {category}:\n"
            for item in items:
                message += f"• {item[1]} - {item[2]}₽\n"
            message += "\n"

    await update.message.reply_text(
        message,
        reply_markup=get_menu_management_keyboard()
    )


async def show_categories_for_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action):
    """Показать категории для выбора действия"""
    if not is_admin(update.effective_user.id):
        return

    categories = db.get_all_menu_categories()

    if not categories:
        await update.message.reply_text(
            "📭 Нет доступных категорий. Сначала добавьте позиции в меню.",
            reply_markup=get_menu_management_keyboard()
        )
        return

    action_texts = {
        "add": "➕ Добавление новой позиции",
        "edit": "✏️ Редактирование позиции",
        "delete": "🗑️ Удаление позиции"
    }

    # Сохраняем действие в context для дальнейшего использования
    context.user_data['menu_action'] = action

    await update.message.reply_text(
        f"{action_texts.get(action, 'Действие')}\n\n"
        "Выберите категорию:",
        reply_markup=get_categories_keyboard(categories)
    )


async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора категории"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    category = query.data.replace("menu_category_", "")
    action = context.user_data.get('menu_action')

    if action == "add":
        # Для добавления сохраняем категорию и запрашиваем название
        context.user_data['new_item_category'] = category
        await query.message.reply_text(
            f"➕ Добавление в категорию: {category}\n\n"
            "Введите название новой позиции:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_ITEM_NAME

    else:
        # Для других действий показываем список позиций в категории
        items = db.get_menu_items_by_category(category)

        if not items:
            await query.message.reply_text(
                f"📭 В категории '{category}' нет позиций.",
                reply_markup=get_back_to_menu_management_keyboard()
            )
            return

        action_prefixes = {
            "edit": "edit_item",
            "delete": "delete_item"
        }

        prefix = action_prefixes.get(action, "view_item")

        await query.message.reply_text(
            f"📋 Позиции в категории '{category}':",
            reply_markup=get_menu_items_keyboard(items, prefix)
        )


# ДОБАВЛЕНИЕ НОВОЙ ПОЗИЦИИ
async def start_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать добавление новой позиции"""
    if not is_admin(update.effective_user.id):
        return

    await show_categories_for_action(update, context, "add")
    return AWAITING_ITEM_NAME


async def process_item_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия позиции"""
    if update.message.text == "❌ Отмена":
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Добавление позиции отменено.",
            reply_markup=get_menu_management_keyboard()
        )
        return ConversationHandler.END

    item_name = update.message.text.strip()

    # Проверяем, не существует ли уже позиция с таким названием
    existing_item = db.get_menu_item_by_name(item_name)
    if existing_item:
        await update.message.reply_text(
            "❌ Позиция с таким названием уже существует. Введите другое название:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_ITEM_NAME

    context.user_data['new_item_name'] = item_name

    await update.message.reply_text(
        "💰 Введите цену позиции (только число, без символов):",
        reply_markup=get_cancel_keyboard()
    )
    return AWAITING_ITEM_PRICE


async def process_item_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода цены позиции"""
    if update.message.text == "❌ Отмена":
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Добавление позиции отменено.",
            reply_markup=get_menu_management_keyboard()
        )
        return ConversationHandler.END

    try:
        price = int(update.message.text.strip())
        if price <= 0:
            raise ValueError("Цена должна быть положительной")
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат цены. Введите целое положительное число:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_ITEM_PRICE

    # Получаем сохраненные данные
    name = context.user_data.get('new_item_name')
    category = context.user_data.get('new_item_category')

    # Добавляем позицию в базу
    success, message = db.add_menu_item(name, price, category)

    if success:
        await update.message.reply_text(
            f"✅ Позиция успешно добавлена!\n\n"
            f"🍽️ Название: {name}\n"
            f"💰 Цена: {price}₽\n"
            f"📁 Категория: {category}",
            reply_markup=get_menu_management_keyboard()
        )
    else:
        await update.message.reply_text(
            f"❌ {message}",
            reply_markup=get_menu_management_keyboard()
        )

    context.user_data.clear()
    return ConversationHandler.END


# РЕДАКТИРОВАНИЕ ПОЗИЦИЙ
async def start_edit_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать редактирование позиции"""
    if not is_admin(update.effective_user.id):
        return

    await show_categories_for_action(update, context, "edit")


async def handle_edit_item_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора позиции для редактирования"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    item_id = int(query.data.replace("edit_item_", ""))
    item = db.get_menu_item_by_id(item_id)

    if not item:
        await query.message.reply_text(
            "❌ Позиция не найдена.",
            reply_markup=get_back_to_menu_management_keyboard()
        )
        return

    await query.message.reply_text(
        f"✏️ Редактирование позиции:\n\n"
        f"🍽️ Название: {item[1]}\n"
        f"💰 Цена: {item[2]}₽\n"
        f"📁 Категория: {item[3]}\n\n"
        f"Выберите что хотите изменить:",
        reply_markup=get_menu_item_actions_keyboard(item_id)
    )


async def start_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать изменение названия"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    item_id = int(query.data.replace("edit_name_", ""))
    context.user_data['editing_item_id'] = item_id
    context.user_data['editing_field'] = 'name'

    item = db.get_menu_item_by_id(item_id)

    await query.message.reply_text(
        f"✏️ Изменение названия позиции:\n"
        f"Текущее название: {item[1]}\n\n"
        f"Введите новое название:",
        reply_markup=get_cancel_keyboard()
    )
    return AWAITING_EDIT_NAME


async def start_edit_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать изменение цены"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    item_id = int(query.data.replace("edit_price_", ""))
    context.user_data['editing_item_id'] = item_id
    context.user_data['editing_field'] = 'price'

    item = db.get_menu_item_by_id(item_id)

    await query.message.reply_text(
        f"💰 Изменение цены позиции:\n"
        f"Текущая цена: {item[2]}₽\n\n"
        f"Введите новую цену:",
        reply_markup=get_cancel_keyboard()
    )
    return AWAITING_EDIT_PRICE


async def process_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения поля"""
    if update.message.text == "❌ Отмена":
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Редактирование отменено.",
            reply_markup=get_menu_management_keyboard()
        )
        return ConversationHandler.END

    item_id = context.user_data.get('editing_item_id')
    field = context.user_data.get('editing_field')
    value = update.message.text.strip()

    item = db.get_menu_item_by_id(item_id)
    if not item:
        await update.message.reply_text(
            "❌ Позиция не найдена.",
            reply_markup=get_menu_management_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END

    try:
        if field == 'name':
            # Проверяем, не существует ли другой позиции с таким же названием
            existing_item = db.get_menu_item_by_name(value)
            if existing_item and existing_item[0] != item_id:
                await update.message.reply_text(
                    "❌ Позиция с таким названием уже существует. Введите другое название:",
                    reply_markup=get_cancel_keyboard()
                )
                return AWAITING_EDIT_NAME

            success, message = db.update_menu_item(item_id, value, item[2], item[3])

        elif field == 'price':
            try:
                price = int(value)
                if price <= 0:
                    raise ValueError("Цена должна быть положительной")
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат цены. Введите целое положительное число:",
                    reply_markup=get_cancel_keyboard()
                )
                return AWAITING_EDIT_PRICE

            success, message = db.update_menu_item(item_id, item[1], price, item[3])

        if success:
            updated_item = db.get_menu_item_by_id(item_id)
            await update.message.reply_text(
                f"✅ {message}\n\n"
                f"Обновленная позиция:\n"
                f"🍽️ Название: {updated_item[1]}\n"
                f"💰 Цена: {updated_item[2]}₽\n"
                f"📁 Категория: {updated_item[3]}",
                reply_markup=get_menu_management_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ {message}",
                reply_markup=get_menu_management_keyboard()
            )

    except Exception as e:
        logger.error(f"Ошибка при редактировании позиции: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при редактировании.",
            reply_markup=get_menu_management_keyboard()
        )

    context.user_data.clear()
    return ConversationHandler.END


# УДАЛЕНИЕ ПОЗИЦИЙ
async def start_delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать удаление позиции"""
    if not is_admin(update.effective_user.id):
        return

    await show_categories_for_action(update, context, "delete")


async def handle_delete_item_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора позиции для удаления"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    item_id = int(query.data.replace("delete_item_", ""))
    item = db.get_menu_item_by_id(item_id)

    if not item:
        await query.message.reply_text(
            "❌ Позиция не найдена.",
            reply_markup=get_back_to_menu_management_keyboard()
        )
        return

    await query.message.reply_text(
        f"🗑️ Вы уверены, что хотите удалить позицию?\n\n"
        f"🍽️ Название: {item[1]}\n"
        f"💰 Цена: {item[2]}₽\n"
        f"📁 Категория: {item[3]}\n\n"
        f"Эта операция необратима!",
        reply_markup=get_edit_confirmation_keyboard(item_id)
    )


async def confirm_delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления позиции"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    item_id = int(query.data.replace("confirm_delete_", ""))
    item = db.get_menu_item_by_id(item_id)

    if not item:
        await query.message.reply_text(
            "❌ Позиция не найдена.",
            reply_markup=get_back_to_menu_management_keyboard()
        )
        return

    success, message = db.delete_menu_item(item_id)

    if success:
        await query.message.reply_text(
            f"✅ {message}\n\n"
            f"Удаленная позиция: {item[1]}",
            reply_markup=get_back_to_menu_management_keyboard()
        )
    else:
        await query.message.reply_text(
            f"❌ {message}",
            reply_markup=get_back_to_menu_management_keyboard()
        )


async def cancel_delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена удаления позиции"""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "❌ Удаление отменено.",
        reply_markup=get_back_to_menu_management_keyboard()
    )


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
async def back_to_categories_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к списку категорий"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    action = context.user_data.get('menu_action')
    categories = db.get_all_menu_categories()

    action_texts = {
        "add": "➕ Добавление новой позиции",
        "edit": "✏️ Редактирование позиции",
        "delete": "🗑️ Удаление позиции"
    }

    await query.message.reply_text(
        f"{action_texts.get(action, 'Действие')}\n\n"
        "Выберите категорию:",
        reply_markup=get_categories_keyboard(categories)
    )


async def back_to_menu_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в управление меню"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    context.user_data.clear()
    await query.message.reply_text(
        "🍴 Управление меню",
        reply_markup=get_menu_management_keyboard()
    )


async def back_to_admin_main_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню администратора из управления меню"""
    if not is_admin(update.effective_user.id):
        return

    context.user_data.clear()
    await update.message.reply_text(
        "👨‍💼 Панель администратора",
        reply_markup=get_admin_main_menu()
    )


async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=get_menu_management_keyboard()
    )
    return ConversationHandler.END


# Создаем обработчики
def get_menu_management_handlers():
    """Возвращает все обработчики для управления меню"""

    add_item_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить позицию$"), start_add_item)],
        states={
            AWAITING_ITEM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_item_name)],
            AWAITING_ITEM_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_item_price)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_operation),
            MessageHandler(filters.Regex("^⬅️ Назад в админ-панель$"), back_to_admin_main_from_menu)
        ]
    )

    edit_name_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_name, pattern="^edit_name_")],
        states={
            AWAITING_EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_field)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_operation),
            MessageHandler(filters.Regex("^⬅️ Назад в админ-панель$"), back_to_admin_main_from_menu)
        ]
    )

    edit_price_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_price, pattern="^edit_price_")],
        states={
            AWAITING_EDIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_field)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_operation),
            MessageHandler(filters.Regex("^⬅️ Назад в админ-панель$"), back_to_admin_main_from_menu)
        ]
    )

    return [
        # Обработчики кнопок меню
        MessageHandler(filters.Regex("^🍴 Управление меню$") & filters.User(ADMIN_IDS), manage_menu),
        MessageHandler(filters.Regex("^📋 Просмотр меню$") & filters.User(ADMIN_IDS), view_menu),
        MessageHandler(filters.Regex("^🗑️ Удалить позицию$") & filters.User(ADMIN_IDS), start_delete_item),
        MessageHandler(filters.Regex("^⬅️ Назад в админ-панель$") & filters.User(ADMIN_IDS),
                       back_to_admin_main_from_menu),

        # Conversation handlers
        add_item_handler,
        edit_name_handler,
        edit_price_handler,

        # Callback handlers
        CallbackQueryHandler(handle_category_selection, pattern="^menu_category_"),
        CallbackQueryHandler(handle_delete_item_selection, pattern="^delete_item_"),
        CallbackQueryHandler(confirm_delete_item, pattern="^confirm_delete_"),
        CallbackQueryHandler(cancel_delete_item, pattern="^cancel_delete_"),
        CallbackQueryHandler(start_edit_item, pattern="^✏️ Редактировать позицию$"),
        CallbackQueryHandler(handle_edit_item_selection, pattern="^edit_item_"),
        CallbackQueryHandler(back_to_categories_list, pattern="^back_to_categories_list$"),
        CallbackQueryHandler(back_to_menu_management, pattern="^back_to_menu_management$")
    ]