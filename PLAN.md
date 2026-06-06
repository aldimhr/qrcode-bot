# QR Code Telegram Bot — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** A Telegram bot that generates QR codes from text/URLs/WiFi configs, decodes QR codes from images, and supports inline mode — all running on CPU with no external API dependencies.

**Architecture:** Python/aiogram bot with `qrcode` + `Pillow` for generation, `pyzbar` + `libzbar` for decoding. Handlers are thin; all QR logic lives in `core.py` for testability. Ephemeral temp files, JSON-backed admin stats.

**Tech Stack:** Python 3.11, aiogram 3, qrcode[pil], Pillow, pyzbar, pydantic-settings

---

## Features

| Feature | Input | Output |
|---------|-------|--------|
| Generate QR | Text/URL message | QR code image (PNG) |
| Decode QR | Photo/document with QR | Extracted text |
| WiFi QR | `/wifi` command → guided flow | QR that auto-connects to WiFi |
| Inline mode | `@botname text` | QR code as inline result |
| Custom colors | `/style` command | Set QR foreground/background colors |
| Admin stats | `/stats` (admin only) | Usage counters |

## Commands

- `/start` — Welcome message + feature overview
- `/help` — Usage guide with examples
- `/wifi` — Generate WiFi QR (guided: SSID → password → encryption)
- `/style` — Customize QR colors (fg/bg hex codes)
- `/privacy` — File retention policy
- `/stats` — Admin-only usage dashboard

## User Flow

1. **Generate:** User sends any text/URL → bot replies with QR code image
2. **Decode:** User sends photo or image document containing a QR → bot extracts and returns the text
3. **WiFi:** User taps `/wifi` → bot asks for SSID → password → encryption type → generates WiFi QR
4. **Inline:** In any chat, type `@botname https://example.com` → QR appears as inline result
5. **Style:** User sends `/style #FF0000 #FFFFFF` → sets red QR on white background for future QRs

---

## Project Structure

```
/opt/hermes/qrcode_bot/
├── pyproject.toml
├── .env.example
├── .env
├── .gitignore
├── README.md
├── PLAN.md
├── src/
│   └── qrcode_bot/
│       ├── __init__.py
│       ├── bot.py          # aiogram handlers, router setup
│       ├── config.py       # pydantic-settings, env parsing
│       ├── core.py         # pure QR logic (generate, decode, wifi, style)
│       └── keyboards.py    # reply/inline keyboards
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_core.py        # pure QR logic tests
    └── test_parsing.py     # WiFi input parsing, style parsing
```

---

## Task 1: Project scaffold + dependencies

**Objective:** Create the project structure, pyproject.toml, .env, .gitignore, and install dependencies.

**Files:**
- Create: `/opt/hermes/qrcode_bot/pyproject.toml`
- Create: `/opt/hermes/qrcode_bot/.env.example`
- Create: `/opt/hermes/qrcode_bot/.env` (with real token)
- Create: `/opt/hermes/qrcode_bot/.gitignore`
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/__init__.py`

**Steps:**

1. Install system dependency for pyzbar:
```bash
apt-get update && apt-get install -y libzbar0
```

2. Create pyproject.toml:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "qrcode-bot"
version = "0.1.0"
description = "Telegram bot for QR code generation and decoding"
requires-python = ">=3.11"
dependencies = [
    "aiogram>=3.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
    "qrcode[pil]>=7.0",
    "pillow>=10.0",
    "pyzbar>=0.1.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "strict"
testpaths = ["tests"]
```

3. Create .env.example:
```env
BOT_TOKEN=put-your-token-here
ADMIN_IDS=
QR_DEFAULT_FG=#000000
QR_DEFAULT_BG=#FFFFFF
QR_BOX_SIZE=10
QR_BORDER=4
```

4. Create .gitignore:
```
.env
.venv/
__pycache__/
.pytest_cache/
data/
*.egg-info/
dist/
build/
```

5. Create `src/qrcode_bot/__init__.py` (empty).

