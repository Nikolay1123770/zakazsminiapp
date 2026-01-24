# keyboards/menus.py
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, date, timedelta
from calendar import monthrange


# ========== ДОБАВЬТЕ ЭТОТ СЛОВАРЬ ЗДЕСЬ ==========
# Словарь для отображения названий методов оплаты
PAYMENT_METHOD_NAMES = {
    'qr': 'QR-код',
    'card': 'Картой',
    'cash': 'Наличными',
    'transfer': 'Переводом'
}
# ========== КОНЕЦ ДОБАВЛЕНИЯ ==========


# Главное меню пользователя
def get_user_main_menu():
    keyboard = [
        [KeyboardButton("💰 Мой баланс")],
        [KeyboardButton("🎁 Списать баллы")],
        [KeyboardButton("📅 Забронировать стол"), KeyboardButton("📋 Мои бронирования")],
        [KeyboardButton("🎁 Реферальная программа"), KeyboardButton("📞 Контакты")],
        [KeyboardButton("⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# Клавиатура контактов
def get_contacts_keyboard():
    keyboard = [
        [KeyboardButton("📞 Позвонить"), KeyboardButton("💬 Написать в Telegram")],
        [KeyboardButton("📍 Мы на картах"), KeyboardButton("⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# Меню фильтрации бронирований для пользователя
def get_user_booking_filter_menu():
    keyboard = [
        [KeyboardButton("⏳ Ожидающие"), KeyboardButton("✅ Подтвержденные")],
        [KeyboardButton("❌ Отмененные"), KeyboardButton("📋 Все бронирования")],
        [KeyboardButton("⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# Клавиатура для отмены бронирования пользователем
def get_user_booking_cancel_keyboard(booking_id):
    keyboard = [
        [InlineKeyboardButton("❌ Отменить бронирование", callback_data=f"user_cancel_booking_{booking_id}")],
        [InlineKeyboardButton("⬅️ Назад к списку", callback_data="back_to_bookings_list")]
    ]
    return InlineKeyboardMarkup(keyboard)


# Главное меню администратора (ОБНОВЛЕНО: убрана кнопка "Написать пользователю")
def get_admin_main_menu():
    keyboard = [
        [KeyboardButton("👥 Список пользователей")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📢 Рассылка")],
        [KeyboardButton("📋 Запросы на списание"), KeyboardButton("📅 Бронирования")],
        [KeyboardButton("🍽️ Управление заказами"), KeyboardButton("🍴 Управление меню")],
        [KeyboardButton("⬅️ В главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# Меню управления меню для администратора
def get_menu_management_keyboard():
    keyboard = [
        [KeyboardButton("📋 Просмотр меню")],
        [KeyboardButton("➕ Добавить позицию"), KeyboardButton("✏️ Редактировать позицию")],
        [KeyboardButton("🗑️ Удалить позицию")],
        [KeyboardButton("⬅️ Назад в админ-панель")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# Меню фильтрации бронирований для администратора
def get_booking_filter_menu():
    keyboard = [
        [KeyboardButton("⏳ Ожидающие"), KeyboardButton("✅ Подтвержденные")],
        [KeyboardButton("❌ Отмененные"), KeyboardButton("📅 По дате")],
        [KeyboardButton("📋 Все бронирования"), KeyboardButton("⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# Клавиатура для выбора даты бронирования
def get_dates_keyboard(dates):
    keyboard = []
    row = []
    for i, date in enumerate(dates):
        row.append(KeyboardButton(date))
        if len(row) == 2 or i == len(dates) - 1:
            keyboard.append(row)
            row = []

    # Добавляем кнопку отмены
    if keyboard:
        keyboard.append([KeyboardButton("❌ Отмена")])
    else:
        keyboard = [[KeyboardButton("❌ Отмена")]]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# Клавиатура для выбора пользователя
def get_users_keyboard(users):
    keyboard = []
    for user in users:
        keyboard.append([InlineKeyboardButton(
            f"{user[2]} {user[3]} (ID: {user[0]})",
            callback_data=f"select_user_{user[0]}"
        )])
    return InlineKeyboardMarkup(keyboard)


# Клавиатура для действий с пользователем (ОСТАЕТСЯ КНОПКА "Написать")
def get_user_actions_keyboard(user_id):
    keyboard = [
        [
            InlineKeyboardButton("💰 Начислить 5%", callback_data=f"add_bonus_{user_id}"),
            InlineKeyboardButton("✉️ Написать", callback_data=f"message_{user_id}")
        ],
        [
            InlineKeyboardButton("📊 Списать баллы", callback_data=f"remove_bonus_{user_id}"),
            InlineKeyboardButton("👤 Информация", callback_data=f"info_{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# Клавиатура для подтверждения запросов на списание
def get_bonus_request_keyboard(request_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve_{request_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# Клавиатура для управления бронированиями администратором
def get_booking_actions_keyboard(booking_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{booking_id}"),
            InlineKeyboardButton("❌ Отменить с причиной", callback_data=f"cancel_booking_reason_{booking_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# Кнопка для отправки номера телефона
def get_phone_keyboard():
    keyboard = [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# Клавиатура подтверждения
def get_confirmation_keyboard():
    keyboard = [
        [KeyboardButton("✅ Подтвердить"), KeyboardButton("✏️ Изменить данные")],
        [KeyboardButton("❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# Клавиатура отмены
def get_cancel_keyboard():
    keyboard = [[KeyboardButton("❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# Клавиатура для списания баллов
def get_spend_bonus_keyboard():
    keyboard = [
        [KeyboardButton("50 баллов"), KeyboardButton("100 баллов")],
        [KeyboardButton("200 баллов"), KeyboardButton("500 баллов")],
        [KeyboardButton("❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


# Клавиатура реферальной программы
def get_referral_keyboard():
    keyboard = [
        [KeyboardButton("📊 Моя статистика"), KeyboardButton("🔗 Получить ссылку")],
        [KeyboardButton("⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_bonus_requests_menu():
    """Меню для управления запросами на списание"""
    keyboard = [
        [KeyboardButton("🔄 Обновить список запросов")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📅 Бронирования")],
        [KeyboardButton("👥 Список пользователей"), KeyboardButton("📢 Рассылка")],
        [KeyboardButton("✉️ Написать пользователю"), KeyboardButton("⬅️ В главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# НОВЫЕ КЛАВИАТУРЫ ДЛЯ УПРАВЛЕНИЯ МЕНЮ

def get_categories_keyboard(categories):
    """Клавиатура для выбора категории меню"""
    keyboard = []
    row = []
    for i, category in enumerate(categories):
        row.append(InlineKeyboardButton(category, callback_data=f"menu_category_{category}"))
        if len(row) == 2 or i == len(categories) - 1:
            keyboard.append(row)
            row = []
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu_management")])
    return InlineKeyboardMarkup(keyboard)


def get_menu_items_keyboard(items, action_prefix):
    """Клавиатура для выбора позиций меню"""
    keyboard = []
    for item in items:
        keyboard.append([
            InlineKeyboardButton(
                f"{item[1]} - {item[2]}₽",
                callback_data=f"{action_prefix}_{item[0]}"
            )
        ])
    keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_categories_list")])
    return InlineKeyboardMarkup(keyboard)


def get_menu_item_actions_keyboard(item_id):
    """Клавиатура действий с позицией меню"""
    keyboard = [
        [
            InlineKeyboardButton("✏️ Изменить название", callback_data=f"edit_name_{item_id}"),
            InlineKeyboardButton("💰 Изменить цену", callback_data=f"edit_price_{item_id}")
        ],
        [InlineKeyboardButton("⬅️ Назад к списку", callback_data="back_to_categories_list")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_edit_confirmation_keyboard(item_id):
    """Клавиатура подтверждения удаления"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{item_id}"),
            InlineKeyboardButton("❌ Нет, отменить", callback_data=f"cancel_delete_{item_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_management_keyboard():
    """Клавиатура для возврата в управление меню"""
    keyboard = [[InlineKeyboardButton("⬅️ Назад в управление меню", callback_data="back_to_menu_management")]]
    return InlineKeyboardMarkup(keyboard)


# ========== КАЛЕНДАРНАЯ КЛАВИАТУРА ==========

def get_calendar_keyboard(year=None, month=None, selected_date=None):
    """Создает инлайн клавиатуру-календарь с подсветкой выбранной даты"""
    from datetime import date
    from calendar import monthrange

    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    # Названия месяцев
    month_names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                   "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

    # Получаем первый день месяца и количество дней
    first_weekday, num_days = monthrange(year, month)

    # Заголовок календаря
    keyboard = []
    header = [
        InlineKeyboardButton("◀️", callback_data=f"cal_prev_{year}_{month}"),
        InlineKeyboardButton(f"{month_names[month]} {year}", callback_data="ignore"),
        InlineKeyboardButton("▶️", callback_data=f"cal_next_{year}_{month}")
    ]
    keyboard.append(header)

    # Дни недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in weekdays])

    # Дни месяца
    current_day = 1
    for week in range(6):  # Максимум 6 недель в месяце
        row = []
        for day in range(7):
            if current_day > num_days:
                # Пустые кнопки после последнего дня
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            elif week == 0 and day < first_weekday:
                # Пустые кнопки перед первым днем
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                # Определяем, является ли эта дата выбранной
                is_selected = False
                if selected_date:
                    try:
                        selected_day, selected_month, selected_year = map(int, selected_date.split('.'))
                        if (current_day == selected_day and
                                month == selected_month and
                                year == selected_year):
                            is_selected = True
                    except:
                        pass

                # Определяем, является ли дата сегодняшней
                is_today = (current_day == today.day and
                            month == today.month and
                            year == today.year)

                # Формируем текст кнопки с эмодзи для выделения
                if is_selected:
                    button_text = f"✅ {current_day}"
                elif is_today:
                    button_text = f"📍 {current_day}"
                elif date(year, month, current_day) < today:
                    button_text = f"·{current_day}·"
                else:
                    button_text = str(current_day)

                # Создаем callback_data
                day_str = f"{current_day:02d}"
                month_str = f"{month:02d}"
                callback_data = f"cal_day_{year}_{month_str}_{day_str}"

                row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
                current_day += 1

        # Добавляем строку, если в ней есть активные кнопки
        if any(btn.text.strip() not in [" ", "·1·", "·2·", "·3·", "·4·", "·5·", "·6·", "·7·",
                                        "·8·", "·9·", "·10·", "·11·", "·12·", "·13·", "·14·",
                                        "·15·", "·16·", "·17·", "·18·", "·19·", "·20·", "·21·",
                                        "·22·", "·23·", "·24·", "·25·", "·26·", "·27·", "·28·",
                                        "·29·", "·30·", "·31·"] for btn in row):
            keyboard.append(row)

        # Если все дни прошли, выходим из цикла
        if current_day > num_days:
            break

    # Кнопки быстрого выбора
    from datetime import timedelta
    next_week = today + timedelta(days=7)
    keyboard.append([
        InlineKeyboardButton("📅 Сегодня",
                             callback_data=f"cal_day_{today.year}_{today.month:02d}_{today.day:02d}"),
        InlineKeyboardButton("📅 Через неделю",
                             callback_data=f"cal_day_{next_week.year}_{next_week.month:02d}_{next_week.day:02d}")
    ])

    # Кнопка отмены
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="cal_cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_time_keyboard(selected_date_obj=None, selected_time=None):
    """Клавиатура для выбора времени"""
    keyboard = []

    # Если передана дата, проверяем можно ли выбирать прошедшее время
    current_time = datetime.now()
    if selected_date_obj:
        if selected_date_obj < current_time.date():
            # Прошедшая дата - время недоступно
            keyboard.append([
                InlineKeyboardButton("❌ Нельзя выбрать время для прошедшей даты", callback_data="ignore")
            ])
        elif selected_date_obj == current_time.date():
            # Сегодня - показываем только будущее время
            start_hour = current_time.hour + 1
            if start_hour < 10:
                start_hour = 10
        else:
            # Будущая дата - показываем все время
            start_hour = 10
    else:
        start_hour = 10

    # Время работы: с 10:00 до 23:00
    time_slots = []
    for hour in range(start_hour, 23):
        for minute in [0, 30]:
            if hour == start_hour and minute <= current_time.minute and selected_date_obj == current_time.date():
                continue

            time_str = f"{hour:02d}:{minute:02d}"
            if selected_time == time_str:
                button_text = f"✅ {time_str}"
            else:
                button_text = time_str

            time_slots.append((time_str, button_text))

    # Распределяем по 4 кнопки в ряд
    for i in range(0, len(time_slots), 4):
        row = []
        for j in range(4):
            if i + j < len(time_slots):
                time_str, button_text = time_slots[i + j]
                row.append(InlineKeyboardButton(
                    button_text,
                    callback_data=f"time_{time_str}"
                ))
        keyboard.append(row)

    # Кнопки навигации
    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="time_refresh"),
        InlineKeyboardButton("❌ Отмена", callback_data="cal_cancel")
    ])

    return InlineKeyboardMarkup(keyboard)


def get_guests_keyboard(selected_guests=None):
    """Клавиатура для выбора количества гостей"""
    keyboard = []

    # Маленькие компании (1-8 человек)
    for i in range(1, 9, 4):
        row = []
        for j in range(4):
            guests = i + j
            if guests <= 8:
                if selected_guests == guests:
                    button_text = f"✅ {guests}"
                else:
                    button_text = str(guests)
                row.append(InlineKeyboardButton(button_text, callback_data=f"guests_{guests}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("-" * 20, callback_data="ignore")])

    # Средние компании (9-20 человек)
    medium_groups = [(9, 12), (13, 16), (17, 20)]
    row = []
    for start, end in medium_groups:
        if selected_guests and start <= selected_guests <= end:
            button_text = f"✅ {start}-{end}"
        else:
            button_text = f"{start}-{end}"
        row.append(InlineKeyboardButton(button_text, callback_data=f"guests_{(start + end) // 2}"))
    keyboard.append(row)

    # Большие компании
    keyboard.append([
        InlineKeyboardButton("21-30", callback_data="guests_25"),
        InlineKeyboardButton("31-40", callback_data="guests_35"),
        InlineKeyboardButton("40+", callback_data="guests_45")
    ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="guests_back"),
        InlineKeyboardButton("❌ Отмена", callback_data="cal_cancel")
    ])

    return InlineKeyboardMarkup(keyboard)

# Добавьте этот код в конец файла keyboards/menus.py (перед закрывающей скобкой файла)

def get_payment_method_keyboard(order_id):
    """Клавиатура выбора способа оплаты"""
    keyboard = [
        [InlineKeyboardButton("📱 QR-код", callback_data=f"payment_qr_{order_id}")],
        [InlineKeyboardButton("💳 Картой", callback_data=f"payment_card_{order_id}")],
        [InlineKeyboardButton("💵 Наличные", callback_data=f"payment_cash_{order_id}")],
        [InlineKeyboardButton("💸 Перевод", callback_data=f"payment_transfer_{order_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_calculation_{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)