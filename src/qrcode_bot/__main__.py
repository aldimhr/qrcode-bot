import asyncio
import logging

from qrcode_bot.bot import create_bot
from qrcode_bot.config import load_settings


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    settings = load_settings()
    bot, dp = create_bot(settings)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
