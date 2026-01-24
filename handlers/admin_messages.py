"""
Рассылка сообщений и отправка личных сообщений пользователям
"""
import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton  # УЖЕ ЕСТЬ
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from config import ADMIN_IDS
from database import Database

logger = logging.getLogger(__name__)
db = Database()

# Состояния для админских функций
AWAITING_BROADCAST_MEDIA, AWAITING_USER_MESSAGE, SELECTING_USER = range(3)


def is_admin(user_id):
    return user_id in ADMIN_IDS


# Рассылка сообщений с медиа
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать рассылку сообщений"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    from keyboards.menus import get_cancel_keyboard

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    context.user_data['awaiting_broadcast'] = True
    await message_manager.send_message(
        update, context,
        "📢 Рассылка сообщений\n\n"
        "Отправьте сообщение для рассылки (текст, фото, видео, документ или аудио):",
        reply_markup=get_cancel_keyboard(),
        is_temporary=False
    )
    return AWAITING_BROADCAST_MEDIA


async def process_broadcast_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка рассылки медиа"""
    if update.message.text == "❌ Отмена":
        context.user_data.pop('awaiting_broadcast', None)
        from message_manager import message_manager
        from keyboards.menus import get_admin_main_menu
        await message_manager.send_message(
            update, context,
            "❌ Рассылка отменена.",
            reply_markup=get_admin_main_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    if not is_admin(update.effective_user.id) or not context.user_data.get('awaiting_broadcast'):
        return

    # Получаем ВСЕХ пользователей
    all_users = db.get_all_users()

    if not all_users:
        from message_manager import message_manager
        from keyboards.menus import get_admin_main_menu
        await message_manager.send_message(
            update, context,
            "❌ В базе данных нет пользователей для рассылки.",
            reply_markup=get_admin_main_menu(),
            is_temporary=True
        )
        context.user_data.pop('awaiting_broadcast', None)
        return ConversationHandler.END

    from message_manager import message_manager
    from keyboards.menus import get_admin_main_menu

    # Проверяем доступность пользователей перед рассылкой
    await message_manager.send_message(
        update, context,
        f"🔍 Начинаю проверку доступности пользователей...\n"
        f"📊 Всего пользователей в базе: {len(all_users)}",
        is_temporary=True
    )

    available_users = []
    unavailable_users = []

    # Проверяем каждого пользователя
    for i, user in enumerate(all_users, 1):
        user_id = user[0]
        telegram_id = user[1]
        first_name = user[2]
        last_name = user[3]

        if i % 10 == 0 or i == len(all_users):
            await message_manager.send_message(
                update, context,
                f"🔍 Проверено {i}/{len(all_users)} пользователей...",
                is_temporary=True
            )

        try:
            await context.bot.send_chat_action(telegram_id, 'typing')
            available_users.append(user)
        except Exception as e:
            error_message = str(e)
            error_type = "Неизвестная ошибка"
            if "bot was blocked" in error_message.lower() or "bot blocked" in error_message.lower():
                error_type = "Пользователь заблокировал бота"
            elif "user not found" in error_message.lower():
                error_type = "Пользователь не найден"
            elif "chat not found" in error_message.lower():
                error_type = "Чат не найден"
            elif "forbidden" in error_message.lower():
                error_type = "Доступ запрещен"

            unavailable_users.append({
                'id': user_id,
                'telegram_id': telegram_id,
                'name': f"{first_name} {last_name}",
                'error_type': error_type,
                'error_details': error_message
            })
            logger.warning(f"Пользователь {telegram_id} недоступен: {error_type}")

    users_for_broadcast = available_users  # Включаем всех доступных пользователей

    if not users_for_broadcast:
        report_message = f"📊 Отчет проверки доступности пользователей:\n\n"
        report_message += f"👥 Всего пользователей в базе: {len(all_users)}\n"
        report_message += f"✅ Доступных пользователей: {len(available_users)}\n"
        report_message += f"❌ Недоступных пользователей: {len(unavailable_users)}\n\n"

        if unavailable_users:
            report_message += f"📋 Детали по недоступным пользователям:\n"
            for i, user in enumerate(unavailable_users[:5], 1):
                report_message += f"{i}. 👤 {user['name']} (ID: {user['id']})\n"
                report_message += f"   ❌ Тип ошибки: {user['error_type']}\n"

        report_message += f"\n💡 Рекомендации:\n"
        report_message += f"• Нет доступных пользователей для рассылки\n"
        report_message += f"• Проверьте список недоступных пользователей\n"
        report_message += f"• Убедитесь, что пользователи не заблокировали бота\n"

        await message_manager.send_message(
            update, context,
            report_message,
            reply_markup=get_admin_main_menu(),
            is_temporary=False
        )

        context.user_data.pop('awaiting_broadcast', None)
        return ConversationHandler.END

    # Начинаем рассылку
    await message_manager.send_message(
        update, context,
        f"📨 Начинаю рассылку для {len(users_for_broadcast)} доступных пользователей...\n"
        f"ℹ️ Администраторы также получат сообщение.",
        is_temporary=True
    )

    success_count = 0
    failed_users = []
    send_errors_by_type = {}
    admin_received = False

    for i, user in enumerate(users_for_broadcast, 1):
        user_id = user[0]
        telegram_id = user[1]
        first_name = user[2]
        last_name = user[3]
        is_admin_user = is_admin(telegram_id)

        if i % 10 == 0 or i == len(users_for_broadcast):
            progress_msg = f"📨 Отправлено {i}/{len(users_for_broadcast)} сообщений..."
            if is_admin_user:
                progress_msg += f"\n👨‍💼 Администратор {first_name} {last_name} получит сообщение"
            await message_manager.send_message(
                update, context,
                progress_msg,
                is_temporary=True
            )

        try:
            # Отправляем текст
            if update.message.text:
                await context.bot.send_message(
                    telegram_id,
                    f"📢 Сообщение от администратора:\n\n{update.message.text}"
                )

            # Отправляем фото
            if update.message.photo:
                await context.bot.send_photo(
                    telegram_id,
                    photo=update.message.photo[-1].file_id,
                    caption=update.message.caption if update.message.caption else "📢 Рассылка от администратора"
                )

            # Отправляем видео
            if update.message.video:
                await context.bot.send_video(
                    telegram_id,
                    video=update.message.video.file_id,
                    caption=update.message.caption if update.message.caption else "📢 Рассылка от администратора"
                )

            # Отправляем документ
            if update.message.document:
                await context.bot.send_document(
                    telegram_id,
                    document=update.message.document.file_id,
                    caption=update.message.caption if update.message.caption else "📢 Рассылка от администратора"
                )

            # Отправляем аудио
            if update.message.audio:
                await context.bot.send_audio(
                    telegram_id,
                    audio=update.message.audio.file_id,
                    caption=update.message.caption if update.message.caption else "📢 Рассылка от администратора"
                )

            success_count += 1

            if is_admin_user:
                admin_received = True
                logger.info(f"Администратор {first_name} {last_name} (ID: {user_id}) получил рассылку")

        except Exception as e:
            error_message = str(e)
            error_type = "Неизвестная ошибка"
            if "bot was blocked" in error_message.lower():
                error_type = "Пользователь заблокировал бота"
            elif "user not found" in error_message.lower():
                error_type = "Пользователь не найден"
            elif "chat not found" in error_message.lower():
                error_type = "Чат не найден"
            elif "forbidden" in error_message.lower():
                error_type = "Доступ запрещен"
            elif "flood" in error_message.lower():
                error_type = "Превышен лимит отправки"
            elif "too many requests" in error_message.lower():
                error_type = "Слишком много запросов"

            if error_type not in send_errors_by_type:
                send_errors_by_type[error_type] = 0
            send_errors_by_type[error_type] += 1

            user_type = "👤 Пользователь"
            if is_admin_user:
                user_type = "👨‍💼 Администратор"

            failed_users.append({
                'id': user_id,
                'telegram_id': telegram_id,
                'name': f"{first_name} {last_name}",
                'type': user_type,
                'error_type': error_type,
                'error_details': error_message[:100]
            })

    # Формируем детальный финальный отчет
    message = "✅ РАССЫЛКА ЗАВЕРШЕНА\n\n"
    message += "📊 ПОДРОБНАЯ СТАТИСТИКА:\n"
    message += f"• 👥 Всего пользователей в базе: {len(all_users)}\n"
    message += f"• ✅ Доступных для проверки: {len(available_users)}\n"
    message += f"• ❌ Недоступных при проверке: {len(unavailable_users)}\n"
    message += f"• 📨 Получателей рассылки: {len(users_for_broadcast)}\n"
    message += f"• 🎯 Успешно доставлено: {success_count}\n"
    message += f"• ⚠️  Ошибок при отправке: {len(failed_users)}\n"

    admin_count = sum(1 for user in users_for_broadcast if is_admin(user[1]))
    admin_success = admin_count - sum(1 for failed in failed_users if failed['type'] == "👨‍💼 Администратор")

    if admin_count > 0:
        message += f"• 👨‍💼 Администраторов в рассылке: {admin_count}\n"
        message += f"• ✅ Администраторов получило: {admin_success}\n\n"
    else:
        message += "\n"

    if failed_users:
        message += "📋 ОШИБКИ ПРИ ОТПРАВКЕ:\n"
        if send_errors_by_type:
            message += "📈 Распределение ошибок по типам:\n"
            for error_type, count in send_errors_by_type.items():
                message += f"  • {error_type}: {count}\n"
            message += "\n"

        admin_errors = [f for f in failed_users if f['type'] == "👨‍💼 Администратор"]
        user_errors = [f for f in failed_users if f['type'] == "👤 Пользователь"]

        if admin_errors:
            message += "👨‍💼 Ошибки администраторов:\n"
            for i, failed in enumerate(admin_errors[:3], 1):
                message += f"{i}. {failed['name']} (ID: {failed['id']})\n"
                message += f"   ❌ Тип: {failed['error_type']}\n"
                if len(failed['error_details']) > 0:
                    message += f"   📝 Детали: {failed['error_details']}\n"
            if len(admin_errors) > 3:
                message += f"... и еще {len(admin_errors) - 3} ошибок администраторов\n"
            message += "\n"

        if user_errors:
            message += "👤 Ошибки пользователей (первые 5):\n"
            for i, failed in enumerate(user_errors[:5], 1):
                message += f"{i}. {failed['name']} (ID: {failed['id']})\n"
                message += f"   ❌ Тип: {failed['error_type']}\n"
                if len(failed['error_details']) > 0:
                    message += f"   📝 Детали: {failed['error_details']}\n"

            if len(user_errors) > 5:
                message += f"... и еще {len(user_errors) - 5} ошибок пользователей\n\n"
            else:
                message += "\n"

    if unavailable_users:
        message += "📋 НЕДОСТУПНЫЕ ПОЛЬЗОВАТЕЛИ (при проверке):\n"
        error_groups = {}
        for user in unavailable_users:
            error_type = user['error_type']
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(user)

        for error_type, users in error_groups.items():
            message += f"• {error_type}: {len(users)} пользователей\n"

        message += "\n👁️ Примеры недоступных пользователей:\n"
        for i, user in enumerate(unavailable_users[:3], 1):
            message += f"{i}. {user['name']} (ID: {user['id']}) - {user['error_type']}\n"

        if len(unavailable_users) > 3:
            message += f"... и еще {len(unavailable_users) - 3} пользователей\n\n"
        else:
            message += "\n"

    message += "💡 РЕКОМЕНДАЦИИ:\n"
    if len(failed_users) > 0:
        message += "• Проверьте пользователей с ошибками отправки\n"
        message += "• Попробуйте отправить им сообщение вручную\n"

        admin_errors_count = len([f for f in failed_users if f['type'] == "👨‍💼 Администратор"])
        if admin_errors_count > 0:
            message += "• ⚠️ Администраторы не получили сообщение. Проверьте их настройки\n"

    if len(unavailable_users) > 0:
        message += "• Рассмотрите удаление недоступных пользователей из базы\n"
        message += f"• Всего недоступных: {len(unavailable_users)} пользователей\n"

    if success_count == len(users_for_broadcast):
        message += "• Отличный результат! Все сообщения доставлены\n"
        if admin_received:
            message += "• Администраторы также получили сообщение\n"

    if len(failed_users) > len(users_for_broadcast) / 2:
        message += "• ⚠️ Много ошибок. Проверьте настройки бота и лимиты Telegram\n"

    delivery_rate = (success_count / len(users_for_broadcast) * 100) if users_for_broadcast else 0
    message += f"\n📈 Эффективность рассылки: {delivery_rate:.1f}% успешных отправок\n"

    if delivery_rate < 50:
        message += "⚠️ Низкая эффективность. Рекомендуется проверить базу пользователей\n"
    elif delivery_rate > 90:
        message += "✅ Отличная эффективность рассылки!\n"
        if admin_received:
            message += "✅ Администраторы получили сообщение\n"

    context.user_data['broadcast_details'] = {
        'total_users': len(all_users),
        'available_count': len(available_users),
        'unavailable_count': len(unavailable_users),
        'sent_count': len(users_for_broadcast),
        'success_count': success_count,
        'failed_count': len(failed_users),
        'delivery_rate': delivery_rate,
        'admin_included': True,
        'admin_received': admin_received,
        'admin_count': admin_count,
        'admin_success': admin_success,
        'unavailable_users': unavailable_users,
        'failed_users': failed_users,
        'error_stats': send_errors_by_type,
        'message_content': update.message.text or "Медиа-сообщение",
        'timestamp': db.get_moscow_time()
    }

    await message_manager.send_message(
        update, context,
        message,
        reply_markup=get_admin_main_menu(),
        is_temporary=False
    )

    logger.info(
        f"Рассылка завершена. "
        f"Всего: {len(all_users)}, "
        f"Доступно: {len(available_users)}, "
        f"Отправлено: {len(users_for_broadcast)}, "
        f"Успешно: {success_count}, "
        f"Ошибок: {len(failed_users)}, "
        f"Администраторов: {admin_count}, "
        f"Админ получили: {admin_success}, "
        f"Эффективность: {delivery_rate:.1f}%"
    )

    context.user_data.pop('awaiting_broadcast', None)
    return ConversationHandler.END


# Личные сообщения пользователям
async def start_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать отправку личного сообщения пользователю"""
    if not is_admin(update.effective_user.id):
        return

    from message_manager import message_manager
    from keyboards.menus import get_users_keyboard

    # Очищаем только временные сообщения при переходе между разделами
    await message_manager.cleanup_user_messages(context, update.effective_user.id)

    users = db.get_all_users()

    if not users:
        await message_manager.send_message(update, context, "📭 Пользователи не найдены.", is_temporary=True)
        return

    await message_manager.send_message(
        update, context,
        "✉️ Выберите пользователя для отправки сообщения:",
        reply_markup=get_users_keyboard(users),
        is_temporary=False
    )
    return SELECTING_USER


