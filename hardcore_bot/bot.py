from __future__ import annotations

import asyncio
import os

from .formatting import format_digest, format_products, product_title
from .i18n import t
from .models import WatchRule
from .storage import connect, init_db, list_products, add_watch, ensure_user, set_user_lang, count_observations, latest_observations

DB_PATH = os.getenv("HARDCORE_BOT_DB", "data/hardcore.sqlite3")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def require_aiogram():
    try:
        from aiogram import Bot, Dispatcher, types
        from aiogram.filters import Command
    except ImportError as exc:
        raise SystemExit("aiogram is not installed. Run: python -m pip install -e .") from exc
    return Bot, Dispatcher, types, Command


async def run() -> None:
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required for live Telegram mode. Core CLI/tests work without it.")
    Bot, Dispatcher, types, Command = require_aiogram()
    bot = Bot(TOKEN)
    dp = Dispatcher()
    con = connect(DB_PATH)
    init_db(con)

    @dp.message(Command("start"))
    async def start(message: types.Message):
        ensure_user(con, message.from_user.id, "uk")
        await message.answer(t("welcome", "uk") + "\n\n/lang_uk /lang_ru\n/products\n/digest")

    @dp.message(Command("lang_uk"))
    async def lang_uk(message: types.Message):
        set_user_lang(con, message.from_user.id, "uk")
        await message.answer(t("language_set", "uk"))

    @dp.message(Command("lang_ru"))
    async def lang_ru(message: types.Message):
        set_user_lang(con, message.from_user.id, "ru")
        await message.answer(t("language_set", "ru"))

    @dp.message(Command("products"))
    async def products(message: types.Message):
        await message.answer(format_products(list_products(con), "uk"))

    @dp.message(Command("digest"))
    async def digest(message: types.Message):
        await message.answer(format_digest(list_products(con), latest_observations(con), "uk"))

    @dp.message(Command("watch"))
    async def watch(message: types.Message):
        parts = (message.text or "").split(maxsplit=1)
        products = {p.id: p for p in list_products(con)}
        if len(parts) < 2 or parts[1].strip() not in products:
            await message.answer(t("unknown_product", "uk"))
            return
        product_id = parts[1].strip()
        add_watch(con, WatchRule(user_id=message.from_user.id, product_id=product_id))
        await message.answer(t("watch_added", "uk", product=product_title(products[product_id], "uk")))

    @dp.message(Command("status"))
    async def status(message: types.Message):
        await message.answer(t("status", "uk", products=len(list_products(con)), observations=count_observations(con)))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
