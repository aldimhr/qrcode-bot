# QR Code Bot — High-Impact UX Improvements

> **For Hermes:** Execute task-by-task directly.

**Goal:** Make the QR Code bot feel polished and frictionless by adding action buttons after generation, making keyboard buttons trigger real actions, adding cancel buttons to FSM flows, and enabling quick re-generation.

**Architecture:** Add `InlineKeyboardMarkup` with action buttons to every QR output message. Refactor keyboard button handlers to trigger actual commands. Add cancel callback to all FSM states.

**Tech Stack:** Python 3.11 + aiogram 3 + qrcode[pil]

---

### Task 1: Add action buttons after QR generation

**Objective:** Every QR code sent to the user gets inline action buttons below it.

**Files:**
- Modify: `src/qrcode_bot/keyboards.py` — add `qr_result_keyboard()` function
- Modify: `src/qrcode_bot/bot.py` — add `reply_markup=qr_result_keyboard()` to every QR output, add callback handlers for action buttons

**Step 1: Create `qr_result_keyboard()` in keyboards.py**

```python
def qr_result_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown below every generated QR code."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎨 Style", callback_data="qr:style"),
            InlineKeyboardButton(text="🖼 Frame", callback_data="qr:frame"),
        ],
        [
            InlineKeyboardButton(text="➕ Logo", callback_data="qr:logo"),
            InlineKeyboardButton(text="📤 Sticker", callback_data="qr:sticker"),
        ],
        [
            InlineKeyboardButton(text="🔄 New QR", callback_data="qr:new"),
        ],
    ])
```

**Step 2: Add callback handlers in bot.py**

```python
@router.callback_query(F.data.startswith("qr:"))
async def cb_qr_action(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    await callback.answer()
    uid = callback.from_user.id

    if action == "style":
        # Re-trigger /style inline
        await cmd_style(callback.message, state)
    elif action == "frame":
        await cmd_frame(callback.message, state)
    elif action == "logo":
        await callback.message.answer(
            "🏷️ *Logo QR Generator*\n\n"
            "Step 1/2: Send me the *text or URL* for your QR code.",
            parse_mode="Markdown",
        )
        await state.set_state(LogoStates.waiting_text)
    elif action == "sticker":
        # Get the photo from the message and convert to sticker
        if callback.message.photo:
            file_id = callback.message.photo[-1].file_id
            file = await callback.bot.get_file(file_id)
            file_bytes = await callback.bot.download_file(file.file_path)
            png_bytes = file_bytes.read() if hasattr(file_bytes, "read") else bytes(file_bytes)
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(png_bytes))
            # Resize to 512x512 for sticker
            img = img.resize((512, 512), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            sticker = BufferedInputFile(buf.getvalue(), filename="qr_sticker.png")
            await callback.message.answer_sticker(sticker)
    elif action == "new":
        await callback.message.answer("✏️ Send me any text or URL to generate a new QR code.")
```

**Step 3: Wire into all QR-sending handlers**

In `handle_text`, `_generate_location_qr`, `contact_org`, `email_body`, `phone_number`, `event_location`, `wifi_password`, `logo_image` — add `reply_markup=qr_result_keyboard()` to every `answer_photo()` call.

**Step 4: Test and verify**

```bash
cd /opt/hermes/qrcode_bot && source .venv/bin/activate
python -m pytest tests/ -q
python -m compileall src/
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat(ux): add action buttons after QR generation"
```

---

### Task 2: Make keyboard buttons trigger real actions

**Objective:** "📱 Generate QR" prompts for input, "🎨 Style" opens the preset picker directly, "📶 WiFi QR" starts the WiFi flow, etc.

**Files:**
- Modify: `src/qrcode_bot/bot.py` — update keyboard button handlers in `handle_text`

**Step 1: Update button handlers**

Replace the passive text responses with actual actions:

```python
if text == "📱 Generate QR":
    await message.answer("✏️ Send me any text or URL to generate a QR code.")
elif text == "📷 Decode QR":
    await message.answer("📷 Send me a photo containing a QR code.")
elif text == "📶 WiFi QR":
    await cmd_wifi(message, state)
elif text == "🎨 Style":
    # Show the preset picker directly (reuse cmd_style logic)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬛ Classic", callback_data="vstyle:classic"),
         InlineKeyboardButton(text="⬜ Dark", callback_data="vstyle:dark")],
        [InlineKeyboardButton(text="🌊 Ocean", callback_data="vstyle:ocean"),
         InlineKeyboardButton(text="🌅 Sunset", callback_data="vstyle:sunset")],
        [InlineKeyboardButton(text="💚 Neon", callback_data="vstyle:neon"),
         InlineKeyboardButton(text="🔵 Rounded", callback_data="vstyle:rounded")],
        [InlineKeyboardButton(text="🔤 Default", callback_data="vstyle:default")],
    ])
    await message.answer(
        "🎨 *Choose a QR Style*\n\nPick a preset or use `/style #FF0000 #FFFFFF` for custom colors.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
elif text == "💰 Donate":
    await message.answer(DONATE_TEXT, reply_markup=donation_keyboard(), parse_mode="Markdown")
elif text == "🏷️ Logo QR":
    await cmd_logo(message, state)
elif text == "📋 More Types":
    await cmd_types(message)
elif text == "🖼️ Frame":
    await cmd_frame(message, state)
elif text == "ℹ️ Help":
    await cmd_help(message)
elif text == "🔒 Privacy":
    await cmd_privacy(message)
