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
            [KeyboardButton(text="📋 More Types"), KeyboardButton(text="🖼️ Frame")],
            [KeyboardButton(text="🎨 Style"), KeyboardButton(text="💰 Donate")],
            [KeyboardButton(text="ℹ️ Help"), KeyboardButton(text="🔒 Privacy")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Send text to generate QR...",
    )


def qr_result_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown below every generated QR code."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎨 Style", callback_data="qr:style"),
            InlineKeyboardButton(text="🖼 Frame", callback_data="qr:frame"),
        ],
        [
            InlineKeyboardButton(text="➕ Logo", callback_data="qr:logo"),
            InlineKeyboardButton(text="📤 Sticker", callback_data="qr:sticker"),
        ],
        [
            InlineKeyboardButton(text="🔄 New QR", callback_data="qr:new"),
        ],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button for FSM flows."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])


def decode_result_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown below decoded QR results."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Generate QR from this", callback_data="decode:gen")],
        [InlineKeyboardButton(text="📋 Copy text", callback_data="decode:copy")],
    ])


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
