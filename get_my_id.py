import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN') or "8548648991:AAEwYfIevnbCHMxuJ8F_3ISfXbshbjtlpzw"


async def get_my_id():
    bot = Bot(token=BOT_TOKEN)

    # Получаем информацию о боте
    me = await bot.get_me()
    print(f"🤖 Бот: {me.first_name} (@{me.username})")

    # Получаем последние обновления
    updates = await bot.get_updates()

    if updates:
        print("\n📋 Найдены обновления:")
        for i, update in enumerate(updates[-5:]):  # Последние 5 обновлений
            if update.message:
                user = update.message.from_user
                print(f"{i + 1}. ID: {user.id} | Имя: {user.first_name} | Сообщение: {update.message.text}")
    else:
        print("\n📭 Нет обновлений.")
        print("💡 Отправьте любое сообщение боту и запустите скрипт снова")

    print(f"\n⚠️ ЗАМЕНИТЕ в config.py: ADMIN_IDS = [ВАШ_ID]")


if __name__ == '__main__':
    print("🔍 Получаю информацию о пользователях...")

    asyncio.run(get_my_id())


