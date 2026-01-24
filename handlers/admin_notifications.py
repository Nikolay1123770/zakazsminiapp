# admin_notifications.py
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from database import Database

logger = logging.getLogger(__name__)

async def send_booking_notification(bot, booking_id, booking_data):
    """Отправить уведомление о новом бронировании"""
    try:
        from config import ADMIN_IDS
        
        # Форматируем номер телефона для безопасности
        phone = booking_data['phone']
        if len(phone) > 4:
            phone_display = f"{phone[:4]}***{phone[-2:]}"
        else:
            phone_display = phone
            
        message = f"""
🎯 **НОВАЯ БРОНЬ ИЗ MINIAPP!** 🎯

📋 **ID:** #{booking_id}
👤 **Клиент:** {booking_data['name']}
📞 **Телефон:** {phone_display}
📅 **Дата:** {booking_data['date']}
⏰ **Время:** {booking_data['time']}
👥 **Гостей:** {booking_data['guests']}
💬 **Комментарий:** {booking_data.get('comment', 'Нет')}
🔗 **Источник:** 🌐 MiniApp
"""
        
        # Добавляем информацию о пользователе если есть
        db = Database()
        if booking_data.get('user_id'):
            user = db.get_user_by_id(booking_data['user_id'])
            if user:
                message += f"\n👤 **Пользователь:** {user[3]} {user[4] or ''}"
                if user[5]:  # телефон
                    message += f"\n📱 **Телефон в профиле:** {user[5]}"
        
        message += "\n\n📊 **Быстрые действия:**"
        
        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{booking_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_booking_{booking_id}")
            ],
            [
                InlineKeyboardButton("📋 Подробнее", callback_data=f"info_booking_{booking_id}"),
                InlineKeyboardButton("🔄 Обновить", callback_data="refresh_bookings")
            ]
        ])
        
        # Отправляем всем администраторам
        successful_sends = 0
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                successful_sends += 1
                logger.info(f"✅ Уведомление о бронировании #{booking_id} отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")
        
        return successful_sends > 0
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка отправки уведомления: {e}")
        return False

async def send_booking_update(bot, booking_id, action, admin_id):
    """Отправить уведомление об обновлении бронирования"""
    try:
        db = Database()
        booking = db.get_booking_by_id(booking_id)
        
        if not booking:
            return False
            
        status_text = {
            'confirmed': '✅ подтверждено',
            'cancelled': '❌ отменено'
        }.get(action, action)
        
        message = f"""
🔄 **Бронирование обновлено**

📋 **ID:** #{booking_id}
👤 **Клиент:** {booking[8]} ({booking[9]})
📅 **Дата:** {booking[2]}
⏰ **Время:** {booking[3]}
📊 **Статус:** {status_text}
👥 **Гостей:** {booking[4]}
"""
        
        # Уведомляем всех админов кроме того, кто выполнил действие
        from config import ADMIN_IDS
        for admin in ADMIN_IDS:
            if admin != admin_id:
                try:
                    await bot.send_message(
                        chat_id=admin,
                        text=message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа {admin}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки обновления: {e}")
        return False
