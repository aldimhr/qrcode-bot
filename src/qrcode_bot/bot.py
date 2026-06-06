from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedPhoto, LabeledPrice

from qrcode_bot.config import Settings
from qrcode_bot.core import decode_qr, generate_qr, generate_qr_wifi, parse_hex_color
from qrcode_bot.donate import DONATE_TEXT, donation_keyboard, send_invoice
from qrcode_bot.keyboards import main_reply_keyboard
from qrcode_bot.stats import get_stats, record_decode, record_generation, record_inline, record_wifi

logger = logging.getLogger(__name__)

CHANNEL_FOOTER = "\n\n📢 @x0projects"

# Per-user style preferences (in-memory, resets on restart)
user_styles: dict[int, dict] = {}

# Per-user frame preferences (in-memory)
user_frames: dict[int, dict] = {}

# Per-user visual style preferences (in-memory)
# Keys: "preset" (name), "gradient_top", "gradient_bottom", "rounded", "text_overlay"
user_visual: dict[int, dict] = {}


class WiFiStates(StatesGroup):
    waiting_ssid = State()
    waiting_password = State()


class LogoStates(StatesGroup):
    waiting_text = State()
    waiting_logo = State()


class ContactStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_email = State()
    waiting_org = State()


class EmailStates(StatesGroup):
    waiting_to = State()
    waiting_subject = State()
    waiting_body = State()


class PhoneStates(StatesGroup):
    waiting_number = State()


class LocationStates(StatesGroup):
    waiting_coords = State()


class EventStates(StatesGroup):
    waiting_title = State()
    waiting_start = State()
    waiting_end = State()
    waiting_location = State()


class FrameStates(StatesGroup):
    waiting_text = State()


def get_user_style(user_id: int, settings: Settings) -> dict:
    style = user_styles.get(user_id, {})
    return {
        "fg_color": style.get("fg", settings.qr_default_fg),
        "bg_color": style.get("bg", settings.qr_default_bg),
        "box_size": settings.qr_box_size,
        "border": settings.qr_border,
    }


def apply_user_frame(qr_bytes: bytes, user_id: int) -> bytes:
    """Apply user's frame preference to QR bytes if set."""
    # Apply visual effects first (gradient, rounded modules)
    qr_bytes = apply_user_visual(qr_bytes, user_id)
    # Then apply frame
    frame = user_frames.get(user_id)
    if not frame:
        return qr_bytes
    from qrcode_bot.frames import apply_frame, apply_rounded_frame
    if frame["style"] == "rounded":
        return apply_rounded_frame(qr_bytes, text=frame.get("text", "Scan Me!"))
    return apply_frame(qr_bytes, text=frame.get("text", "Scan Me!"))


