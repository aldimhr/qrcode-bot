from __future__ import annotations

import re
import urllib.parse
from typing import Optional


def build_vcard(name: str, phone: str = "", email: str = "", org: str = "") -> str:
    """Build a vCard 3.0 string."""
    parts = ["BEGIN:VCARD", "VERSION:3.0"]

    name = name.strip()
    if name:
        parts.append(f"N:{name}")
        parts.append(f"FN:{name}")

    if phone.strip():
        parts.append(f"TEL;TYPE=CELL:{phone.strip()}")

    if email.strip():
        parts.append(f"EMAIL:{email.strip()}")

    if org.strip():
        parts.append(f"ORG:{org.strip()}")

    parts.append("END:VCARD")
    return "\n".join(parts)


def build_email(to: str, subject: str = "", body: str = "") -> str:
    """Build a mailto: URI."""
    to = to.strip()
    if not to:
        raise ValueError("Email address is required")

    params = []
    if subject.strip():
        params.append(f"subject={urllib.parse.quote(subject.strip(), safe='')}")
    if body.strip():
        params.append(f"body={urllib.parse.quote(body.strip(), safe='')}")

    query = "&".join(params)
    return f"mailto:{to}" + (f"?{query}" if query else "")


def build_phone(phone: str) -> str:
    """Build a tel: URI."""
    phone = phone.strip()
    if not phone:
        raise ValueError("Phone number is required")
    cleaned = re.sub(r"[\s\-()]", "", phone)
    if not cleaned.startswith("+") and len(cleaned) > 10:
        cleaned = "+" + cleaned
    return f"tel:{cleaned}"


def build_location(lat: float, lng: float) -> str:
    """Build a geo: URI."""
    return f"geo:{lat},{lng}"


def build_event(
    summary: str,
    dtstart: str,
    dtend: str,
    location: str = "",
    description: str = "",
) -> str:
    """Build a vCalendar VEVENT string.

    Args:
        summary: Event title
        dtstart: Start datetime in YYYYMMDDTHHMMSS format
        dtend: End datetime in YYYYMMDDTHHMMSS format
        location: Optional location
        description: Optional description
    """
    parts = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "BEGIN:VEVENT",
        f"SUMMARY:{summary.strip()}",
        f"DTSTART:{dtstart.strip()}",
        f"DTEND:{dtend.strip()}",
    ]

    if location.strip():
        parts.append(f"LOCATION:{location.strip()}")
    if description.strip():
        parts.append(f"DESCRIPTION:{description.strip()}")

    parts.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\n".join(parts)


def parse_location_text(text: str) -> Optional[tuple[float, float]]:
    """Parse lat,lng from text. Returns (lat, lng) or None."""
    text = text.strip()
    match = re.match(r"^(-?\d+\.?\d*)\s*[,]\s*(-?\d+\.?\d*)$", text)
    if match:
        lat, lng = float(match.group(1)), float(match.group(2))
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return (lat, lng)
    return None


def parse_datetime(text: str) -> Optional[str]:
    """Parse 'YYYY-MM-DD HH:MM' into 'YYYYMMDDTHHMMSS'."""
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", text.strip())
    if match:
        return f"{match[1]}{match[2]}{match[3]}T{match[4]}{match[5]}00"
    return None


def format_datetime(dt_str: str) -> str:
    """Format 'YYYYMMDDTHHMMSS' to 'YYYY-MM-DD HH:MM'."""
    if len(dt_str) == 15 and "T" in dt_str:
        return f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:8]} {dt_str[9:11]}:{dt_str[11:13]}"
    return dt_str
