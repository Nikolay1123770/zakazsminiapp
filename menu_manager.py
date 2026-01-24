from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import Database
import logging

logger = logging.getLogger(__name__)


class MenuManager:
    def __init__(self):
        self.db = Database()
        # Базовые данные для инициализации (используются только если база пустая)
        self.menu_items = [
            # Кальяны
            ("Пенсионный", 800, "Кальяны"),
            ("Стандарт", 1000, "Кальяны"),
            ("Премиум", 1200, "Кальяны"),
            ("Фруктовая чаша", 1500, "Кальяны"),
            ("Сигарный", 1500, "Кальяны"),
            ("Парфюм", 2000, "Кальяны"),

            # Напитки
            ("Вода", 100, "Напитки"),
            ("Кола 0,5л", 100, "Напитки"),
            ("Кола/Фанта/Спрайт 1л", 200, "Напитки"),
            ("Пиво/Энергетик", 200, "Напитки"),

            # Коктейли
            ("В/кола", 400, "Коктейли"),
            ("Санрайз", 400, "Коктейли"),
            ("Лагуна", 400, "Коктейли"),
            ("Фиеро", 400, "Коктейли"),
            ("Пробирки", 600, "Коктейли"),

            # Чай
            ("Да Хун Пао", 400, "Чай"),
            ("Те Гуань Инь", 400, "Чай"),
            ("Шу пуэр", 400, "Чай"),
            ("Сяо Чжун", 400, "Чай"),
            ("Юэ Гуан Бай", 400, "Чай"),
            ("Габа", 400, "Чай"),
            ("Гречишный", 400, "Чай"),
            ("Медовая дыня", 400, "Чай"),
            ("Малина/Мята", 400, "Чай"),
            ("Наглый фрукт", 400, "Чай"),
            ("Вишневый пуэр", 500, "Чай"),
            ("Марокканский", 500, "Чай"),
            ("Голубика", 500, "Чай"),
            ("Смородиновый", 500, "Чай"),
            ("Клубничный", 500, "Чай"),
            ("Облепиховый", 500, "Чай")
        ]

    def get_categories(self):
        """Получить список категорий меню из базы данных"""
        return self.db.get_all_menu_categories()

    def get_items_by_category(self, category):
        """Получить позиции меню по категории из базы данных"""
        items = self.db.get_menu_items_by_category(category)
        return [(item[1], item[2], item[3]) for item in items]  # преобразуем в формат (name, price, category)

    def get_all_items_with_categories(self):
        """Получить все позиции меню с их категориями - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            items = self.db.get_all_menu_items()

            # Если таблица пустая, используем данные из памяти и заполняем базу
            if not items:
                logger.warning("Таблица menu_items пуста, заполняем базовыми данными")
                for item in self.menu_items:
                    self.db.add_menu_item(item[0], item[1], item[2])

                # Получаем данные снова после заполнения
                items = self.db.get_all_menu_items()

            # Логируем для отладки
            logger.info(f"Загружено {len(items)} позиций из базы данных")
            for item in items:
                logger.debug(f"Меню: {item[1]} - {item[2]}₽ - Категория: {item[3]} - Активен: {item[4]}")

            # Преобразуем в формат (name, price, category)
            return [(item[1], item[2], item[3]) for item in items if item[4]]
        except Exception as e:
            logger.error(f"Error getting menu items from database: {e}")
            # Возвращаем данные из памяти как fallback
            return self.menu_items

    def get_item_by_name(self, name):
        """Найти позицию меню по названию в базе данных"""
        item = self.db.get_menu_item_by_name(name)
        if item and item[4]:  # проверяем is_active
            return (item[1], item[2], item[3])  # (name, price, category)
        return None

    def create_order(self, table_number, admin_id):
        """Создать новый заказ"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            INSERT INTO orders (table_number, admin_id, status, created_at)
            VALUES (?, ?, ?, ?)
        ''', (table_number, admin_id, 'active', self.db.get_moscow_time()))
        order_id = cursor.lastrowid
        self.db.conn.commit()
        return order_id

    def add_item_to_order(self, order_id, item_name, quantity=1):
        """Добавить позицию в заказ"""
        item = self.get_item_by_name(item_name)
        if not item:
            return False

        cursor = self.db.conn.cursor()
        cursor.execute('''
            INSERT INTO order_items (order_id, item_name, price, quantity, added_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (order_id, item[0], item[1], quantity, self.db.get_moscow_time()))
        self.db.conn.commit()
        return True

    # НОВЫЙ МЕТОД ДЛЯ УДАЛЕНИЯ ПОЗИЦИЙ ИЗ ЗАКАЗА
    def remove_item_from_order(self, order_id, item_name):
        """Удалить позицию из заказа"""
        return self.db.remove_item_from_order(order_id, item_name)

    def get_active_order_by_table(self, table_number):
        """Получить активный заказ по номеру стола"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT * FROM orders 
            WHERE table_number = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        ''', (table_number,))
        return cursor.fetchone()

    def get_order_items(self, order_id):
        """Получить все позиции заказа"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT * FROM order_items WHERE order_id = ?
        ''', (order_id,))
        return cursor.fetchall()

    def calculate_order_total(self, order_id):
        """Рассчитать общую сумму заказа"""
        items = self.get_order_items(order_id)
        total = sum(item[3] * item[4] for item in items)  # price * quantity
        return total

    def close_order(self, order_id):
        """Закрыть заказ"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            UPDATE orders SET status = 'closed', closed_at = ? WHERE id = ?
        ''', (self.db.get_moscow_time(), order_id))
        self.db.conn.commit()

    def get_category_keyboard(self):
        """Клавиатура для выбора категорий меню"""
        categories = self.get_categories()
        keyboard = []
        row = []
        for i, category in enumerate(categories):
            row.append(InlineKeyboardButton(category, callback_data=f"category_{category}"))
            if len(row) == 2 or i == len(categories) - 1:
                keyboard.append(row)
                row = []
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")])
        return InlineKeyboardMarkup(keyboard)

    def get_items_keyboard(self, category):
        """Клавиатура для выбора позиций в категории"""
        items = self.get_items_by_category(category)
        keyboard = []
        for item in items:
            keyboard.append([
                InlineKeyboardButton(
                    f"{item[0]} - {item[1]}₽",
                    callback_data=f"item_{item[0]}"
                )
            ])
        keyboard.append([InlineKeyboardButton("⬅️ Назад к категориям",
                                              callback_data="back_to_categories")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_order")])
        return InlineKeyboardMarkup(keyboard)


# Глобальный экземпляр менеджера меню
menu_manager = MenuManager()