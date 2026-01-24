import sqlite3
from config import DB_NAME


def check_categories():
    """Проверить категории для конкретных позиций"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Проверяем категории для нужных позиций
    items_to_check = ["Марокканский", "Голубика", "Смородиновый", "Клубничный", "Пиво/Энергетик"]

    print("📋 Проверка категорий в базе данных:")
    print("-" * 40)

    for item_name in items_to_check:
        cursor.execute('SELECT name, price, category FROM menu_items WHERE name = ?', (item_name,))
        result = cursor.fetchone()

        if result:
            name, price, category = result
            print(f"✅ {name}: {category} - {price}₽")
        else:
            print(f"❌ {item_name}: не найдено в базе данных")

    print("-" * 40)
    conn.close()


if __name__ == "__main__":
    check_categories()