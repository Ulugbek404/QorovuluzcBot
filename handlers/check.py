import random
import asyncio
import re
import aiohttp
import urllib.parse
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


# ========== REAL PLAGIAT TEKSHIRUV ==========

def split_into_sentences(text: str) -> list:
    """Matnni gaplarga ajratish"""
    # Nuqta, savol belgisi, undov belgisi bo'yicha ajratish
    sentences = re.split(r'[.!?。]+', text)
    # Bo'sh va qisqa gaplarni olib tashlash (kamida 30 belgi)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 30]
    return sentences


async def search_google(session: aiohttp.ClientSession, query: str) -> dict:
    """Google orqali matn qidirish va natija olish"""
    try:
        # Google qidiruvni simulyatsiya qilish
        encoded_query = urllib.parse.quote(f'"{query}"')
        url = f"https://www.google.com/search?q={encoded_query}&num=5&hl=uz"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uz,en;q=0.5",
        }

        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                html = await response.text()

                # Natijalar sonini tekshirish
                has_results = False

                # "natija topilmadi" yoki "did not match" belgilari
                no_result_markers = [
                    "did not match any documents",
                    "No results found",
                    "natija topilmadi",
                    "Your search -",
                    "did not match",
                ]

                for marker in no_result_markers:
                    if marker.lower() in html.lower():
                        return {"found": False, "count": 0}

                # Natijalar mavjudligini tekshirish
                # Google natijalarida <div class="g"> yoki <h3> mavjud bo'lsa
                result_indicators = ['class="g"', '<h3', 'class="tF2Cxc"', 'class="LC20lb"']
                for indicator in result_indicators:
                    if indicator in html:
                        has_results = True
                        break

                if has_results:
                    # Natijalar sonini hisoblash (taxminiy)
                    count = html.count('class="g"')
                    if count == 0:
                        count = html.count('<h3')
                    return {"found": True, "count": max(count, 1)}

                return {"found": False, "count": 0}
            elif response.status == 429:
                # Too many requests — random natija
                return {"found": None, "count": 0}
            else:
                return {"found": None, "count": 0}

    except (asyncio.TimeoutError, aiohttp.ClientError, Exception):
        return {"found": None, "count": 0}


async def check_plagiat_real(text: str) -> dict:
    """
    REAL plagiat tekshiruv — Google Search orqali.

    Algoritm:
    1. Matnni gaplarga ajratish
    2. Har bir gapni Google da qidirish ("")
    3. Topilgan natijalar soniga qarab plagiat foizini hisoblash
    """
    sentences = split_into_sentences(text)

    if not sentences:
        # Gaplar juda qisqa — butun matnni tekshiring
        sentences = [text[:150]]

    # Maksimum 8 ta gapni tekshirish (Google cheklovlari uchun)
    if len(sentences) > 8:
        # Tasodifiy tanlash — turli qismlardan
        step = len(sentences) // 8
        selected = [sentences[i * step] for i in range(8)]
        sentences = selected

    total_sentences = len(sentences)
    found_count = 0
    checked_count = 0
    results_detail = []

    async with aiohttp.ClientSession() as session:
        for i, sentence in enumerate(sentences):
            # Gapni qisqartirish (Google qidiruv uchun optimal uzunlik)
            search_query = sentence[:100].strip()

            result = await search_google(session, search_query)

            if result["found"] is not None:
                checked_count += 1
                if result["found"]:
                    found_count += 1
                    results_detail.append({
                        "sentence": search_query[:60] + "...",
                        "found": True
                    })
                else:
                    results_detail.append({
                        "sentence": search_query[:60] + "...",
                        "found": False
                    })

            # Google cheklovlaridan himoya — har bir so'rov o'rtasida kutish
            if i < len(sentences) - 1:
                await asyncio.sleep(2)

    # Natijani hisoblash
    if checked_count == 0:
        # Google javobi olmadi — demo rejimga o'tish
        percent = random.uniform(15, 45)
        method = "demo"
    else:
        percent = (found_count / checked_count) * 100
        method = "google"

    return {
        "percent": round(percent, 1),
        "method": method,
        "total_sentences": total_sentences,
        "checked": checked_count,
        "found": found_count,
        "details": results_detail[:5]  # Faqat 5 ta ko'rsatish
    }


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
        "🌐 Matn internetdagi manbalar bilan taqqoslanadi.\n\n"
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
        "🌐 Matn internetdagi manbalar bilan taqqoslanmoqda...\n"
        "⏱ Bu 10-30 soniya davom etishi mumkin.",
        parse_mode="HTML"
    )

    # REAL plagiat tekshiruv
    result = await check_plagiat_real(text)
    result_percent = result["percent"]

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

    # Tekshiruv usuli
    if result["method"] == "google":
        method_text = "🌐 Google Search"
        detail_text = (
            f"\n📊 <b>Tahlil:</b>\n"
            f"   📝 Jami gaplar: {result['total_sentences']} ta\n"
            f"   🔍 Tekshirilgan: {result['checked']} ta\n"
            f"   ⚠️ Internetda topilgan: {result['found']} ta\n"
        )

        # Batafsil natijalar
        if result["details"]:
            detail_text += "\n📋 <b>Batafsil:</b>\n"
            for d in result["details"]:
                icon = "🔴" if d["found"] else "🟢"
                detail_text += f"   {icon} <i>{d['sentence']}</i>\n"
    else:
        method_text = "🔄 Demo rejim"
        detail_text = "\n⚠️ <i>Google qidiruvga ulanib bo'lmadi, demo natija ko'rsatilmoqda.</i>\n"

    await message.answer(
        f"📋 <b>Tekshiruv natijasi</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji} <b>Holat:</b> {status}\n"
        f"📊 <b>Plagiat foizi:</b> {result_percent}%\n"
        f"[{progress_bar}]\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 {comment}\n\n"
        f"🔧 <b>Tekshiruv usuli:</b> {method_text}\n"
        f"📝 <b>Matn uzunligi:</b> {len(text)} belgi\n"
        f"{detail_text}\n"
        "🔍 Yana tekshirish uchun \"🔍 Matn tekshirish\" ni bosing.",
        parse_mode="HTML"
    )

    # FSM ni tozalash, lekin login holatini saqlash
    await state.set_state(None)
    await state.update_data(logged_in=True, user_id=user["id"] if user else None)
