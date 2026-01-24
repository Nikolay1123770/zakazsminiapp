import sqlite3
import os


def update_database():
    db_name = 'loyalty_bot.db'

    if not os.path.exists(db_name):
        print("❌ База данных не найдена!")
        return

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        # Проверяем наличие колонки referred_by
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'referred_by' not in columns:
            print("🔄 Добавляем колонку referred_by в таблицу users...")
            cursor.execute('ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL')
            print("✅ Колонка referred_by добавлена")
        else:
            print("✅ Колонка referred_by уже существует")

        # Проверяем наличие таблицы referrals
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='referrals'")
        if not cursor.fetchone():
            print("🔄 Создаем таблицу referrals...")
            cursor.execute('''
                CREATE TABLE referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER UNIQUE,
                    bonus_awarded BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users (id),
                    FOREIGN KEY (referred_id) REFERENCES users (id)
                )
            ''')
            print("✅ Таблица referrals создана")
        else:
            print("✅ Таблица referrals уже существует")

        conn.commit()
        print("🎉 База данных успешно обновлена!")

    except Exception as e:
        print(f"❌ Ошибка при обновлении базы данных: {e}")
    finally:
        conn.close()


if __name__ == '__main__':
    update_database()