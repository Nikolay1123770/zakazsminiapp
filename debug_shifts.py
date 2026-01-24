# debug_shifts.py
from database import Database


def debug_shifts():
    """Отладочная функция для проверки смен в базе данных"""
    db = Database()

    print("🔍 Проверка смен в базе данных...")

    # Проверить все смены
    cursor = db.conn.cursor()
    cursor.execute('SELECT shift_number, opened_at, closed_at, status FROM shifts ORDER BY opened_at DESC')
    shifts = cursor.fetchall()

    print(f"\n📊 Всего смен в базе: {len(shifts)}")

    for shift in shifts:
        shift_number, opened_at, closed_at, status = shift
        print(f"  Смена #{shift_number}: {opened_at} - {closed_at} [{status}]")

    # Проверить годы
    years = db.get_shift_years()
    print(f"\n📅 Годы в базе: {years}")

    # Проверить смены по статусу
    cursor.execute('SELECT status, COUNT(*) FROM shifts GROUP BY status')
    status_stats = cursor.fetchall()
    print(f"\n📈 Статистика по статусам:")
    for status, count in status_stats:
        print(f"  {status}: {count} смен")

    if not shifts:
        print("\n❌ В базе нет ни одной смены!")
        print("   Для тестирования статистики нужно:")
        print("   1. Открыть смену через бота")
        print("   2. Создать тестовый заказ")
        print("   3. Закрыть заказ")
        print("   4. Закрыть смену")


if __name__ == "__main__":
    debug_shifts()