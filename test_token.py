import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Проверяем загрузку токена
BOT_TOKEN = os.getenv('BOT_TOKEN')

print(f"Токен из .env: {BOT_TOKEN}")
print(f"Тип токена: {type(BOT_TOKEN)}")
print(f"Длина токена: {len(BOT_TOKEN) if BOT_TOKEN else 0}")

if not BOT_TOKEN:
    print("❌ Токен не загружен!")
    print("Текущая рабочая директория:", os.getcwd())
    print("Файлы в директории:", os.listdir('.'))
else:
    print("✅ Токен успешно загружен!")