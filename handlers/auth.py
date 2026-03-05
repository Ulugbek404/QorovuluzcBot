import hashlib
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from config import MIN_PASSWORD_LENGTH, MIN_LOGIN_LENGTH, MAX_LOGIN_ATTEMPTS
from database import (
    add_user, get_user_by_telegram_id, get_user_by_login,
    update_last_login, increment_login_attempts, reset_login_attempts,
    block_user, check_login_exists
)

auth_router = Router()


# ========== FSM STATES ==========

class RegisterStates(StatesGroup):
    full_name = State()
    login = State()
    password = State()
    confirm_password = State()


class LoginStates(StatesGroup):
    login = State()
    password = State()


# ========== YORDAMCHI FUNKSIYALAR ==========

def hash_password(password: str) -> str:
    """Parolni SHA-256 bilan hash qilish"""
    return hashlib.sha256(password.encode()).hexdigest()


def get_main_menu_keyboard():
    """Asosiy menyu tugmalari"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔍 Matn tekshirish"),
                KeyboardButton(text="📊 Tarix"),
            ],
            [
                KeyboardButton(text="👤 Profil"),
                KeyboardButton(text="🚪 Chiqish"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyu tanlang..."
    )
    return keyboard


def get_start_keyboard():
    """Boshlang'ich menyu — Ro'yxatdan o'tish / Kirish"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Ro'yxatdan o'tish", callback_data="register"),
                InlineKeyboardButton(text="🔑 Kirish", callback_data="login"),
            ]
        ]
    )
    return keyboard


# ========== /START ==========

@auth_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Bot ishga tushirilganda"""
    await state.clear()

    user = await get_user_by_telegram_id(message.from_user.id)

    if user and user["is_active"] == 1:
        # Foydalanuvchi allaqachon ro'yxatdan o'tgan
        await message.answer(
            f"👋 Salom, <b>{user['full_name']}</b>!\n\n"
            f"Tizimga kirish uchun \"🔑 Kirish\" tugmasini bosing.\n"
            f"Yoki yangi akkaunt ochish uchun \"📝 Ro'yxatdan o'tish\" ni tanlang.",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
    elif user and user["is_active"] == 0:
        await message.answer(
            "🚫 Sizning akkauntingiz <b>bloklangan</b>.\n"
            "Admin bilan bog'laning.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "👋 <b>QorovuluzcBot</b> ga xush kelibsiz!\n\n"
            "🔎 Men sizning matnlaringizni plagiatga tekshiraman.\n\n"
            "Boshlash uchun ro'yxatdan o'ting yoki tizimga kiring:",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )


# ========== /HELP ==========

@auth_router.message(Command("help"))
async def cmd_help(message: Message):
    """Yordam buyrug'i"""
    await message.answer(
        "❓ <b>Yordam — QorovuluzcBot</b>\n\n"
        "📋 <b>Buyruqlar ro'yxati:</b>\n\n"
        "/start — 🚀 Botni ishga tushirish\n"
        "/help — ❓ Yordam va ko'rsatmalar\n"
        "/check — 🔍 Matnni plagiatga tekshirish\n"
        "/profile — 👤 Profil ma'lumotlari\n"
        "/history — 📊 Tekshiruv tarixi\n"
        "/admin — 🛠 Admin panel\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📖 <b>Qanday ishlaydi?</b>\n\n"
        "1️⃣ /start bosing → Ro'yxatdan o'ting\n"
        "2️⃣ 🔑 Tizimga kiring\n"
        "3️⃣ 🔍 \"Matn tekshirish\" ni bosing\n"
        "4️⃣ Matningizni yuboring\n"
        "5️⃣ 📊 Natijani oling!\n\n"
        "🌐 Matn internetdagi manbalar bilan taqqoslanadi.\n"
        "⏱ Tekshiruv 10-30 soniya davom etadi.\n\n"
        "💡 <b>Maslahat:</b> Uzunroq matn = aniqroq natija!",
        parse_mode="HTML"
    )


# ========== RO'YXATDAN O'TISH ==========

