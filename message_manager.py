import asyncio
from typing import List, Optional
from telegram import Message, Update
from telegram.ext import ContextTypes
from config import MESSAGE_CLEANUP_DELAY
import logging

logger = logging.getLogger(__name__)


class MessageManager:
    def __init__(self):
        self.temporary_messages = {}
        self.permanent_messages = {}
        self.notification_messages = {}  # Отдельное хранилище для уведомлений

    async def send_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                           text: str, is_temporary: bool = False, is_notification: bool = False, **kwargs) -> Message:
        """Отправляет сообщение и управляет его временем жизни"""
        try:
            if hasattr(update, 'message') and update.message:
                message = await update.message.reply_text(text, **kwargs)
            elif hasattr(update, 'callback_query') and update.callback_query:
                message = await update.callback_query.message.reply_text(text, **kwargs)
            else:
                # Если нет прямого доступа к сообщению, используем context
                chat_id = update.effective_chat.id
                message = await context.bot.send_message(chat_id, text, **kwargs)

            user_id = update.effective_user.id

            if is_notification:
                # Уведомления никогда не очищаются автоматически
                if user_id not in self.notification_messages:
                    self.notification_messages[user_id] = []
                self.notification_messages[user_id].append(message.message_id)

            elif is_temporary:
                if user_id not in self.temporary_messages:
                    self.temporary_messages[user_id] = []
                self.temporary_messages[user_id].append(message.message_id)

                # Запланировать удаление временного сообщения
                asyncio.create_task(self._delete_temporary_message(context, user_id, message.message_id))
            else:
                # Постоянные сообщения (меню)
                if user_id not in self.permanent_messages:
                    self.permanent_messages[user_id] = []
                self.permanent_messages[user_id].append(message.message_id)

            return message
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            raise

    async def send_message_to_chat(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                                   text: str, is_temporary: bool = False, is_notification: bool = False,
                                   **kwargs) -> Message:
        """Отправляет сообщение в указанный чат"""
        try:
            message = await context.bot.send_message(chat_id, text, **kwargs)

            if is_notification:
                # Уведомления никогда не очищаются автоматически
                if chat_id not in self.notification_messages:
                    self.notification_messages[chat_id] = []
                self.notification_messages[chat_id].append(message.message_id)

            elif is_temporary:
                if chat_id not in self.temporary_messages:
                    self.temporary_messages[chat_id] = []
                self.temporary_messages[chat_id].append(message.message_id)

                asyncio.create_task(self._delete_temporary_message(context, chat_id, message.message_id))
            else:
                if chat_id not in self.permanent_messages:
                    self.permanent_messages[chat_id] = []
                self.permanent_messages[chat_id].append(message.message_id)

            return message
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")
            raise

    async def _delete_temporary_message(self, context: ContextTypes.DEFAULT_TYPE,
                                        chat_id: int, message_id: int):
        """Удаляет временное сообщение после задержки"""
        await asyncio.sleep(MESSAGE_CLEANUP_DELAY)
        try:
            # Проверяем, не является ли сообщение уведомлением или постоянным
            if (chat_id in self.notification_messages and
                    message_id in self.notification_messages[chat_id]):
                return  # Не удаляем уведомления

            if (chat_id in self.permanent_messages and
                    message_id in self.permanent_messages[chat_id]):
                return  # Не удаляем постоянные сообщения

            await context.bot.delete_message(chat_id, message_id)

            # Удаляем из списка временных сообщений
            if (chat_id in self.temporary_messages and
                    message_id in self.temporary_messages[chat_id]):
                self.temporary_messages[chat_id].remove(message_id)
        except Exception as e:
            logger.debug(f"Не удалось удалить временное сообщение {message_id} для {chat_id}: {e}")

    async def cleanup_user_messages(self, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Очищает все временные сообщения пользователя (но не уведомления)"""
        if user_id in self.temporary_messages:
            for message_id in self.temporary_messages[user_id][:]:
                try:
                    await context.bot.delete_message(user_id, message_id)
                except Exception as e:
                    logger.debug(f"Не удалось удалить сообщение {message_id} при очистке: {e}")
            self.temporary_messages[user_id] = []

    async def cleanup_all_messages(self, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Полная очистка ВСЕХ сообщений пользователя (используется при возврате в главное меню)"""
        try:
            deleted_count = 0

            # Очищаем временные сообщения
            if user_id in self.temporary_messages:
                for message_id in self.temporary_messages[user_id][:]:
                    try:
                        await context.bot.delete_message(user_id, message_id)
                        deleted_count += 1
                    except Exception as e:
                        logger.debug(f"Не удалось удалить временное сообщение {message_id}: {e}")
                self.temporary_messages[user_id] = []

            # Очищаем постоянные сообщения (кроме самого последнего - главного меню)
            if user_id in self.permanent_messages and self.permanent_messages[user_id]:
                # Сохраняем ID последнего сообщения (главное меню)
                last_message_id = self.permanent_messages[user_id][-1] if self.permanent_messages[user_id] else None

                for message_id in self.permanent_messages[user_id][:]:
                    if message_id != last_message_id:  # Не удаляем главное меню
                        try:
                            await context.bot.delete_message(user_id, message_id)
                            deleted_count += 1
                        except Exception as e:
                            logger.debug(f"Не удалось удалить постоянное сообщение {message_id}: {e}")

                # Оставляем только последнее сообщение (главное меню)
                if last_message_id:
                    self.permanent_messages[user_id] = [last_message_id]
                else:
                    self.permanent_messages[user_id] = []

            # УВЕДОМЛЕНИЯ НЕ ОЧИЩАЕМ - они остаются всегда

            logger.debug(f"Очищено {deleted_count} сообщений для пользователя {user_id}")

        except Exception as e:
            logger.error(f"Ошибка при полной очистке сообщений для {user_id}: {e}")

    def is_temporary_message(self, user_id: int, message_id: int) -> bool:
        """Проверяет, является ли сообщение временным"""
        return (user_id in self.temporary_messages and
                message_id in self.temporary_messages[user_id])


# Глобальный экземпляр менеджера сообщений
message_manager = MessageManager()