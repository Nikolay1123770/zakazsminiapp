import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def migrate_database(db_path):
    """Миграция базы данных до актуальной схемы"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🔄 Начинаем миграцию базы данных...")

    try:
        # Проверяем существование таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [table[0] for table in cursor.fetchall()]
        print(f"📋 Существующие таблицы: {existing_tables}")

        # 1. Таблица заказов
        if 'orders' not in existing_tables:
            print("🔄 Создаем таблицу orders...")
            cursor.execute('''
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_number INTEGER,
                    admin_id INTEGER,
                    status TEXT DEFAULT 'active',
                    created_at TEXT,
                    closed_at TEXT
                )
            ''')

        # 2. Таблица позиций заказа
        if 'order_items' not in existing_tables:
            print("🔄 Создаем таблицу order_items...")
            cursor.execute('''
                CREATE TABLE order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    item_name TEXT,
                    price INTEGER,
                    quantity INTEGER DEFAULT 1,
                    added_at TEXT,
                    FOREIGN KEY (order_id) REFERENCES orders (id)
                )
            ''')

        # 3. Таблица смен
        if 'shifts' not in existing_tables:
            print("🔄 Создаем таблицу shifts...")
            cursor.execute('''
                CREATE TABLE shifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shift_number INTEGER UNIQUE,
                    admin_id INTEGER,
                    opened_at TEXT,
                    closed_at TEXT,
                    total_revenue INTEGER DEFAULT 0,
                    total_orders INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'open',
                    FOREIGN KEY (admin_id) REFERENCES users (id)
                )
            ''')

        # 4. Таблица статистики продаж по сменам
        if 'shift_sales' not in existing_tables:
            print("🔄 Создаем таблицу shift_sales...")
            cursor.execute('''
                CREATE TABLE shift_sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shift_id INTEGER,
                    item_name TEXT,
                    quantity INTEGER,
                    total_amount INTEGER,
                    FOREIGN KEY (shift_id) REFERENCES shifts (id)
                )
            ''')

        # 5. Таблица меню
        if 'menu_items' not in existing_tables:
            print("🔄 Создаем таблицу menu_items...")
            cursor.execute('''
                CREATE TABLE menu_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    price INTEGER,
                    category TEXT
                )
            ''')

            # Заполняем меню базовыми данными
            menu_items = [
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

            for name, price, category in menu_items:
                try:
                    cursor.execute(
                        'INSERT INTO menu_items (name, price, category) VALUES (?, ?, ?)',
                        (name, price, category)
                    )
                except sqlite3.IntegrityError:
                    continue

            print("✅ Таблица menu_items заполнена данными")

        # 6. Проверяем и добавляем отсутствующие колонки в таблицу users
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in cursor.fetchall()]

        if 'referred_by' not in user_columns:
            print("🔄 Добавляем колонку referred_by в таблицу users...")
            cursor.execute('ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL')

        # 7. Проверяем и добавляем отсутствующие колонки в таблицу orders
        if 'orders' in existing_tables:
            cursor.execute("PRAGMA table_info(orders)")
            order_columns = [column[1] for column in cursor.fetchall()]

            if 'closed_at' not in order_columns:
                print("🔄 Добавляем колонку closed_at в таблицу orders...")
                cursor.execute('ALTER TABLE orders ADD COLUMN closed_at TEXT')

        conn.commit()
        print("✅ Миграция базы данных завершена успешно!")

        # Показываем статистику
        print("\n📊 Статистика базы данных:")
        for table in ['users', 'orders', 'order_items', 'shifts', 'shift_sales', 'menu_items']:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            print(f"   {table}: {count} записей")

    except Exception as e:
        print(f"❌ Ошибка при миграции базы данных: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    # Укажите путь к вашей базе данных
    db_path = 'loyalty_bot.db'  # или другое имя файла
    migrate_database(db_path)