@auth_router.callback_query(F.data == "register")
async def start_register(callback: CallbackQuery, state: FSMContext):
    """Ro'yxatdan o'tish jarayonini boshlash"""
    await callback.answer()

    # Tekshirish: allaqachon ro'yxatdan o'tganmi?
    user = await get_user_by_telegram_id(callback.from_user.id)
    if user:
        await callback.message.answer(
            "⚠️ Siz allaqachon ro'yxatdan o'tgansiz!\n"
            "\"🔑 Kirish\" tugmasini bosing.",
            reply_markup=get_start_keyboard()
        )
        return

    await state.set_state(RegisterStates.full_name)
    await callback.message.answer(
        "📝 <b>Ro'yxatdan o'tish</b>\n\n"
        "1️⃣ To'liq ismingizni kiriting (FIO):\n\n"
        "📌 Misol: <i>Karimov Jasur Baxtiyorovich</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )


@auth_router.message(RegisterStates.full_name)
async def process_full_name(message: Message, state: FSMContext):
    """FIO qabul qilish"""
    full_name = message.text.strip()

    if len(full_name) < 3:
        await message.answer("❌ Ism juda qisqa. Kamida 3 ta belgi kiriting.")
        return

    if len(full_name) > 100:
        await message.answer("❌ Ism juda uzun. Maksimum 100 ta belgi.")
        return

    await state.update_data(full_name=full_name)
    await state.set_state(RegisterStates.login)

    await message.answer(
        "✅ Ajoyib!\n\n"
        "2️⃣ Endi <b>login</b> o'ylab toping:\n\n"
        f"📌 Faqat lotin harflari va raqamlar, kamida {MIN_LOGIN_LENGTH} belgi\n"
        "📌 Misol: <i>jasur2024</i>",
        parse_mode="HTML"
    )


@auth_router.message(RegisterStates.login)
async def process_login(message: Message, state: FSMContext):
    """Login qabul qilish va validatsiya"""
    login = message.text.strip().lower()

    # Validatsiya
    if len(login) < MIN_LOGIN_LENGTH:
        await message.answer(
            f"❌ Login kamida <b>{MIN_LOGIN_LENGTH}</b> belgidan iborat bo'lishi kerak.",
            parse_mode="HTML"
        )
        return

    if not re.match(r'^[a-z0-9_]+$', login):
        await message.answer(
            "❌ Login faqat lotin harflari, raqamlar va pastki chiziq (_) dan iborat bo'lishi kerak.",
        )
        return

    # Login bandmi?
    if await check_login_exists(login):
        await message.answer("❌ Bu login allaqachon band. Boshqa login tanlang.")
        return

    await state.update_data(login=login)
    await state.set_state(RegisterStates.password)

    await message.answer(
        "✅ Login qabul qilindi!\n\n"
        "3️⃣ Endi <b>parol</b> o'ylab toping:\n\n"
        f"📌 Kamida {MIN_PASSWORD_LENGTH} ta belgi\n"
        "🔒 Parol xavfsiz saqlanadi",
        parse_mode="HTML"
    )


@auth_router.message(RegisterStates.password)
async def process_password(message: Message, state: FSMContext):
    """Parol qabul qilish"""
    password = message.text.strip()

    if len(password) < MIN_PASSWORD_LENGTH:
        await message.answer(
            f"❌ Parol kamida <b>{MIN_PASSWORD_LENGTH}</b> belgidan iborat bo'lishi kerak.",
            parse_mode="HTML"
        )
        return

    # Parolni xotirada saqlash (hali hash qilinmaydi)
    await state.update_data(password=password)
    await state.set_state(RegisterStates.confirm_password)

    # Parol xabarini o'chirish (xavfsizlik uchun)
    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(
        "4️⃣ Parolni <b>tasdiqlang</b> — qaytadan kiriting:",
        parse_mode="HTML"
    )


@auth_router.message(RegisterStates.confirm_password)
async def process_confirm_password(message: Message, state: FSMContext):
    """Parolni tasdiqlash va bazaga yozish"""
    confirm = message.text.strip()
    data = await state.get_data()

    # Parol xabarini o'chirish
    try:
        await message.delete()
    except Exception:
        pass

    if confirm != data["password"]:
        await message.answer(
            "❌ Parollar mos kelmadi! Qaytadan kiriting:",
        )
        return

    # Bazaga yozish
    password_hash = hash_password(data["password"])
    success = await add_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=data["full_name"],
        login=data["login"],
        password_hash=password_hash
    )

    await state.clear()

    if success:
        await message.answer(
            "🎉 <b>Tabriklaymiz!</b> Ro'yxatdan muvaffaqiyatli o'tdingiz!\n\n"
            f"👤 Ism: <b>{data['full_name']}</b>\n"
            f"🔑 Login: <code>{data['login']}</code>\n\n"
            "Endi tizimga kirishingiz mumkin 👇",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Xatolik yuz berdi. Bu login yoki Telegram ID allaqachon ro'yxatda.\n"
            "Qaytadan urinib ko'ring: /start"
        )


