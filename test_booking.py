# test_booking.py
import requests
import json
import sys

def test_booking():
    """Тестирование создания бронирования"""
    url = "http://localhost:3000/api/booking/create"
    
    # Тестовые данные
    booking_data = {
        "name": "Иван Тестовый",
        "phone": "+79991234567",
        "date": "2024-01-25",
        "time": "19:00",
        "guests": "4",
        "comment": "Тестовое бронирование из скрипта",
        "source": "miniapp",
        "user_id": 1  # ID тестового пользователя
    }
    
    print("🧪 Тестирование создания бронирования...")
    print(f"📤 Данные: {json.dumps(booking_data, ensure_ascii=False)}")
    
    try:
        response = requests.post(
            url,
            json=booking_data,
            headers={
                'Content-Type': 'application/json',
                # Для теста можно добавить заглушку для авторизации
                'X-Telegram-Init-Data': 'test_auth'
            },
            timeout=10
        )
        
        print(f"📥 Ответ: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Успех! Booking ID: {result.get('booking_id')}")
            print(f"📊 Статус: {result.get('status')}")
            print(f"💬 Сообщение: {result.get('message')}")
            
            # Проверяем в базе данных
            import sqlite3
            conn = sqlite3.connect('vovsetyagskie.db')
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM bookings ORDER BY id DESC LIMIT 1')
            last_booking = cursor.fetchone()
            conn.close()
            
            if last_booking:
                print(f"\n📊 Проверка базы данных:")
                print(f"   ID: {last_booking[0]}")
                print(f"   Клиент: {last_booking[8]}")
                print(f"   Телефон: {last_booking[9]}")
                print(f"   Дата: {last_booking[2]}")
                print(f"   Статус: {last_booking[6]}")
                
        else:
            print(f"❌ Ошибка: {response.text}")
            
    except Exception as e:
        print(f"❌ Исключение: {str(e)}")

if __name__ == "__main__":
    test_booking()
