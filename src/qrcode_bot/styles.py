from __future__ import annotations

import io
import os

from PIL import Image, ImageDraw, ImageFont


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
    """Render QR with rounded dot modules instead of squares."""
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
    w, h = qr_img.size

    pixels = qr_img.load()

    # Create high-res canvas
    hr_w, hr_h = w * scale, h * scale
    result = Image.new("RGB", (hr_w, hr_h), (255, 255, 255))
    draw = ImageDraw.Draw(result)

    circle_r = int(scale * 0.45)

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
    """Overlay text in the center of the QR code."""
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGBA")
    w, h = qr_img.size

    # Text area: ~50% width, ~15% height
    area_w = int(w * 0.5)
    area_h = int(h * 0.15)

    x0 = (w - area_w) // 2
    y0 = (h - area_h) // 2

    # White background for text area
    draw = ImageDraw.Draw(qr_img)
    pad = 6
    draw.rectangle(
        (x0 - pad, y0 - pad, x0 + area_w + pad, y0 + area_h + pad),
        fill=bg_color,
    )

    font = _get_font(min(font_size, area_h - 4))

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
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