async def user_selected_for_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора пользователя для сообщения"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(query.data.split('_')[-1])
    context.user_data['selected_user_id'] = user_id

    # ВЫКЛЮЧАЕМ РЕЖИМ ПОИСКА ПРИ ВЫБОРЕ ПОЛЬЗОВАТЕЛЯ ДЛЯ СООБЩЕНИЯ
    context.user_data.pop('search_users_mode', None)

    user_data = db.get_user_by_id(user_id)

    from keyboards.menus import get_cancel_keyboard
    try:
        await query.edit_message_text(
            f"✉️ Отправка сообщения пользователю:\n"
            f"👤 {user_data[2]} {user_data[3]}\n"
            f"📱 {user_data[4]}\n\n"
            f"Введите сообщение:",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Ошибка при выборе пользователя для сообщения: {e}")
            from message_manager import message_manager
            await message_manager.send_message(
                update, context,
                f"✉️ Отправка сообщения пользователю:\n👤 {user_data[2]} {user_data[3]}\n📱 {user_data[4]}\n\nВведите сообщение:",
                reply_markup=get_cancel_keyboard(),
                is_temporary=False
            )
    return AWAITING_USER_MESSAGE


async def process_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отправки личного сообщения"""
    if update.message.text == "❌ Отмена":
        context.user_data.pop('selected_user_id', None)
        context.user_data.pop('search_users_mode', None)

        from message_manager import message_manager
        from keyboards.menus import get_admin_main_menu
        await message_manager.send_message(
            update, context,
            "❌ Отправка сообщения отменена.",
            reply_markup=get_admin_main_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    if not is_admin(update.effective_user.id) or 'selected_user_id' not in context.user_data:
        return

    user_id = context.user_data['selected_user_id']
    user_data = db.get_user_by_id(user_id)
    message_text = update.message.text

    try:
        await context.bot.send_message(
            user_data[1],
            f"✉️ Сообщение от администратора:\n\n{message_text}"
        )

        context.user_data.pop('search_users_mode', None)
        context.user_data.pop('selected_user_id', None)

        from message_manager import message_manager
        from keyboards.menus import get_admin_main_menu
        await message_manager.send_message(
            update, context,
            f"✅ Сообщение отправлено пользователю:\n"
            f"👤 {user_data[2]} {user_data[3]}",
            reply_markup=get_admin_main_menu(),
            is_temporary=False
        )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Не удалось отправить сообщение пользователю {user_data[1]}: {e}")
        from message_manager import message_manager
        from keyboards.menus import get_admin_main_menu
        await message_manager.send_message(
            update, context,
            f"❌ Не удалось отправить сообщение пользователю {user_data[2]} {user_data[3]}",
            reply_markup=get_admin_main_menu(),
            is_temporary=True
        )

        context.user_data.pop('search_users_mode', None)
        context.user_data.pop('selected_user_id', None)
        return ConversationHandler.END


async def message_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки отправки сообщения пользователю"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    user_id = int(query.data.split('_')[-1])
    context.user_data['selected_user_id'] = user_id
    user_data = db.get_user_by_id(user_id)

    from keyboards.menus import get_cancel_keyboard
    try:
        await query.edit_message_text(
            f"✉️ Отправка сообщения пользователю:\n"
            f"👤 {user_data[2]} {user_data[3]}\n"
            f"📱 {user_data[4]}\n\n"
            f"Введите сообщение:",
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Ошибка при отправке сообщения пользователю: {e}")
            from message_manager import message_manager
            await message_manager.send_message(
                update, context,
                f"✉️ Отправка сообщения пользователю:\n👤 {user_data[2]} {user_data[3]}\n📱 {user_data[4]}\n\nВведите сообщение:",
                reply_markup=get_cancel_keyboard(),
                is_temporary=False
            )
    return AWAITING_USER_MESSAGE


def get_broadcast_handler():
    """Создать обработчик рассылки"""
    from telegram.ext import ConversationHandler, MessageHandler, filters

    # ЛОКАЛЬНАЯ ФУНКЦИЯ ОТМЕНЫ ДЛЯ РАССЫЛКИ
    async def cancel_broadcast_operation(update, context):
        from message_manager import message_manager
        from keyboards.menus import get_admin_main_menu

        context.user_data.clear()
        await message_manager.send_message(
            update, context,
            "❌ Рассылка отменена.",
            reply_markup=get_admin_main_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Рассылка$"), broadcast_message)],
        states={
            AWAITING_BROADCAST_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_broadcast_media),
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO,
                               process_broadcast_media)
            ]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel_broadcast_operation)]  # ИСПОЛЬЗУЕМ ЛОКАЛЬНУЮ
    )


def get_user_message_handler():
    """Создать обработчик личных сообщений"""
    from telegram.ext import ConversationHandler, MessageHandler, filters, CallbackQueryHandler

    # ЛОКАЛЬНАЯ ФУНКЦИЯ ОТМЕНЫ
    async def cancel_user_message_operation(update, context):
        from message_manager import message_manager
        from keyboards.menus import get_admin_main_menu

        context.user_data.clear()
        await message_manager.send_message(
            update, context,
            "❌ Отправка сообщения отменена.",
            reply_markup=get_admin_main_menu(),
            is_temporary=True
        )
        return ConversationHandler.END

    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✉️ Написать пользователю$"), start_user_message),
            CallbackQueryHandler(message_user_callback, pattern="^message_")
        ],
        states={
            SELECTING_USER: [CallbackQueryHandler(user_selected_for_message, pattern="^select_user_")],
            AWAITING_USER_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_message)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel_user_message_operation)]  # ИСПОЛЬЗУЕМ ЛОКАЛЬНУЮ
    )