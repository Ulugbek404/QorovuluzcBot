import asyncio
import logging
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, MODE, PORT, WEBHOOK_PATH, WEBHOOK_URL
from database import init_db
from handlers import all_routers


# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


# Bot va Dispatcher yaratish
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())


# Handlerlarni registratsiya qilish
for router in all_routers:
    dp.include_router(router)


# Noma'lum xabarlar uchun catch-all handler
fallback_router = Router()

@fallback_router.message()
async def fallback_handler(message: Message):
    """Handle qilinmagan barcha xabarlar"""
    if message.text and not message.text.startswith("/"):
        await message.answer(
            "⚠️ Tushunmadim. Iltimos, menyu tugmalaridan foydalaning.\n\n"
            "Yoki /start buyrug'ini yuboring.",
        )

dp.include_router(fallback_router)


# ========== WEBHOOK REJIM (Render uchun) ==========

async def on_startup_webhook(app: web.Application):
    """Webhook rejimda bot ishga tushganda"""
    await init_db()
    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True
    )
    bot_info = await bot.get_me()
    logger.info(f"✅ Bot ishga tushdi (WEBHOOK): @{bot_info.username}")
    logger.info(f"🌐 Webhook URL: {WEBHOOK_URL}")


async def on_shutdown_webhook(app: web.Application):
    """Webhook rejimda bot to'xtaganda"""
    logger.info("🔴 Bot to'xtatildi.")
    await bot.delete_webhook()
    await bot.session.close()


async def health_check(request):
    """Render health check — bot ishlayotganini tekshirish"""
    return web.Response(text="✅ QorovuluzcBot ishlayapti!")


def run_webhook():
    """Webhook rejimda ishga tushirish (Render uchun)"""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    # Webhook handler
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup_webhook)
    app.on_shutdown.append(on_shutdown_webhook)

    logger.info(f"🚀 Webhook rejimda ishga tushirilmoqda (port: {PORT})...")
    web.run_app(app, host="0.0.0.0", port=PORT)


# ========== POLLING REJIM (Lokal uchun) ==========

async def on_startup_polling(bot: Bot):
    """Polling rejimda bot ishga tushganda"""
    await init_db()
    # Webhook ni tozalash (agar avval webhook ishlagan bo'lsa)
    await bot.delete_webhook(drop_pending_updates=True)
    bot_info = await bot.get_me()
    logger.info(f"✅ Bot ishga tushdi (POLLING): @{bot_info.username}")
    logger.info(f"📛 Bot nomi: {bot_info.first_name}")
    logger.info("🔄 Polling boshlandi...")


async def on_shutdown_polling(bot: Bot):
    """Polling rejimda bot to'xtaganda"""
    logger.info("🔴 Bot to'xtatildi.")


async def run_polling():
    """Polling rejimda ishga tushirish (lokal uchun)"""
    dp.startup.register(on_startup_polling)
    dp.shutdown.register(on_shutdown_polling)

    logger.info("🚀 Polling rejimda ishga tushirilmoqda...")
    await dp.start_polling(bot)


# ========== ASOSIY ISHGA TUSHIRISH ==========

if __name__ == "__main__":
    logger.info(f"📌 Ishlash rejimi: {MODE}")

    if MODE == "webhook":
        run_webhook()
    else:
        try:
            asyncio.run(run_polling())
        except KeyboardInterrupt:
            logger.info("👋 Bot foydalanuvchi tomonidan to'xtatildi.")
