# More QR Types — Implementation Plan

> **For Hermes:** Execute task-by-task, commit after each.

**Goal:** Add guided flows for 5 new QR types: vCard (contact), Email, Phone, Location, Calendar Event. Each has its own command with FSM-based multi-step input.

**Architecture:** New `qr_types.py` module with pure functions that build QR strings for each type. Each function is testable without Telegram. Bot handlers use FSM states to collect fields step by step.

**Tech Stack:** existing qrcode + core.py, aiogram FSM for guided flows

---

## QR Type Formats

| Type | QR String Format | Command | Fields |
|------|-----------------|---------|--------|
| vCard | `BEGIN:VCARD\nVERSION:3.0\nN:Last;First\nTEL:...\nEMAIL:...\nORG:...\nEND:VCARD` | `/contact` | Name, phone, email, org |
| Email | `mailto:user@example.com?subject=...&body=...` | `/email` | To, subject, body |
| Phone | `tel:+628123456789` | `/phone` | Phone number |
| Location | `geo:-6.2088,106.8456` | `/location` | Latitude, longitude |
| Event | `BEGIN:VEVENT\nSUMMARY:...\nDTSTART:YYYYMMDDTHHMMSS\nDTEND:...\nLOCATION:...\nEND:VEVENT` | `/event` | Title, start, end, location |

## New Commands

| Command | Description |
|---------|-------------|
| `/contact` | Generate vCard QR (guided: name → phone → email → org) |
| `/email` | Generate email QR (guided: to → subject → body) |
| `/phone` | Generate phone QR (one-step: send number) |
| `/location` | Generate location QR (guided: lat,lng or send location) |
| `/event` | Generate calendar event QR (guided: title → start → end → location) |
| `/types` | Show all available QR types menu |

---

## Task 1: QR types module (TDD)

**Objective:** Create `qr_types.py` with pure functions for each QR type string builder.

**Files:**
- Create: `/opt/hermes/qrcode_bot/src/qrcode_bot/qr_types.py`
- Modify: `/opt/hermes/qrcode_bot/tests/test_core.py`

**qr_types.py:**
```python
from __future__ import annotations

import re
from typing import Optional


def build_vcard(name: str, phone: str = "", email: str = "", org: str = "") -> str:
    """Build a vCard 3.0 string."""
    parts = ["BEGIN:VCARD", "VERSION:3.0"]
    
    # Name format: Last;First
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
        params.append(f"subject={_url_encode(subject.strip())}")
    if body.strip():
        params.append(f"body={_url_encode(body.strip())}")
    
    query = "&".join(params)
    return f"mailto:{to}" + (f"?{query}" if query else "")


def build_phone(phone: str) -> str:
    """Build a tel: URI."""
    phone = phone.strip()
    if not phone:
        raise ValueError("Phone number is required")
    # Remove spaces and dashes for tel: format
    cleaned = re.sub(r"[\s\-]", "", phone)
    # Add + if missing and looks international
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
    # Match "lat,lng" or "lat lng" or "lat, lng"
    match = re.match(r"^(-?\d+\.?\d*)\s*[,]\s*(-?\d+\.?\d*)$", text)
    if match:
        lat, lng = float(match.group(1)), float(match.group(2))
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return (lat, lng)
    return None


def _url_encode(text: str) -> str:
    """Simple URL encoding for mailto params."""
    import urllib.parse
    return urllib.parse.quote(text, safe="")
```

