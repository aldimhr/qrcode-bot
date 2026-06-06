from __future__ import annotations

import io
import re
from typing import Optional

import qrcode
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode, ZBarSymbol


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


def generate_qr_wifi(ssid: str, password: str, security: str = "WPA") -> bytes:
    """Generate a WiFi QR code. Security: WPA, WEP, or nopass."""
    def escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace('"', '\\"')

    security_upper = security.upper()
    if security_upper == "NOPASS":
        wifi_str = f"WIFI:T:nopass;S:{escape(ssid)};;"
    else:
        wifi_str = f"WIFI:T:{security_upper};S:{escape(ssid)};P:{escape(password)};;"

    return generate_qr(wifi_str)


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


def parse_hex_color(text: str) -> Optional[str]:
    """Validate and normalize a hex color string. Returns None if invalid."""
    text = text.strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", text):
        return f"#{text.upper()}"
    return None
