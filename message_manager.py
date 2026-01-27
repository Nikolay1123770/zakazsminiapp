import asyncio
from typing import List, Optional
from telegram import Message, Update, error
from telegram.ext import ContextTypes
from config import MESSAGE_CLEANUP_DELAY
import logging

logger = logging.getLogger(__name__)


class MessageManager:
    def __init__(self):
        self.temporary_messages = {}
        self.permanent_messages = {}
        self.notification_messages = {}  # Отдельное хранилище для уведомлений
        self.inactive_users = set()  # Пользователи, заблокировавшие бота

    async def send_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                           text: str, is_temporary: bool = False, is_notification: bool = False, **kwargs) -> Optional[Message]:
        """Отправляет сообщение и управляет его временем жизни"""
        try:
            user_id = update.effective_user.id
            
            # Проверяем, не заблокировал ли пользователь бота
            if user_id in self.inactive_users:
                logger.warning(f"Пользователь {user_id} заблокировал бота, пропускаем отправку")
                return None

            if hasattr(update, 'message') and update.message:
                message = await update.message.reply_text(text, **kwargs)
            elif hasattr(update, 'callback_query') and update.callback_query:
                message = await update.callback_query.message.reply_text(text, **kwargs)
            else:
                # Если нет прямого доступа к сообщению, используем context
                chat_id = update.effective_chat.id
                message = await context.bot.send_message(chat_id, text, **kwargs)

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
            
        except error.BadRequest as e:
            error_msg = str(e)
            if "Chat not found" in error_msg or "user is deactivated" in error_msg:
                logger.error(f"❌ Пользователь {user_id} заблокировал бота или чат не найден: {error_msg}")
                self.inactive_users.add(user_id)
                return None
            else:
                logger.error(f"❌ Ошибка BadRequest при отправке сообщения: {error_msg}")
                raise
                
        except error.Forbidden as e:
            logger.error(f"❌ Бот заблокирован пользователем {user_id}: {e}")
            self.inactive_users.add(user_id)
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке сообщения пользователю {user_id}: {e}")
            raise

    async def send_message_to_chat(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                                   text: str, is_temporary: bool = False, is_notification: bool = False,
                                   **kwargs) -> Optional[Message]:
        """Отправляет сообщение в указанный чат"""
        try:
            # Проверяем, не заблокировал ли пользователь бота
            if chat_id in self.inactive_users:
                logger.warning(f"Чат {chat_id} заблокировал бота, пропускаем отправку")
                return None

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
            
        except error.BadRequest as e:
            error_msg = str(e)
            if "Chat not found" in error_msg or "user is deactivated" in error_msg:
                logger.error(f"❌ Чат {chat_id} не найден или пользователь деактивирован: {error_msg}")
                self.inactive_users.add(chat_id)
                return None
            else:
                logger.error(f"❌ Ошибка BadRequest при отправке в чат {chat_id}: {error_msg}")
                return None
                
        except error.Forbidden as e:
            logger.error(f"❌ Бот заблокирован в чате {chat_id}: {e}")
            self.inactive_users.add(chat_id)
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке сообщения в чат {chat_id}: {e}")
            return None

    async def _delete_temporary_message(self, context: ContextTypes.DEFAULT_TYPE,
                                        chat_id: int, message_id: int):
        """Удаляет временное сообщение после задержки"""
        await asyncio.sleep(MESSAGE_CLEANUP_DELAY)
        try:
            # Проверяем, не является ли пользователь неактивным
            if chat_id in self.inactive_users:
                return  # Не пытаемся удалять сообщения у неактивных пользователей

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
        except error.BadRequest as e:
            error_msg = str(e)
            if "Chat not found" in error_msg or "user is deactivated" in error_msg:
                logger.warning(f"⚠️ Чат {chat_id} не найден при удалении сообщения, добавляем в неактивные")
                self.inactive_users.add(chat_id)
            elif "Message to delete not found" in error_msg:
                logger.debug(f"Сообщение {message_id} уже удалено для чата {chat_id}")
            else:
                logger.debug(f"Не удалось удалить временное сообщение {message_id} для {chat_id}: {e}")
        except Exception as e:
            logger.debug(f"Не удалось удалить временное сообщение {message_id} для {chat_id}: {e}")

    async def cleanup_user_messages(self, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Очищает все временные сообщения пользователя (но не уведомления)"""
        if user_id in self.temporary_messages:
            for message_id in self.temporary_messages[user_id][:]:
                try:
                    await context.bot.delete_message(user_id, message_id)
                except error.BadRequest as e:
                    error_msg = str(e)
                    if "Chat not found" in error_msg or "user is deactivated" in error_msg:
                        logger.warning(f"⚠️ Чат {user_id} не найден при очистке, добавляем в неактивные")
                        self.inactive_users.add(user_id)
                        break  # Прерываем очистку
                    elif "Message to delete not found" in error_msg:
                        continue  # Сообщение уже удалено
                    else:
                        logger.debug(f"Не удалось удалить сообщение {message_id} при очистке: {e}")
                except Exception as e:
                    logger.debug(f"Не удалось удалить сообщение {message_id} при очистке: {e}")
            self.temporary_messages[user_id] = []

    async def cleanup_all_messages(self, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Полная очистка ВСЕХ сообщений пользователя (используется при возврате в главное меню)"""
        try:
            # Проверяем, не заблокировал ли пользователь бота
            if user_id in self.inactive_users:
                logger.warning(f"Пользователь {user_id} неактивен, пропускаем очистку")
                return

            deleted_count = 0

            # Очищаем временные сообщения
            if user_id in self.temporary_messages:
                for message_id in self.temporary_messages[user_id][:]:
                    try:
                        await context.bot.delete_message(user_id, message_id)
                        deleted_count += 1
                    except error.BadRequest as e:
                        error_msg = str(e)
                        if "Chat not found" in error_msg or "user is deactivated" in error_msg:
                            logger.warning(f"⚠️ Чат {user_id} не найден при очистке, добавляем в неактивные")
                            self.inactive_users.add(user_id)
                            break  # Прерываем очистку
                        elif "Message to delete not found" in error_msg:
                            continue  # Сообщение уже удалено
                        else:
                            logger.debug(f"Не удалось удалить временное сообщение {message_id}: {e}")
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
                        except error.BadRequest as e:
                            error_msg = str(e)
                            if "Chat not found" in error_msg or "user is deactivated" in error_msg:
                                logger.warning(f"⚠️ Чат {user_id} не найден при очистке, добавляем в неактивные")
                                self.inactive_users.add(user_id)
                                break  # Прерываем очистку
                            elif "Message to delete not found" in error_msg:
                                continue  # Сообщение уже удалено
                            else:
                                logger.debug(f"Не удалось удалить постоянное сообщение {message_id}: {e}")
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
    
    def is_user_inactive(self, user_id: int) -> bool:
        """Проверяет, заблокировал ли пользователь бота"""
        return user_id in self.inactive_users
    
    def remove_inactive_user(self, user_id: int):
        """Удаляет пользователя из списка неактивных (если он снова начал общение)"""
        if user_id in self.inactive_users:
            self.inactive_users.remove(user_id)
            logger.info(f"✅ Пользователь {user_id} удален из списка неактивных")


# Глобальный экземпляр менеджера сообщений
message_manager = MessageManager()