**Tests (append to test_core.py):**
```python
from qrcode_bot.qr_types import build_vcard, build_email, build_phone, build_location, build_event, parse_location_text


def test_build_vcard_basic():
    vcard = build_vcard("John Doe", phone="+628123456789", email="john@example.com")
    assert "BEGIN:VCARD" in vcard
    assert "FN:John Doe" in vcard
    assert "TEL" in vcard
    assert "EMAIL" in vcard
    assert "END:VCARD" in vcard


def test_build_vcard_minimal():
    vcard = build_vcard("Jane")
    assert "BEGIN:VCARD" in vcard
    assert "FN:Jane" in vcard
    assert "END:VCARD" in vcard


def test_build_email_simple():
    assert build_email("test@example.com") == "mailto:test@example.com"


def test_build_email_with_subject():
    result = build_email("test@example.com", subject="Hello")
    assert result.startswith("mailto:test@example.com?")
    assert "subject=Hello" in result


def test_build_email_empty_raises():
    with pytest.raises(ValueError):
        build_email("")


def test_build_phone_basic():
    assert build_phone("+628123456789") == "tel:+628123456789"


def test_build_phone_with_spaces():
    result = build_phone("+62 812-3456-789")
    assert result == "tel:+628123456789"


def test_build_phone_empty_raises():
    with pytest.raises(ValueError):
        build_phone("")


def test_build_location():
    result = build_location(-6.2088, 106.8456)
    assert result == "geo:-6.2088,106.8456"


def test_build_event_basic():
    event = build_event("Meeting", "20260615T140000", "20260615T150000", location="Jakarta")
    assert "BEGIN:VCALENDAR" in event
    assert "SUMMARY:Meeting" in event
    assert "DTSTART:20260615T140000" in event
    assert "LOCATION:Jakarta" in event
    assert "END:VCALENDAR" in event


def test_parse_location_text_valid():
    assert parse_location_text("-6.2088,106.8456") == (-6.2088, 106.8456)
    assert parse_location_text("0,0") == (0.0, 0.0)


def test_parse_location_text_invalid():
    assert parse_location_text("hello") is None
    assert parse_location_text("999,106") is None  # lat > 90
    assert parse_location_text("") is None
```

**Run:** `.venv/bin/pytest tests/ -v` → all pass

**Commit:** `feat: QR type builders (vCard, email, phone, location, event) with TDD`

---

## Task 2: Add keyboard + /types command

**Objective:** Add a "📋 More Types" keyboard button and `/types` command that shows all available QR types.

**Files:**
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/keyboards.py`
- Modify: `/opt/hermes/qrcode_bot/src/qrcode_bot/bot.py`

**In keyboards.py — replace keyboard layout:**
```python
keyboard=[
    [KeyboardButton(text="📱 Generate QR"), KeyboardButton(text="📷 Decode QR")],
    [KeyboardButton(text="📶 WiFi QR"), KeyboardButton(text="🏷️ Logo QR")],
    [KeyboardButton(text="📋 More Types")],
    [KeyboardButton(text="🎨 Style"), KeyboardButton(text="💰 Donate")],
    [KeyboardButton(text="ℹ️ Help"), KeyboardButton(text="🔒 Privacy")],
],
```

**In bot.py — add /types handler:**
```python
@router.message(Command("types"))
async def cmd_types(message: types.Message):
    text = (
        "📋 *Available QR Types*\n\n"
        "Choose a type or use the command:\n\n"
        "📇 /contact — Contact card (vCard)\n"
        "📧 /email — Email with subject & body\n"
        "📞 /phone — Phone number\n"
        "📍 /location — GPS coordinates\n"
        "📅 /event — Calendar event\n"
        "📶 /wifi — WiFi network login\n"
        "🏷️ /logo — QR with your logo\n\n"
        "Or just send any text/URL for a quick QR!"
    )
    await message.answer(text, parse_mode="Markdown")
```

**Handle keyboard button in handle_text:**
```python
elif text == "📋 More Types":
    await cmd_types(message)
```

**Run:** compile + test

**Commit:** `feat: add /types command and More Types keyboard button`

---

## Task 3: /contact (vCard) handler

**Objective:** Guided flow for vCard QR: name → phone → email → org (optional).

**In bot.py — add ContactStates + handlers:**
```python
class ContactStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_email = State()
    waiting_org = State()


@router.message(Command("contact"))
async def cmd_contact(message: types.Message, state: FSMContext):
    await state.set_state(ContactStates.waiting_name)
    await message.answer(
        "📇 *Contact QR (vCard)*\n\n"
        "Step 1/4: What is the *full name*?",
        parse_mode="Markdown",
    )

@router.message(ContactStates.waiting_name)
async def contact_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(ContactStates.waiting_phone)
    await message.answer(
        "📞 Step 2/4: What is the *phone number*?\nSend `skip` to skip.",
        parse_mode="Markdown",
    )

