import sqlite3
import logging
from config import DB_NAME
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.create_tables()
        self.fix_menu_categories()
        self.add_payment_method_column()
        self.create_miniapp_tables()  # Создаем таблицы для MiniApp

    def get_moscow_time(self):
        """Получить текущее время в московском часовом поясе"""
        tz = pytz.timezone('Europe/Moscow')
        return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

    def create_tables(self):
        """Создание всех таблиц с правильной структурой"""
        cursor = self.conn.cursor()

        # Создаем все остальные таблицы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                bonus_balance INTEGER DEFAULT 0,
                registration_date TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                referred_by INTEGER DEFAULT NULL,
                total_spent INTEGER DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                FOREIGN KEY (referred_by) REFERENCES users (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT, -- 'earn' или 'spend'
                description TEXT,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                customer_name TEXT,
                customer_phone TEXT,
                booking_date TEXT,
                booking_time TEXT,
                guests INTEGER,
                comment TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                source TEXT DEFAULT 'bot',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bonus_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                bonus_awarded BOOLEAN DEFAULT FALSE,
                created_at TEXT,
                FOREIGN KEY (referrer_id) REFERENCES users (id),
                FOREIGN KEY (referred_id) REFERENCES users (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_number INTEGER,
                admin_id INTEGER,
                status TEXT DEFAULT 'active', -- 'active' или 'closed'
                created_at TEXT,
                closed_at TEXT,
                payment_method TEXT DEFAULT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                item_name TEXT,
                price INTEGER,
                quantity INTEGER DEFAULT 1,
                added_at TEXT,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                price INTEGER,
                category TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        # Проверяем таблицу shifts
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shifts'")
        shifts_table_exists = cursor.fetchone()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_shift_month'")
        index_exists = cursor.fetchone()

        if not shifts_table_exists or not index_exists:
            print("🔄 Создаем/обновляем таблицу shifts...")
            cursor.execute('PRAGMA foreign_keys = OFF')

            if shifts_table_exists:
                cursor.execute('ALTER TABLE shifts RENAME TO shifts_old')

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shift_sales'")
            if cursor.fetchone():
                cursor.execute('ALTER TABLE shift_sales RENAME TO shift_sales_old')

            cursor.execute('''
                CREATE TABLE shifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shift_number INTEGER,
                    month_year TEXT,
                    admin_id INTEGER,
                    opened_at TEXT,
                    closed_at TEXT,
                    total_revenue INTEGER DEFAULT 0,
                    total_orders INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'open',
                    FOREIGN KEY (admin_id) REFERENCES users (id)
                )
            ''')

            if not index_exists:
                cursor.execute('CREATE UNIQUE INDEX idx_shift_month ON shifts (shift_number, month_year)')

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

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shifts_old'")
            if cursor.fetchone():
                cursor.execute('''
                    INSERT INTO shifts (id, shift_number, month_year, admin_id, opened_at, closed_at, 
                                      total_revenue, total_orders, status)
                    SELECT id, shift_number, 
                           CASE 
                               WHEN month_year IS NOT NULL THEN month_year
                               ELSE substr(opened_at, 1, 7)
                           END as month_year,
                           admin_id, opened_at, closed_at, total_revenue, total_orders, status
                    FROM shifts_old
                    ORDER BY id
                ''')

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shift_sales_old'")
                if cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO shift_sales (shift_id, item_name, quantity, total_amount)
                        SELECT shift_id, item_name, quantity, total_amount
                        FROM shift_sales_old
                    ''')

                cursor.execute('DROP TABLE IF EXISTS shifts_old')
                cursor.execute('DROP TABLE IF EXISTS shift_sales_old')

            cursor.execute('PRAGMA foreign_keys = ON')
        else:
            print("✅ Таблица shifts уже существует с правильным индексом")

        self.conn.commit()
        self._update_schema()
        self.populate_menu_items()
        self.fix_menu_categories()

    def create_miniapp_tables(self):
        """Создать таблицы для MiniApp"""
        cursor = self.conn.cursor()
        
        # Таблица для конфигурации MiniApp
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(section, key)
            )
        ''')
        
        # Таблица для меню MiniApp (расширенная)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                old_price INTEGER DEFAULT NULL,
                category TEXT NOT NULL,
                icon TEXT DEFAULT '🍽️',
                badge TEXT DEFAULT NULL,
                position INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name)
            )
        ''')
        
        # Таблица для галереи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS miniapp_gallery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                emoji TEXT DEFAULT '📸',
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        
        # Добавляем базовую конфигурацию
        default_config = [
            ('contacts', 'address', 'ул. Химическая, 52', 'Адрес заведения'),
            ('contacts', 'phone', '+7 (999) 123-45-67', 'Телефон для связи'),
            ('contacts', 'instagram', '@vovseTyajkie', 'Instagram профиль'),
            ('schedule', 'weekdays', '14:00 — 02:00', 'Время работы Пн-Чт'),
            ('schedule', 'weekend', '14:00 — 04:00', 'Время работы Пт-Вс'),
            ('stats', 'flavors', '50+', 'Количество вкусов'),
            ('stats', 'experience', '5', 'Лет опыта'),
            ('stats', 'guests', '10K', 'Количество гостей'),
            ('miniapp', 'welcome_message', 'Добро пожаловать!', 'Приветственное сообщение'),
            ('miniapp', 'theme', 'dark', 'Тема приложения'),
            ('miniapp', 'primary_color', '#a855f7', 'Основной цвет')
        ]
        
        for config_item in default_config:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_config (section, key, value, description)
                    VALUES (?, ?, ?, ?)
                ''', config_item)
            except:
                pass
        
        # Добавляем базовые товары для MiniApp
        default_menu = [
            ('Классический', 'Один вкус премиум табака на выбор', 1200, 1500, 'hookah', '💨', 'hit', 1),
            ('Premium', 'Tangiers, Darkside, Element — топовые табаки мира', 1800, None, 'hookah', '🔮', 'premium', 2),
            ('VIP Кальян', 'Эксклюзивные табаки + фрукты + авторская подача', 2500, None, 'hookah', '👑', 'vip', 3),
            ('Blue Crystal', 'Ледяная свежесть с нотками мяты и цитруса', 2000, None, 'signature', '🧊', 'hit', 1),
            ('Heisenberg', 'Секретный рецепт шефа. 99.1% чистого наслаждения', 2200, None, 'signature', '⚗️', 'signature', 2),
            ('Los Pollos', 'Пряный микс с перцем и тропическими фруктами', 2000, None, 'signature', '🔥', 'hot', 3),
            ('Чай (чайник)', 'Чёрный, зелёный, фруктовый или травяной', 400, None, 'drinks', '🍵', None, 1),
            ('Лимонады', 'Клубничный, цитрусовый, мохито, манго', 350, None, 'drinks', '🍹', None, 2),
            ('Кофе', 'Эспрессо, американо, капучино, латте, раф', 250, None, 'drinks', '☕', None, 3),
            ('Пицца', 'Маргарита, Пепперони, 4 сыра, BBQ курица', 650, None, 'food', '🍕', None, 1),
            ('Салаты', 'Цезарь, Греческий, с креветками', 450, None, 'food', '🥗', None, 2),
            ('Закуски', 'Картофель фри, наггетсы, сырные палочки', 350, None, 'food', '🍟', None, 3)
        ]
        
        for menu_item in default_menu:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_menu (name, description, price, old_price, category, icon, badge, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', menu_item)
            except:
                pass
        
        # Добавляем галерею
        default_gallery = [
            ('Лаборатория вкусов', '🧪', 'Авторские миксы', 1),
            ('Премиум кальяны', '💨', 'Эксклюзивные табаки', 2),
            ('VIP зона', '🛋️', 'Уютная атмосфера', 3),
            ('Коктейли', '🍹', 'Авторские напитки', 4),
            ('Вечерние посиделки', '🔥', 'Атмосферные вечера', 5),
            ('Кухня', '⚗️', 'Вкусные закуски', 6)
        ]
        
        for gallery_item in default_gallery:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO miniapp_gallery (title, emoji, description, position)
                    VALUES (?, ?, ?, ?)
                ''', gallery_item)
            except:
                pass
        
        self.conn.commit()
        logger.info("✅ Таблицы для MiniApp созданы/проверены")

    def _update_schema(self):
        """Обновляет схему базы данных, добавляя отсутствующие колонки"""
        cursor = self.conn.cursor()

        # Проверяем наличие колонки referred_by в таблице users
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'referred_by' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL')

        # Проверяем наличие колонки closed_at в таблице orders
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'closed_at' not in columns:
            cursor.execute('ALTER TABLE orders ADD COLUMN closed_at TEXT')

        # Проверяем наличие колонки payment_method в orders
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'payment_method' not in columns:
            cursor.execute('ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT NULL')

        # Проверяем наличие колонки month_year в таблице shifts
        cursor.execute("PRAGMA table_info(shifts)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'month_year' not in columns:
            cursor.execute('ALTER TABLE shifts ADD COLUMN month_year TEXT')
            cursor.execute('SELECT id, opened_at FROM shifts')
            shifts = cursor.fetchall()
            for shift_id, opened_at in shifts:
                if opened_at:
                    month_year = opened_at[:7]
                    cursor.execute('UPDATE shifts SET month_year = ? WHERE id = ?', (month_year, shift_id))

        # Проверяем наличие колонки is_active в таблице menu_items
        cursor.execute("PRAGMA table_info(menu_items)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'is_active' not in columns:
            cursor.execute('ALTER TABLE menu_items ADD COLUMN is_active BOOLEAN DEFAULT TRUE')

        # Проверяем наличие колонок для MiniApp в bookings
        cursor.execute("PRAGMA table_info(bookings)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'source' not in columns:
            cursor.execute('ALTER TABLE bookings ADD COLUMN source TEXT DEFAULT "bot"')
        
        if 'customer_name' not in columns:
            cursor.execute('ALTER TABLE bookings ADD COLUMN customer_name TEXT')
        
        if 'customer_phone' not in columns:
            cursor.execute('ALTER TABLE bookings ADD COLUMN customer_phone TEXT')

        # Добавляем колонки total_spent и total_orders в users если их нет
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'total_spent' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN total_spent INTEGER DEFAULT 0')
        
        if 'total_orders' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN total_orders INTEGER DEFAULT 0')

        self.conn.commit()

    def fix_menu_categories(self):
        """Исправить категории в меню если необходимо"""
        cursor = self.conn.cursor()

        hookah_items = ["Пенсионный", "Стандарт", "Премиум", "Фруктовая чаша", "Сигарный", "Парфюм"]

        for item_name in hookah_items:
            cursor.execute('SELECT category FROM menu_items WHERE name = ?', (item_name,))
            result = cursor.fetchone()

            if result and result[0] != 'Кальяны':
                cursor.execute('UPDATE menu_items SET category = ? WHERE name = ?', ('Кальяны', item_name))

        self.conn.commit()

    def populate_menu_items(self):
        """Заполнить таблицу menu_items базовыми данными"""
        cursor = self.conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM menu_items')
        count = cursor.fetchone()[0]

        if count == 0:
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
                ("Марроканский", 500, "Чай"),
                ("Голубика", 500, "Чай"),
                ("Смородиновый", 500, "Чай"),
                ("Клубничный", 500, "Чай"),
                ("Облепиховый", 500, "Чай")
            ]

            for name, price, category in menu_items:
                try:
                    cursor.execute(
                        'INSERT INTO menu_items (name, price, category, is_active) VALUES (?, ?, ?, ?)',
                        (name, price, category, True)
                    )
                except sqlite3.IntegrityError:
                    continue

            self.conn.commit()

    # ========== МЕТОДЫ ДЛЯ MINIAPP ==========

    def get_miniapp_menu(self, category=None):
        """Получить меню для MiniApp"""
        cursor = self.conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT id, name, description, price, old_price, category, icon, badge 
                FROM miniapp_menu 
                WHERE category = ? AND is_active = TRUE 
                ORDER BY position, name
            ''', (category,))
        else:
            cursor.execute('''
                SELECT id, name, description, price, old_price, category, icon, badge 
                FROM miniapp_menu 
                WHERE is_active = TRUE 
                ORDER BY category, position, name
            ''')
        
        return cursor.fetchall()

    def get_miniapp_menu_item(self, item_id):
        """Получить товар из меню MiniApp по ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, name, description, price, old_price, category, icon, badge 
            FROM miniapp_menu 
            WHERE id = ? AND is_active = TRUE
        ''', (item_id,))
        return cursor.fetchone()

    def add_miniapp_menu_item(self, name, description, price, category, icon='🍽️', badge=None, old_price=None):
        """Добавить товар в меню MiniApp"""
        cursor = self.conn.cursor()
        
        # Получаем максимальную позицию для категории
        cursor.execute('''
            SELECT MAX(position) FROM miniapp_menu WHERE category = ?
        ''', (category,))
        result = cursor.fetchone()
        position = (result[0] or 0) + 1
        
        try:
            cursor.execute('''
                INSERT INTO miniapp_menu (name, description, price, old_price, category, icon, badge, position)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, price, old_price, category, icon, badge, position))
            self.conn.commit()
            return True, "✅ Товар добавлен в меню MiniApp"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"

    def update_miniapp_menu_item(self, item_id, **kwargs):
        """Обновить товар в меню MiniApp"""
        cursor = self.conn.cursor()
        
        fields = []
        values = []
        
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False, "❌ Нет данных для обновления"
        
        values.append(item_id)
        query = f"UPDATE miniapp_menu SET {', '.join(fields)} WHERE id = ?"
        
        try:
            cursor.execute(query, values)
            self.conn.commit()
            return True, "✅ Товар обновлен"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"

    def toggle_miniapp_menu_item(self, item_id, is_active):
        """Включить/выключить товар в меню MiniApp"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('UPDATE miniapp_menu SET is_active = ? WHERE id = ?', (is_active, item_id))
            self.conn.commit()
            status = "включен" if is_active else "выключен"
            return True, f"✅ Товар {status}"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"

    def get_miniapp_config(self, section=None, key=None):
        """Получить конфигурацию MiniApp"""
        cursor = self.conn.cursor()
        
        if section and key:
            cursor.execute('SELECT value FROM miniapp_config WHERE section = ? AND key = ?', (section, key))
            result = cursor.fetchone()
            return result[0] if result else None
        elif section:
            cursor.execute('SELECT key, value FROM miniapp_config WHERE section = ?', (section,))
            return dict(cursor.fetchall())
        else:
            cursor.execute('SELECT section, key, value, description FROM miniapp_config')
            return cursor.fetchall()

    def set_miniapp_config(self, section, key, value, description=None):
        """Установить значение конфигурации MiniApp"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO miniapp_config (section, key, value, description, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (section, key, value, description))
        self.conn.commit()

    def get_miniapp_gallery(self):
        """Получить галерею для MiniApp"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, title, emoji, description 
            FROM miniapp_gallery 
            WHERE is_active = TRUE 
            ORDER BY position
        ''')
        return cursor.fetchall()

    def add_miniapp_gallery_item(self, title, emoji, description):
        """Добавить элемент в галерею MiniApp"""
        cursor = self.conn.cursor()
        
        # Получаем максимальную позицию
        cursor.execute('SELECT MAX(position) FROM miniapp_gallery')
        result = cursor.fetchone()
        position = (result[0] or 0) + 1
        
        try:
            cursor.execute('''
                INSERT INTO miniapp_gallery (title, emoji, description, position)
                VALUES (?, ?, ?, ?)
            ''', (title, emoji, description, position))
            self.conn.commit()
            return True, "✅ Элемент добавлен в галерею"
        except Exception as e:
            return False, f"❌ Ошибка: {str(e)}"

    def get_user_by_telegram_id(self, telegram_id):
        """Получить пользователя по Telegram ID для MiniApp"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, telegram_id, first_name, last_name, phone, bonus_balance, registration_date, total_spent, total_orders
            FROM users 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        return cursor.fetchone()

    def create_miniapp_booking(self, user_id, name, phone, date, time, guests, comment="", source="miniapp"):
        """Создать бронирование из MiniApp"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO bookings (user_id, customer_name, customer_phone, booking_date, booking_time, guests, comment, status, created_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            ''', (user_id, name, phone, date, time, guests, comment, self.get_moscow_time(), source))
            
            booking_id = cursor.lastrowid
            self.conn.commit()
            
            return booking_id
        except Exception as e:
            logger.error(f"Ошибка создания бронирования из MiniApp: {e}")
            return None

    def get_miniapp_user_bookings(self, user_id):
        """Получить бронирования пользователя для MiniApp"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, booking_date, booking_time, guests, comment, status, created_at
            FROM bookings 
            WHERE user_id = ? AND source = 'miniapp'
            ORDER BY booking_date DESC, booking_time DESC
            LIMIT 10
        ''', (user_id,))
        return cursor.fetchall()

    def get_or_create_miniapp_user(self, telegram_user):
        """Получить или создать пользователя для MiniApp"""
        cursor = self.conn.cursor()
        
        # Проверяем существование пользователя
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_user.get('id'),))
        user = cursor.fetchone()
        
        if user:
            return user[0]
        
        # Создаем нового пользователя
        try:
            cursor.execute('''
                INSERT INTO users (telegram_id, first_name, last_name, registration_date, bonus_balance)
                VALUES (?, ?, ?, ?, 0)
            ''', (
                telegram_user.get('id'),
                telegram_user.get('first_name', ''),
                telegram_user.get('last_name', ''),
                self.get_moscow_time()
            ))
            user_id = cursor.lastrowid
            self.conn.commit()
            return user_id
        except Exception as e:
            logger.error(f"Ошибка создания пользователя: {e}")
            return None

    # ========== МЕТОДЫ ДЛЯ БРОНИРОВАНИЙ (ИСПРАВЛЕННЫЕ) ==========

    def create_booking(self, user_id, date, time, guests, comment='', source='bot', customer_name='', customer_phone=''):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO bookings (user_id, customer_name, customer_phone, booking_date, booking_time, guests, comment, created_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, customer_name, customer_phone, date, time, guests, comment, self.get_moscow_time(), source))
        self.conn.commit()
        return cursor.lastrowid

    def get_bookings_by_status(self, status):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT b.*, u.first_name, u.last_name, u.phone, u.telegram_id
            FROM bookings b 
            LEFT JOIN users u ON b.user_id = u.id 
            WHERE b.status = ?
            ORDER BY b.booking_date, b.booking_time
        ''', (status,))
        return cursor.fetchall()

    def get_bookings_by_date(self, date):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT b.*, u.first_name, u.last_name, u.phone, u.telegram_id
            FROM bookings b 
            LEFT JOIN users u ON b.user_id = u.id 
            WHERE b.booking_date = ?
            ORDER BY b.booking_time
        ''', (date,))
        return cursor.fetchall()

    def get_all_bookings_sorted(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT b.*, u.first_name, u.last_name, u.phone, u.telegram_id
            FROM bookings b 
            LEFT JOIN users u ON b.user_id = u.id 
            ORDER BY b.booking_date, b.booking_time
        ''')
        return cursor.fetchall()

    def get_booking_stats(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                status,
                COUNT(*) as count
            FROM bookings 
            GROUP BY status
        ''')
        stats = cursor.fetchall()

        stats_dict = {}
        total = 0
        for status, count in stats:
            stats_dict[status] = count
            total += count

        stats_dict['total'] = total
        return stats_dict

    def update_booking_status(self, booking_id, status):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', (status, booking_id))
        self.conn.commit()
        return True

    # ========== СУЩЕСТВУЮЩИЕ МЕТОДЫ (сохраняем все из вашего файла) ==========

    def add_user(self, telegram_id, first_name, last_name, phone, referred_by=None):
        try:
            cursor = self.conn.cursor()
            registration_date = self.get_moscow_time()

            cursor.execute('''
                INSERT INTO users (telegram_id, first_name, last_name, phone, bonus_balance, referred_by, registration_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (telegram_id, first_name, last_name, phone, 100, referred_by, registration_date))
            user_id = cursor.lastrowid

            if referred_by:
                cursor.execute('''
                    INSERT INTO referrals (referrer_id, referred_id, created_at)
                    VALUES (?, ?, ?)
                ''', (referred_by, user_id, self.get_moscow_time()))

            self.conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            return None

    def get_user(self, telegram_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        return cursor.fetchone()

    def get_user_by_id(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        return cursor.fetchone()

    def update_user_balance(self, user_id, amount):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET bonus_balance = bonus_balance + ? WHERE id = ?', (amount, user_id))
        self.conn.commit()

    def add_transaction(self, user_id, amount, transaction_type, description):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description, date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, transaction_type, description, self.get_moscow_time()))
        self.conn.commit()

    def create_bonus_request(self, user_id, amount):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO bonus_requests (user_id, amount, created_at)
            VALUES (?, ?, ?)
        ''', (user_id, amount, self.get_moscow_time()))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE is_active = TRUE ORDER BY id DESC')
        return cursor.fetchall()

    def get_pending_requests(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT br.*, u.first_name, u.last_name 
            FROM bonus_requests br 
            JOIN users u ON br.user_id = u.id 
            WHERE br.status = 'pending'
            ORDER BY br.created_at DESC
        ''')
        return cursor.fetchall()

    def update_bonus_request(self, request_id, status):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE bonus_requests SET status = ? WHERE id = ?', (status, request_id))
        self.conn.commit()

    def get_user_bookings(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM bookings WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        return cursor.fetchall()

    def get_referrer_stats(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as total_referrals, 
                   SUM(CASE WHEN bonus_awarded = 1 THEN 1 ELSE 0 END) as awarded_referrals
            FROM referrals 
            WHERE referrer_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        return result if result else (0, 0)

    def award_referral_bonus(self, referred_user_id):
        cursor = self.conn.cursor()

        cursor.execute('SELECT referred_by FROM users WHERE id = ?', (referred_user_id,))
        result = cursor.fetchone()

        if result and result[0]:
            referrer_id = result[0]

            cursor.execute('''
                SELECT bonus_awarded FROM referrals 
                WHERE referred_id = ? AND referrer_id = ?
            ''', (referred_user_id, referrer_id))

            referral = cursor.fetchone()

            if referral and not referral[0]:
                from config import REFERRAL_BONUS
                self.update_user_balance(referrer_id, REFERRAL_BONUS)
                self.add_transaction(referrer_id, REFERRAL_BONUS, 'earn',
                                     f'Реферальный бонус за приглашенного пользователя')

                cursor.execute('''
                    UPDATE referrals SET bonus_awarded = 1 
                    WHERE referred_id = ? AND referrer_id = ?
                ''', (referred_user_id, referrer_id))

                self.conn.commit()
                return referrer_id, REFERRAL_BONUS

        return None, 0

    def get_booking_dates(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT booking_date 
            FROM bookings 
            ORDER BY booking_date
        ''')
        dates = cursor.fetchall()
        return [date[0] for date in dates] if dates else []

    def get_order_by_id(self, order_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        return cursor.fetchone()

    def get_active_orders(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT o.*, u.first_name, u.last_name 
            FROM orders o 
            LEFT JOIN users u ON o.admin_id = u.id 
            WHERE o.status = 'active'
            ORDER BY o.created_at DESC
        ''')
        return cursor.fetchall()

    def get_active_order_by_table(self, table_number):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM orders 
            WHERE table_number = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        ''', (table_number,))
        return cursor.fetchone()

    def get_orders_by_date(self, date, status=None):
        cursor = self.conn.cursor()
        if status:
            cursor.execute('''
                SELECT o.*, u.first_name, u.last_name 
                FROM orders o 
                LEFT JOIN users u ON o.admin_id = u.id 
                WHERE DATE(o.created_at) = ? AND o.status = ?
                ORDER BY o.created_at DESC
            ''', (date, status))
        else:
            cursor.execute('''
                SELECT o.*, u.first_name, u.last_name 
                FROM orders o 
                LEFT JOIN users u ON o.admin_id = u.id 
                WHERE DATE(o.created_at) = ?
                ORDER BY o.created_at DESC
            ''', (date,))
        return cursor.fetchall()

    def get_all_closed_orders(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT o.*, u.first_name, u.last_name 
            FROM orders o 
            LEFT JOIN users u ON o.admin_id = u.id 
            WHERE o.status = 'closed'
            ORDER BY o.closed_at DESC
        ''')
        return cursor.fetchall()

    def get_order_dates(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT DATE(created_at) as order_date 
            FROM orders 
            WHERE status = 'closed'
            ORDER BY order_date DESC
        ''')
        dates = cursor.fetchall()
        return [date[0] for date in dates] if dates else []

    def remove_item_from_order(self, order_id, item_name):
        cursor = self.conn.cursor()

        cursor.execute('''
            SELECT id, quantity FROM order_items 
            WHERE order_id = ? AND item_name = ?
        ''', (order_id, item_name))

        item = cursor.fetchone()

        if not item:
            return False, "Позиция не найдена"

        item_id, current_quantity = item

        if current_quantity > 1:
            cursor.execute('''
                UPDATE order_items 
                SET quantity = quantity - 1 
                WHERE id = ?
            ''', (item_id,))
            message = "Количество уменьшено"
        else:
            cursor.execute('''
                DELETE FROM order_items 
                WHERE id = ?
            ''', (item_id,))
            message = "Позиция удалена"

        self.conn.commit()
        return True, message

    def get_orders_by_shift_id(self, shift_id):
        cursor = self.conn.cursor()

        cursor.execute('SELECT opened_at, closed_at FROM shifts WHERE id = ?', (shift_id,))
        shift_info = cursor.fetchone()

        if not shift_info:
            return []

        opened_at, closed_at = shift_info

        if closed_at:
            cursor.execute('''
                SELECT * FROM orders 
                WHERE created_at >= ? AND created_at <= ?
                ORDER BY created_at DESC
            ''', (opened_at, closed_at))
        else:
            cursor.execute('''
                SELECT * FROM orders 
                WHERE created_at >= ?
                ORDER BY created_at DESC
            ''', (opened_at,))

        return cursor.fetchall()

    def get_next_shift_number(self, month_year=None):
        cursor = self.conn.cursor()

        if not month_year:
            month_year = datetime.now().strftime('%Y-%m')

        cursor.execute('''
            SELECT MAX(shift_number) FROM shifts 
            WHERE month_year = ?
        ''', (month_year,))

        result = cursor.fetchone()
        return (result[0] or 0) + 1

    def create_shift(self, admin_id, month_year=None):
        cursor = self.conn.cursor()

        if not month_year:
            month_year = datetime.now().strftime('%Y-%m')

        shift_number = self.get_next_shift_number(month_year)

        try:
            cursor.execute('''
                INSERT INTO shifts (shift_number, month_year, admin_id, opened_at, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (shift_number, month_year, admin_id, self.get_moscow_time(), 'open'))
            self.conn.commit()
            return shift_number
        except sqlite3.IntegrityError as e:
            print(f"⚠️ Ошибка уникальности: {e}. Пробуем найти максимальный номер...")
            cursor.execute(''' 
                SELECT shift_number FROM shifts 
                WHERE month_year = ?
                ORDER BY shift_number DESC LIMIT 1
            ''', (month_year,))
            result = cursor.fetchone()

            if result:
                shift_number = result[0] + 1
            else:
                shift_number = 1

            print(f"🔄 Пробуем создать смену с номером {shift_number}")

            try:
                cursor.execute('''
                    INSERT INTO shifts (shift_number, month_year, admin_id, opened_at, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (shift_number, month_year, admin_id, self.get_moscow_time(), 'open'))
                self.conn.commit()
                return shift_number
            except sqlite3.IntegrityError as e2:
                print(f"❌ Вторая ошибка уникальности: {e2}")
                cursor.execute('''
                    SELECT shift_number FROM shifts 
                    WHERE month_year = ?
                    ORDER BY shift_number
                ''', (month_year,))
                existing_shifts = cursor.fetchall()
                existing_numbers = [s[0] for s in existing_shifts]

                for i in range(1, 1000):
                    if i not in existing_numbers:
                        shift_number = i
                        break

                cursor.execute('''
                    INSERT INTO shifts (shift_number, month_year, admin_id, opened_at, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (shift_number, month_year, admin_id, self.get_moscow_time(), 'open'))
                self.conn.commit()
                return shift_number

    def get_active_shift(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM shifts 
            WHERE status = 'open' 
            ORDER BY opened_at DESC 
            LIMIT 1
        ''')
        return cursor.fetchone()

    def get_shift_by_number_and_month(self, shift_number, month_year):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM shifts 
            WHERE shift_number = ? AND month_year = ?
        ''', (shift_number, month_year))
        return cursor.fetchone()

    def get_shift_by_number(self, shift_number, month_year=None):
        cursor = self.conn.cursor()

        if month_year:
            cursor.execute('SELECT * FROM shifts WHERE shift_number = ? AND month_year = ?',
                           (shift_number, month_year))
        else:
            cursor.execute('''
                SELECT * FROM shifts 
                WHERE shift_number = ? 
                ORDER BY month_year DESC, opened_at DESC 
                LIMIT 1
            ''', (shift_number,))

        return cursor.fetchone()

    def close_shift(self, shift_number, month_year, total_revenue, total_orders):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE shifts 
            SET closed_at = ?, status = 'closed', total_revenue = ?, total_orders = ?
            WHERE shift_number = ? AND month_year = ?
        ''', (self.get_moscow_time(), total_revenue, total_orders, shift_number, month_year))
        self.conn.commit()

    def save_shift_sales(self, shift_number, month_year, sales_data):
        cursor = self.conn.cursor()

        cursor.execute('SELECT id FROM shifts WHERE shift_number = ? AND month_year = ?',
                       (shift_number, month_year))
        shift = cursor.fetchone()

        if not shift:
            print(f"⚠️ Смена #{shift_number} ({month_year}) не найдена")
            return

        shift_id = shift[0]

        cursor.execute('DELETE FROM shift_sales WHERE shift_id = ?', (shift_id,))

        for item_name, data in sales_data.items():
            cursor.execute('''
                INSERT INTO shift_sales (shift_id, item_name, quantity, total_amount)
                VALUES (?, ?, ?, ?)
            ''', (shift_id, item_name, data['quantity'], data['total_amount']))

        self.conn.commit()

    def get_shift_sales(self, shift_number, month_year):
        cursor = self.conn.cursor()

        shift = self.get_shift_by_number_and_month(shift_number, month_year)
        if not shift:
            return []

        shift_id = shift[0]

        cursor.execute('''
            SELECT item_name, SUM(quantity) as total_quantity, SUM(total_amount) as total_amount
            FROM shift_sales 
            WHERE shift_id = ?
            GROUP BY item_name
            ORDER BY total_amount DESC
        ''', (shift_id,))
        return cursor.fetchall()

    def get_shift_years(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT substr(month_year, 1, 4) as year 
            FROM shifts 
            WHERE status = 'closed'
            ORDER BY year DESC
        ''')
        years = cursor.fetchall()
        return [year[0] for year in years] if years else []

    def get_shift_months(self, year):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT substr(month_year, 6, 2) as month 
            FROM shifts 
            WHERE substr(month_year, 1, 4) = ? AND status = 'closed'
            ORDER BY month DESC
        ''', (year,))
        months = cursor.fetchall()
        return [month[0] for month in months] if months else []

    def get_shifts_by_year_month(self, year, month):
        cursor = self.conn.cursor()
        month_year = f"{year}-{month:02d}" if isinstance(month, int) else f"{year}-{month}"

        cursor.execute('''
            SELECT * FROM shifts 
            WHERE month_year = ? AND status = 'closed'
            ORDER BY shift_number DESC
        ''', (month_year,))
        return cursor.fetchall()

    def get_all_shifts_sorted(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM shifts 
            WHERE status = 'closed'
            ORDER BY month_year DESC, shift_number DESC
        ''')
        return cursor.fetchall()

    def get_shifts_by_period(self, period='all'):
        cursor = self.conn.cursor()

        if period == 'month':
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT * FROM shifts 
                WHERE DATE(opened_at) >= ? AND status = 'closed'
                ORDER BY month_year DESC, shift_number DESC
            ''', (start_date,))
        elif period == 'year':
            start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT * FROM shifts 
                WHERE DATE(opened_at) >= ? AND status = 'closed'
                ORDER BY month_year DESC, shift_number DESC
            ''', (start_date,))
        else:
            cursor.execute('''
                SELECT * FROM shifts 
                WHERE status = 'closed'
                ORDER BY month_year DESC, shift_number DESC
            ''')
        return cursor.fetchall()

    def get_sales_statistics_by_period(self, period):
        cursor = self.conn.cursor()

        if period == 'month':
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT ss.item_name, SUM(ss.quantity) as total_quantity, SUM(ss.total_amount) as total_amount
                FROM shift_sales ss
                JOIN shifts s ON ss.shift_id = s.id
                WHERE DATE(s.opened_at) >= ? AND s.status = 'closed'
                GROUP BY ss.item_name
                ORDER BY total_amount DESC
            ''', (start_date,))
        elif period == 'year':
            start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT ss.item_name, SUM(ss.quantity) as total_quantity, SUM(ss.total_amount) as total_amount
                FROM shift_sales ss
                JOIN shifts s ON ss.shift_id = s.id
                WHERE DATE(s.opened_at) >= ? AND s.status = 'closed'
                GROUP BY ss.item_name
                ORDER BY total_amount DESC
            ''', (start_date,))
        else:
            cursor.execute('''
                SELECT ss.item_name, SUM(ss.quantity) as total_quantity, SUM(ss.total_amount) as total_amount
                FROM shift_sales ss
                JOIN shifts s ON ss.shift_id = s.id
                WHERE s.status = 'closed'
                GROUP BY ss.item_name
                ORDER BY total_amount DESC
            ''')
        return cursor.fetchall()

    def get_total_revenue_by_period(self, period):
        cursor = self.conn.cursor()

        if period == 'month':
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT SUM(total_revenue) FROM shifts 
                WHERE DATE(opened_at) >= ? AND status = 'closed'
            ''', (start_date,))
        elif period == 'year':
            start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT SUM(total_revenue) FROM shifts 
                WHERE DATE(opened_at) >= ? AND status = 'closed'
            ''', (start_date,))
        else:
            cursor.execute('SELECT SUM(total_revenue) FROM shifts WHERE status = "closed"')

        result = cursor.fetchone()
        return result[0] or 0

    def get_sales_statistics_by_year(self, year):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ss.item_name, SUM(ss.quantity) as total_quantity, SUM(ss.total_amount) as total_amount
            FROM shift_sales ss
            JOIN shifts s ON ss.shift_id = s.id
            WHERE substr(s.month_year, 1, 4) = ? AND s.status = 'closed'
            GROUP BY ss.item_name
            ORDER BY total_amount DESC
        ''', (year,))
        return cursor.fetchall()

    def get_total_revenue_by_year(self, year):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT SUM(total_revenue) FROM shifts 
            WHERE substr(month_year, 1, 4) = ? AND status = 'closed'
        ''', (year,))
        result = cursor.fetchone()
        return result[0] or 0

    def get_sales_statistics_by_year_month(self, year, month):
        cursor = self.conn.cursor()
        month_year = f"{year}-{month:02d}" if isinstance(month, int) else f"{year}-{month}"

        cursor.execute('''
            SELECT ss.item_name, SUM(ss.quantity) as total_quantity, SUM(ss.total_amount) as total_amount
            FROM shift_sales ss
            JOIN shifts s ON ss.shift_id = s.id
            WHERE s.month_year = ? AND s.status = 'closed'
            GROUP BY ss.item_name
            ORDER BY total_amount DESC
        ''', (month_year,))
        return cursor.fetchall()

    def get_total_revenue_by_year_month(self, year, month):
        cursor = self.conn.cursor()
        month_year = f"{year}-{month:02d}" if isinstance(month, int) else f"{year}-{month}"

        cursor.execute('''
            SELECT SUM(total_revenue) FROM shifts 
            WHERE month_year = ? AND status = 'closed'
        ''', (month_year,))
        result = cursor.fetchone()
        return result[0] or 0

    def get_all_shifts(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM shifts 
            ORDER BY opened_at DESC
        ''')
        return cursor.fetchall()

    def get_shifts_by_month(self, month_year):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM shifts 
            WHERE month_year = ? 
            ORDER BY shift_number ASC
        ''', (month_year,))
        return cursor.fetchall()

    def get_all_shifts_debug(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, shift_number, month_year, opened_at, closed_at, 
                   total_revenue, total_orders, status
            FROM shifts 
            ORDER BY month_year DESC, shift_number DESC
        ''')
        return cursor.fetchall()

    def get_current_month_year(self):
        return datetime.now().strftime('%Y-%m')

    def get_spent_bonuses_by_shift(self, shift_number, month_year):
        cursor = self.conn.cursor()

        shift = self.get_shift_by_number_and_month(shift_number, month_year)
        if not shift:
            return 0

        shift_id = shift[0]
        opened_at, closed_at = shift[4], shift[5]

        if closed_at:
            cursor.execute('''
                SELECT SUM(amount) 
                FROM transactions 
                WHERE type = 'spend' 
                AND date >= ? AND date <= ?
            ''', (opened_at, closed_at))
        else:
            cursor.execute('''
                SELECT SUM(amount) 
                FROM transactions 
                WHERE type = 'spend' 
                AND date >= ?
            ''', (opened_at,))

        result = cursor.fetchone()
        return result[0] or 0

    def get_spent_bonuses_by_month(self, year, month):
        cursor = self.conn.cursor()

        if isinstance(month, int):
            month_str = f"{year}-{month:02d}"
        else:
            month_str = f"{year}-{month}"

        cursor.execute('''
            SELECT SUM(amount) 
            FROM transactions 
            WHERE type = 'spend' 
            AND strftime('%Y-%m', date) = ?
        ''', (month_str,))

        result = cursor.fetchone()
        return result[0] or 0

    def get_spent_bonuses_by_year(self, year):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT SUM(amount) 
            FROM transactions 
            WHERE type = 'spend' 
            AND strftime('%Y', date) = ?
        ''', (year,))

        result = cursor.fetchone()
        return result[0] or 0

    def get_spent_bonuses_by_period(self, period):
        cursor = self.conn.cursor()

        if period == 'month':
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT SUM(amount) 
                FROM transactions 
                WHERE type = 'spend' 
                AND date >= ?
            ''', (start_date,))
        elif period == 'year':
            start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT SUM(amount) 
                FROM transactions 
                WHERE type = 'spend' 
                AND date >= ?
            ''', (start_date,))
        else:
            cursor.execute('SELECT SUM(amount) FROM transactions WHERE type = "spend"')

        result = cursor.fetchone()
        return result[0] or 0

    def get_payment_statistics_by_month(self, year, month):
        cursor = self.conn.cursor()
        month_year = f"{year}-{month:02d}" if isinstance(month, int) else f"{year}-{month}"

        cursor.execute('''
            SELECT o.payment_method, COUNT(*) as count, SUM(total) as total_amount
            FROM (
                SELECT o.id, o.payment_method, 
                       SUM(oi.price * oi.quantity) as total
                FROM orders o
                LEFT JOIN order_items oi ON o.id = oi.order_id
                WHERE strftime('%Y-%m', o.created_at) = ? 
                    AND o.status = 'closed'
                    AND o.payment_method IS NOT NULL
                GROUP BY o.id
            ) o
            GROUP BY o.payment_method
        ''', (month_year,))

        stats = {}
        for payment_method, count, total_amount in cursor.fetchall():
            stats[payment_method] = {'count': count, 'total_amount': total_amount or 0}

        return stats

    def get_payment_statistics_by_year(self, year):
        cursor = self.conn.cursor()

        cursor.execute('''
            SELECT o.payment_method, COUNT(*) as count, SUM(total) as total_amount
            FROM (
                SELECT o.id, o.payment_method, 
                       SUM(oi.price * oi.quantity) as total
                FROM orders o
                LEFT JOIN order_items oi ON o.id = oi.order_id
                WHERE strftime('%Y', o.created_at) = ? 
                    AND o.status = 'closed'
                    AND o.payment_method IS NOT NULL
                GROUP BY o.id
            ) o
            GROUP BY o.payment_method
        ''', (year,))

        stats = {}
        for payment_method, count, total_amount in cursor.fetchall():
            stats[payment_method] = {'count': count, 'total_amount': total_amount or 0}

        return stats

    def add_payment_method_column(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'payment_method' not in columns:
            cursor.execute('ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT NULL')
            self.conn.commit()
            return True
        return False

    def update_order_payment_method(self, order_id, payment_method):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE orders SET payment_method = ? WHERE id = ?
        ''', (payment_method, order_id))
        self.conn.commit()

    def get_payment_statistics_by_shift(self, shift_number, month_year):
        cursor = self.conn.cursor()

        shift = self.get_shift_by_number_and_month(shift_number, month_year)
        if not shift:
            return {}

        shift_id = shift[0]
        opened_at, closed_at = shift[4], shift[5]

        if closed_at:
            cursor.execute('''
                SELECT o.payment_method, COUNT(*) as count, SUM(total) as total_amount
                FROM (
                    SELECT o.id, o.payment_method, 
                           SUM(oi.price * oi.quantity) as total
                    FROM orders o
                    LEFT JOIN order_items oi ON o.id = oi.order_id
                    WHERE o.created_at >= ? AND o.created_at <= ? 
                        AND o.status = 'closed'
                        AND o.payment_method IS NOT NULL
                    GROUP BY o.id
                ) o
                GROUP BY o.payment_method
            ''', (opened_at, closed_at))
        else:
            cursor.execute('''
                SELECT o.payment_method, COUNT(*) as count, SUM(total) as total_amount
                FROM (
                    SELECT o.id, o.payment_method, 
                           SUM(oi.price * oi.quantity) as total
                    FROM orders o
                    LEFT JOIN order_items oi ON o.id = oi.order_id
                    WHERE o.created_at >= ? 
                        AND o.status = 'closed'
                        AND o.payment_method IS NOT NULL
                    GROUP BY o.id
                ) o
                GROUP BY o.payment_method
            ''', (opened_at,))

        stats = {}
        for payment_method, count, total_amount in cursor.fetchall():
            stats[payment_method] = {'count': count, 'total_amount': total_amount or 0}

        return stats

    def get_payment_statistics_by_period(self, period):
        cursor = self.conn.cursor()

        if period == 'month':
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT o.payment_method, COUNT(*) as count, SUM(total) as total_amount
                FROM (
                    SELECT o.id, o.payment_method, 
                           SUM(oi.price * oi.quantity) as total
                    FROM orders o
                    LEFT JOIN order_items oi ON o.id = oi.order_id
                    WHERE o.created_at >= ? 
                        AND o.status = 'closed'
                        AND o.payment_method IS NOT NULL
                    GROUP BY o.id
                ) o
                GROUP BY o.payment_method
            ''', (start_date,))
        elif period == 'year':
            start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT o.payment_method, COUNT(*) as count, SUM(total) as total_amount
                FROM (
                    SELECT o.id, o.payment_method, 
                           SUM(oi.price * oi.quantity) as total
                    FROM orders o
                    LEFT JOIN order_items oi ON o.id = oi.order_id
                    WHERE o.created_at >= ? 
                        AND o.status = 'closed'
                        AND o.payment_method IS NOT NULL
                    GROUP BY o.id
                ) o
                GROUP BY o.payment_method
            ''', (start_date,))
        else:
            cursor.execute('''
                SELECT o.payment_method, COUNT(*) as count, SUM(total) as total_amount
                FROM (
                    SELECT o.id, o.payment_method, 
                           SUM(oi.price * oi.quantity) as total
                    FROM orders o
                    LEFT JOIN order_items oi ON o.id = oi.order_id
                    WHERE o.status = 'closed'
                        AND o.payment_method IS NOT NULL
                    GROUP BY o.id
                ) o
                GROUP BY o.payment_method
            ''')

        stats = {}
        for payment_method, count, total_amount in cursor.fetchall():
            stats[payment_method] = {'count': count, 'total_amount': total_amount or 0}

        return stats

    # ========== МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ МЕНЮ ==========

    def get_all_menu_categories(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT category FROM menu_items WHERE is_active = TRUE ORDER BY category')
        categories = cursor.fetchall()
        return [category[0] for category in categories] if categories else []

    def get_menu_items_by_category(self, category):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, name, price, category, is_active 
            FROM menu_items 
            WHERE category = ? AND is_active = TRUE 
            ORDER BY name
        ''', (category,))
        return cursor.fetchall()

    def get_all_menu_items(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, name, price, category, is_active 
            FROM menu_items 
            ORDER BY category, name
        ''')
        return cursor.fetchall()

    def get_menu_item_by_id(self, item_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, name, price, category, is_active FROM menu_items WHERE id = ?', (item_id,))
        return cursor.fetchone()

    def get_menu_item_by_name(self, name):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, name, price, category, is_active FROM menu_items WHERE name = ?', (name,))
        return cursor.fetchone()

    def add_menu_item(self, name, price, category):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO menu_items (name, price, category, is_active) VALUES (?, ?, ?, ?)',
                (name, price, category, True)
            )
            self.conn.commit()
            return True, "✅ Позиция успешно добавлена"
        except sqlite3.IntegrityError:
            return False, "❌ Позиция с таким названием уже существует"
        except Exception as e:
            return False, f"❌ Ошибка при добавлении: {str(e)}"

    def update_menu_item(self, item_id, name, price, category):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT id FROM menu_items WHERE name = ? AND id != ?', (name, item_id))
            if cursor.fetchone():
                return False, "❌ Позиция с таким названием уже существует"

            cursor.execute(
                'UPDATE menu_items SET name = ?, price = ?, category = ? WHERE id = ?',
                (name, price, category, item_id)
            )
            self.conn.commit()
            return True, "✅ Позиция успешно обновлена"
        except Exception as e:
            return False, f"❌ Ошибка при обновлении: {str(e)}"

    def delete_menu_item(self, item_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute('UPDATE menu_items SET is_active = FALSE WHERE id = ?', (item_id,))
            self.conn.commit()
            return True, "✅ Позиция успешно удалена"
        except Exception as e:
            return False, f"❌ Ошибка при удалении: {str(e)}"

    def restore_menu_item(self, item_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute('UPDATE menu_items SET is_active = TRUE WHERE id = ?', (item_id,))
            self.conn.commit()
            return True, "✅ Позиция успешно восстановлена"
        except Exception as e:
            return False, f"❌ Ошибка при восстановлении: {str(e)}"

    def get_inactive_menu_items(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, name, price, category, is_active 
            FROM menu_items 
            WHERE is_active = FALSE 
            ORDER BY category, name
        ''')
        return cursor.fetchall()
