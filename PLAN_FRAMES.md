# Custom Frames — Implementation Plan

> **For Hermes:** Execute task-by-task, commit after each.

**Goal:** Add decorative frames around QR codes with text labels like "Scan Me", "WiFi", or custom text. Makes QR codes look polished for print, posters, and marketing materials.

**Architecture:** New `frames.py` module with PIL-based frame drawing. Frame is applied after QR generation, before sending. Users set their frame style with `/frame` command, and it persists per-user (like colors). Frame is applied to ALL QR types (text, wifi, contact, logo, etc.)

**Tech Stack:** Pillow (ImageDraw, ImageFont), existing QR generation pipeline

---

## Frame Styles

| Style | Description | Preview |
|-------|-------------|---------|
| `none` | No frame (default) | Plain QR |
| `scan_me` | Bottom bar with "Scan Me" text | QR with white bar + text |
| `wifi` | Bottom bar with WiFi icon text | QR with "Connect to WiFi" |
| `custom` | Bottom bar with user's custom text | QR with any text |
| `rounded` | Rounded corner border + text | QR with rounded border |

## User Flow

1. User sends `/frame` → bot shows frame options as inline keyboard
2. User picks a style (e.g., "Scan Me") → bot confirms
3. For custom: user sends `/frame custom Your Text Here`
4. All subsequent QR codes include the frame
5. User sends `/frame off` to disable

## Integration Points

Frame is applied in a shared helper `_send_qr_with_frame()` that ALL QR-generating handlers call instead of directly sending. This ensures:
- Frame applies to text QR, wifi QR, contact QR, email QR, phone QR, location QR, event QR, logo QR
- Frame respects user's color settings
- Frame is optional (default: off)

---

## Task 1: Frames module (TDD)

**Objective:** Create `frames.py` with `apply_frame()` function.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/frames.py`
- Modify: `/opt/hermes/qrcode_bot/tests/test_core.py`

**frames.py:**
```python
from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

FRAME_STYLES = {
    "none": "",
    "scan_me": "Scan Me!",
    "wifi": "📶 Connect to WiFi",
    "custom": "",  # user provides text
}