def apply_user_visual(qr_bytes: bytes, user_id: int) -> bytes:
    """Apply user's visual style preference to QR bytes."""
    visual = user_visual.get(user_id)
    if not visual:
        return qr_bytes
    from qrcode_bot.styles import apply_gradient, apply_rounded_modules
    if visual.get("rounded"):
        return apply_rounded_modules(qr_bytes)
    if visual.get("gradient_top") and visual.get("gradient_bottom"):
        return apply_gradient(qr_bytes, visual["gradient_top"], visual["gradient_bottom"])
    return qr_bytes


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
            "• Use /contact to create a contact QR (vCard)\n"
            "• Use /email, /phone, /location, /event for more types\n"
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
            "*More QR Types:*\n"
            "📇 /contact — Contact card (vCard)\n"
            "📧 /email — Email with subject & body\n"
            "📞 /phone — Phone number\n"
            "📍 /location — GPS coordinates\n"
            "📅 /event — Calendar event\n\n"
            "*Custom Colors:*\n"
            "Tap 🎨 Style or use /style `#FF0000 #FFFFFF`\n\n"
            "*Custom Frames:*\n"
            "Tap 🖼️ Frame or use /frame — add \"Scan Me!\" or custom text below QR.\n\n"
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
                user_visual.pop(message.from_user.id, None)
                await message.answer(
                    f"🎨 *Style updated!*\n\nForeground: `{fg}`\nBackground: `{bg}`\n\n"
                    "Send any text to see your new style in action.",
                    parse_mode="Markdown",
                )
                return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬛ Classic", callback_data="vstyle:classic"),
             InlineKeyboardButton(text="⬜ Dark", callback_data="vstyle:dark")],
            [InlineKeyboardButton(text="🌊 Ocean", callback_data="vstyle:ocean"),
             InlineKeyboardButton(text="🌅 Sunset", callback_data="vstyle:sunset")],
            [InlineKeyboardButton(text="💚 Neon", callback_data="vstyle:neon"),
             InlineKeyboardButton(text="🔵 Rounded", callback_data="vstyle:rounded")],
            [InlineKeyboardButton(text="🔤 Default", callback_data="vstyle:default")],
        ])
        await message.answer(
            "🎨 *Choose a QR Style*\n\n"
            "Pick a preset or use `/style #FF0000 #FFFFFF` for custom colors.",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    @router.callback_query(F.data.startswith("vstyle:"))
    async def cb_vstyle(callback: types.CallbackQuery):
        preset = callback.data.split(":")[1]
        await callback.answer()
        uid = callback.from_user.id

        presets = {
            "classic": {"fg": "#000000", "bg": "#FFFFFF"},
            "dark": {"fg": "#FFFFFF", "bg": "#000000"},
            "neon": {"fg": "#00FF00", "bg": "#000000"},
        }
        gradient_presets = {
            "ocean": {"top": "#0077BE", "bottom": "#00D4FF"},
            "sunset": {"top": "#FF6B35", "bottom": "#FFD700"},
        }

        if preset == "default":
            user_visual.pop(uid, None)
            user_styles.pop(uid, None)
            await callback.message.edit_text("🔤 Default style restored.")
        elif preset == "rounded":
            user_visual[uid] = {"rounded": True}
            user_styles.pop(uid, None)
            await callback.message.edit_text("🔵 *Rounded modules* style set!\n\nYour QR codes will use rounded dots.")
        elif preset in gradient_presets:
            gp = gradient_presets[preset]
            user_visual[uid] = {"gradient_top": gp["top"], "gradient_bottom": gp["bottom"]}
            user_styles.pop(uid, None)
            await callback.message.edit_text(f"🌊 *{preset.title()} gradient* style set!")
        elif preset in presets:
            ps = presets[preset]
            user_styles[uid] = {"fg": ps["fg"], "bg": ps["bg"]}
            user_visual.pop(uid, None)
            await callback.message.edit_text(f"🎨 *{preset.title()}* style set!")

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

        png_bytes = apply_user_frame(png_bytes, message.from_user.id)
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

    # --- /logo ---
    @router.message(Command("logo"))
    async def cmd_logo(message: types.Message, state: FSMContext):
        await state.set_state(LogoStates.waiting_text)
        await message.answer(
            "🏷️ *Logo QR Generator*\n\n"
            "Step 1/2: Send me the *text or URL* for your QR code.",
            parse_mode="Markdown",
        )

    @router.message(LogoStates.waiting_text)
    async def logo_text(message: types.Message, state: FSMContext):
        text = message.text.strip()
        if len(text) > 2000:
            await message.answer("❌ Text is too long (max 2000 characters).")
            return
        await state.update_data(qr_text=text)
        await state.set_state(LogoStates.waiting_logo)
        await message.answer(
            f"📝 Text: `{text[:100]}{'...' if len(text) > 100 else ''}`\n\n"
            "Step 2/2: Now send me a *logo image* (PNG/JPG, max 5MB).\n\n"
            "The logo will be placed in the center of the QR code.",
            parse_mode="Markdown",
        )

    @router.message(LogoStates.waiting_logo, F.photo | F.document)
    async def logo_image(message: types.Message, state: FSMContext, bot: Bot):
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
            file_id = message.document.file_id
        else:
            await message.answer("📷 Please send an image file (PNG/JPG).")
            return

        status_msg = await message.answer("🔄 Generating QR with logo...")
        try:
            file = await bot.get_file(file_id)
            file_bytes = await bot.download_file(file.file_path)
            logo_bytes = file_bytes.read() if hasattr(file_bytes, "read") else bytes(file_bytes)

            from qrcode_bot.logo import validate_logo, embed_logo
            if not validate_logo(logo_bytes):
                await status_msg.edit_text("❌ Invalid logo or too large (max 5MB). Please try again.")
                return

            data = await state.get_data()
            qr_text = data["qr_text"]

            qr_bytes = generate_qr(qr_text, error_correction="H")
            result_bytes = embed_logo(qr_bytes, logo_bytes)

            result_bytes = apply_user_frame(result_bytes, message.from_user.id)
            photo = BufferedInputFile(result_bytes, filename="logo_qr.png")
            display_text = qr_text[:100] + ("..." if len(qr_text) > 100 else "")
            await status_msg.delete()
            await message.answer_photo(
                photo,
                caption=f"🏷️ *QR with Logo!*\n\n`{display_text}`{CHANNEL_FOOTER}",
                parse_mode="Markdown",
                reply_markup=main_reply_keyboard(),
            )
            record_generation(message.from_user.id)
        except Exception as e:
            logger.exception("Logo QR error: %s", e)
            await status_msg.edit_text("❌ Failed to generate QR with logo. Please try again.")
        finally:
            await state.clear()

    @router.message(LogoStates.waiting_logo)
    async def logo_wrong_input(message: types.Message):
        await message.answer("📷 Please send a *photo or image file* as your logo.", parse_mode="Markdown")

    # --- /types ---
    @router.message(Command("types"))
    async def cmd_types(message: types.Message):
        text = (
            "📋 *Available QR Types*\n\n"
            "Choose a type or use the command:\n\n"
            "📇 /contact — Contact card (vCard)\n"
            "📧 /email — Email with subject & body\n"
            "📞 /phone — Phone number\n"
            "📍 /location — GPS coordinates\n"
            "📅 /event — Calendar event\n"
            "📶 /wifi — WiFi network login\n"
            "🏷️ /logo — QR with your logo\n\n"
            "Or just send any text/URL for a quick QR!"
        )
        await message.answer(text, parse_mode="Markdown")

    # --- /frame ---
    @router.message(Command("frame"))
    async def cmd_frame(message: types.Message, state: FSMContext):
        parts = message.text.split(maxsplit=2)
        if len(parts) >= 3 and parts[1].lower() == "custom":
            custom_text = parts[2].strip()
            if len(custom_text) > 50:
                await message.answer("❌ Frame text too long (max 50 characters).")
                return
            user_frames[message.from_user.id] = {"style": "custom", "text": custom_text}
            await message.answer(
                f"🖼️ *Custom frame set!*\n\nText: `{custom_text}`\n\nAll your QR codes will now include this frame.",
                parse_mode="Markdown",
            )
            return
        if len(parts) >= 2 and parts[1].lower() == "off":
            user_frames.pop(message.from_user.id, None)
            await message.answer("🖼️ Frame removed. QR codes will be plain.")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ No Frame", callback_data="frame:none")],
            [InlineKeyboardButton(text="📱 Scan Me!", callback_data="frame:scan_me")],
            [InlineKeyboardButton(text="📶 WiFi", callback_data="frame:wifi")],
            [InlineKeyboardButton(text="✏️ Custom Text", callback_data="frame:custom_prompt")],
            [InlineKeyboardButton(text="🖼️ Rounded Border", callback_data="frame:rounded")],
        ])
        await message.answer(
            "🖼️ *Choose a QR Frame Style*\n\n"
            "Selected style will apply to all your QR codes.\n"
            "Use `/frame off` to remove.",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    @router.callback_query(F.data.startswith("frame:"))
    async def cb_frame(callback: types.CallbackQuery, state: FSMContext):
        style = callback.data.split(":")[1]
        await callback.answer()

        if style == "none":
            user_frames.pop(callback.from_user.id, None)
            await callback.message.edit_text("🖼️ Frame removed. QR codes will be plain.")
        elif style == "custom_prompt":
            await callback.message.edit_text(
                "✏️ Send me the *custom text* for your frame (max 50 chars):",
                parse_mode="Markdown",
            )
            await state.set_state(FrameStates.waiting_text)
        elif style == "rounded":
            user_frames[callback.from_user.id] = {"style": "rounded", "text": "Scan Me!"}
            await callback.message.edit_text(
                "🖼️ *Rounded border frame set!*\n\nAll your QR codes will now have a rounded border.",
                parse_mode="Markdown",
            )
        else:
            text_map = {"scan_me": "Scan Me!", "wifi": "📶 Connect to WiFi"}
            user_frames[callback.from_user.id] = {"style": style, "text": text_map.get(style, "Scan Me!")}
            await callback.message.edit_text(
                f"🖼️ *Frame set!* Style: {text_map.get(style, style)}\n\nAll your QR codes will now include this frame.",
                parse_mode="Markdown",
            )

    @router.message(FrameStates.waiting_text)
    async def frame_custom_text(message: types.Message, state: FSMContext):
        text = message.text.strip()[:50]
        user_frames[message.from_user.id] = {"style": "custom", "text": text}
        await message.answer(
            f"🖼️ *Custom frame set!*\n\nText: `{text}`\n\nAll your QR codes will now include this frame.",
            parse_mode="Markdown",
        )
        await state.clear()

    # --- /contact (vCard) ---
    @router.message(Command("contact"))
    async def cmd_contact(message: types.Message, state: FSMContext):
        await state.set_state(ContactStates.waiting_name)
        await message.answer(
            "📇 *Contact QR (vCard)*\n\nStep 1/4: What is the *full name*?",
            parse_mode="Markdown",
        )

    @router.message(ContactStates.waiting_name)
    async def contact_name(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text.strip())
        await state.set_state(ContactStates.waiting_phone)
        await message.answer(
            "📞 Step 2/4: What is the *phone number*?\nSend `skip` to skip.",
            parse_mode="Markdown",
        )

    @router.message(ContactStates.waiting_phone)
    async def contact_phone(message: types.Message, state: FSMContext):
        phone = "" if message.text.strip().lower() == "skip" else message.text.strip()
        await state.update_data(phone=phone)
        await state.set_state(ContactStates.waiting_email)
        await message.answer(
            "📧 Step 3/4: What is the *email address*?\nSend `skip` to skip.",
            parse_mode="Markdown",
        )

    @router.message(ContactStates.waiting_email)
    async def contact_email(message: types.Message, state: FSMContext):
        email = "" if message.text.strip().lower() == "skip" else message.text.strip()
        await state.update_data(email=email)
        await state.set_state(ContactStates.waiting_org)
        await message.answer(
            "🏢 Step 4/4: What is the *organization/company*?\nSend `skip` to skip.",
            parse_mode="Markdown",
        )

    @router.message(ContactStates.waiting_org)
    async def contact_org(message: types.Message, state: FSMContext):
        data = await state.get_data()
        org = "" if message.text.strip().lower() == "skip" else message.text.strip()
        from qrcode_bot.qr_types import build_vcard
        vcard = build_vcard(data["name"], data.get("phone", ""), data.get("email", ""), org)
        style = get_user_style(message.from_user.id, settings)
        png_bytes = generate_qr(vcard, **style)
        png_bytes = apply_user_frame(png_bytes, message.from_user.id)
        photo = BufferedInputFile(png_bytes, filename="contact_qr.png")
        lines = [f"📇 *Contact QR*\n", f"Name: {data['name']}"]
        if data.get("phone"):
            lines.append(f"Phone: {data['phone']}")
        if data.get("email"):
            lines.append(f"Email: {data['email']}")
        if org:
            lines.append(f"Org: {org}")
        lines.append(CHANNEL_FOOTER)
        await message.answer_photo(photo, caption="\n".join(lines), parse_mode="Markdown", reply_markup=main_reply_keyboard())
        record_generation(message.from_user.id)
        await state.clear()

    # --- /email ---
    @router.message(Command("email"))
    async def cmd_email(message: types.Message, state: FSMContext):
        await state.set_state(EmailStates.waiting_to)
        await message.answer(
            "📧 *Email QR*\n\nStep 1/3: What is the *recipient email address*?",
            parse_mode="Markdown",
        )

    @router.message(EmailStates.waiting_to)
    async def email_to(message: types.Message, state: FSMContext):
        await state.update_data(to=message.text.strip())
        await state.set_state(EmailStates.waiting_subject)
        await message.answer(
            "📝 Step 2/3: What is the *subject line*?\nSend `skip` to skip.",
            parse_mode="Markdown",
        )

    @router.message(EmailStates.waiting_subject)
    async def email_subject(message: types.Message, state: FSMContext):
        subject = "" if message.text.strip().lower() == "skip" else message.text.strip()
        await state.update_data(subject=subject)
        await state.set_state(EmailStates.waiting_body)
        await message.answer(
            "📄 Step 3/3: What is the *email body*?\nSend `skip` to skip.",
            parse_mode="Markdown",
        )

    @router.message(EmailStates.waiting_body)
    async def email_body(message: types.Message, state: FSMContext):
        data = await state.get_data()
        body = "" if message.text.strip().lower() == "skip" else message.text.strip()
        from qrcode_bot.qr_types import build_email
        email_str = build_email(data["to"], data.get("subject", ""), body)
        style = get_user_style(message.from_user.id, settings)
        png_bytes = generate_qr(email_str, **style)
        png_bytes = apply_user_frame(png_bytes, message.from_user.id)
        photo = BufferedInputFile(png_bytes, filename="email_qr.png")
        caption = f"📧 *Email QR*\n\nTo: {data['to']}"
        if data.get("subject"):
            caption += f"\nSubject: {data['subject']}"
        caption += CHANNEL_FOOTER
        await message.answer_photo(photo, caption=caption, parse_mode="Markdown", reply_markup=main_reply_keyboard())
        record_generation(message.from_user.id)
        await state.clear()

    # --- /phone ---
    @router.message(Command("phone"))
    async def cmd_phone(message: types.Message, state: FSMContext):
        await state.set_state(PhoneStates.waiting_number)
        await message.answer(
            "📞 *Phone QR*\n\nSend me the *phone number* (e.g. `+628****6789`).",
            parse_mode="Markdown",
        )

    @router.message(PhoneStates.waiting_number)
    async def phone_number(message: types.Message, state: FSMContext):
        from qrcode_bot.qr_types import build_phone
        try:
            phone_str = build_phone(message.text)
        except ValueError:
            await message.answer("❌ Please enter a valid phone number.")
            return
        style = get_user_style(message.from_user.id, settings)
        png_bytes = generate_qr(phone_str, **style)
        png_bytes = apply_user_frame(png_bytes, message.from_user.id)
        photo = BufferedInputFile(png_bytes, filename="phone_qr.png")
        await message.answer_photo(photo, caption=f"📞 *Phone QR*\n\n`{phone_str}`{CHANNEL_FOOTER}", parse_mode="Markdown", reply_markup=main_reply_keyboard())
        record_generation(message.from_user.id)
        await state.clear()

    # --- /location ---
    @router.message(Command("location"))
    async def cmd_location(message: types.Message, state: FSMContext):
        await state.set_state(LocationStates.waiting_coords)
        await message.answer(
            "📍 *Location QR*\n\n"
            "Send coordinates as `lat,lng` (e.g. `-6.2088,106.8456`)\n\n"
            "Or share a Telegram location 📍 and I'll use those coordinates.",
            parse_mode="Markdown",
        )

    @router.message(LocationStates.waiting_coords, F.location)
    async def location_from_share(message: types.Message, state: FSMContext):
        lat, lng = message.location.latitude, message.location.longitude
        await _generate_location_qr(message, state, lat, lng)

    @router.message(LocationStates.waiting_coords)
    async def location_from_text(message: types.Message, state: FSMContext):
        from qrcode_bot.qr_types import parse_location_text
        coords = parse_location_text(message.text)
        if not coords:
            await message.answer("❌ Invalid format. Use `lat,lng` (e.g. `-6.2088,106.8456`)")
            return
        await _generate_location_qr(message, state, coords[0], coords[1])

    async def _generate_location_qr(message: types.Message, state: FSMContext, lat: float, lng: float):
        from qrcode_bot.qr_types import build_location
        geo_str = build_location(lat, lng)
        style = get_user_style(message.from_user.id, settings)
        png_bytes = generate_qr(geo_str, **style)
        png_bytes = apply_user_frame(png_bytes, message.from_user.id)
        photo = BufferedInputFile(png_bytes, filename="location_qr.png")
        await message.answer_photo(
            photo,
            caption=f"📍 *Location QR*\n\n`{geo_str}`\n[Open in Maps](https://maps.google.com/?q={lat},{lng}){CHANNEL_FOOTER}",
            parse_mode="Markdown",
            reply_markup=main_reply_keyboard(),
        )
        record_generation(message.from_user.id)
        await state.clear()

    # --- /event ---
    @router.message(Command("event"))
    async def cmd_event(message: types.Message, state: FSMContext):
        await state.set_state(EventStates.waiting_title)
        await message.answer(
            "📅 *Calendar Event QR*\n\nStep 1/4: What is the *event title*?",
            parse_mode="Markdown",
        )

    @router.message(EventStates.waiting_title)
    async def event_title(message: types.Message, state: FSMContext):
        await state.update_data(title=message.text.strip())
        await state.set_state(EventStates.waiting_start)
        await message.answer(
            "🕐 Step 2/4: When does it *start*?\n\nFormat: `2026-06-15 14:00` (YYYY-MM-DD HH:MM)",
            parse_mode="Markdown",
        )

    @router.message(EventStates.waiting_start)
    async def event_start(message: types.Message, state: FSMContext):
        from qrcode_bot.qr_types import parse_datetime
        dt = parse_datetime(message.text.strip())
        if not dt:
            await message.answer("❌ Invalid format. Use `YYYY-MM-DD HH:MM` (e.g. `2026-06-15 14:00`)")
            return
        await state.update_data(start=dt)
        await state.set_state(EventStates.waiting_end)
        await message.answer(
            "🕐 Step 3/4: When does it *end*?\n\nFormat: `2026-06-15 15:00`",
            parse_mode="Markdown",
        )

    @router.message(EventStates.waiting_end)
    async def event_end(message: types.Message, state: FSMContext):
        from qrcode_bot.qr_types import parse_datetime
        dt = parse_datetime(message.text.strip())
        if not dt:
            await message.answer("❌ Invalid format. Use `YYYY-MM-DD HH:MM`")
            return
        await state.update_data(end=dt)
        await state.set_state(EventStates.waiting_location)
        await message.answer(
            "📍 Step 4/4: Where is the *location*?\nSend `skip` to skip.",
            parse_mode="Markdown",
        )

    @router.message(EventStates.waiting_location)
    async def event_location(message: types.Message, state: FSMContext):
        data = await state.get_data()
        location = "" if message.text.strip().lower() == "skip" else message.text.strip()
        from qrcode_bot.qr_types import build_event, format_datetime
        event_str = build_event(data["title"], data["start"], data["end"], location)
        style = get_user_style(message.from_user.id, settings)
        png_bytes = generate_qr(event_str, **style)
        png_bytes = apply_user_frame(png_bytes, message.from_user.id)
        photo = BufferedInputFile(png_bytes, filename="event_qr.png")
        caption = f"📅 *Event QR*\n\n📌 {data['title']}\n🕐 {format_datetime(data['start'])} → {format_datetime(data['end'])}"
        if location:
            caption += f"\n📍 {location}"
        caption += CHANNEL_FOOTER
        await message.answer_photo(photo, caption=caption, parse_mode="Markdown", reply_markup=main_reply_keyboard())
        record_generation(message.from_user.id)
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
    async def handle_text(message: types.Message, state: FSMContext):
        text = message.text.strip()
        # Skip keyboard button labels
        if text in ("📱 Generate QR", "📷 Decode QR", "📶 WiFi QR", "🏷️ Logo QR", "📋 More Types", "🖼️ Frame", "🎨 Style", "ℹ️ Help", "🔒 Privacy", "💰 Donate"):
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
            elif text == "🏷️ Logo QR":
                await cmd_logo(message, state)
            elif text == "📋 More Types":
                await cmd_types(message)
            elif text == "🖼️ Frame":
                await cmd_frame(message, state)
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

        png_bytes = apply_user_frame(png_bytes, message.from_user.id)
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


async def register_commands(bot: Bot, admin_ids: list[int]) -> None:
    """Register bot commands in Telegram's menu."""
    from aiogram.types import BotCommand, BotCommandScopeChat

    # Default commands — visible to ALL users
    default_commands = [
        BotCommand(command="start", description="🚀 Start the bot"),
        BotCommand(command="help", description="📖 How to use this bot"),
        BotCommand(command="wifi", description="📶 Generate WiFi QR code"),
        BotCommand(command="contact", description="📇 Contact card (vCard)"),
        BotCommand(command="email", description="📧 Email QR code"),
        BotCommand(command="phone", description="📞 Phone number QR"),
        BotCommand(command="location", description="📍 Location QR code"),
        BotCommand(command="event", description="📅 Calendar event QR"),
        BotCommand(command="logo", description="🏷️ QR with your logo"),
        BotCommand(command="frame", description="🖼️ Add frame to QR"),
        BotCommand(command="style", description="🎨 Customize QR colors"),
        BotCommand(command="donate", description="💝 Support with Stars"),
        BotCommand(command="privacy", description="🔒 Privacy policy"),
        BotCommand(command="types", description="📋 All QR types"),
    ]
    await bot.set_my_commands(default_commands)

    # Admin commands — visible only in admin DMs
    admin_commands = default_commands + [
        BotCommand(command="stats", description="📊 Bot statistics"),
    ]
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception as e:
            logging.warning("Failed to set admin commands for %s: %s", admin_id, e)


def create_bot(settings: Settings) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    router = create_router(settings)
    dp.include_router(router)

    @dp.startup()
    async def on_startup(bot: Bot):
        await register_commands(bot, settings.admin_ids)
        logging.info("Commands registered")

    return bot, dp