@router.message(ContactStates.waiting_phone)
async def contact_phone(message: types.Message, state: FSMContext):
    phone = "" if message.text.strip().lower() == "skip" else message.text.strip()
    await state.update_data(phone=phone)
    await state.set_state(ContactStates.waiting_email)
    await message.answer(
        "📧 Step 3/4: What is the *email address*?\nSend `skip` to skip.",
        parse_mode="Markdown",
    )

@router.message(ContactStates.waiting_email)
async def contact_email(message: types.Message, state: FSMContext):
    email = "" if message.text.strip().lower() == "skip" else message.text.strip()
    await state.update_data(email=email)
    await state.set_state(ContactStates.waiting_org)
    await message.answer(
        "🏢 Step 4/4: What is the *organization/company*?\nSend `skip` to skip.",
        parse_mode="Markdown",
    )

@router.message(ContactStates.waiting_org)
async def contact_org(message: types.Message, state: FSMContext):
    data = await state.get_data()
    org = "" if message.text.strip().lower() == "skip" else message.text.strip()
    
    from qrcode_bot.qr_types import build_vcard
    vcard = build_vcard(data["name"], data["phone"], data["email"], org)
    
    style = get_user_style(message.from_user.id, settings)
    png_bytes = generate_qr(vcard, **style)
    photo = BufferedInputFile(png_bytes, filename="contact_qr.png")
    
    await message.answer_photo(
        photo,
        caption=(
            f"📇 *Contact QR*\n\n"
            f"Name: {data['name']}\n"
            f"{'Phone: ' + data['phone'] + chr(10) if data['phone'] else ''}"
            f"{'Email: ' + data['email'] + chr(10) if data['email'] else ''}"
            f"{'Org: ' + org if org else ''}"
            f"{CHANNEL_FOOTER}"
        ),
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(),
    )
    record_generation(message.from_user.id)
    await state.clear()
```

**Run:** compile + test

**Commit:** `feat: add /contact vCard QR with guided FSM flow`

---

## Task 4: /email handler

**Objective:** Guided flow for email QR: to → subject → body.

**Add EmailStates + handlers:**
```python
class EmailStates(StatesGroup):
    waiting_to = State()
    waiting_subject = State()
    waiting_body = State()


@router.message(Command("email"))
async def cmd_email(message: types.Message, state: FSMContext):
    await state.set_state(EmailStates.waiting_to)
    await message.answer(
        "📧 *Email QR*\n\n"
        "Step 1/3: What is the *recipient email address*?",
        parse_mode="Markdown",
    )

@router.message(EmailStates.waiting_to)
async def email_to(message: types.Message, state: FSMContext):
    await state.update_data(to=message.text.strip())
    await state.set_state(EmailStates.waiting_subject)
    await message.answer(
        "📝 Step 2/3: What is the *subject line*?\nSend `skip` to skip.",
        parse_mode="Markdown",
    )

@router.message(EmailStates.waiting_subject)
async def email_subject(message: types.Message, state: FSMContext):
    subject = "" if message.text.strip().lower() == "skip" else message.text.strip()
    await state.update_data(subject=subject)
    await state.set_state(EmailStates.waiting_body)
    await message.answer(
        "📄 Step 3/3: What is the *email body*?\nSend `skip` to skip.",
        parse_mode="Markdown",
    )

@router.message(EmailStates.waiting_body)
async def email_body(message: types.Message, state: FSMContext):
    data = await state.get_data()
    body = "" if message.text.strip().lower() == "skip" else message.text.strip()
    
    from qrcode_bot.qr_types import build_email
    email_str = build_email(data["to"], data["subject"], body)
    
    style = get_user_style(message.from_user.id, settings)
    png_bytes = generate_qr(email_str, **style)
    photo = BufferedInputFile(png_bytes, filename="email_qr.png")
    
    await message.answer_photo(
        photo,
        caption=(
            f"📧 *Email QR*\n\n"
            f"To: {data['to']}\n"
            f"{'Subject: ' + data['subject'] + chr(10) if data['subject'] else ''}"
            f"{CHANNEL_FOOTER}"
        ),
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(),
    )
    record_generation(message.from_user.id)
    await state.clear()
