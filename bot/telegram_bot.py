import asyncio
import json
import logging
import os
import sys
from datetime import datetime
import httpx

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    UserProfilePhotos,
)
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
API_URL = "http://localhost:8000"

dp = Dispatcher()

user_data = {}


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Welcome message to the user when pressing the start command"""

    await message.answer(f"Hello, {message.from_user.full_name}!")


@dp.message(Command("open"))
async def command_open_app_handler(message: Message) -> None:
    """Displaying the open button of telegram mini app when entering the open command"""

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Open",
                    web_app=WebAppInfo(
                        url="https://0997-117-121-211-107.ngrok-free.app"
                    ),
                )
            ]
        ]
    )
    await message.answer("Welcome to the app:", reply_markup=markup)


@dp.message(Command("users"))
async def handle_save_or_get_user_data(message: Message) -> None:
    """Creating and updating user data with data output"""

    auth_date = int(datetime.now().timestamp())  # temporary field

    user_info = {
        "tg_id": str(message.from_user.id),
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "username": message.from_user.username,
        "is_premium": message.from_user.is_premium,
        "tg_image": None,
        "auth_date": auth_date,
    }

    bot = message.bot
    user_photos: UserProfilePhotos = await bot.get_user_profile_photos(
        message.from_user.id
    )

    if user_photos.total_count > 0:
        photo_file_id = user_photos.photos[0][0].file_id
        photo_info = await bot.get_file(photo_file_id)
        avatar_url = f"https://api.telegram.org/file/bot{TOKEN}/{photo_info.file_path}"
        user_info["tg_image"] = avatar_url

    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(f"{API_URL}/users", json=user_info)
            if response.status_code == 200:
                user_data = response.json()
                user_json = json.dumps(user_data, indent=2)
                await message.answer(
                    f"<pre>{user_json}</pre>", parse_mode=ParseMode.HTML
                )
            else:
                await message.answer(
                    f"Failed to save or get user data. Status code: {response.status_code}."
                    f"Response text: {response.text}"
                )
        except Exception as e:
            logging.error(f"Error sending user data to server: {e}", exc_info=True)
            await message.answer("An error occurred while saving or getting user data.")


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
