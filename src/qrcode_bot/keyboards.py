from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Generate QR"), KeyboardButton(text="📷 Decode QR")],
            [KeyboardButton(text="📶 WiFi QR"), KeyboardButton(text="🏷️ Logo QR")],
            [KeyboardButton(text="🎨 Style")],
            [KeyboardButton(text="💰 Donate")],
            [KeyboardButton(text="ℹ️ Help"), KeyboardButton(text="🔒 Privacy")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Send text to generate QR...",
    )


def wifi_security_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="WPA/WPA2", callback_data="wifi:wpa"),
                InlineKeyboardButton(text="WEP", callback_data="wifi:wep"),
                InlineKeyboardButton(text="None", callback_data="wifi:nopass"),
            ],
        ]
    )
