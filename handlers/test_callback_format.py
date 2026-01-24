# test_callback_format.py
def test_callback_format():
    """Тест формата callback_data"""
    test_cases = [
        "edit_order_123",
        "edit_order_1",
        "edit_order_100",
        "edit_order_",
        "edit_order_abc"
    ]

    for callback in test_cases:
        print(f"Testing: '{callback}'")

        if callback.startswith("edit_order_"):
            try:
                order_id = int(callback.replace("edit_order_", ""))
                print(f"✅ Valid: order_id = {order_id}")
            except ValueError:
                print(f"❌ Invalid: cannot extract order_id")
        else:
            print(f"❌ Not an edit_order callback")

    # Проверяем создание кнопки
    from telegram import InlineKeyboardButton

    order_id = 123
    button = InlineKeyboardButton(
        "✏️ Редактировать заказ",
        callback_data=f"edit_order_{order_id}"
    )

    print(f"\n✅ Button created: {button.callback_data}")


if __name__ == "__main__":
    test_callback_format()