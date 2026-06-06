from __future__ import annotations

import io
import os

from PIL import Image, ImageDraw, ImageFont


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

    font = _get_font(font_size)

    # Measure text
    temp_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    frame_h = text_h + padding * 2
    total_h = qr_h + frame_h

    result = Image.new("RGB", (qr_w, total_h), bg_color)
    result.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(result)
    text_x = (qr_w - text_w) // 2
    text_y = qr_h + padding
    draw.text((text_x, text_y), text, fill=text_color, font=font)

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

    temp_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    outer_pad = border_width + padding
    frame_h = text_h + padding * 2
    total_w = qr_w + outer_pad * 2
    total_h = qr_h + frame_h + outer_pad * 2

    result = Image.new("RGB", (total_w, total_h), bg_color)
    draw = ImageDraw.Draw(result)

    draw.rounded_rectangle(
        [(0, 0), (total_w - 1, total_h - 1)],
        radius=radius,
        outline=border_color,
        width=border_width,
    )

    result.paste(qr_img, (outer_pad, outer_pad))

    text_x = (total_w - text_w) // 2
    text_y = outer_pad + qr_h + padding
    draw.text((text_x, text_y), text, fill=text_color, font=font)

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


def _get_font(size: int):
    """Try to load a nice font, fall back to default."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
