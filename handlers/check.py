import random
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import MIN_TEXT_LENGTH
from database import get_user_by_telegram_id, add_check_result

check_router = Router()


# ========== FSM STATES ==========

class CheckStates(StatesGroup):
    waiting_text = State()


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


async def check_plagiat_demo(text: str) -> float:
    """
    DEMO plagiat tekshiruv — random natija qaytaradi.
    
    TODO: Real API bilan almashtirilishi kerak:
    - SherlockReport API
    - AntiPlagiat.uz API
    - Copyscape API
    
    async def check_plagiat_api(text: str) -> float:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://API_URL/check",
                json={"text": text, "api_key": API_KEY}
            ) as response:
                data = await response.json()
                return data["plagiat_percent"]
    """
    # Demo: matn uzunligiga qarab biroz realroq natija
    base = random.uniform(10, 85)

    # Uzunroq matnlar — biroz pastroq plagiat (real hayotda shunday)
    length_factor = max(0.7, 1 - len(text) / 5000)
    result = base * length_factor

    return round(result, 1)


# ========== MATN TEKSHIRISH ==========

@check_router.message(F.text == "🔍 Matn tekshirish")
async def start_check(message: Message, state: FSMContext):
    """Plagiat tekshiruvini boshlash"""
    user = await get_logged_in_user(message, state)
    if not user:
        return

    # FSM ga o'tish, lekin logged_in holatini saqlash
    current_data = await state.get_data()
    await state.set_state(CheckStates.waiting_text)
    await state.update_data(**current_data)

    await message.answer(
        "🔍 <b>Plagiat tekshiruv</b>\n\n"
        "Tekshirmoqchi bo'lgan matningizni yuboring.\n\n"
        f"📌 Kamida <b>{MIN_TEXT_LENGTH}</b> belgili matn kiriting.\n"
        "📌 Matnni to'liq yuboring — qisqa matnlar noto'g'ri natija berishi mumkin.\n\n"
        "❌ Bekor qilish uchun /start bosing.",
        parse_mode="HTML"
    )


@check_router.message(CheckStates.waiting_text)
async def process_text_check(message: Message, state: FSMContext):
    """Matnni qabul qilish va tekshirish"""
    text = message.text

    if not text:
        await message.answer("❌ Faqat matn yuboring (rasm, sticker emas).")
        return

    text = text.strip()

    if len(text) < MIN_TEXT_LENGTH:
        await message.answer(
            f"❌ Matn juda qisqa! Kamida <b>{MIN_TEXT_LENGTH}</b> belgi kerak.\n"
            f"📊 Sizning matn: <b>{len(text)}</b> belgi.\n\n"
            "Uzunroq matn yuboring:",
            parse_mode="HTML"
        )
        return

    # Kutish xabari
    wait_msg = await message.answer(
        "⏳ <b>Tekshirilmoqda...</b>\n\n"
        "🔄 Matn tahlil qilinmoqda, biroz kuting...",
        parse_mode="HTML"
    )

    # Plagiat tekshiruv (DEMO)
    result_percent = await check_plagiat_demo(text)

    # Natijaga qarab xabar
    if result_percent < 20:
        emoji = "🟢"
        status = "ORIGINAL"
        comment = "Matn original ko'rinmoqda. Ajoyib natija! 🎉"
    elif result_percent < 50:
        emoji = "🟡"
        status = "O'RTACHA"
        comment = "Ba'zi o'xshashliklar aniqlandi. Matnni qayta ishlashni tavsiya qilamiz."
    elif result_percent < 75:
        emoji = "🔴"
        status = "PLAGIAT ANIQLANDI"
        comment = "Sezilarli darajada o'xshashlik topildi. Matnni qaytadan yozing."
    else:
        emoji = "🚨"
        status = "YUQORI PLAGIAT"
        comment = "Juda yuqori o'xshashlik! Matn to'liq qayta yozilishi kerak."

    # Natijani bazaga saqlash
    data = await state.get_data()
    user = await get_user_by_telegram_id(message.from_user.id)
    if user:
        await add_check_result(
            user_id=user["id"],
            text_preview=text[:100],
            result_percent=result_percent
        )

    # Kutish xabarini o'chirish
    try:
        await wait_msg.delete()
    except Exception:
        pass

    # Progress bar yasash
    filled = int(result_percent / 10)
    empty = 10 - filled
    progress_bar = "█" * filled + "░" * empty

    await message.answer(
        f"📋 <b>Tekshiruv natijasi</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji} <b>Holat:</b> {status}\n"
        f"📊 <b>Plagiat foizi:</b> {result_percent}%\n"
        f"[{progress_bar}]\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 {comment}\n\n"
        f"📝 <b>Matn uzunligi:</b> {len(text)} belgi\n"
        f"📌 <i>Matn preview:</i> {text[:80]}...\n\n"
        "🔍 Yana tekshirish uchun \"🔍 Matn tekshirish\" ni bosing.",
        parse_mode="HTML"
    )

    # FSM ni tozalash, lekin login holatini saqlash
    await state.set_state(None)
    # logged_in holatini saqlash
    await state.update_data(logged_in=True, user_id=user["id"] if user else None)