```

**Step 2: Test**

```bash
python -m pytest tests/ -q
python -m compileall src/
```

**Step 3: Commit**

```bash
git add -A && git commit -m "feat(ux): keyboard buttons trigger real actions"
```

---

### Task 3: Add cancel button to FSM flows

**Objective:** Every multi-step flow (WiFi, Logo, Contact, Email, Phone, Location, Event, Frame custom text) shows a ❌ Cancel button. Tapping it clears state and returns to main keyboard.

**Files:**
- Modify: `src/qrcode_bot/keyboards.py` — add `cancel_keyboard()` function
- Modify: `src/qrcode_bot/bot.py` — add cancel callback handler, add cancel keyboard to all FSM prompts

**Step 1: Create `cancel_keyboard()` in keyboards.py**

```python
def cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel button for FSM flows."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])
```

**Step 2: Add cancel callback handler in bot.py**

```python
@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    await callback.message.edit_text("❌ Cancelled.")
    await callback.message.answer("What would you like to do?", reply_markup=main_reply_keyboard())
```

**Step 3: Add cancel keyboard to all FSM prompts**

In every handler that sets a state (`await state.set_state(...)`), add `reply_markup=cancel_keyboard()` to the prompt message:

- `cmd_wifi` → "Step 1/2: What is the WiFi network name?"
- `wifi_ssid` → "Step 2/2: What is the password?"
- `cmd_logo` → "Step 1/2: Send me the text or URL"
- `logo_text` → "Step 2/2: Now send me a logo image"
- `cmd_contact` → "Step 1/4: What is the full name?"
- All contact steps
- `cmd_email` → "Step 1/3: What is the recipient email?"
- All email steps
- `cmd_phone` → "Send me the phone number"
- `cmd_location` → "Send coordinates"
- `cmd_event` → "Step 1/4: What is the event title?"
- All event steps
- `cb_frame` (custom_prompt) → "Send me the custom text"

**Step 4: Test and commit**

```bash
python -m pytest tests/ -q
python -m compileall src/
git add -A && git commit -m "feat(ux): add cancel button to all FSM flows"
```

---

### Task 4: Quick "Generate another" after QR decode

**Objective:** After decoding a QR code, show a "🔄 Generate QR from this?" button that pre-fills the decoded text into a new QR generation.

**Files:**
- Modify: `src/qrcode_bot/bot.py` — update `_decode_image` to add action button, add callback handler

**Step 1: Add decode result keyboard in keyboards.py**

```python
def decode_result_keyboard(decoded_text: str) -> InlineKeyboardMarkup:
    """Buttons shown below decoded QR results."""
    # Store decoded text in callback data would be too long
    # Instead, use a flag and store in a dict
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Generate QR from this", callback_data="decode:gen")],
        [InlineKeyboardButton(text="📋 Copy text", callback_data="decode:copy")],
    ])
```

**Step 2: Store last decoded text per user**

```python
# In bot.py, module level
last_decoded: dict[int, str] = {}

# In _decode_image, after successful decode:
last_decoded[message.from_user.id] = results[0]  # or joined for multi
```

**Step 3: Add callback handler**

```python
@router.callback_query(F.data.startswith("decode:"))
async def cb_decode_action(callback: types.CallbackQuery):
    action = callback.data.split(":")[1]
    uid = callback.from_user.id
    decoded = last_decoded.get(uid)
    
    if action == "gen" and decoded:
        await callback.answer()
        style = get_user_style(uid, settings)
        png_bytes = generate_qr(decoded, **style)
        png_bytes = apply_user_frame(png_bytes, uid)
        photo = BufferedInputFile(png_bytes, filename="qr.png")
        display_text = decoded[:100] + ("..." if len(decoded) > 100 else "")
        await callback.message.answer_photo(
            photo,
            caption=f"✅ *QR Code Generated!*\n\n`{display_text}`{CHANNEL_FOOTER}",
            parse_mode="Markdown",
            reply_markup=qr_result_keyboard(),
        )
        record_generation(uid)
    elif action == "copy" and decoded:
        await callback.answer(f"📋 {decoded[:200]}", show_alert=True)
    else:
        await callback.answer("❌ No decoded text available.")
```

**Step 4: Test and commit**

```bash
python -m pytest tests/ -q
python -m compileall src/
git add -A && git commit -m "feat(ux): add quick generate-from-decode button"
```

---

### Task 5: Deploy and verify

**Objective:** Restart the bot service and verify all features work in Telegram.

**Step 1: Compile and test**

```bash
cd /opt/hermes/qrcode_bot && source .venv/bin/activate
python -m pytest tests/ -q
python -m compileall src/
```

**Step 2: Push to GitHub**

```bash
cd /opt/hermes/qrcode_bot
git push origin main
```

**Step 3: Restart service**

```bash
systemctl restart qrcode-bot.service
systemctl is-active qrcode-bot.service
```

**Step 4: Verify in Telegram**

- Send any text → QR should appear with action buttons (🎨 Style, 🖼 Frame, ➕ Logo, 📤 Sticker, 🔄 New QR)
- Tap "🎨 Style" on reply keyboard → preset picker should open directly (not text instruction)
- Start /wifi → should see ❌ Cancel button alongside the prompt
- Tap ❌ Cancel → should return to main keyboard
- Send a QR photo for decoding → decoded result should have "🔄 Generate QR from this" button
- Tap "🔄 Generate QR from this" → should generate QR from decoded text with action buttons
