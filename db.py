from datetime import date as date_cls, time as time_cls
import aiosqlite
from config import DB_PATH

_db_path = DB_PATH


async def init_db():
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                phone TEXT,
                blacklisted INTEGER DEFAULT 0
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER REFERENCES clients(id),
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                reminder_day_sent INTEGER DEFAULT 0,
                reminder_hour_sent INTEGER DEFAULT 0
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS closed_days (
                booking_date TEXT PRIMARY KEY
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS slot_overrides (
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                action TEXT NOT NULL CHECK (action IN ('blocked', 'added')),
                PRIMARY KEY (booking_date, booking_time)
            );
        """)
        await conn.commit()


def _row_to_client(row) -> dict:
    return {
        "id": row["id"],
        "tg_id": row["tg_id"],
        "name": row["name"],
        "phone": row["phone"],
        "blacklisted": bool(row["blacklisted"]),
    }


def _row_to_booking(row) -> dict:
    d = dict(row)
    d["booking_date"] = date_cls.fromisoformat(d["booking_date"])
    d["booking_time"] = time_cls.fromisoformat(d["booking_time"])
    d["reminder_day_sent"] = bool(d["reminder_day_sent"])
    d["reminder_hour_sent"] = bool(d["reminder_hour_sent"])
    return d


# ---------- CLIENTS ----------

async def get_or_create_client(tg_id: int, name: str) -> dict:
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM clients WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        if row:
            return _row_to_client(row)
        cur = await conn.execute(
            "INSERT INTO clients (tg_id, name) VALUES (?, ?)", (tg_id, name)
        )
        await conn.commit()
        cur2 = await conn.execute("SELECT * FROM clients WHERE id = ?", (cur.lastrowid,))
        row = await cur2.fetchone()
        return _row_to_client(row)


async def is_blacklisted(tg_id: int) -> bool:
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT blacklisted FROM clients WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        return bool(row and row["blacklisted"])


async def set_blacklist(client_id: int, value: bool):
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute("UPDATE clients SET blacklisted = ? WHERE id = ?", (int(value), client_id))
        if value:
            await conn.execute(
                "UPDATE bookings SET status = 'cancelled' WHERE client_id = ? AND status = 'active'",
                (client_id,)
            )
        await conn.commit()


async def get_blacklisted_clients():
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM clients WHERE blacklisted = 1")
        rows = await cur.fetchall()
        return [_row_to_client(r) for r in rows]


# ---------- SCHEDULE MANAGEMENT ----------

async def is_day_closed(booking_date) -> bool:
    async with aiosqlite.connect(_db_path) as conn:
        cur = await conn.execute(
            "SELECT 1 FROM closed_days WHERE booking_date = ?", (booking_date.isoformat(),)
        )
        return await cur.fetchone() is not None


async def close_day(booking_date):
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO closed_days (booking_date) VALUES (?)",
            (booking_date.isoformat(),)
        )
        await conn.commit()


async def open_day(booking_date):
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute("DELETE FROM closed_days WHERE booking_date = ?", (booking_date.isoformat(),))
        await conn.commit()


async def get_slot_overrides(booking_date) -> dict:
    """Возвращает {time: 'blocked'|'added'} для конкретной даты."""
    async with aiosqlite.connect(_db_path) as conn:
        cur = await conn.execute(
            "SELECT booking_time, action FROM slot_overrides WHERE booking_date = ?",
            (booking_date.isoformat(),)
        )
        rows = await cur.fetchall()
        return {time_cls.fromisoformat(r[0]): r[1] for r in rows}


async def add_time_override(booking_date, booking_time):
    """Добавляет доп. слот. Если он ранее был заблокирован — override просто снимается."""
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO slot_overrides (booking_date, booking_time, action) VALUES (?, ?, 'added')",
            (booking_date.isoformat(), booking_time.isoformat())
        )
        await conn.commit()


async def block_time_override(booking_date, booking_time):
    """Блокирует слот (и стандартный, и ранее добавленный)."""
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO slot_overrides (booking_date, booking_time, action) VALUES (?, ?, 'blocked')",
            (booking_date.isoformat(), booking_time.isoformat())
        )
        await conn.commit()


async def clear_override(booking_date, booking_time):
    """Убирает override полностью, слот возвращается к состоянию по умолчанию."""
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute(
            "DELETE FROM slot_overrides WHERE booking_date = ? AND booking_time = ?",
            (booking_date.isoformat(), booking_time.isoformat())
        )
        await conn.commit()


async def cancel_all_bookings_for_date(booking_date) -> list:
    """Отменяет все активные записи на дату, возвращает список tg_id клиентов для уведомления."""
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            """SELECT b.id, c.tg_id AS client_tg_id FROM bookings b
               JOIN clients c ON b.client_id = c.id
               WHERE b.status = 'active' AND b.booking_date = ?""",
            (booking_date.isoformat(),)
        )
        rows = await cur.fetchall()
        await conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE status = 'active' AND booking_date = ?",
            (booking_date.isoformat(),)
        )
        await conn.commit()
        return [r["client_tg_id"] for r in rows]


# ---------- BOOKINGS ----------

async def expire_past_bookings():
    """Помечает как 'expired' активные записи, время которых уже прошло."""
    from datetime import datetime
    now = datetime.now()
    today_str = now.date().isoformat()
    now_time_str = now.time().strftime("%H:%M:%S")
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute(
            """UPDATE bookings SET status = 'expired'
               WHERE status = 'active' AND (
                   booking_date < ? OR (booking_date = ? AND booking_time <= ?)
               )""",
            (today_str, today_str, now_time_str)
        )
        await conn.commit()


async def get_booked_times(booking_date) -> list:
    async with aiosqlite.connect(_db_path) as conn:
        cur = await conn.execute(
            "SELECT booking_time FROM bookings WHERE booking_date = ? AND status = 'active'",
            (booking_date.isoformat(),)
        )
        rows = await cur.fetchall()
        return [time_cls.fromisoformat(r[0]) for r in rows]


async def get_available_slots(booking_date) -> list:
    """Возвращает отсортированный список свободных для записи time-слотов на дату,
    с учётом закрытых дней, override'ов расписания, уже забронированных слотов
    и прошедшего времени (если дата — сегодня)."""
    from datetime import datetime
    from config import WORK_HOUR_START, WORK_HOUR_END, SLOT_STEP_HOURS

    if await is_day_closed(booking_date):
        return []

    default_slots = set()
    h = WORK_HOUR_START
    while h < WORK_HOUR_END:
        default_slots.add(time_cls(hour=h))
        h += SLOT_STEP_HOURS

    overrides = await get_slot_overrides(booking_date)
    for t, action in overrides.items():
        if action == "added":
            default_slots.add(t)
        elif action == "blocked":
            default_slots.discard(t)

    taken = set(await get_booked_times(booking_date))
    available = default_slots - taken

    now = datetime.now()
    if booking_date == now.date():
        available = {t for t in available if t > now.time()}

    return sorted(available)


async def create_booking(client_id: int, booking_date, booking_time) -> dict:
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "INSERT INTO bookings (client_id, booking_date, booking_time) VALUES (?, ?, ?)",
            (client_id, booking_date.isoformat(), booking_time.isoformat())
        )
        await conn.commit()
        cur2 = await conn.execute("SELECT * FROM bookings WHERE id = ?", (cur.lastrowid,))
        row = await cur2.fetchone()
        return _row_to_booking(row)


async def get_active_booking(client_id: int):
    await expire_past_bookings()
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            """SELECT * FROM bookings WHERE client_id = ? AND status = 'active'
               ORDER BY booking_date, booking_time LIMIT 1""",
            (client_id,)
        )
        row = await cur.fetchone()
        return _row_to_booking(row) if row else None


async def cancel_booking(booking_id: int):
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        await conn.commit()


async def delete_booking(booking_id: int):
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        await conn.commit()


async def get_bookings_by_date_range(date_from, date_to=None):
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        if date_to:
            cur = await conn.execute(
                """SELECT b.*, c.name, c.phone, c.tg_id AS client_tg_id
                   FROM bookings b JOIN clients c ON b.client_id = c.id
                   WHERE b.status = 'active' AND b.booking_date BETWEEN ? AND ?
                   ORDER BY b.booking_date, b.booking_time""",
                (date_from.isoformat(), date_to.isoformat())
            )
        else:
            cur = await conn.execute(
                """SELECT b.*, c.name, c.phone, c.tg_id AS client_tg_id
                   FROM bookings b JOIN clients c ON b.client_id = c.id
                   WHERE b.status = 'active' AND b.booking_date = ?
                   ORDER BY b.booking_time""",
                (date_from.isoformat(),)
            )
        rows = await cur.fetchall()
        return [_row_to_booking(r) for r in rows]


async def get_booking_by_id(booking_id: int):
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            """SELECT b.*, c.tg_id AS client_tg_id, c.name
               FROM bookings b JOIN clients c ON b.client_id = c.id
               WHERE b.id = ?""",
            (booking_id,)
        )
        row = await cur.fetchone()
        return _row_to_booking(row) if row else None


async def get_bookings_needing_reminders():
    async with aiosqlite.connect(_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            """SELECT b.*, c.tg_id AS client_tg_id
               FROM bookings b JOIN clients c ON b.client_id = c.id
               WHERE b.status = 'active'
                 AND (b.reminder_day_sent = 0 OR b.reminder_hour_sent = 0)"""
        )
        rows = await cur.fetchall()
        return [_row_to_booking(r) for r in rows]


async def mark_reminder_sent(booking_id: int, kind: str):
    field = "reminder_day_sent" if kind == "day" else "reminder_hour_sent"
    async with aiosqlite.connect(_db_path) as conn:
        await conn.execute(f"UPDATE bookings SET {field} = 1 WHERE id = ?", (booking_id,))
        await conn.commit()
