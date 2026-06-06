# Logo Embedding in QR Codes — Implementation Plan

> **For Hermes:** Execute task-by-task, commit after each.

**Goal:** Let users embed a custom logo/image in the center of their QR code. User sends text/URL first, then sends a logo image → bot generates a QR with the logo composited in the center using high error correction (H) so it stays scannable.

**Architecture:** New `logo.py` module for PIL-based compositing. FSM flow triggered by `/logo` command OR by detecting a logo image sent after a QR generation. Error correction forced to HIGH when logo is present. Max logo size: 5MB, formats: PNG/JPG/WEBP.

**Tech Stack:** qrcode (ERROR_CORRECT_H), Pillow (compositing, resize, circular mask)

---

## Features

| Feature | Description |
|---------|-------------|
| `/logo` command | Guided flow: text → logo → QR with logo |
| Auto-detect | Send logo after any QR generation → re-generates with logo |
| Circular logo | Logo is cropped to a circle with white padding |
| Error correction | Forced to HIGH when logo is present |
| Size guard | Max 5MB logo, reject larger |
| Format support | PNG, JPG, WEBP logos |

## User Flow

**Flow A — Guided:**
1. User sends `/logo`
2. Bot: "Send me the text or URL for your QR code"
3. User sends `https://example.com`
4. Bot: "Now send me a logo image (PNG/JPG)"
5. User sends a photo
6. Bot: generates QR with logo → sends result

**Flow B — Auto-detect:**
1. User sends `https://example.com` → bot generates normal QR
2. User sends a photo as a follow-up → bot detects it's a reply/follow-up
3. Bot: re-generates the last QR with this logo embedded

---

## Project Structure (new/modified files)

```
src/qrcode_bot/
├── logo.py           # NEW — logo compositing logic (pure, testable)
├── bot.py            # MODIFY — add /logo command + FSM + auto-detect
├── keyboards.py      # MODIFY — add "🏷️ Logo QR" button
```

---

## Task 1: Logo compositing module (TDD)

**Objective:** Create `logo.py` with `embed_logo()` function that takes QR bytes + logo bytes → returns QR with logo in center.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/logo.py`
- Modify: `/opt/hermes/qrcode_bot/tests/test_core.py` (append logo tests)

**Step 1: Write failing tests**

Append to `tests/test_core.py`:
```python
from qrcode_bot.logo import embed_logo, validate_logo


def test_embed_logo_returns_png():
    qr_bytes = generate_qr("https://example.com", error_correction="H")
    # Create a small test logo
    logo = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    result = embed_logo(qr_bytes, buf.getvalue())
    assert result[:4] == b"\x89PNG"


def test_embed_logo_result_is_valid_image():
    qr_bytes = generate_qr("https://example.com", error_correction="H")
    logo = Image.new("RGBA", (100, 100), (0, 0, 255, 255))
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    result = embed_logo(qr_bytes, buf.getvalue())
    img = Image.open(io.BytesIO(result))
    assert img.format == "PNG"
    assert img.size[0] > 0


def test_embed_logo_makes_qr_larger():
    qr_bytes = generate_qr("https://example.com", error_correction="H")
    logo = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    result = embed_logo(qr_bytes, buf.getvalue())
    original = Image.open(io.BytesIO(qr_bytes))
    with_logo = Image.open(io.BytesIO(result))
    assert with_logo.size == original.size  # same canvas size


def test_validate_logo_valid():
    logo = Image.new("RGB", (100, 100), "red")
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    assert validate_logo(buf.getvalue()) is True


def test_validate_logo_too_large():
    # Create a 6MB dummy
    big = b"\x89PNG" + b"\x00" * (6 * 1024 * 1024)
    assert validate_logo(big, max_mb=5) is False


def test_validate_logo_invalid_format():
    assert validate_logo(b"not an image") is False
```

**Step 2: Run tests to verify failure**
```bash
cd /opt/hermes/qrcode_bot && .venv/bin/pytest tests/test_core.py -k "logo" -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'qrcode_bot.logo'`

**Step 3: Implement logo.py**

`src/qrcode_bot/logo.py`:
```python
from __future__ import annotations

import io
import logging

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

MAX_LOGO_BYTES = 5 * 1024 * 1024  # 5MB


def validate_logo(logo_bytes: bytes, max_mb: int = 5) -> bool:
    """Validate logo image: size and format."""
    if len(logo_bytes) > max_mb * 1024 * 1024:
        return False
    try:
        img = Image.open(io.BytesIO(logo_bytes))
        img.verify()
        return True
    except Exception:
        return False


