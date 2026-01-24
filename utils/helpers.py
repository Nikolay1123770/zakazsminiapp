import re


def validate_phone(phone):
    # Удаляем все нецифровые символы
    cleaned_phone = re.sub(r'\D', '', phone)

    # Проверяем длину номера (10-15 цифр)
    if len(cleaned_phone) < 10 or len(cleaned_phone) > 15:
        return False

    # Проверяем, что номер содержит только цифры
    if not cleaned_phone.isdigit():
        return False

    return True


def validate_name(name):
    # Проверяем, что имя содержит только буквы и пробелы
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s]{2,50}$', name):
        return False

    # Проверяем минимальную длину
    if len(name.strip()) < 2:
        return False

    return True


import re


def validate_phone(phone):
    # Удаляем все нецифровые символы
    cleaned_phone = re.sub(r'\D', '', phone)

    # Проверяем длину номера (10-15 цифр)
    if len(cleaned_phone) < 10 or len(cleaned_phone) > 15:
        return False

    # Проверяем, что номер содержит только цифры
    if not cleaned_phone.isdigit():
        return False

    return True


def validate_name(name):
    # Проверяем, что имя содержит только буквы и пробелы
    if not re.match(r'^[a-zA-Zа-яА-ЯёЁ\s]{2,50}$', name):
        return False

    # Проверяем минимальную длину
    if len(name.strip()) < 2:
        return False

    return True


def format_user_data(user_data):
    return (
        f"📋 Проверьте ваши данные:\n\n"
        f"👤 Имя: {user_data['first_name']}\n"
        f"👤 Фамилия: {user_data['last_name']}\n"
        f"📱 Телефон: {user_data['phone']}\n\n"
        f"Если все верно, нажмите '✅ Подтвердить'"
    )


def format_booking_info(booking_data):
    status_emoji = {
        'pending': '⏳',
        'confirmed': '✅',
        'cancelled': '❌'
    }

    return (
        f"{status_emoji.get(booking_data[4], '📅')} Бронирование #{booking_data[0]}\n"
        f"📅 Дата: {booking_data[2]}\n"
        f"⏰ Время: {booking_data[3]}\n"
        f"👥 Гостей: {booking_data[4]}\n"
        f"📊 Статус: {booking_data[5]}"
    )