def apply_frame(
    qr_bytes: bytes,
    text: str = "Scan Me!",
    bg_color: str = "#FFFFFF",
    text_color: str = "#000000",
    padding: int = 20,
    font_size: int = 36,
) -> bytes:
    """Apply a text frame below the QR code.
    
    Args:
        qr_bytes: PNG bytes of the QR code
        text: Text to display below the QR
        bg_color: Background color of the frame
        text_color: Text color
        padding: Padding around text in pixels
        font_size: Font size for the text
    
    Returns:
        PNG bytes of the framed QR code
    """
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
    qr_w, qr_h = qr_img.size
    
    # Try to load a good font, fall back to default
    font = _get_font(font_size)
    
    # Calculate text size
    # Use a temporary draw to measure text
    temp_img = Image.new("RGB", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Frame height = text height + padding
    frame_h = text_h + padding * 2
    
    # New image: QR + frame below
    total_h = qr_h + frame_h
    result = Image.new("RGB", (qr_w, total_h), bg_color)
    
    # Paste QR at top
    result.paste(qr_img, (0, 0))
    
    # Draw text centered in frame area
    draw = ImageDraw.Draw(result)
    text_x = (qr_w - text_w) // 2
    text_y = qr_h + padding
    draw.text((text_x, text_y), text, fill=text_color, font=font)
    
    # Save
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


def apply_rounded_frame(
    qr_bytes: bytes,
    text: str = "Scan Me!",
    border_color: str = "#000000",
    bg_color: str = "#FFFFFF",
    text_color: str = "#000000",
    radius: int = 20,
    border_width: int = 4,
    padding: int = 15,
    font_size: int = 32,
) -> bytes:
    """Apply a rounded border frame with text below."""
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
    qr_w, qr_h = qr_img.size
    
    font = _get_font(font_size)
    
    # Measure text
    temp_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Calculate dimensions
    outer_pad = border_width + padding
    frame_h = text_h + padding * 2
    total_w = qr_w + outer_pad * 2
    total_h = qr_h + frame_h + outer_pad * 2
    
    # Create canvas
    result = Image.new("RGB", (total_w, total_h), bg_color)
    draw = ImageDraw.Draw(result)
    
    # Draw rounded rectangle border
    draw.rounded_rectangle(
        [(0, 0), (total_w - 1, total_h - 1)],
        radius=radius,
        outline=border_color,
        width=border_width,
    )
    
    # Paste QR centered
    qr_x = outer_pad
    qr_y = outer_pad
    result.paste(qr_img, (qr_x, qr_y))
    
    # Draw text centered below QR
    text_x = (total_w - text_w) // 2
    text_y = qr_y + qr_h + padding
    draw.text((text_x, text_y), text, fill=text_color, font=font)
    
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


def _get_font(size: int):
    """Try to load a nice font, fall back to default."""
    import os
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
```

**Tests (append to test_core.py):**
```python
from qrcode_bot.frames import apply_frame, apply_rounded_frame


def test_apply_frame_returns_png():
    qr = generate_qr("https://example.com")
    result = apply_frame(qr, text="Scan Me!")
    assert result[:4] == b"\x89PNG"


def test_apply_frame_taller_than_original():
    qr = generate_qr("https://example.com")
    result = apply_frame(qr, text="Scan Me!")
    original = Image.open(io.BytesIO(qr))
    framed = Image.open(io.BytesIO(result))
    assert framed.size[1] > original.size[1]  # taller
    assert framed.size[0] == original.size[0]  # same width


def test_apply_frame_custom_text():
    qr = generate_qr("test")
    result = apply_frame(qr, text="Visit us at example.com")
    assert result[:4] == b"\x89PNG"


def test_apply_rounded_frame_returns_png():
    qr = generate_qr("https://example.com")
    result = apply_rounded_frame(qr, text="Scan Me!")
    assert result[:4] == b"\x89PNG"


def test_apply_rounded_frame_larger():
    qr = generate_qr("test")
    result = apply_rounded_frame(qr, text="Hello")
    original = Image.open(io.BytesIO(qr))
    framed = Image.open(io.BytesIO(result))
    assert framed.size[0] > original.size[0]  # wider (border)
    assert framed.size[1] > original.size[1]  # taller (border + text)
```

**Run:** `.venv/bin/pytest tests/ -v` → all pass

**Commit:** `feat: frames module with text and rounded border styles (TDD)`

---

## Task 2: User frame preferences

**Objective:** Store per-user frame style in memory (like user_styles).

**In bot.py — add frame state tracking:**
```python
# Per-user frame preferences (in-memory)
user_frames: dict[int, dict] = {}  # {user_id: {"style": "scan_me", "text": "Scan Me!"}}

def get_user_frame(user_id: int) -> Optional[dict]:
    return user_frames.get(user_id)
```

**Commit:** included in Task 3

---

## Task 3: /frame command + inline keyboard

**Objective:** Add /frame command with inline keyboard for style selection.

**In bot.py — add handler:**
```python
@router.message(Command("frame"))
async def cmd_frame(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) >= 3 and parts[1].lower() == "custom":
        # /frame custom Your Text Here
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
        # Set a state to catch the next message
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


class FrameStates(StatesGroup):
    waiting_text = State()

@router.message(FrameStates.waiting_text)
async def frame_custom_text(message: types.Message, state: FSMContext):
    text = message.text.strip()[:50]
    user_frames[message.from_user.id] = {"style": "custom", "text": text}
    await message.answer(
        f"🖼️ *Custom frame set!*\n\nText: `{text}`\n\nAll your QR codes will now include this frame.",
        parse_mode="Markdown",
    )
    await state.clear()
```

**Commit:** `feat: add /frame command with inline keyboard style picker`

---

## Task 4: Apply frame to all QR output

**Objective:** Create a shared helper that applies frame before sending, and wire it into all QR-generating handlers.

**In bot.py — add shared helper:**
```python
async def _send_qr(message: types.Message, qr_bytes: bytes, caption: str, user_id: int):
    """Send QR code with optional frame applied."""
    frame = get_user_frame(user_id)
    if frame:
        from qrcode_bot.frames import apply_frame, apply_rounded_frame
        if frame["style"] == "rounded":
            qr_bytes = apply_rounded_frame(qr_bytes, text=frame.get("text", "Scan Me!"))
        else:
            qr_bytes = apply_frame(qr_bytes, text=frame.get("text", "Scan Me!"))
    
    photo = BufferedInputFile(qr_bytes, filename="qr.png")
    await message.answer_photo(photo, caption=caption, parse_mode="Markdown", reply_markup=main_reply_keyboard())
```

**Then replace all `message.answer_photo(...)` calls in QR handlers with `_send_qr(...)` calls.**

This affects:
- `handle_text` (text QR)
- `wifi_password` (wifi QR)
- `contact_org` (vCard QR)
- `email_body` (email QR)
- `phone_number` (phone QR)
- `_generate_location_qr` (location QR)
- `event_location` (event QR)
- `logo_image` (logo QR)

**Run:** compile + test

**Commit:** `feat: apply frames to all QR output via shared helper`

---

## Task 5: Update keyboards + /help + commands

**Objective:** Add "🖼️ Frame" to keyboard, update help, register /frame command.

**Steps:**
1. Add KeyboardButton("🖼️ Frame") to keyboards.py
2. Handle "🖼️ Frame" in handle_text button labels
3. Add /frame to register_commands
4. Update /help to mention frames
5. Compile, restart, push

**Commit:** `feat: add frame keyboard button, update help and commands`

---

## Summary

| Task | What | Time |
|------|------|------|
| 1 | Frames module (TDD) | 4 min |
| 2 | User frame preferences | 1 min |
| 3 | /frame command + inline keyboard | 4 min |
| 4 | Apply frame to all QR output | 5 min |
| 5 | Update keyboards + /help + commands | 3 min |

**Total: 5 tasks, ~17 minutes**
