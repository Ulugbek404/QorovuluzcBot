from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram import Bot

from database import (
    get_all_users, get_user_by_id, block_user, unblock_user,
    get_statistics, get_daily_stats, get_monthly_stats,
    add_subscription, remove_subscription, get_subscriptions,
    broadcast_get_all_telegram_ids
)
from config import ADMIN_IDS

admin_router = Router()


# ====== FSM ======
class BroadcastState(StatesGroup):
    message = State()


class SubscriptionState(StatesGroup):
    user_id = State()
    days = State()


# ====== Admin tekshiruv ======
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ====== Klaviaturalar ======
def admin_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton(text="💳 Obunalar", callback_data="admin_subs"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="❌ Yopish", callback_data="admin_close"),
        ]
    ])


def users_list_keyboard(users: list, page: int = 0):
    PAGE_SIZE = 5
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_users = users[start:end]

    buttons = []
    for u in page_users:
        status = "🟢" if u["is_active"] else "🔴"
        sub = "⭐" if u["has_subscription"] else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{status}{sub} {u['full_name']} | {u['login']}",
                callback_data=f"admin_user_{u['id']}"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_users_page_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{(len(users)-1)//PAGE_SIZE+1}", callback_data="noop"))
    if end < len(users):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_users_page_{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_detail_keyboard(user_id: int, is_active: bool, has_sub: bool):
    buttons = [
        [
            InlineKeyboardButton(
                text="🔴 Bloklash" if is_active else "🟢 Blokdan chiqarish",
                callback_data=f"admin_block_{user_id}" if is_active else f"admin_unblock_{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="⭐ Obuna berish" if not has_sub else "❌ Obunani olish",
                callback_data=f"admin_give_sub_{user_id}" if not has_sub else f"admin_remove_sub_{user_id}"
            )
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_users")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stats_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Bugungi", callback_data="admin_stats_today"),
            InlineKeyboardButton(text="📆 Oylik", callback_data="admin_stats_monthly"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_main")]
    ])


def subs_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Obuna berish (ID bilan)", callback_data="admin_add_sub")],
        [InlineKeyboardButton(text="📋 Barcha obunalar", callback_data="admin_list_subs")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_main")]
    ])


# ====== /admin buyrug'i ======
@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return

    stats = await get_statistics()
    text = (
        f"🛠 <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"🟢 Faol: <b>{stats['active_users']}</b>\n"
        f"⭐ Obunali: <b>{stats['subscribed_users']}</b>\n"
        f"🔍 Bugungi tekshiruvlar: <b>{stats['today_checks']}</b>\n"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_main_keyboard())


# ====== Callback handler ======
@admin_router.callback_query(F.data == "admin_main")
async def cb_admin_main(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Ruxsat yo'q!")

    await state.clear()
    stats = await get_statistics()
    text = (
        f"🛠 <b>Admin Panel</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"🟢 Faol: <b>{stats['active_users']}</b>\n"
        f"⭐ Obunali: <b>{stats['subscribed_users']}</b>\n"
        f"🔍 Bugungi tekshiruvlar: <b>{stats['today_checks']}</b>\n"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_main_keyboard())


# ====== FOYDALANUVCHILAR ======
@admin_router.callback_query(F.data == "admin_users")
async def cb_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Ruxsat yo'q!")

    users = await get_all_users()
    if not users:
        return await call.message.edit_text("👥 Foydalanuvchilar yo'q.", reply_markup=admin_main_keyboard())

    await call.message.edit_text(
        f"👥 <b>Foydalanuvchilar</b> ({len(users)} ta)\n\n🟢 Faol | 🔴 Bloklangan | ⭐ Obunali",
        parse_mode="HTML",
        reply_markup=users_list_keyboard(users, 0)
    )


@admin_router.callback_query(F.data.startswith("admin_users_page_"))
async def cb_users_page(call: CallbackQuery):
    page = int(call.data.split("_")[-1])
    users = await get_all_users()
    await call.message.edit_reply_markup(reply_markup=users_list_keyboard(users, page))


@admin_router.callback_query(F.data.startswith("admin_user_"))
async def cb_user_detail(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Ruxsat yo'q!")

    user_id = int(call.data.split("_")[-1])
    user = await get_user_by_id(user_id)
    if not user:
        return await call.answer("Foydalanuvchi topilmadi!")

    sub_text = f"⭐ Obuna: <b>Ha</b> (tugash: {user['sub_end']})" if user["has_subscription"] else "⭐ Obuna: <b>Yo'q</b>"
    text = (
        f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
        f"📛 Ism: {user['full_name']}\n"
        f"🔑 Login: <code>{user['login']}</code>\n"
        f"📱 Telegram: @{user['username'] or 'yoq'}\n"
        f"📅 Ro'yxat: {user['created_at'][:10]}\n"
        f"🕐 Oxirgi kirish: {user['last_login'][:16] if user['last_login'] else 'Hech qachon'}\n"
        f"🔍 Tekshiruvlar: {user['total_checks']} ta\n"
        f"{'🟢 Faol' if user['is_active'] else '🔴 Bloklangan'}\n"
        f"{sub_text}"
    )
    await call.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=user_detail_keyboard(user_id, user["is_active"], user["has_subscription"])
    )


@admin_router.callback_query(F.data.startswith("admin_block_"))
async def cb_block_user(call: CallbackQuery):
    user_id = int(call.data.split("_")[-1])
    await block_user(user_id)
    await call.answer("🔴 Foydalanuvchi bloklandi!")
    user = await get_user_by_id(user_id)
    await call.message.edit_reply_markup(
        reply_markup=user_detail_keyboard(user_id, False, user["has_subscription"])
    )


@admin_router.callback_query(F.data.startswith("admin_unblock_"))
async def cb_unblock_user(call: CallbackQuery):
    user_id = int(call.data.split("_")[-1])
    await unblock_user(user_id)
    await call.answer("🟢 Foydalanuvchi blokdan chiqarildi!")
    user = await get_user_by_id(user_id)
    await call.message.edit_reply_markup(
        reply_markup=user_detail_keyboard(user_id, True, user["has_subscription"])
    )


# ====== STATISTIKA ======
@admin_router.callback_query(F.data == "admin_stats")
async def cb_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Ruxsat yo'q!")

    stats = await get_statistics()
    text = (
        f"📊 <b>Umumiy statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>\n"
        f"🟢 Faol: <b>{stats['active_users']}</b>\n"
        f"🔴 Bloklangan: <b>{stats['blocked_users']}</b>\n"
        f"⭐ Obunali: <b>{stats['subscribed_users']}</b>\n\n"
        f"🔍 Jami tekshiruvlar: <b>{stats['total_checks']}</b>\n"
        f"📅 Bugungi tekshiruvlar: <b>{stats['today_checks']}</b>\n"
        f"📆 Oylik tekshiruvlar: <b>{stats['monthly_checks']}</b>\n"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=stats_keyboard())


@admin_router.callback_query(F.data == "admin_stats_today")
async def cb_stats_today(call: CallbackQuery):
    stats = await get_daily_stats()
    if not stats:
        return await call.answer("📅 Bugun tekshiruv amalga oshirilmagan!")

    text = "📅 <b>Bugungi statistika (soatlar bo'yicha)</b>\n\n"
    for row in stats:
        bar = "▓" * min(row["count"], 20)
        text += f"<code>{row['hour']:02d}:00</code> {bar} {row['count']}\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=stats_keyboard())


@admin_router.callback_query(F.data == "admin_stats_monthly")
async def cb_stats_monthly(call: CallbackQuery):
    stats = await get_monthly_stats()
    if not stats:
        return await call.answer("📆 Bu oyda tekshiruv amalga oshirilmagan!")

    text = "📆 <b>Oylik statistika (kunlar bo'yicha)</b>\n\n"
    for row in stats:
        bar = "▓" * min(row["count"], 15)
        text += f"<code>{row['day']}</code> {bar} {row['count']}\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=stats_keyboard())


# ====== OBUNALAR ======
@admin_router.callback_query(F.data == "admin_subs")
async def cb_subs(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Ruxsat yo'q!")

    subs = await get_subscriptions()
    text = f"💳 <b>Obuna boshqaruvi</b>\n\nFaol obunalar: <b>{len(subs)}</b> ta"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=subs_keyboard())


@admin_router.callback_query(F.data == "admin_list_subs")
async def cb_list_subs(call: CallbackQuery):
    subs = await get_subscriptions()
    if not subs:
        return await call.answer("Obunali foydalanuvchilar yo'q!")

    text = "⭐ <b>Obunali foydalanuvchilar:</b>\n\n"
    for s in subs:
        text += f"• {s['full_name']} (<code>{s['login']}</code>) — {s['sub_end'][:10]} gacha\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=subs_keyboard())


@admin_router.callback_query(F.data == "admin_add_sub")
async def cb_add_sub(call: CallbackQuery, state: FSMContext):
    await state.set_state(SubscriptionState.user_id)
    await call.message.edit_text(
        "💳 <b>Obuna berish</b>\n\nFoydalanuvchi loginini kiriting:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor", callback_data="admin_subs")]
        ])
    )


