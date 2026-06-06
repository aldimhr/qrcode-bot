from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, InlineQueryResultCachedPhoto, LabeledPrice

from qrcode_bot.config import Settings
from qrcode_bot.core import decode_qr, generate_qr, generate_qr_wifi, parse_hex_color
from qrcode_bot.donate import DONATE_TEXT, donation_keyboard, send_invoice
from qrcode_bot.keyboards import main_reply_keyboard
from qrcode_bot.stats import get_stats, record_decode, record_generation, record_inline, record_wifi

logger = logging.getLogger(__name__)

CHANNEL_FOOTER = "\n\n📢 @x0projects"

# Per-user style preferences (in-memory, resets on restart)
user_styles: dict[int, dict] = {}


class WiFiStates(StatesGroup):
    waiting_ssid = State()
    waiting_password = State()


def get_user_style(user_id: int, settings: Settings) -> dict:
    style = user_styles.get(user_id, {})
    return {
        "fg_color": style.get("fg", settings.qr_default_fg),
        "bg_color": style.get("bg", settings.qr_default_bg),
        "box_size": settings.qr_box_size,
        "border": settings.qr_border,
    }


def create_router(settings: Settings) -> Router:
    router = Router()

    # --- /start ---
    @router.message(CommandStart())
    async def cmd_start(message: types.Message):
        text = (
            "👋 *Welcome to QR Code Bot!*\n\n"
            "I can generate and decode QR codes instantly.\n\n"
            "*What I can do:*\n"
            "• Send me any *text or URL* → I'll generate a QR code\n"
            "• Send me a *photo with a QR code* → I'll decode it\n"
            "• Use /wifi to create a WiFi QR code\n"
            "• Use /style to customize QR colors\n"
            "• Use me inline: `@botname your text`\n\n"
            "Just send me something to get started!"
            f"{CHANNEL_FOOTER}"
        )
        await message.answer(text, parse_mode="Markdown", reply_markup=main_reply_keyboard())

    # --- /help ---
    @router.message(Command("help"))
    async def cmd_help(message: types.Message):
        text = (
            "📖 *How to use QR Code Bot*\n\n"
            "*Generate QR:*\n"
            "Send any text, URL, or message — I'll turn it into a QR code.\n\n"
            "*Decode QR:*\n"
            "Send me a photo or image containing a QR code.\n\n"
            "*WiFi QR:*\n"
            "Tap 📶 WiFi QR or use /wifi — I'll guide you.\n\n"
            "*Custom Colors:*\n"
            "Tap 🎨 Style or use /style `#FF0000 #FFFFFF`\n\n"
            "*Inline Mode:*\n"
            "In any chat, type `@botname your-text-here`\n\n"
            "*Supported formats:*\n"
            "Text, URLs, email addresses, phone numbers, WiFi configs, and more."
            f"{CHANNEL_FOOTER}"
        )
        await message.answer(text, parse_mode="Markdown")

    # --- /privacy ---
    @router.message(Command("privacy"))
    async def cmd_privacy(message: types.Message):
        text = (
            "🔒 *Privacy Policy*\n\n"
            "• Your images and text are processed in-memory and *never stored*.\n"
            "• Generated QR codes are sent directly to you and deleted immediately.\n"
            "• No data is shared with third parties.\n"
            "• Style preferences reset when the bot restarts."
        )
        await message.answer(text, parse_mode="Markdown")

    # --- /style ---
    @router.message(Command("style"))
    async def cmd_style(message: types.Message):
        parts = message.text.split(maxsplit=2)
        if len(parts) >= 3:
            fg = parse_hex_color(parts[1])
            bg = parse_hex_color(parts[2])
            if fg and bg:
                user_styles[message.from_user.id] = {"fg": fg, "bg": bg}
                await message.answer(
                    f"🎨 *Style updated!*\n\nForeground: `{fg}`\nBackground: `{bg}`\n\n"
                    "Send any text to see your new style in action.",
                    parse_mode="Markdown",
                )
                return
        await message.answer(
            "🎨 *Set QR Colors*\n\n"
            "Usage: `/style #FF0000 #FFFFFF`\n"
            "First color = QR dots, second = background.",
            parse_mode="Markdown",
        )

    # --- /stats (admin only) ---
    @router.message(Command("stats"))
    async def cmd_stats(message: types.Message):
        if message.from_user.id not in settings.admin_ids:
            return
        s = get_stats()
        uptime_hours = (time.time() - s.get("started_at", time.time())) / 3600
        text = (
            "📊 *Bot Statistics*\n\n"
            f"🖼 QR Generated: {s.get('generated', 0)}\n"
            f"📷 QR Decoded: {s.get('decoded', 0)}\n"
            f"📶 WiFi QR: {s.get('wifi', 0)}\n"
            f"📱 Inline Uses: {s.get('inline', 0)}\n"
            f"👥 Unique Users: {len(s.get('users', []))}\n"
            f"⏱ Uptime: {uptime_hours:.1f}h"
        )
        await message.answer(text, parse_mode="Markdown")

    # --- /donate ---
    @router.message(Command("donate"))
    async def cmd_donate(message: types.Message):
        parts = message.text.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[1])
                if 1 <= amount <= 10000:
                    ok = await send_invoice(message.bot, message.chat.id, amount, message.message_id)
                    if not ok:
                        await message.answer("❌ Failed to create invoice.")
                    return
            except ValueError:
                pass
        await message.answer(DONATE_TEXT, reply_markup=donation_keyboard(), parse_mode="Markdown")

    # --- /wifi ---
    @router.message(Command("wifi"))
    async def cmd_wifi(message: types.Message, state: FSMContext):
        await state.set_state(WiFiStates.waiting_ssid)
        await message.answer(
            "📶 *WiFi QR Generator*\n\nStep 1/2: What is the *WiFi network name (SSID)*?",
            parse_mode="Markdown",
        )

    @router.message(WiFiStates.waiting_ssid)
    async def wifi_ssid(message: types.Message, state: FSMContext):
        ssid = message.text.strip()
        if len(ssid) > 100:
            await message.answer("❌ SSID is too long. Please try again.")
            return
        await state.update_data(ssid=ssid)
        await state.set_state(WiFiStates.waiting_password)
        await message.answer(
            f"📶 Network: `{ssid}`\n\nStep 2/2: What is the *password*?\nSend `none` for open networks.",
            parse_mode="Markdown",
        )

    @router.message(WiFiStates.waiting_password)
    async def wifi_password(message: types.Message, state: FSMContext):
        data = await state.get_data()
        ssid = data["ssid"]
        password = message.text.strip()
        security = "WPA"

        if password.lower() == "none":
            password = ""
            security = "NOPASS"

        try:
            png_bytes = generate_qr_wifi(ssid, password, security)
        except Exception:
            await message.answer("❌ Failed to generate WiFi QR. Please try again.")
            await state.clear()
            return

        photo = BufferedInputFile(png_bytes, filename="wifi_qr.png")
        security_label = "Open" if security == "NOPASS" else security
        await message.answer_photo(
            photo,
            caption=(
                f"📶 *WiFi QR Code*\n\nNetwork: `{ssid}`\nSecurity: {security_label}\n\n"
                f"_Scan this QR to connect!_{CHANNEL_FOOTER}"
            ),
            parse_mode="Markdown",
            reply_markup=main_reply_keyboard(),
        )
        record_wifi(message.from_user.id)
        await state.clear()

    # --- Handle photos (decode QR) ---
    @router.message(F.photo)
    async def handle_photo(message: types.Message, bot: Bot):
        await _decode_image(message, message.photo[-1].file_id, bot)

    # --- Handle documents (decode QR from image docs) ---
    @router.message(F.document)
    async def handle_document(message: types.Message, bot: Bot):
        doc = message.document
        if not doc.mime_type or not doc.mime_type.startswith("image/"):
            await message.answer("📷 Please send an image file containing a QR code.")
            return
        await _decode_image(message, doc.file_id, bot)

    # --- Handle text (generate QR) ---
    @router.message(F.text)
    async def handle_text(message: types.Message):
        text = message.text.strip()
        # Skip keyboard button labels
        if text in ("📱 Generate QR", "📷 Decode QR", "📶 WiFi QR", "🎨 Style", "ℹ️ Help", "🔒 Privacy", "💰 Donate"):
            if text == "📱 Generate QR":
                await message.answer("✏️ Send me any text or URL to generate a QR code.")
            elif text == "📷 Decode QR":
                await message.answer("📷 Send me a photo containing a QR code.")
            elif text == "🎨 Style":
                await message.answer(
                    "🎨 *Set QR Colors*\n\nUsage: `/style #FF0000 #FFFFFF`",
                    parse_mode="Markdown",
                )
            elif text == "💰 Donate":
                await message.answer(DONATE_TEXT, reply_markup=donation_keyboard(), parse_mode="Markdown")
            elif text == "ℹ️ Help":
                # Re-trigger help
                await cmd_help(message)
            elif text == "🔒 Privacy":
                await cmd_privacy(message)
            return

        style = get_user_style(message.from_user.id, settings)
        try:
            png_bytes = generate_qr(text, **style)
        except ValueError:
            await message.answer("❌ Text is too long or empty for a QR code.")
            return

        photo = BufferedInputFile(png_bytes, filename="qr.png")
        display_text = text[:100] + ("..." if len(text) > 100 else "")
        await message.answer_photo(
            photo,
            caption=f"✅ *QR Code Generated!*\n\n`{display_text}`{CHANNEL_FOOTER}",
            parse_mode="Markdown",
        )
        record_generation(message.from_user.id)

    # --- Inline mode ---
    @router.inline_query()
    async def inline_qr(inline_query: types.InlineQuery):
        query_text = inline_query.query.strip()
        if not query_text:
            await inline_query.answer(
                results=[],
                switch_pm_text="Type text to generate QR...",
                switch_pm_parameter="inline_help",
                cache_time=1,
            )
            return

        style = get_user_style(inline_query.from_user.id, settings)
        try:
            png_bytes = generate_qr(query_text, **style)
        except ValueError:
            await inline_query.answer(results=[], cache_time=1)
            return

        # Send to admin chat to get a file_id for inline use
        admin_chat = settings.admin_ids[0] if settings.admin_ids else inline_query.from_user.id
        try:
            sent = await inline_query.bot.send_photo(
                chat_id=admin_chat,
                photo=BufferedInputFile(png_bytes, filename="qr.png"),
            )
            file_id = sent.photo[-1].file_id

            result = InlineQueryResultCachedPhoto(
                id="qr",
                photo_file_id=file_id,
                title=f"QR: {query_text[:50]}",
                description=f"QR code for: {query_text[:100]}",
            )
            await inline_query.answer(results=[result], cache_time=300, is_personal=True)
        except Exception as e:
            logger.warning("Inline QR failed: %s", e)
            await inline_query.answer(results=[], cache_time=1)

        record_inline(inline_query.from_user.id)

    # --- Helper: decode image ---
    async def _decode_image(message: types.Message, file_id: str, bot: Bot):
        status_msg = await message.answer("🔍 Scanning for QR code...")
        try:
            file = await bot.get_file(file_id)
            file_bytes = await bot.download_file(file.file_path)
            image_bytes = file_bytes.read() if hasattr(file_bytes, "read") else bytes(file_bytes)

            results = decode_qr(image_bytes)

            if not results:
                await status_msg.edit_text("❌ No QR code found in this image.")
                return

            if len(results) == 1:
                await status_msg.edit_text(
                    f"✅ *Decoded!*\n\n`{results[0]}`",
                    parse_mode="Markdown",
                )
            else:
                decoded_text = "\n".join(f"{i+1}. `{r}`" for i, r in enumerate(results))
                await status_msg.edit_text(
                    f"✅ *Found {len(results)} QR codes:*\n\n{decoded_text}",
                    parse_mode="Markdown",
                )
            record_decode(message.from_user.id)
        except Exception as e:
            logger.exception("Decode error: %s", e)
            await status_msg.edit_text("❌ Failed to process the image. Please try again.")

    # --- Donate callback ---
    @router.callback_query(F.data.startswith("donate:"))
    async def cb_donate(callback: types.CallbackQuery):
        amount_str = callback.data.split(":")[1]
        if amount_str == "custom":
            await callback.answer("Type /donate <amount> for custom amount", show_alert=True)
            return
        await callback.answer()
        ok = await send_invoice(callback.bot, callback.message.chat.id, int(amount_str), callback.message.message_id)
        if not ok:
            await callback.message.answer("❌ Invoice failed.")

    # --- Pre-checkout (required for Stars) ---
    @router.pre_checkout_query()
    async def on_pre_checkout(query: types.PreCheckoutQuery):
        await query.answer(ok=True)

    # --- Successful payment ---
    @router.message(F.successful_payment)
    async def on_successful_payment(message: types.Message):
        stars = message.successful_payment.total_amount
        await message.answer(
            f"🎉 Thank you! You donated <b>{stars} Stars</b> ⭐\n\nYour support keeps the bot running!",
            parse_mode="HTML",
        )

    return router


def create_bot(settings: Settings) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    router = create_router(settings)
    dp.include_router(router)
    return bot, dp
