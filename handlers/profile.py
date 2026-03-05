from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database import get_user_by_telegram_id, get_check_history

profile_router = Router()


# ========== YORDAMCHI ==========

async def get_logged_in_user(message: Message, state: FSMContext) -> dict | None:
    """Foydalanuvchi tizimga kirganligini tekshirish"""
    data = await state.get_data()
    if not data.get("logged_in"):
        await message.answer(
            "⚠️ Avval tizimga kiring!\n"
            "👉 /start buyrug'ini yuboring."
        )
        return None

    user = await get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi. /start buyrug'ini yuboring.")
        return None

    return user


# ========== PROFIL ==========

@profile_router.message(F.text == "👤 Profil")
async def show_profile(message: Message, state: FSMContext):
    """Foydalanuvchi profilini ko'rsatish"""
    user = await get_logged_in_user(message, state)
    if not user:
        return

    status = "✅ Faol" if user["is_active"] == 1 else "🚫 Bloklangan"
    last_login = user["last_login"] or "Hali kirmagan"

    await message.answer(
        "👤 <b>Sizning profilingiz</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 <b>Ism:</b> {user['full_name']}\n"
        f"🔑 <b>Login:</b> <code>{user['login']}</code>\n"
        f"📊 <b>Holat:</b> {status}\n"
        f"📅 <b>Ro'yxatdan o'tgan:</b> {user['created_at']}\n"
        f"🕐 <b>Oxirgi kirish:</b> {last_login}\n"
        "━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )


# ========== TARIX ==========

@profile_router.message(F.text == "📊 Tarix")
async def show_history(message: Message, state: FSMContext):
    """Tekshiruv tarixini ko'rsatish"""
    user = await get_logged_in_user(message, state)
    if not user:
        return

    history = await get_check_history(user["id"])

    if not history:
        await message.answer(
            "📊 <b>Tekshiruv tarixi</b>\n\n"
            "📭 Hali hech qanday tekshiruv amalga oshirilmagan.\n\n"
            "\"🔍 Matn tekshirish\" tugmasini bosib boshlang!",
            parse_mode="HTML"
        )
        return

    text = "📊 <b>Tekshiruv tarixi</b> (so'nggi 10 ta)\n\n"

    for i, item in enumerate(history, 1):
        percent = item["result_percent"]

        # Natija bo'yicha emoji
        if percent < 20:
            emoji = "🟢"  # Original
        elif percent < 50:
            emoji = "🟡"  # O'rtacha
        else:
            emoji = "🔴"  # Plagiat

        preview = item["text_preview"][:50]
        if len(item["text_preview"]) > 50:
            preview += "..."

        text += (
            f"<b>{i}.</b> {emoji} <b>{percent:.1f}%</b> plagiat\n"
            f"   📝 <i>{preview}</i>\n"
            f"   🕐 {item['checked_at']}\n\n"
        )

    text += (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🟢 0-20% — Original\n"
        "🟡 20-50% — O'rtacha\n"
        "🔴 50%+ — Plagiat aniqlandi"
    )

    await message.answer(text, parse_mode="HTML")