```

**Run:** compile + test

**Commit:** `feat: add /email QR with guided FSM flow`

---

## Task 5: /phone handler

**Objective:** One-step flow for phone QR.

**Add handler:**
```python
@router.message(Command("phone"))
async def cmd_phone(message: types.Message, state: FSMContext):
    await state.set_state(PhoneStates.waiting_number)
    await message.answer(
        "📞 *Phone QR*\n\n"
        "Send me the *phone number* (e.g. `+628123456789`).",
        parse_mode="Markdown",
    )

class PhoneStates(StatesGroup):
    waiting_number = State()

@router.message(PhoneStates.waiting_number)
async def phone_number(message: types.Message, state: FSMContext):
    from qrcode_bot.qr_types import build_phone
    try:
        phone_str = build_phone(message.text)
    except ValueError:
        await message.answer("❌ Please enter a valid phone number.")
        return
    
    style = get_user_style(message.from_user.id, settings)
    png_bytes = generate_qr(phone_str, **style)
    photo = BufferedInputFile(png_bytes, filename="phone_qr.png")
    
    await message.answer_photo(
        photo,
        caption=f"📞 *Phone QR*\n\n`{phone_str}`{CHANNEL_FOOTER}",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(),
    )
    record_generation(message.from_user.id)
    await state.clear()
```

**Run:** compile + test

**Commit:** `feat: add /phone QR with guided flow`

---

## Task 6: /location handler

**Objective:** Location QR — accepts text `lat,lng` or Telegram location share.

**Add handler:**
```python
class LocationStates(StatesGroup):
    waiting_coords = State()

@router.message(Command("location"))
async def cmd_location(message: types.Message, state: FSMContext):
    await state.set_state(LocationStates.waiting_coords)
    await message.answer(
        "📍 *Location QR*\n\n"
        "Send coordinates as `lat,lng` (e.g. `-6.2088,106.8456`)\n\n"
        "Or share a Telegram location 📍 and I'll use those coordinates.",
        parse_mode="Markdown",
    )

@router.message(LocationStates.waiting_coords, F.location)
async def location_from_share(message: types.Message, state: FSMContext):
    lat, lng = message.location.latitude, message.location.longitude
    await _generate_location_qr(message, state, lat, lng)

@router.message(LocationStates.waiting_coords)
async def location_from_text(message: types.Message, state: FSMContext):
    from qrcode_bot.qr_types import parse_location_text
    coords = parse_location_text(message.text)
    if not coords:
        await message.answer("❌ Invalid format. Use `lat,lng` (e.g. `-6.2088,106.8456`)")
        return
    await _generate_location_qr(message, state, coords[0], coords[1])

async def _generate_location_qr(message: types.Message, state: FSMContext, lat: float, lng: float):
    from qrcode_bot.qr_types import build_location
    geo_str = build_location(lat, lng)
    style = get_user_style(message.from_user.id, settings)
    png_bytes = generate_qr(geo_str, **style)
    photo = BufferedInputFile(png_bytes, filename="location_qr.png")
    
    await message.answer_photo(
        photo,
        caption=f"📍 *Location QR*\n\n`{geo_str}`\n[Open in Maps](https://maps.google.com/?q={lat},{lng}){CHANNEL_FOOTER}",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(),
    )
    record_generation(message.from_user.id)
    await state.clear()
```

**Run:** compile + test

**Commit:** `feat: add /location QR with text and Telegram location support`

---

## Task 7: /event handler

**Objective:** Calendar event QR: title → start → end → location (optional).

**Add EventStates + handlers:**
```python
class EventStates(StatesGroup):
    waiting_title = State()
    waiting_start = State()
    waiting_end = State()
    waiting_location = State()

@router.message(Command("event"))
async def cmd_event(message: types.Message, state: FSMContext):
    await state.set_state(EventStates.waiting_title)
    await message.answer(
        "📅 *Calendar Event QR*\n\n"
        "Step 1/4: What is the *event title*?",
        parse_mode="Markdown",
    )

