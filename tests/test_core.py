import io

import pytest
from PIL import Image

from qrcode_bot.core import generate_qr, generate_qr_wifi, decode_qr, parse_hex_color
from qrcode_bot.logo import embed_logo, validate_logo


# --- Generation tests ---

def test_generate_qr_returns_png_bytes():
    data = generate_qr("https://example.com")
    assert isinstance(data, bytes)
    assert data[:4] == b"\x89PNG"


def test_generate_qr_is_valid_image():
    data = generate_qr("hello world")
    img = Image.open(io.BytesIO(data))
    assert img.format == "PNG"
    assert img.size[0] > 0
    assert img.size[1] > 0


def test_generate_qr_custom_colors():
    data = generate_qr("test", fg_color="#FF0000", bg_color="#00FF00")
    img = Image.open(io.BytesIO(data)).convert("RGB")
    pixel = img.getpixel((0, 0))
    assert pixel[1] > 200  # green channel high (background)


def test_generate_qr_custom_size():
    small = generate_qr("test", box_size=5, border=1)
    large = generate_qr("test", box_size=20, border=4)
    small_img = Image.open(io.BytesIO(small))
    large_img = Image.open(io.BytesIO(large))
    assert large_img.size[0] > small_img.size[0]


def test_generate_qr_empty_text_raises():
    with pytest.raises(ValueError):
        generate_qr("")


def test_generate_qr_error_correction_high():
    data = generate_qr("test", error_correction="H")
    assert data[:4] == b"\x89PNG"


# --- WiFi QR tests ---

def test_generate_qr_wifi_wpa():
    data = generate_qr_wifi("MyNetwork", "password123", "WPA")
    assert isinstance(data, bytes)
    assert data[:4] == b"\x89PNG"


def test_generate_qr_wifi_nopass():
    data = generate_qr_wifi("OpenNetwork", "", "nopass")
    assert isinstance(data, bytes)
    img = Image.open(io.BytesIO(data))
    assert img.format == "PNG"


# --- Decode tests ---

def test_decode_qr_from_generated():
    original = "https://example.com/test?foo=bar"
    png_bytes = generate_qr(original)
    results = decode_qr(png_bytes)
    assert len(results) >= 1
    assert results[0] == original


def test_decode_qr_no_qr_returns_empty():
    img = Image.new("RGB", (200, 200), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    results = decode_qr(buf.getvalue())
    assert results == []


def test_decode_qr_invalid_image_returns_empty():
    results = decode_qr(b"not an image")
    assert results == []


# --- Color parsing tests ---

def test_parse_hex_color_valid():
    assert parse_hex_color("#FF0000") == "#FF0000"
    assert parse_hex_color("ff0000") == "#FF0000"
    assert parse_hex_color("#abc") is None  # 3-char not supported


def test_parse_hex_color_invalid():
    assert parse_hex_color("red") is None
    assert parse_hex_color("#GGGGGG") is None
    assert parse_hex_color("") is None


# --- Logo embedding tests ---

def test_embed_logo_returns_png():
    qr_bytes = generate_qr("https://example.com", error_correction="H")
    logo = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    result = embed_logo(qr_bytes, buf.getvalue())
    assert isinstance(result, bytes)
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


def test_embed_logo_preserves_canvas_size():
    qr_bytes = generate_qr("https://example.com", error_correction="H")
    logo = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    result = embed_logo(qr_bytes, buf.getvalue())
    original = Image.open(io.BytesIO(qr_bytes))
    with_logo = Image.open(io.BytesIO(result))
    assert with_logo.size == original.size


def test_validate_logo_valid():
    logo = Image.new("RGB", (100, 100), "red")
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    assert validate_logo(buf.getvalue()) is True


def test_validate_logo_too_large():
    big = b"\x89PNG" + b"\x00" * (6 * 1024 * 1024)
    assert validate_logo(big, max_mb=5) is False


def test_validate_logo_invalid_format():
    assert validate_logo(b"not an image") is False
