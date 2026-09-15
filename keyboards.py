from datetime import date, timedelta, time
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import WORK_HOUR_START, WORK_HOUR_END, SLOT_STEP_HOURS, DAYS_AHEAD

# ---------- REPLY (главные меню) ----------

client_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Записаться")],
        [KeyboardButton(text="📋 Моя запись"), KeyboardButton(text="❌ Отменить запись")],
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Записи на сегодня")],
        [KeyboardButton(text="📆 Записи вперёд")],
        [KeyboardButton(text="🚫 Чёрный список")],
        [KeyboardButton(text="⚙️ Управление расписанием")],
    ],
    resize_keyboard=True
)

# ---------- INLINE: выбор даты ----------

RU_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def dates_keyboard() -> InlineKeyboardMarkup:
    today = date.today()
    buttons = []
    for i in range(DAYS_AHEAD):
        d = today + timedelta(days=i)
        label = f"{d.strftime('%d.%m')} ({RU_WEEKDAYS[d.weekday()]})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"date:{d.isoformat()}")])
    buttons.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="booking_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def times_keyboard(chosen_date_iso: str, available_slots: list) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for slot in available_slots:
        label = slot.strftime("%H:%M")
        row.append(InlineKeyboardButton(text=label, callback_data=f"time:{chosen_date_iso}:{label}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="booking_back_to_date")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_booking_keyboard(date_iso: str, time_str: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{date_iso}:{time_str}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="booking_back_to_date")],
    ])


# ---------- INLINE: отмена клиентом ----------

def cancel_confirm_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Да, отменить", callback_data=f"do_cancel:{booking_id}")],
        [InlineKeyboardButton(text="Не отменять", callback_data="keep_booking")],
    ])


# ---------- INLINE: админ управление конкретной бронью ----------

def admin_booking_actions(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Удалить бронь", callback_data=f"admin_del:{booking_id}"),
            InlineKeyboardButton(text="🚫 В ЧС", callback_data=f"admin_ban:{booking_id}"),
        ]
    ])


def admin_confirm_keyboard(action: str, target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"{action}_yes:{target_id}")],
        [InlineKeyboardButton(text="Нет", callback_data=f"{action}_no")],
    ])


def unban_keyboard(client_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Разбанить", callback_data=f"unban:{client_id}")]
    ])


# ---------- INLINE: управление расписанием ----------

SCHEDULE_DAYS_AHEAD = 30
EXTRA_HOURS_RANGE = range(6, 24)  # диапазон для добавления доп. времени


def schedule_dates_keyboard() -> InlineKeyboardMarkup:
    today = date.today()
    buttons = []
    row = []
    for i in range(SCHEDULE_DAYS_AHEAD):
        d = today + timedelta(days=i)
        label = f"{d.strftime('%d.%m')} ({RU_WEEKDAYS[d.weekday()]})"
        row.append(InlineKeyboardButton(text=label, callback_data=f"sched_date:{d.isoformat()}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def schedule_day_menu_keyboard(date_iso: str, is_closed: bool) -> InlineKeyboardMarkup:
    toggle_btn = (
        InlineKeyboardButton(text="✅ Открыть день", callback_data=f"sched_open:{date_iso}")
        if is_closed else
        InlineKeyboardButton(text="🚫 Закрыть день", callback_data=f"sched_close_ask:{date_iso}")
    )
    buttons = [[toggle_btn]]
    if not is_closed:
        buttons.append([
            InlineKeyboardButton(text="➕ Добавить время", callback_data=f"sched_add_menu:{date_iso}"),
            InlineKeyboardButton(text="❌ Убрать время", callback_data=f"sched_block_menu:{date_iso}"),
        ])
    buttons.append([
        InlineKeyboardButton(text="🗑 Отменить все записи на этот день", callback_data=f"sched_cancelall_ask:{date_iso}")
    ])
    buttons.append([InlineKeyboardButton(text="🔙 Другая дата", callback_data="sched_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def schedule_time_pick_keyboard(date_iso: str, times: list, action_prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for t in times:
        label = t.strftime("%H:%M")
        row.append(InlineKeyboardButton(text=label, callback_data=f"{action_prefix}:{date_iso}:{label}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if not times:
        buttons.append([InlineKeyboardButton(text="(нечего выбрать)", callback_data="noop")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"sched_date:{date_iso}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def schedule_confirm_keyboard(action: str, date_iso: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"{action}_yes:{date_iso}")],
        [InlineKeyboardButton(text="Нет", callback_data=f"sched_date:{date_iso}")],
    ])
