# test_database_methods.py
from database import Database


def test_database_methods():
    """Тестирование методов базы данных"""
    print("🔍 Тестирование методов базы данных...")

    db = Database()

    # Тестируем get_shift_years
    print("\n1. Тестируем get_shift_years():")
    years = db.get_shift_years()
    print(f"   Результат: {years}")

    # Тестируем get_shift_months
    print("\n2. Тестируем get_shift_months('2024'):")
    months = db.get_shift_months('2024')
    print(f"   Результат: {months}")

    # Тестируем get_shifts_by_year_month
    print("\n3. Тестируем get_shifts_by_year_month('2024', '11'):")
    shifts = db.get_shifts_by_year_month('2024', '11')
    print(f"   Найдено смен: {len(shifts)}")

    # Проверим все смены в базе
    print("\n4. Все смены в базе:")
    cursor = db.conn.cursor()
    cursor.execute('SELECT shift_number, opened_at, closed_at, status FROM shifts ORDER BY opened_at DESC')
    all_shifts = cursor.fetchall()

    for shift in all_shifts:
        shift_number, opened_at, closed_at, status = shift
        print(f"   Смена #{shift_number}: {opened_at} - {closed_at} [{status}]")

    if not all_shifts:
        print("   ❌ В базе нет смен!")
        print("\n   Для тестирования нужно:")
        print("   1. Открыть смену через бота")
        print("   2. Создать тестовый заказ")
        print("   3. Закрыть заказ")
        print("   4. Закрыть смену")


if __name__ == "__main__":
    test_database_methods()