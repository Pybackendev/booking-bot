from datetime import date, time as time_cls, timedelta, datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

import db
from config import ADMIN_IDS
from keyboards import (
    admin_menu, admin_booking_actions, admin_confirm_keyboard, unban_keyboard,
    schedule_dates_keyboard, schedule_day_menu_keyboard, schedule_time_pick_keyboard,
    schedule_confirm_keyboard, EXTRA_HOURS_RANGE
)

router = Router()


async def _admin_only(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


def _format_booking_line(b: dict) -> str:
    return (
        f"👤 {b['name'] or 'без имени'}\n"
        f"📅 {b['booking_date'].strftime('%d.%m')} 🕐 {b['booking_time'].strftime('%H:%M')}"
    )


@router.message(F.text == "📋 Записи на сегодня")
async def bookings_today(message: Message):
    if not await _admin_only(message):
        return
    bookings = await db.get_bookings_by_date_range(date.today())
    if not bookings:
        await message.answer("На сегодня записей нет.")
        return
    await message.answer(f"📋 Записи на сегодня ({len(bookings)}):")
    for b in bookings:
        await message.answer(_format_booking_line(b), reply_markup=admin_booking_actions(b["id"]))


@router.message(F.text == "📆 Записи вперёд")
async def bookings_upcoming(message: Message):
    if not await _admin_only(message):
        return
    today = date.today()
    bookings = await db.get_bookings_by_date_range(today, today + timedelta(days=14))
    if not bookings:
        await message.answer("Ближайших записей нет.")
        return
    await message.answer(f"📆 Записи на ближайшие 14 дней ({len(bookings)}):")
    for b in bookings:
        await message.answer(_format_booking_line(b), reply_markup=admin_booking_actions(b["id"]))


@router.message(F.text == "🚫 Чёрный список")
async def blacklist_view(message: Message):
    if not await _admin_only(message):
        return
    clients = await db.get_blacklisted_clients()
    if not clients:
        await message.answer("Чёрный список пуст.")
        return
    await message.answer(f"🚫 В чёрном списке ({len(clients)}):")
    for c in clients:
        await message.answer(f"👤 {c['name'] or 'без имени'}", reply_markup=unban_keyboard(c["id"]))


# ---------- действия с конкретной бронью ----------

@router.callback_query(F.data.startswith("admin_del:"))
async def ask_delete(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        callback.message.text + "\n\n❗ Точно удалить эту бронь?",
        reply_markup=admin_confirm_keyboard("del", booking_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_yes:"))
async def confirm_delete(callback: CallbackQuery, bot: Bot):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking_by_id(booking_id)
    await db.delete_booking(booking_id)
    await callback.message.edit_text("✅ Бронь удалена.")
    if booking:
        try:
            await bot.send_message(
                booking["client_tg_id"],
                f"⚠️ Ваша запись на {booking['booking_date'].strftime('%d.%m')} "
                f"в {booking['booking_time'].strftime('%H:%M')} была отменена администратором."
            )
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data == "del_no")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban:"))
async def ask_ban(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        callback.message.text + "\n\n❗ Добавить клиента в чёрный список? Все его записи будут отменены.",
        reply_markup=admin_confirm_keyboard("ban", booking_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ban_yes:"))
async def confirm_ban(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking_by_id(booking_id)
    if booking:
        await db.set_blacklist(booking["client_id"], True)
    await callback.message.edit_text("🚫 Клиент добавлен в чёрный список.")
    await callback.answer()


@router.callback_query(F.data == "ban_no")
async def cancel_ban(callback: CallbackQuery):
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("unban:"))
async def unban_client(callback: CallbackQuery):
    client_id = int(callback.data.split(":")[1])
    await db.set_blacklist(client_id, False)
    await callback.message.edit_text("✅ Клиент разбанен.")
    await callback.answer()


async def show_admin_menu(message: Message):
    await message.answer("👨‍💼 Админ-панель", reply_markup=admin_menu)


# ---------- управление расписанием ----------

async def _render_day_menu(message_or_callback, date_iso: str, edit: bool = False):
    chosen_date = date.fromisoformat(date_iso)
    is_closed = await db.is_day_closed(chosen_date)
    bookings = await db.get_bookings_by_date_range(chosen_date)

    status_line = "🚫 День закрыт для записи" if is_closed else "✅ День открыт для записи"
    text = (
        f"⚙️ Расписание на {chosen_date.strftime('%d.%m')}\n\n"
        f"{status_line}\n"
        f"Активных записей клиентов: {len(bookings)}"
    )
    keyboard = schedule_day_menu_keyboard(date_iso, is_closed)

    target = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    if edit:
        await target.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


@router.message(F.text == "⚙️ Управление расписанием")
async def schedule_menu(message: Message):
    if not await _admin_only(message):
        return
    await message.answer("Выбери дату для управления 📅", reply_markup=schedule_dates_keyboard())


@router.callback_query(F.data.startswith("sched_date:"))
async def schedule_pick_date(callback: CallbackQuery):
    date_iso = callback.data.split(":", 1)[1]
    await _render_day_menu(callback, date_iso, edit=True)
    await callback.answer()


@router.callback_query(F.data == "sched_back")
async def schedule_back(callback: CallbackQuery):
    await callback.message.edit_text("Выбери дату для управления 📅", reply_markup=schedule_dates_keyboard())
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()


# ---------- закрыть / открыть день ----------

@router.callback_query(F.data.startswith("sched_close_ask:"))
async def schedule_close_ask(callback: CallbackQuery):
    date_iso = callback.data.split(":", 1)[1]
    chosen_date = date.fromisoformat(date_iso)
    await callback.message.edit_text(
        f"Закрыть {chosen_date.strftime('%d.%m')} для новых записей?\n"
        f"(уже существующие записи клиентов останутся активными)",
        reply_markup=schedule_confirm_keyboard("sched_close", date_iso)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched_close_yes:"))
async def schedule_close_yes(callback: CallbackQuery):
    date_iso = callback.data.split(":", 1)[1]
    await db.close_day(date.fromisoformat(date_iso))
    await _render_day_menu(callback, date_iso, edit=True)
    await callback.answer("День закрыт")


@router.callback_query(F.data.startswith("sched_open:"))
async def schedule_open(callback: CallbackQuery):
    date_iso = callback.data.split(":", 1)[1]
    await db.open_day(date.fromisoformat(date_iso))
    await _render_day_menu(callback, date_iso, edit=True)
    await callback.answer("День открыт")


# ---------- добавить время ----------

@router.callback_query(F.data.startswith("sched_add_menu:"))
async def schedule_add_menu(callback: CallbackQuery):
    date_iso = callback.data.split(":", 1)[1]
    chosen_date = date.fromisoformat(date_iso)
    available = set(await db.get_available_slots(chosen_date))
    candidates = sorted(
        time_cls(hour=h) for h in EXTRA_HOURS_RANGE if time_cls(hour=h) not in available
    )
    await callback.message.edit_text(
        f"Выбери время, которое нужно добавить на {chosen_date.strftime('%d.%m')}:",
        reply_markup=schedule_time_pick_keyboard(date_iso, candidates, "sched_addtime")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched_addtime:"))
async def schedule_add_time(callback: CallbackQuery):
    _, date_iso, time_str = callback.data.split(":", 2)
    chosen_date = date.fromisoformat(date_iso)
    chosen_time = datetime.strptime(time_str, "%H:%M").time()
    await db.add_time_override(chosen_date, chosen_time)
    await _render_day_menu(callback, date_iso, edit=True)
    await callback.answer(f"Добавлено время {time_str}")


# ---------- убрать время ----------

@router.callback_query(F.data.startswith("sched_block_menu:"))
async def schedule_block_menu(callback: CallbackQuery):
    date_iso = callback.data.split(":", 1)[1]
    chosen_date = date.fromisoformat(date_iso)
    available = await db.get_available_slots(chosen_date)
    await callback.message.edit_text(
        f"Выбери время, которое нужно убрать на {chosen_date.strftime('%d.%m')}:",
        reply_markup=schedule_time_pick_keyboard(date_iso, available, "sched_blocktime")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched_blocktime:"))
async def schedule_block_time(callback: CallbackQuery):
    _, date_iso, time_str = callback.data.split(":", 2)
    chosen_date = date.fromisoformat(date_iso)
    chosen_time = datetime.strptime(time_str, "%H:%M").time()
    await db.block_time_override(chosen_date, chosen_time)
    await _render_day_menu(callback, date_iso, edit=True)
    await callback.answer(f"Время {time_str} убрано")


# ---------- отменить все записи на день ----------

@router.callback_query(F.data.startswith("sched_cancelall_ask:"))
async def schedule_cancel_all_ask(callback: CallbackQuery):
    date_iso = callback.data.split(":", 1)[1]
    chosen_date = date.fromisoformat(date_iso)
    bookings = await db.get_bookings_by_date_range(chosen_date)
    if not bookings:
        await callback.answer("На эту дату нет активных записей", show_alert=True)
        return
    await callback.message.edit_text(
        f"❗ Отменить все записи ({len(bookings)}) на {chosen_date.strftime('%d.%m')}?\n"
        f"Клиенты получат уведомление об отмене.",
        reply_markup=schedule_confirm_keyboard("sched_cancelall", date_iso)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched_cancelall_yes:"))
async def schedule_cancel_all_yes(callback: CallbackQuery, bot: Bot):
    date_iso = callback.data.split(":", 1)[1]
    chosen_date = date.fromisoformat(date_iso)
    client_tg_ids = await db.cancel_all_bookings_for_date(chosen_date)

    for tg_id in client_tg_ids:
        try:
            await bot.send_message(
                tg_id,
                f"⚠️ Ваша запись на {chosen_date.strftime('%d.%m')} была отменена администратором."
            )
        except Exception:
            pass

    await _render_day_menu(callback, date_iso, edit=True)
    await callback.answer(f"Отменено записей: {len(client_tg_ids)}")