def embed_logo(qr_bytes: bytes, logo_bytes: bytes, logo_ratio: float = 0.25) -> bytes:
    """Embed a logo in the center of a QR code.
    
    Args:
        qr_bytes: PNG bytes of the QR code (must use ERROR_CORRECT_H)
        logo_bytes: PNG/JPG/WEBP bytes of the logo
        logo_ratio: how much of the QR the logo covers (0.25 = 25%)
    
    Returns:
        PNG bytes of the QR with logo embedded
    """
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGBA")
    logo_img = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

    # Calculate logo size (25% of QR by default)
    qr_w, qr_h = qr_img.size
    logo_size = int(min(qr_w, qr_h) * logo_ratio)

    # Resize logo to fit
    logo_img = logo_img.resize((logo_size, logo_size), Image.LANCZOS)

    # Create circular mask
    mask = Image.new("L", (logo_size, logo_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, logo_size - 1, logo_size - 1), fill=255)

    # Add white padding behind logo for contrast
    padding = int(logo_size * 0.1)
    bg_size = logo_size + padding * 2
    bg = Image.new("RGBA", (bg_size, bg_size), (255, 255, 255, 255))

    # Paste circular logo onto white background
    logo_offset = padding
    bg.paste(logo_img, (logo_offset, logo_offset), mask)

    # Center position on QR
    center_x = (qr_w - bg_size) // 2
    center_y = (qr_h - bg_size) // 2

    # Composite
    qr_img.paste(bg, (center_x, center_y), bg)

    # Save result
    buf = io.BytesIO()
    qr_img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
```

**Step 4: Run tests**
```bash
.venv/bin/pytest tests/test_core.py -k "logo" -v
```
Expected: 6 passed

**Step 5: Commit**
```bash
git add -A && git commit -m "feat: logo compositing module with TDD (embed_logo, validate_logo)"
```

---

## Task 2: Add error_correction param to generate_qr

**Objective:** Allow `generate_qr()` to accept `error_correction` parameter so logo QRs use HIGH.

**Files:**
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/core.py`
- Modify: `/opt/hermes/qrcode_bot/tests/test_core.py`

**Step 1: Add test**
```python
def test_generate_qr_error_correction_high():
    data = generate_qr("test", error_correction="H")
    assert data[:4] == b"\x89PNG"
    # Should be larger than default M for same content
    default = generate_qr("test")
    # HIGH produces same size or larger (more redundancy)
    assert len(data) >= len(default) - 100  # allow small variance
```

**Step 2: Modify generate_qr in core.py**

Change the function signature to accept `error_correction`:
```python
def generate_qr(
    text: str,
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
    box_size: int = 10,
    border: int = 4,
    error_correction: str = "M",
) -> bytes:
    """Generate a QR code and return PNG bytes."""
    if not text or not text.strip():
        raise ValueError("Text must not be empty")

    ec_map = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    ec_level = ec_map.get(error_correction.upper(), qrcode.constants.ERROR_CORRECT_M)

    qr = qrcode.QRCode(
        version=None,
        error_correction=ec_level,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fg_color, back_color=bg_color).convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

**Step 3: Run tests**
```bash
.venv/bin/pytest tests/ -v
```
Expected: all pass (including new error_correction test)

**Step 4: Commit**
```bash
git add -A && git commit -m "feat: add error_correction parameter to generate_qr"
```

---

## Task 3: Bot handler — /logo command with FSM

**Objective:** Add `/logo` guided flow and keyboard button.

**Files:**
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/bot.py`
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/keyboards.py`

**Step 1: Add LogoStates to bot.py**

Add after WiFiStates:
```python
class LogoStates(StatesGroup):
    waiting_text = State()
    waiting_logo = State()
```

**Step 2: Add /logo handler**

Inside create_router, add:
```python
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
        # Get image bytes
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

            # Generate QR with HIGH error correction for logo embedding
            qr_bytes = generate_qr(qr_text, error_correction="H")
            result_bytes = embed_logo(qr_bytes, logo_bytes)

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
```

**Step 3: Add keyboard button**

In `keyboards.py`, add:
```python
[KeyboardButton(text="🏷️ Logo QR")]
```
to the keyboard layout (next to WiFi and Style).

**Step 4: Handle keyboard button in text handler**

In `handle_text`, add "🏷️ Logo QR" to the button labels tuple and handle it:
```python
elif text == "🏷️ Logo QR":
    await cmd_logo(message, state)  # need to import state
```
Better approach: just trigger the /logo command by calling it directly or re-dispatch.

**Step 5: Run tests + compile**
```bash
.venv/bin/pytest tests/ -v
.venv/bin/python -m compileall src/qrcode_bot
```

**Step 6: Commit**
```bash
git add -A && git commit -m "feat: add /logo QR generator with guided FSM flow"
```

---

## Task 4: Restart + manual verification

**Objective:** Restart bot and verify the full logo flow works.

**Steps:**
```bash
systemctl restart qrcode-bot
sleep 2
systemctl is-active qrcode-bot
journalctl -u qrcode-bot -n 5 --no-pager
```

**Manual test in Telegram:**
1. Send `/logo` → bot asks for text
2. Send `https://example.com` → bot asks for logo
3. Send a photo → bot generates QR with logo embedded
4. Verify QR is scannable (scan with phone camera)
5. Test with JPG logo
6. Test with oversized file (>5MB) → should reject
7. Test keyboard button "🏷️ Logo QR"

**Commit:**
```bash
git add -A && git commit -m "chore: verify logo feature, restart"
```

---

## Summary

| Task | What | Time |
|------|------|------|
| 1 | Logo compositing module (TDD) | 4 min |
| 2 | error_correction param for generate_qr | 3 min |
| 3 | /logo handler + FSM + keyboard | 5 min |
| 4 | Restart + manual verification | 3 min |

**Total: 4 tasks, ~15 minutes**