6. Create venv + install:
```bash
cd /opt/hermes/qrcode_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Verify:**
```bash
.venv/bin/python -c "import qrcode; import pyzbar; print('OK')"
```
Expected: `OK`

**Commit:**
```bash
git init && git add -A && git commit -m "chore: project scaffold with dependencies"
```

---

## Task 2: Config + settings module

**Objective:** Create config.py with pydantic-settings for env parsing.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/config.py`

**Code:**
```python
from __future__ import annotations

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids: List[int] = Field(default_factory=list, alias="ADMIN_IDS")

    qr_default_fg: str = Field(default="#000000", alias="QR_DEFAULT_FG")
    qr_default_bg: str = Field(default="#FFFFFF", alias="QR_DEFAULT_BG")
    qr_box_size: int = Field(default=10, alias="QR_BOX_SIZE")
    qr_border: int = Field(default=4, alias="QR_BORDER")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return value


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

**Verify:**
```bash
.venv/bin/python -c "from qrcode_bot.config import load_settings; s = load_settings(); print(s.bot_token[:5])"
```
Expected: first 5 chars of token

**Commit:**
```bash
git add -A && git commit -m "feat: add config module with pydantic-settings"
```

---

## Task 3: Core QR logic — generation (TDD)

**Objective:** Implement `generate_qr()` in core.py that takes text + colors + size and returns PNG bytes.

**Files:**
- Create: `/opt/hermes/qrcode_bot/tests/__init__.py`
- Create: `/opt/hermes/qrcode_bot/tests/conftest.py`
- Create: `/opt/hermes/qrcode_bot/tests/test_core.py`
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/core.py`

**Step 1: Write failing tests**

`tests/test_core.py`:
```python
import io
from PIL import Image
from qrcode_bot.core import generate_qr


def test_generate_qr_returns_png_bytes():
    data = generate_qr("https://example.com")
    assert isinstance(data, bytes)
    assert data[:4] == b"\x89PNG"  # PNG magic bytes


def test_generate_qr_is_valid_image():
    data = generate_qr("hello world")
    img = Image.open(io.BytesIO(data))
    assert img.format == "PNG"
    assert img.size[0] > 0
    assert img.size[1] > 0


def test_generate_qr_custom_colors():
    data = generate_qr("test", fg_color="#FF0000", bg_color="#00FF00")
    img = Image.open(io.BytesIO(data)).convert("RGB")
    # Check corner pixel (background area, border)
    pixel = img.getpixel((0, 0))
    # Should be green-ish (background)
    assert pixel[1] > 200  # green channel high


def test_generate_qr_custom_size():
    small = generate_qr("test", box_size=5, border=1)
    large = generate_qr("test", box_size=20, border=4)
    small_img = Image.open(io.BytesIO(small))
    large_img = Image.open(io.BytesIO(large))
    assert large_img.size[0] > small_img.size[0]


def test_generate_qr_empty_text_raises():
    import pytest
    with pytest.raises(ValueError):
        generate_qr("")


def test_generate_qr_wifi():
    data = generate_qr_wifi("MyNetwork", "password123", "WPA")
    assert isinstance(data, bytes)
    assert data[:4] == b"\x89PNG"
    img = Image.open(io.BytesIO(data))
    assert img.format == "PNG"
```

**Step 2: Run tests to verify failure**
```bash
cd /opt/hermes/qrcode_bot && .venv/bin/pytest tests/test_core.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'qrcode_bot.core'`

**Step 3: Implement core.py**

