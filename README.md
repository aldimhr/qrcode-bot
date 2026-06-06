# QR Code Bot 📱

A Telegram bot that generates and decodes QR codes instantly — right inside Telegram.

**Bot:** [@QRCode99_bot](https://t.me/QRCode99_bot)

## Features

- 📱 **Generate QR** — Send any text or URL → get a QR code
- 📷 **Decode QR** — Send a photo with QR → extract the text
- 📶 **WiFi QR** — `/wifi` guided flow → scannable WiFi login QR
- 🏷️ **Logo QR** — `/logo` → embed your logo in the center of a QR code
- 🎨 **Custom Colors** — `/style #FF0000 #FFFFFF` → custom QR colors
- 📱 **Inline Mode** — `@QRCode99_bot text` in any chat → instant QR
- 💝 **Telegram Stars** — `/donate` → support the bot with Stars
- 🔒 **Privacy First** — all processing in-memory, no data stored

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + feature overview |
| `/help` | Usage guide with examples |
| `/wifi` | Generate WiFi login QR code |
| `/logo` | Generate QR with your logo embedded |
| `/style` | Set QR foreground/background colors |
| `/donate` | Support the bot with Telegram Stars |
| `/privacy` | File retention policy |
| `/stats` | Admin-only usage dashboard |

## Tech Stack

- **Python 3.11** + [aiogram 3](https://docs.aiogram.dev/)
- **[qrcode](https://pypi.org/project/qrcode/)** — QR code generation
- **[Pillow](https://python-pillow.org/)** — image processing + logo compositing
- **[pyzbar](https://pypi.org/project/pyzbar/)** — QR code decoding
- **[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)** — config management

## Project Structure

```
├── pyproject.toml
├── .env.example
├── PLAN.md                  # Implementation plan
├── PLAN_LOGO.md             # Logo feature plan
├── src/
│   └── qrcode_bot/
│       ├── __init__.py
│       ├── __main__.py      # Entrypoint
│       ├── bot.py            # aiogram handlers, router setup
│       ├── config.py         # pydantic-settings, env parsing
│       ├── core.py           # Pure QR logic (generate, decode, wifi)
│       ├── donate.py         # Telegram Stars donation module
│       ├── keyboards.py      # Reply/inline keyboards
│       ├── logo.py           # Logo embedding compositing
│       └── stats.py          # JSON-backed usage statistics
└── tests/
    ├── conftest.py
    └── test_core.py          # 19 tests (generation, decoding, wifi, logo, colors)
```

## Setup

### Prerequisites

```bash
# System dependency for pyzbar
apt-get install -y libzbar0
```

### Install

```bash
git clone https://github.com/aldimhr/qrcode-bot.git
cd qrcode-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Edit .env with your bot token from @BotFather
```

```env
BOT_TOKEN=your-bot-token-here
ADMIN_IDS=your-telegram-id
```

### Run

```bash
# Development
python -m qrcode_bot

# Production (systemd)
sudo cp qrcode-bot.service /etc/systemd/system/
sudo systemctl enable --now qrcode-bot
```

### Test

```bash
pytest tests/ -v
```

## Deployment

The bot runs as a systemd service with polling mode:

```ini
[Unit]
Description=QR Code Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/hermes/qrcode_bot
ExecStart=/opt/hermes/qrcode_bot/.venv/bin/python -m qrcode_bot
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

## License

MIT

## Channel

📢 Join [@x0projects](https://t.me/x0projects) for updates & new bots
