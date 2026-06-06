# Visual Upgrades — Implementation Plan

> **For Hermes:** Execute task-by-task, commit after each.

**Goal:** Add 3 visual enhancements to QR codes: gradient colors, rounded dot modules, and text overlay inside the QR. All accessible via `/style` presets.

**Architecture:** Extend `core.py` with new style options. Gradient and rounded need custom QR rendering using PIL post-processing. Text overlay uses the logo embedding pattern. All three are "presets" users can pick from `/style` inline keyboard.

**Tech Stack:** existing qrcode + Pillow

---

## Features

| Feature | Description | How |
|---------|-------------|-----|
| Gradient QR | Top-to-bottom color gradient (e.g., blue→purple) | PIL gradient overlay on QR pixels |
| Rounded Modules | Rounded dots instead of square pixels | Custom PIL drawing with circles |
| Text Overlay | Show text/URL INSIDE the center of QR | Same as logo but with rendered text |
| Presets | Quick-pick styles via /style inline keyboard | Pre-configured color combos |

## Preset Styles

| Preset | FG | BG | Effect |
|--------|----|----|--------|
| Classic | #000000 | #FFFFFF | Default |
| Dark | #FFFFFF | #000000 | White on black |
| Ocean | gradient(#0077BE→#00D4FF) | #FFFFFF | Blue gradient |
| Sunset | gradient(#FF6B35→#FFD700) | #FFFFFF | Orange→gold gradient |
| Neon | #00FF00 | #000000 | Green on black |
| Rounded | #000000 | #FFFFFF | Rounded dot modules |

## User Flow

1. User sends `/style` → shows inline keyboard with presets + custom color option
2. User picks "🌊 Ocean" → style set, next QR uses blue gradient
3. User picks "🔵 Rounded" → rounded dot style applied
4. User can still do `/style #FF0000 #FFFFFF` for custom colors

---

## Task 1: Gradient rendering (TDD)

**Objective:** Add `apply_gradient()` function that applies a color gradient to a QR code.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/styles.py`
- Modify: `/opt/hermes/qrcode_bot/tests/test_core.py`

**styles.py:**
```python
from __future__ import annotations

import io

from PIL import Image, ImageDraw


def apply_gradient(
    qr_bytes: bytes,
    color_top: str = "#0077BE",
    color_bottom: str = "#00D4FF",
) -> bytes:
    """Apply a top-to-bottom color gradient to QR code pixels.
    
    Black pixels get replaced with the gradient. White stays white.
    """
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGBA")
    w, h = qr_img.size
    
    # Create gradient image
    gradient = Image.new("RGBA", (w, h))
    top = _hex_to_rgb(color_top)
    bottom = _hex_to_rgb(color_bottom)
    
    for y in range(h):
        ratio = y / max(h - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        for x in range(w):
            gradient.putpixel((x, y), (r, g, b, 255))
    
    # Create mask from dark pixels (the QR data)
    pixels = qr_img.load()
    mask = Image.new("L", (w, h), 0)
    mask_pixels = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r < 128 and g < 128 and b < 128:
                mask_pixels[x, y] = 255
    
    # White background
    result = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    # Paste gradient where QR pixels are dark
    result.paste(gradient, (0, 0), mask)
    
    buf = io.BytesIO()
    result.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def apply_rounded_modules(qr_bytes: bytes, scale: int = 8) -> bytes:
    """Render QR with rounded dot modules instead of squares.
    
    Uses a higher-resolution render then downscales for smooth circles.
    """
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
    w, h = qr_img.size
    
    # Detect module size by sampling the QR
    # The QR has a quiet zone (white border) then the data
    # We'll work at pixel level: find dark pixels and draw circles
    pixels = qr_img.load()
    
    # Create high-res canvas
    hr_w, hr_h = w * scale, h * scale
    result = Image.new("RGB", (hr_w, hr_h), (255, 255, 255))
    draw = ImageDraw.Draw(result)
    
    circle_r = int(scale * 0.45)  # slightly smaller than grid cell
    
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            if r < 128 and g < 128 and b < 128:
                cx = x * scale + scale // 2
                cy = y * scale + scale // 2
                draw.ellipse(
                    (cx - circle_r, cy - circle_r, cx + circle_r, cy + circle_r),
                    fill=(0, 0, 0),
                )
    
    # Downscale to original size for smooth edges
    result = result.resize((w, h), Image.LANCZOS)
    
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


def apply_text_overlay(
    qr_bytes: bytes,
    text: str,
    font_size: int = 24,
    bg_color: str = "#FFFFFF",
    text_color: str = "#000000",
) -> bytes:
    """Overlay text in the center of the QR code (uses HIGH error correction)."""
    from PIL import ImageFont
    import os
    
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGBA")
    w, h = qr_img.size
    
    # Calculate text area (about 20% of QR)
    area_w = int(w * 0.5)
    area_h = int(h * 0.15)
    
    # Center position
    x0 = (w - area_w) // 2
    y0 = (h - area_h) // 2
    
    # Draw white background for text area
    draw = ImageDraw.Draw(qr_img)
    pad = 4
    draw.rectangle(
        (x0 - pad, y0 - pad, x0 + area_w + pad, y0 + area_h + pad),
        fill=bg_color,
    )
    
    # Load font
    font = _get_font(min(font_size, area_h - 4))
    
    # Center text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    tx = x0 + (area_w - text_w) // 2
    ty = y0 + (area_h - text_h) // 2
    draw.text((tx, ty), text, fill=text_color, font=font)
    
    buf = io.BytesIO()
    qr_img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def _get_font(size: int):
    import os
    from PIL import ImageFont
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
```

**Tests (append to test_core.py):**
```python
from qrcode_bot.styles import apply_gradient, apply_rounded_modules, apply_text_overlay


def test_apply_gradient_returns_png():
    qr = generate_qr("https://example.com")
    result = apply_gradient(qr, "#FF0000", "#0000FF")
    assert result[:4] == b"\x89PNG"


def test_apply_gradient_same_size():
    qr = generate_qr("test")
    result = apply_gradient(qr)
    original = Image.open(io.BytesIO(qr))
    gradient = Image.open(io.BytesIO(result))
    assert gradient.size == original.size


def test_apply_rounded_modules_returns_png():
    qr = generate_qr("https://example.com")
    result = apply_rounded_modules(qr)
    assert result[:4] == b"\x89PNG"


def test_apply_rounded_modules_same_size():
    qr = generate_qr("test")
    result = apply_rounded_modules(qr)
    original = Image.open(io.BytesIO(qr))
    rounded = Image.open(io.BytesIO(result))
    assert rounded.size == original.size


def test_apply_text_overlay_returns_png():
    qr = generate_qr("https://example.com", error_correction="H")
    result = apply_text_overlay(qr, "example.com")
    assert result[:4] == b"\x89PNG"


def test_apply_text_overlay_same_size():
    qr = generate_qr("test", error_correction="H")
    result = apply_text_overlay(qr, "hello")
    original = Image.open(io.BytesIO(qr))
    overlaid = Image.open(io.BytesIO(result))
    assert overlaid.size == original.size
```

**Run:** `.venv/bin/pytest tests/ -v` → all pass

**Commit:** `feat: visual styles module (gradient, rounded modules, text overlay) with TDD`

---

## Task 2: Style presets in /style command

**Objective:** Add inline keyboard presets to /style command.

**Files:**
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/bot.py`

**Changes:**
1. Add `user_visual` dict to track per-user visual style (gradient, rounded, text overlay)
2. Update `/style` to show inline keyboard with presets
3. Add callback handler for style presets
4. Add `apply_user_visual()` helper that applies visual effects after frame

**Presets callback data:**
- `style:classic` — default black on white
- `style:dark` — white on black
- `style:ocean` — blue gradient
- `style:sunset` — orange→gold gradient
- `style:neon` — green on black
- `style:rounded` — rounded dot modules
- `style:custom` — prompt for custom hex colors

**Run:** compile + test

**Commit:** `feat: add visual style presets to /style command`

---

## Task 3: Wire visual effects into QR pipeline

**Objective:** Apply visual effects (gradient, rounded, text overlay) to all QR output.

**Changes:**
1. Add `apply_user_visual()` function that checks user_visual dict and applies effects
2. Call it in `apply_user_frame()` or alongside it in the QR sending flow
3. For text overlay, auto-use error_correction="H"

**Order of operations:**
1. Generate QR (with error_correction=H if text overlay enabled)
2. Apply visual effect (gradient OR rounded OR text overlay)
3. Apply frame
4. Send

**Run:** compile + test

**Commit:** `feat: wire visual effects into QR generation pipeline`

---

## Task 4: Restart + verify + push

**Steps:**
1. Compile + test
2. Restart bot
3. Verify /style shows presets
4. Commit + push

---

## Summary

| Task | What | Time |
|------|------|------|
| 1 | Visual styles module (TDD) | 5 min |
| 2 | Style presets in /style | 4 min |
| 3 | Wire visual effects into pipeline | 3 min |
| 4 | Restart + verify + push | 2 min |

**Total: 4 tasks, ~14 minutes**
