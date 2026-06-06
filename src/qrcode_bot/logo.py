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
        qr_bytes: PNG bytes of the QR code (should use ERROR_CORRECT_H)
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
    padding = int(logo_size * 0.15)
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
