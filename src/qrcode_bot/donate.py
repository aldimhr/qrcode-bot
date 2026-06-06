from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot, types
from aiogram.types import LabeledPrice

logger = logging.getLogger(__name__)

DONATION_AMOUNTS = [
    {"label": "⭐ 25 Stars", "amount": 25},
    {"label": "⭐ 50 Stars", "amount": 50},
    {"label": "⭐ 100 Stars", "amount": 100},
    {"label": "⭐ 250 Stars", "amount": 250},
    {"label": "⭐ 500 Stars", "amount": 500},
]

DONATE_TEXT = (
    "💝 *Support QR Code Bot*\n\n"
    "If you find this bot useful, consider supporting it with Telegram Stars!\n\n"
    "Every donation helps keep the bot running and improving."
    "\n\n📢 @x0projects"
)


def donation_keyboard() -> types.InlineKeyboardMarkup:
    buttons = [
        [types.InlineKeyboardButton(text=d["label"], callback_data=f"donate:{d['amount']}")]
        for d in DONATION_AMOUNTS
    ]
    buttons.append([types.InlineKeyboardButton(text="💝 Custom Amount", callback_data="donate:custom")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_invoice(bot: Bot, chat_id: int, amount: int, reply_to: int | None = None) -> bool:
    try:
        await bot.send_invoice(
            chat_id=chat_id,
            title=f"{amount} Stars Donation",
            description=f"Support QR Code Bot with {amount} Telegram Stars. Thank you! 💙",
            payload=f"donate:{amount}:{int(datetime.now(timezone.utc).timestamp())}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{amount} Stars", amount=amount)],
            reply_to_message_id=reply_to,
        )
        return True
    except Exception as e:
        logger.error("Invoice failed: %s", e)
        return False