`src/qrcode_bot/core.py`:
```python
from __future__ import annotations

import io
import re
from typing import Optional

import qrcode
from PIL import Image


def generate_qr(
    text: str,
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
    box_size: int = 10,
    border: int = 4,
) -> bytes:
    """Generate a QR code and return PNG bytes."""
    if not text or not text.strip():
        raise ValueError("Text must not be empty")

    qr = qrcode.QRCode(
        version=None,  # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fg_color, back_color=bg_color).convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_qr_wifi(ssid: str, password: str, security: str = "WPA") -> bytes:
    """Generate a WiFi QR code. Security: WPA, WEP, or nopass."""
    # Escape special characters in WiFi QR format
    def escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace('"', '\\"')

    security_upper = security.upper()
    if security_upper == "NOPASS":
        wifi_str = f"WIFI:T:nopass;S:{escape(ssid)};;"
    else:
        wifi_str = f"WIFI:T:{security_upper};S:{escape(ssid)};P:{escape(password)};;"

    return generate_qr(wifi_str)


def parse_wifi_string(text: str) -> Optional[dict]:
    """Parse a WiFi QR string back into components."""
    match = re.match(r"WIFI:T:([^;]*);S:([^;]*);P:([^;]*);", text)
    if not match:
        return None
    return {
        "security": match.group(1),
        "ssid": match.group(2).replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\"),
        "password": match.group(3).replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\"),
    }


def parse_hex_color(text: str) -> Optional[str]:
    """Validate and normalize a hex color string. Returns None if invalid."""
    text = text.strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", text):
        return f"#{text.upper()}"
    return None
```

**Step 4: Run tests**
```bash
.venv/bin/pytest tests/test_core.py -v
```
Expected: 6 passed

**Commit:**
```bash
git add -A && git commit -m "feat: core QR generation with TDD"
```

---

## Task 4: Core QR logic — decoding (TDD)

**Objective:** Implement `decode_qr()` that reads QR codes from image bytes.

**Files:**
- Modify: `/opt/hermes/qrcode_bot/tests/test_core.py`
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/core.py`

**Step 1: Add failing tests**

Append to `tests/test_core.py`:
```python
from qrcode_bot.core import decode_qr, generate_qr


def test_decode_qr_from_generated():
    """Round-trip: generate then decode."""
    original = "https://example.com/test?foo=bar"
    png_bytes = generate_qr(original)
    results = decode_qr(png_bytes)
    assert len(results) >= 1
    assert results[0] == original


