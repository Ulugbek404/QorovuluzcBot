import os

# ===== QorovuluzcBot — Konfiguratsiya =====

# Telegram Bot Token (@BotFather dan olingan)
# Render da environment variable sifatida saqlanadi
BOT_TOKEN = os.getenv("BOT_TOKEN", "8674864315:AAH-rJax9RxlvFxGjvUmE0aaG2HQWsllZrE")

# SQLite baza fayli
DATABASE_URL = os.getenv("DATABASE_URL", "database.db")

# Admin Telegram ID lari
ADMIN_IDS = [8459647465]

# Xavfsizlik sozlamalari
MIN_PASSWORD_LENGTH = 6
MAX_LOGIN_ATTEMPTS = 3
MIN_LOGIN_LENGTH = 3
MIN_TEXT_LENGTH = 50

# Render deployment sozlamalari
# Render avtomatik PORT va RENDER_EXTERNAL_URL beradi
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}" if RENDER_EXTERNAL_URL else ""

# Ishlash rejimi: "webhook" yoki "polling"
# Render da avtomatik webhook ga o'tadi
MODE = "webhook" if RENDER_EXTERNAL_URL else "polling"