# ========== KIRISH (LOGIN) ==========

@auth_router.callback_query(F.data == "login")
async def start_login(callback: CallbackQuery, state: FSMContext):
    """Kirish jarayonini boshlash"""
    await callback.answer()

    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.message.answer(
            "⚠️ Siz hali ro'yxatdan o'tmagansiz!\n"
            "Avval \"📝 Ro'yxatdan o'tish\" tugmasini bosing.",
            reply_markup=get_start_keyboard()
        )
        return

    if user["is_active"] == 0:
        await callback.message.answer(
            "🚫 Sizning akkauntingiz <b>bloklangan</b>.\n"
            "Admin bilan bog'laning.",
            parse_mode="HTML"
        )
        return

    await state.set_state(LoginStates.login)
    await callback.message.answer(
        "🔑 <b>Tizimga kirish</b>\n\n"
        "Loginingizni kiriting:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )


@auth_router.message(LoginStates.login)
async def process_login_input(message: Message, state: FSMContext):
    """Kirish — login qabul qilish"""
    login = message.text.strip().lower()

    await state.update_data(login_input=login)
    await state.set_state(LoginStates.password)

    await message.answer("🔒 Endi parolingizni kiriting:")


@auth_router.message(LoginStates.password)
async def process_password_input(message: Message, state: FSMContext):
    """Kirish — parol tekshirish"""
    password = message.text.strip()
    data = await state.get_data()
    login = data["login_input"]

    # Parol xabarini o'chirish
    try:
        await message.delete()
    except Exception:
        pass

    # Foydalanuvchini topish
    user = await get_user_by_login(login)

    if not user:
        await state.clear()
        await message.answer(
            "❌ Login topilmadi. Qaytadan urinib ko'ring.",
            reply_markup=get_start_keyboard()
        )
        return

    # Bloklangan?
    if user["is_active"] == 0:
        await state.clear()
        await message.answer(
            "🚫 Bu akkaunt <b>bloklangan</b>.",
            parse_mode="HTML"
        )
        return

    # Telegram ID mos kelishi kerak
    if user["telegram_id"] != message.from_user.id:
        await state.clear()
        await message.answer(
            "❌ Bu login boshqa Telegram akkauntga tegishli.",
            reply_markup=get_start_keyboard()
        )
        return

    # Parolni tekshirish
    if hash_password(password) != user["password_hash"]:
        attempts = await increment_login_attempts(user["id"])

        if attempts >= MAX_LOGIN_ATTEMPTS:
            await block_user(user["id"])
            await state.clear()
            await message.answer(
                f"🚫 <b>{MAX_LOGIN_ATTEMPTS}</b> marta noto'g'ri parol kiritildi.\n"
                "Akkauntingiz <b>bloklandi</b>. Admin bilan bog'laning.",
                parse_mode="HTML"
            )
        else:
            remaining = MAX_LOGIN_ATTEMPTS - attempts
            await message.answer(
                f"❌ Noto'g'ri parol! Qolgan urinishlar: <b>{remaining}</b>",
                parse_mode="HTML"
            )
            # Parolni qayta so'rash
            await state.set_state(LoginStates.password)
        return

    # Muvaffaqiyatli kirish!
    await reset_login_attempts(user["id"])
    await update_last_login(user["id"])
    await state.clear()

    # Sessiyani belgilash (FSM data orqali)
    await state.update_data(logged_in=True, user_id=user["id"])

    await message.answer(
        f"✅ <b>Xush kelibsiz, {user['full_name']}!</b>\n\n"
        "Quyidagi menyu orqali botdan foydalaning 👇",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )


# ========== CHIQISH (LOGOUT) ==========

@auth_router.message(F.text == "🚪 Chiqish")
async def logout(message: Message, state: FSMContext):
    """Tizimdan chiqish"""
    await state.clear()
    await message.answer(
        "👋 Tizimdan chiqdingiz.\n\n"
        "Qaytadan kirish uchun /start buyrug'ini yuboring.",
        reply_markup=ReplyKeyboardRemove()
    )
