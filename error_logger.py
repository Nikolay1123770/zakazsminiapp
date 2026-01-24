import logging
import os
from datetime import datetime
from config import LOG_FILE


def setup_error_logging():
    """Настройка логирования ошибок в файл"""

    try:
        # Создаем папку для логов если ее нет
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Если файл логов в корневой папке, создаем папку logs
        if not log_dir:
            log_dir = 'logs'
            LOG_FILE = os.path.join(log_dir, 'bot_errors.log')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

        # Настраиваем формат логов
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        # Настраиваем файловый обработчик
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setLevel(logging.ERROR)
        file_handler.setFormatter(logging.Formatter(log_format))

        # Настраиваем обработчик для консоли
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))

        # Получаем корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Очищаем существующие обработчики
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Добавляем наши обработчики
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Логируем запуск
        logging.info(f"🚀 Бот запущен в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"📁 Логи ошибок сохраняются в: {os.path.abspath(LOG_FILE)}")

    except PermissionError:
        # Если нет прав на запись в файл, используем только консольное логирование
        print("⚠️ Нет прав на запись в файл логов. Используется консольное логирование.")

        # Настраиваем только консольное логирование
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Очищаем существующие обработчики
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        root_logger.addHandler(console_handler)
        logging.info(f"🚀 Бот запущен в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (консольное логирование)")

    except Exception as e:
        # Резервное логирование в случае любой ошибки
        print(f"⚠️ Ошибка настройки логирования: {e}")
        print(f"🚀 Бот запущен в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (базовое логирование)")

        # Базовая настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


def log_admin_action(action: str, admin_id: int):
    """Логирование действий администратора"""
    try:
        logger = logging.getLogger(__name__)
        logger.info(f"👨‍💼 Админ действие: {action} | Админ ID: {admin_id} | Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logging.error(f"Ошибка при логировании действия администратора: {e}")


def log_user_action(action: str, user_id: int):
    """Логирование действий пользователя"""
    try:
        logger = logging.getLogger(__name__)
        logger.info(f"👤 Пользователь действие: {action} | Пользователь ID: {user_id} | Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logging.error(f"Ошибка при логировании действия пользователя: {e}")


def log_booking_action(action: str, booking_id: int, user_id: int = None):
    """Логирование действий с бронированиями"""
    try:
        logger = logging.getLogger(__name__)
        user_info = f" | Пользователь ID: {user_id}" if user_id else ""
        logger.info(f"📅 Бронирование действие: {action} | Бронирование ID: {booking_id}{user_info} | Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logging.error(f"Ошибка при логировании действия с бронированием: {e}")


def log_bonus_action(action: str, user_id: int, amount: int = None):
    """Логирование действий с бонусами"""
    try:
        logger = logging.getLogger(__name__)
        amount_info = f" | Сумма: {amount}" if amount is not None else ""
        logger.info(f"💰 Бонус действие: {action} | Пользователь ID: {user_id}{amount_info} | Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        logging.error(f"Ошибка при логировании действия с бонусами: {e}")


def log_error(error_message: str, user_id: int = None, additional_info: str = None):
    """Логирование ошибок"""
    try:
        logger = logging.getLogger(__name__)
        user_info = f" | Пользователь ID: {user_id}" if user_id else ""
        additional = f" | Доп. информация: {additional_info}" if additional_info else ""
        logger.error(f"❌ Ошибка: {error_message}{user_info}{additional} | Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"Критическая ошибка при логировании: {e}")