@admin_router.message(SubscriptionState.user_id)
async def sub_get_login(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(login=message.text.strip())
    await state.set_state(SubscriptionState.days)
    await message.answer("📅 Necha kunlik obuna berish? (masalan: 30)")


@admin_router.message(SubscriptionState.days)
async def sub_get_days(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        days = int(message.text)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
        return

    data = await state.get_data()

    # Agar direct_user_id bo'lsa (tugma orqali)
    if "direct_user_id" in data:
        result = await add_subscription(None, days, user_id=data["direct_user_id"])
    else:
        result = await add_subscription(data["login"], days)

    await state.clear()

    if result["success"]:
        login_text = data.get("login", f"ID:{data.get('direct_user_id', '?')}")
        await message.answer(
            f"✅ <b>{login_text}</b> ga <b>{days}</b> kunlik obuna berildi!\n"
            f"Tugash sanasi: {result['end_date']}",
            parse_mode="HTML"
        )
    else:
        await message.answer(f"❌ Xato: {result['error']}")


@admin_router.callback_query(F.data.startswith("admin_give_sub_"))
async def cb_give_sub(call: CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[-1])
    await state.update_data(direct_user_id=user_id)
    await state.set_state(SubscriptionState.days)
    await call.message.edit_text(
        "📅 Necha kunlik obuna?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="7 kun", callback_data=f"sub_days_7_{user_id}")],
            [InlineKeyboardButton(text="30 kun", callback_data=f"sub_days_30_{user_id}")],
            [InlineKeyboardButton(text="90 kun", callback_data=f"sub_days_90_{user_id}")],
            [InlineKeyboardButton(text="❌ Bekor", callback_data=f"admin_user_{user_id}")],
        ])
    )


