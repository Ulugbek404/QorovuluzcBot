import aiosqlite
from datetime import datetime, timedelta
from config import DATABASE_URL


async def init_db():
    """Bazani yaratish — users, check_history, subscriptions jadvallari"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                login TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                login_attempts INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                start_date TEXT DEFAULT CURRENT_TIMESTAMP,
                end_date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text_preview TEXT NOT NULL,
                result_percent REAL NOT NULL,
                checked_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.commit()
    print("✅ Database tayyor!")


# ========== USERS CRUD ==========

async def add_user(telegram_id: int, username: str, full_name: str,
                   login: str, password_hash: str) -> bool:
    """Yangi foydalanuvchi qo'shish"""
    try:
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute(
                """INSERT INTO users 
                   (telegram_id, username, full_name, login, password_hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (telegram_id, username, full_name, login, password_hash,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def get_user_by_telegram_id(telegram_id: int) -> dict | None:
    """Telegram ID bo'yicha foydalanuvchi topish"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def get_user_by_login(login: str) -> dict | None:
    """Login bo'yicha foydalanuvchi topish"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE login = ?", (login,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def update_last_login(user_id: int):
    """Oxirgi kirish vaqtini yangilash"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id)
        )
        await db.commit()


async def increment_login_attempts(user_id: int) -> int:
    """Noto'g'ri urinishlarni oshirish va hozirgi sonini qaytarish"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE users SET login_attempts = login_attempts + 1 WHERE id = ?",
            (user_id,)
        )
        await db.commit()
        async with db.execute(
            "SELECT login_attempts FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def reset_login_attempts(user_id: int):
    """Urinishlar hisoblagichini nolga tushirish"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE users SET login_attempts = 0 WHERE id = ?", (user_id,)
        )
        await db.commit()


async def block_user(user_id: int):
    """Foydalanuvchini bloklash"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?", (user_id,)
        )
        await db.commit()


async def unblock_user(user_id: int):
    """Foydalanuvchini blokdan chiqarish"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "UPDATE users SET is_active = 1 WHERE id = ?", (user_id,)
        )
        await db.commit()


async def check_login_exists(login: str) -> bool:
    """Login band yoki yo'qligini tekshirish"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        async with db.execute(
            "SELECT id FROM users WHERE login = ?", (login,)
        ) as cursor:
            return await cursor.fetchone() is not None


# ========== CHECK HISTORY CRUD ==========

async def add_check_result(user_id: int, text_preview: str, result_percent: float):
    """Tekshiruv natijasini saqlash"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            """INSERT INTO check_history (user_id, text_preview, result_percent, checked_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, text_preview[:100], result_percent,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()


async def get_check_history(user_id: int, limit: int = 10) -> list:
    """So'nggi N ta tekshiruv natijalarini olish"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM check_history 
               WHERE user_id = ? 
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ========== ADMIN FUNKSIYALARI ==========

async def get_all_users() -> list:
    """Barcha foydalanuvchilar ro'yxati (admin uchun)"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        cursor = await db.execute("""
            SELECT u.id, u.full_name, u.login, u.username, u.is_active,
                   CASE WHEN s.end_date >= date('now') THEN 1 ELSE 0 END as has_sub
            FROM users u
            LEFT JOIN subscriptions s ON u.id = s.user_id
            ORDER BY u.created_at DESC
        """)
        rows = await cursor.fetchall()
        return [{"id": r[0], "full_name": r[1], "login": r[2],
                 "username": r[3], "is_active": bool(r[4]), "has_subscription": bool(r[5])}
                for r in rows]


async def get_user_by_id(user_id: int) -> dict | None:
    """ID bo'yicha foydalanuvchi batafsil ma'lumoti (admin uchun)"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        cursor = await db.execute("""
            SELECT u.id, u.full_name, u.login, u.username, u.is_active,
                   u.created_at, u.last_login, s.end_date,
                   CASE WHEN s.end_date >= date('now') THEN 1 ELSE 0 END as has_sub,
                   COUNT(c.id) as total_checks
            FROM users u
            LEFT JOIN subscriptions s ON u.id = s.user_id
            LEFT JOIN check_history c ON u.id = c.user_id
            WHERE u.id = ?
            GROUP BY u.id
        """, (user_id,))
        r = await cursor.fetchone()
        if r:
            return {
                "id": r[0], "full_name": r[1], "login": r[2], "username": r[3],
                "is_active": bool(r[4]), "created_at": r[5], "last_login": r[6],
                "sub_end": r[7] or "—", "has_subscription": bool(r[8]), "total_checks": r[9]
            }
        return None


# ========== STATISTIKA ==========

async def get_statistics() -> dict:
    """Umumiy statistika (admin uchun)"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        today = datetime.now().date().isoformat()
        month_start = datetime.now().replace(day=1).date().isoformat()
        total = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        active = (await (await db.execute("SELECT COUNT(*) FROM users WHERE is_active=1")).fetchone())[0]
        subscribed = (await (await db.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE end_date >= date('now')"
        )).fetchone())[0]
        total_checks = (await (await db.execute("SELECT COUNT(*) FROM check_history")).fetchone())[0]
        today_checks = (await (await db.execute(
            "SELECT COUNT(*) FROM check_history WHERE date(checked_at) = ?", (today,)
        )).fetchone())[0]
        monthly_checks = (await (await db.execute(
            "SELECT COUNT(*) FROM check_history WHERE date(checked_at) >= ?", (month_start,)
        )).fetchone())[0]
        return {
            "total_users": total, "active_users": active, "blocked_users": total - active,
            "subscribed_users": subscribed, "total_checks": total_checks,
            "today_checks": today_checks, "monthly_checks": monthly_checks
        }