def test_decode_qr_multiple_codes():
    """Test with image containing no QR returns empty list."""
    # Create a blank image with no QR
    from PIL import Image
    img = Image.new("RGB", (200, 200), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    results = decode_qr(buf.getvalue())
    assert results == []


def test_decode_qr_invalid_image():
    """Non-image bytes return empty list."""
    results = decode_qr(b"not an image")
    assert results == []
```

**Step 2: Run to verify failure**
```bash
.venv/bin/pytest tests/test_core.py::test_decode_qr_from_generated -v
```
Expected: FAIL — `AttributeError: module 'qrcode_bot.core' has no attribute 'decode_qr'`

**Step 3: Add decode_qr to core.py**

Append to `core.py`:
```python
from pyzbar.pyzbar import decode as pyzbar_decode, ZBarSymbol


def decode_qr(image_bytes: bytes) -> list[str]:
    """Decode QR codes from image bytes. Returns list of decoded strings."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return []

    try:
        decoded = pyzbar_decode(img, symbols=[ZBarSymbol.QRCODE])
        return [d.data.decode("utf-8", errors="replace") for d in decoded]
    except Exception:
        return []
```

**Step 4: Run tests**
```bash
.venv/bin/pytest tests/test_core.py -v
```
Expected: 9 passed

**Commit:**
```bash
git add -A && git commit -m "feat: add QR code decoding from images"
```

---

## Task 5: Keyboards

**Objective:** Create reply and inline keyboards for the bot.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/keyboards.py`

**Code:**
```python
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
            [KeyboardButton(text="📶 WiFi QR"), KeyboardButton(text="🎨 Style")],
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
```

**Verify:**
```bash
.venv/bin/python -c "from qrcode_bot.keyboards import main_reply_keyboard; print('OK')"
```

**Commit:**
```bash
git add -A && git commit -m "feat: add reply and inline keyboards"
```

---

## Task 6: Bot handlers — generate + decode

**Objective:** Implement the main bot handlers for QR generation and decoding.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/bot.py`

**Code:**
```python
from __future__ import annotations

import io
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile

from qrcode_bot.config import Settings
from qrcode_bot.core import decode_qr, generate_qr
from qrcode_bot.keyboards import main_reply_keyboard

logger = logging.getLogger(__name__)

# Per-user style preferences (in-memory, resets on restart)
user_styles: dict[int, dict] = {}

CHANNEL_FOOTER = "\n\n📢 @x0projects"


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

    @router.message(Command("help"))
    async def cmd_help(message: types.Message):
        text = (
            "📖 *How to use QR Code Bot*\n\n"
            "*Generate QR:*\n"
            "Send any text, URL, or message — I'll turn it into a QR code.\n\n"
            "*Decode QR:*\n"
            "Send me a photo or image containing a QR code.\n\n"
            "*WiFi QR:*\n"
            "Tap 📶 WiFi QR or use /wifi — I'll guide you through creating a WiFi login QR.\n\n"
            "*Custom Colors:*\n"
            "Tap 🎨 Style or use /style — set your QR foreground and background colors.\n\n"
            "*Inline Mode:*\n"
            "In any chat, type `@botname your-text-here` to generate QR codes inline.\n\n"
            "*Supported formats:*\n"
            "Text, URLs, email addresses, phone numbers, WiFi configs, and more."
            f"{CHANNEL_FOOTER}"
        )
        await message.answer(text, parse_mode="Markdown")

    @router.message(Command("privacy"))
    async def cmd_privacy(message: types.Message):
        text = (
            "🔒 *Privacy Policy*\n\n"
            "• Your images and text are processed in-memory and *never stored*.\n"
            "• Generated QR codes are sent directly to you and deleted immediately.\n"
            "• No data is shared with third parties.\n"
            "• In-memory style preferences reset when the bot restarts."
        )
        await message.answer(text, parse_mode="Markdown")

    @router.message(Command("style"))
    async def cmd_style(message: types.Message):
        parts = message.text.split(maxsplit=2)
        if len(parts) >= 3:
            from qrcode_bot.core import parse_hex_color
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
            "First color = QR dots, second = background.\n\n"
            "Or tap the buttons below for presets:",
            parse_mode="Markdown",
        )

    # Handle photo messages (decode QR)
    @router.message(F.photo)
    async def handle_photo(message: types.Message, bot: Bot):
        await _decode_image(message, message.photo[-1].file_id, bot)

    # Handle document messages (decode QR from image docs)
    @router.message(F.document)
    async def handle_document(message: types.Message, bot: Bot):
        doc = message.document
        if not doc.mime_type or not doc.mime_type.startswith("image/"):
            await message.answer("📷 Please send an image file containing a QR code.")
            return
        await _decode_image(message, doc.file_id, bot)

    # Handle text messages (generate QR)
    @router.message(F.text)
    async def handle_text(message: types.Message):
        text = message.text.strip()
        # Skip keyboard button texts (handled as commands)
        if text in ("📱 Generate QR", "📷 Decode QR", "📶 WiFi QR", "🎨 Style", "ℹ️ Help", "🔒 Privacy"):
            return

        style = get_user_style(message.from_user.id, settings)
        try:
            png_bytes = generate_qr(text, **style)
        except ValueError:
            await message.answer("❌ Text is too long or empty for a QR code.")
            return

        photo = BufferedInputFile(png_bytes, filename="qr.png")
        await message.answer_photo(
            photo,
            caption=f"✅ *QR Code Generated!*\n\n`{text[:100]}{'...' if len(text) > 100 else ''}`",
            parse_mode="Markdown",
        )

    async def _decode_image(message: types.Message, file_id: str, bot: Bot):
        """Download image and decode any QR codes in it."""
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
        except Exception as e:
            logger.exception("Decode error: %s", e)
            await status_msg.edit_text("❌ Failed to process the image. Please try again.")

    return router


def create_bot(settings: Settings) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    router = create_router(settings)
    dp.include_router(router)
    return bot, dp
```

**Verify:**
```bash
.venv/bin/python -c "from qrcode_bot.bot import create_bot; print('import OK')"
```

**Commit:**
```bash
git add -A && git commit -m "feat: add bot handlers for generate, decode, style, help"
```

---

## Task 7: WiFi QR handler

**Objective:** Add the /wifi guided flow with FSM states.

**Files:**
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/bot.py`

**Add to bot.py (inside create_router, after existing handlers):**
```python
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class WiFiStates(StatesGroup):
    waiting_ssid = State()
    waiting_password = State()


# Add inside create_router:
    @router.message(Command("wifi"))
    async def cmd_wifi(message: types.Message, state: FSMContext):
        await state.set_state(WiFiStates.waiting_ssid)
        await message.answer(
            "📶 *WiFi QR Generator*\n\n"
            "Step 1/2: What is the *WiFi network name (SSID)*?",
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
            f"📶 Network: `{ssid}`\n\n"
            "Step 2/2: What is the *password*?\n"
            "Send `none` for open networks.",
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

        from qrcode_bot.core import generate_qr_wifi
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
                f"📶 *WiFi QR Code*\n\n"
                f"Network: `{ssid}`\n"
                f"Security: {security_label}\n\n"
                f"_Scan this QR to connect!_"
            ),
            parse_mode="Markdown",
            reply_markup=main_reply_keyboard(),
        )
        await state.clear()
```

**Also add FSM storage to create_bot:**
```python
from aiogram.fsm.storage.memory import MemoryStorage

def create_bot(settings: Settings) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())  # <-- add storage
    router = create_router(settings)
    dp.include_router(router)
    return bot, dp
```

**Verify:**
```bash
.venv/bin/python -c "from qrcode_bot.bot import create_bot; print('OK')"
```

**Commit:**
```bash
git add -A && git commit -m "feat: add WiFi QR guided flow with FSM"
```

---

## Task 8: Inline mode handler

**Objective:** Support `@botname text` inline queries to generate QR codes in any chat.

**Files:**
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/bot.py`

**Add inside create_router:**
```python
from aiogram.types import InlineQueryResultCachedPhoto, InputFile


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

        # Upload to Telegram as a file to reuse in inline results
        photo = BufferedInputFile(png_bytes, filename="qr.png")
        sent = await inline_query.bot.send_photo(
            chat_id=inline_query.bot.id,  # Send to self (saved messages)
            photo=photo,
        )
        file_id = sent.photo[-1].file_id

        result = InlineQueryResultCachedPhoto(
            id="qr",
            photo_file_id=file_id,
            title=f"QR: {query_text[:50]}",
            description=f"QR code for: {query_text[:100]}",
        )
        await inline_query.answer(results=[result], cache_time=300, is_personal=True)
```

**Pitfall:** Sending to `bot.id` may not work for all bots. An alternative is to use a dedicated "storage" chat (the admin's chat). Let's use the first admin ID:

```python
        # Upload photo to admin chat for file_id reuse
        admin_chat = settings.admin_ids[0] if settings.admin_ids else inline_query.from_user.id
        sent = await inline_query.bot.send_photo(
            chat_id=admin_chat,
            photo=photo,
        )
```

**Verify:**
```bash
.venv/bin/python -c "from qrcode_bot.bot import create_bot; print('OK')"
```

**Commit:**
```bash
git add -A && git commit -m "feat: add inline mode for QR generation"
```

---

## Task 9: Admin stats

**Objective:** Track usage counts and expose via /stats for admin.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/stats.py`
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/bot.py`

**stats.py:**
```python
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
STATS_FILE = DATA_DIR / "stats.json"


def _load() -> dict[str, Any]:
    if STATS_FILE.exists():
        return json.loads(STATS_FILE.read_text())
    return {"generated": 0, "decoded": 0, "wifi": 0, "inline": 0, "users": [], "started_at": time.time()}


def _save(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(data, indent=2))


def record_generation(user_id: int) -> None:
    data = _load()
    data["generated"] = data.get("generated", 0) + 1
    if user_id not in data.get("users", []):
        data.setdefault("users", []).append(user_id)
    _save(data)


def record_decode(user_id: int) -> None:
    data = _load()
    data["decoded"] = data.get("decoded", 0) + 1
    if user_id not in data.get("users", []):
        data.setdefault("users", []).append(user_id)
    _save(data)


def record_wifi(user_id: int) -> None:
    data = _load()
    data["wifi"] = data.get("wifi", 0) + 1
    _save(data)


def record_inline(user_id: int) -> None:
    data = _load()
    data["inline"] = data.get("inline", 0) + 1
    _save(data)


def get_stats() -> dict[str, Any]:
    return _load()
```

**Add /stats handler in bot.py:**
```python
    @router.message(Command("stats"))
    async def cmd_stats(message: types.Message):
        if message.from_user.id not in settings.admin_ids:
            return
        from qrcode_bot.stats import get_stats
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
```

**Wire stat recording into handlers:**
- After `generate_qr` in `handle_text` → `record_generation(message.from_user.id)`
- After decode success in `_decode_image` → `record_decode(message.from_user.id)`
- After WiFi QR send → `record_wifi(message.from_user.id)`
- In inline handler → `record_inline(inline_query.from_user.id)`

**Commit:**
```bash
git add -A && git commit -m "feat: add admin stats tracking"
```

---

## Task 10: Main entrypoint + systemd service

**Objective:** Create __main__.py entrypoint and systemd service for deployment.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/__main__.py`
- Create: `/opt/hermes/qrcode_bot/run.py`

**__main__.py:**
```python
import asyncio
import logging

from qrcode_bot.bot import create_bot
from qrcode_bot.config import load_settings


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    settings = load_settings()
    bot, dp = create_bot(settings)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

**run.py:**
```python
from qrcode_bot.__main__ import main
import asyncio
asyncio.run(main())
```

**systemd unit** (`/etc/systemd/system/qrcode-bot.service`):
```ini
[Unit]
Description=QR Code Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/hermes/qrcode_bot
ExecStart=/opt/hermes/qrcode_bot/.venv/bin/python -m qrcode_bot
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

**Deploy:**
```bash
systemctl daemon-reload
systemctl enable --now qrcode-bot
systemctl is-active qrcode-bot
journalctl -u qrcode-bot -n 20 --no-pager
```

**Verify:** Send `/start` to the bot in Telegram.

**Commit:**
```bash
git add -A && git commit -m "feat: entrypoint, systemd service, deployment"
```

---

## Task 11: Tests + final verification

**Objective:** Run full test suite, verify all imports, test the bot manually.

**Steps:**
```bash
cd /opt/hermes/qrcode_bot
.venv/bin/pytest tests/ -v
.venv/bin/python -m compileall src/qrcode_bot
systemctl is-active qrcode-bot
```

**Manual verification in Telegram:**
1. Send `/start` — should show welcome + keyboard
2. Send `https://example.com` — should generate QR
3. Send the QR image back — should decode
4. Tap 📶 WiFi QR — follow the flow
5. Send `/style #FF0000 #FFFFFF` then send text — red QR
6. Use inline in another chat: `@botname test`

**Commit:**
```bash
git add -A && git commit -m "chore: final verification and cleanup"
```

---

## Summary

| Task | What | Time |
|------|------|------|
| 1 | Project scaffold + deps | 3 min |
| 2 | Config module | 2 min |
| 3 | Core QR generation (TDD) | 5 min |
| 4 | Core QR decoding (TDD) | 3 min |
| 5 | Keyboards | 2 min |
| 6 | Bot handlers (generate + decode) | 5 min |
| 7 | WiFi QR handler (FSM) | 4 min |
| 8 | Inline mode | 3 min |
| 9 | Admin stats | 3 min |
| 10 | Entrypoint + systemd | 3 min |
| 11 | Tests + verification | 3 min |

**Total: ~11 tasks, ~35 minutes**
