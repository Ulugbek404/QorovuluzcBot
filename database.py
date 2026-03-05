import aiosqlite
from datetime import datetime
from config import DATABASE_URL


async def init_db():
    """Bazani yaratish — users va check_history jadvallari"""
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
