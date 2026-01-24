# check_all_menu_items.py
from database import Database


def check_all_menu_items():
    """Проверить все позиции в меню"""
    db = Database()
    cursor = db.conn.cursor()

    print("📋 ВСЕ ПОЗИЦИИ В БАЗЕ ДАННЫХ:")
    print("=" * 50)

    cursor.execute("SELECT name, price, category FROM menu_items ORDER BY category, name")
    all_items = cursor.fetchall()

    if not all_items:
        print("❌ База данных пуста!")
        return

    current_category = ""
    for name, price, category in all_items:
        if category != current_category:
            current_category = category
            print(f"\n📁 КАТЕГОРИЯ: {category}")
            print("-" * 30)
        print(f"  • {name} - {price}₽")

    print(f"\n📊 ИТОГО: {len(all_items)} позиций")


def find_missing_hookahs():
    """Найти отсутствующие кальяны"""
    db = Database()
    cursor = db.conn.cursor()

    print("\n🔍 ПОИСК ОТСУТСТВУЮЩИХ КАЛЬЯНОВ:")
    print("=" * 40)

    expected_hookahs = ['Пенсионный', 'Стандарт', 'Премиум', 'Фруктовая чаша', 'Сигарный', 'Парфюм']

    cursor.execute("SELECT name FROM menu_items WHERE name IN ({})".format(
        ','.join('?' for _ in expected_hookahs)
    ), expected_hookahs)

    existing = [row[0] for row in cursor.fetchall()]
    missing = set(expected_hookahs) - set(existing)

    print(f"✅ В базе: {existing}")
    print(f"❌ Отсутствуют: {missing}")

    return missing


if __name__ == "__main__":
    check_all_menu_items()
    missing = find_missing_hookahs()