async def get_daily_stats() -> list:
    """Bugungi statistika soatlar bo'yicha"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        today = datetime.now().date().isoformat()
        cursor = await db.execute("""
            SELECT strftime('%H', checked_at) as hour, COUNT(*) as count
            FROM check_history WHERE date(checked_at) = ?
            GROUP BY hour ORDER BY hour
        """, (today,))
        rows = await cursor.fetchall()
        return [{"hour": int(r[0]), "count": r[1]} for r in rows]


async def get_monthly_stats() -> list:
    """Oylik statistika kunlar bo'yicha"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        month_start = datetime.now().replace(day=1).date().isoformat()
        cursor = await db.execute("""
            SELECT date(checked_at) as day, COUNT(*) as count
            FROM check_history WHERE date(checked_at) >= ?
            GROUP BY day ORDER BY day
        """, (month_start,))
        rows = await cursor.fetchall()
        return [{"day": r[0], "count": r[1]} for r in rows]


# ========== OBUNA (SUBSCRIPTION) ==========

async def add_subscription(login=None, days=30, user_id=None) -> dict:
    """Foydalanuvchiga obuna berish"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        if login:
            cursor = await db.execute("SELECT id FROM users WHERE login = ?", (login,))
            row = await cursor.fetchone()
            if not row:
                return {"success": False, "error": "Foydalanuvchi topilmadi!"}
            user_id = row[0]
        end_date = (datetime.now() + timedelta(days=days)).date().isoformat()
        await db.execute("""
            INSERT INTO subscriptions (user_id, end_date) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET end_date = ?
        """, (user_id, end_date, end_date))
        await db.commit()
        return {"success": True, "end_date": end_date}


async def remove_subscription(user_id: int):
    """Obunani olib tashlash"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_subscriptions() -> list:
    """Barcha faol obunalar ro'yxati"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        cursor = await db.execute("""
            SELECT u.full_name, u.login, s.end_date
            FROM subscriptions s JOIN users u ON u.id = s.user_id
            WHERE s.end_date >= date('now') ORDER BY s.end_date
        """)
        rows = await cursor.fetchall()
        return [{"full_name": r[0], "login": r[1], "sub_end": r[2]} for r in rows]


async def broadcast_get_all_telegram_ids() -> list:
    """Barcha faol foydalanuvchilarning Telegram ID lari (broadcast uchun)"""
    async with aiosqlite.connect(DATABASE_URL) as db:
        cursor = await db.execute("SELECT telegram_id FROM users WHERE is_active = 1")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]