@router.message(EventStates.waiting_title)
async def event_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(EventStates.waiting_start)
    await message.answer(
        "🕐 Step 2/4: When does it *start*?\n\n"
        "Format: `2026-06-15 14:00` (YYYY-MM-DD HH:MM)",
        parse_mode="Markdown",
    )

@router.message(EventStates.waiting_start)
async def event_start(message: types.Message, state: FSMContext):
    dt = _parse_datetime(message.text.strip())
    if not dt:
        await message.answer("❌ Invalid format. Use `YYYY-MM-DD HH:MM` (e.g. `2026-06-15 14:00`)")
        return
    await state.update_data(start=dt)
    await state.set_state(EventStates.waiting_end)
    await message.answer(
        "🕐 Step 3/4: When does it *end*?\n\n"
        "Format: `2026-06-15 15:00`",
        parse_mode="Markdown",
    )

@router.message(EventStates.waiting_end)
async def event_end(message: types.Message, state: FSMContext):
    dt = _parse_datetime(message.text.strip())
    if not dt:
        await message.answer("❌ Invalid format. Use `YYYY-MM-DD HH:MM`")
        return
    await state.update_data(end=dt)
    await state.set_state(EventStates.waiting_location)
    await message.answer(
        "📍 Step 4/4: Where is the *location*?\nSend `skip` to skip.",
        parse_mode="Markdown",
    )

@router.message(EventStates.waiting_location)
async def event_location(message: types.Message, state: FSMContext):
    data = await state.get_data()
    location = "" if message.text.strip().lower() == "skip" else message.text.strip()
    
    from qrcode_bot.qr_types import build_event
    event_str = build_event(data["title"], data["start"], data["end"], location)
    
    style = get_user_style(message.from_user.id, settings)
    png_bytes = generate_qr(event_str, **style)
    photo = BufferedInputFile(png_bytes, filename="event_qr.png")
    
    await message.answer_photo(
        photo,
        caption=(
            f"📅 *Event QR*\n\n"
            f"📌 {data['title']}\n"
            f"🕐 {_format_dt(data['start'])} → {_format_dt(data['end'])}\n"
            f"{'📍 ' + location if location else ''}"
            f"{CHANNEL_FOOTER}"
        ),
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard(),
    )
    record_generation(message.from_user.id)
    await state.clear()

def _parse_datetime(text: str) -> Optional[str]:
    """Parse 'YYYY-MM-DD HH:MM' into 'YYYYMMDDTHHMMSS'."""
    import re
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", text)
    if match:
        return f"{match[1]}{match[2]}{match[3]}T{match[4]}{match[5]}00"
    return None

def _format_dt(dt_str: str) -> str:
    """Format 'YYYYMMDDTHHMMSS' to 'YYYY-MM-DD HH:MM'."""
    if len(dt_str) == 15 and "T" in dt_str:
        return f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:8]} {dt_str[9:11]}:{dt_str[11:13]}"
    return dt_str
```

**Run:** compile + test

**Commit:** `feat: add /event calendar QR with guided FSM flow`

---

## Task 8: Update /help + /start + verify commands

**Objective:** Update help text and start message to mention new types. Register new commands.

**Steps:**
1. Update `/start` message to mention "📇 /contact, 📧 /email, 📞 /phone, 📍 /location, 📅 /event"
2. Update `/help` to include all new types
3. Add new BotCommands to `register_commands`
4. Compile, restart, verify "/" menu shows all commands
5. Commit + push

**Commit:** `feat: update help/start with new QR types, register all commands`

---

## Summary

| Task | What | Time |
|------|------|------|
| 1 | QR types module (TDD) | 5 min |
| 2 | Keyboard + /types command | 3 min |
| 3 | /contact vCard handler | 4 min |
| 4 | /email handler | 3 min |
| 5 | /phone handler | 2 min |
| 6 | /location handler | 3 min |
| 7 | /event handler | 4 min |
| 8 | Update help/start + commands | 3 min |

**Total: 8 tasks, ~27 minutes**