@admin_router.callback_query(F.data.startswith("sub_days_"))
async def cb_sub_days(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    days = int(parts[2])
    user_id = int(parts[3])
    result = await add_subscription(None, days, user_id=user_id)
    await state.clear()
    if result["success"]:
        await call.answer(f"✅ {days} kunlik obuna berildi!")
        user = await get_user_by_id(user_id)
        await call.message.edit_reply_markup(
            reply_markup=user_detail_keyboard(user_id, user["is_active"], True)
        )
    else:
        await call.answer(f"❌ {result['error']}")


@admin_router.callback_query(F.data.startswith("admin_remove_sub_"))
async def cb_remove_sub(call: CallbackQuery):
    user_id = int(call.data.split("_")[-1])
    await remove_subscription(user_id)
    await call.answer("❌ Obuna olib tashlandi!")
    user = await get_user_by_id(user_id)
    await call.message.edit_reply_markup(
        reply_markup=user_detail_keyboard(user_id, user["is_active"], False)
    )


# ====== BROADCAST ======
@admin_router.callback_query(F.data == "admin_broadcast")
async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Ruxsat yo'q!")

    await state.set_state(BroadcastState.message)
    await call.message.edit_text(
        "📢 <b>Broadcast xabari</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni kiriting.\n"
        "<i>(Matn, rasm, yoki hujjat yuborish mumkin)</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_main")]
        ])
    )


@admin_router.message(BroadcastState.message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    telegram_ids = await broadcast_get_all_telegram_ids()

    sent = 0
    failed = 0
    status_msg = await message.answer(f"⏳ Yuborilmoqda... 0/{len(telegram_ids)}")

    for i, tid in enumerate(telegram_ids):
        try:
            await message.copy_to(tid)
            sent += 1
        except Exception:
            failed += 1

        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(f"⏳ Yuborilmoqda... {i+1}/{len(telegram_ids)}")
            except Exception:
                pass

    await status_msg.edit_text(
        f"📢 <b>Broadcast yakunlandi!</b>\n\n"
        f"✅ Yuborildi: <b>{sent}</b> ta\n"
        f"❌ Xato: <b>{failed}</b> ta\n"
        f"📊 Jami: <b>{len(telegram_ids)}</b> ta",
        parse_mode="HTML"
    )


# ====== Yopish ======
@admin_router.callback_query(F.data == "admin_close")
async def cb_close(call: CallbackQuery):
    await call.message.delete()


@admin_router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()
