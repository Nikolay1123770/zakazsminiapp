import sqlite3
from datetime import datetime, timedelta
import pytz


def migrate_database():
    db_name = 'loyalty_bot.db'

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        print("🔄 Начинаем миграцию временных данных...")

        # Функция для конвертации UTC в московское время
        def convert_utc_to_moscow(utc_time_str):
            try:
                utc_time = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S')
                moscow_time = utc_time + timedelta(hours=3)
                return moscow_time.strftime('%Y-%m-%d %H:%M:%S')
            except:
                return utc_time_str

        # Мигрируем таблицу users
        print("📊 Мигрируем таблицу users...")
        cursor.execute("SELECT id, registration_date FROM users")
        users = cursor.fetchall()

        for user_id, reg_date in users:
            if reg_date:
                new_date = convert_utc_to_moscow(reg_date)
                cursor.execute("UPDATE users SET registration_date = ? WHERE id = ?", (new_date, user_id))

        # Мигрируем таблицу transactions
        print("📊 Мигрируем таблицу transactions...")
        cursor.execute("SELECT id, date FROM transactions")
        transactions = cursor.fetchall()

        for trans_id, trans_date in transactions:
            if trans_date:
                new_date = convert_utc_to_moscow(trans_date)
                cursor.execute("UPDATE transactions SET date = ? WHERE id = ?", (new_date, trans_id))

        # Мигрируем таблицу bookings
        print("📊 Мигрируем таблицу bookings...")
        cursor.execute("SELECT id, created_at FROM bookings")
        bookings = cursor.fetchall()

        for booking_id, created_at in bookings:
            if created_at:
                new_date = convert_utc_to_moscow(created_at)
                cursor.execute("UPDATE bookings SET created_at = ? WHERE id = ?", (new_date, booking_id))

        # Мигрируем таблицу bonus_requests
        print("📊 Мигрируем таблицу bonus_requests...")
        cursor.execute("SELECT id, created_at FROM bonus_requests")
        requests = cursor.fetchall()

        for request_id, created_at in requests:
            if created_at:
                new_date = convert_utc_to_moscow(created_at)
                cursor.execute("UPDATE bonus_requests SET created_at = ? WHERE id = ?", (new_date, request_id))

        # Мигрируем таблицу referrals
        print("📊 Мигрируем таблицу referrals...")
        cursor.execute("SELECT id, created_at FROM referrals")
        referrals = cursor.fetchall()

        for referral_id, created_at in referrals:
            if created_at:
                new_date = convert_utc_to_moscow(created_at)
                cursor.execute("UPDATE referrals SET created_at = ? WHERE id = ?", (new_date, referral_id))

        conn.commit()
        print("✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    migrate_database()