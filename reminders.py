from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import db


def _cancel_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"do_cancel:{booking_id}")]
    ])


async def check_and_send_reminders(bot: Bot):
    """Вызывается периодически (свой таймер локально или внешний cron на проде)."""
    await db.expire_past_bookings()

    bookings = await db.get_bookings_needing_reminders()
    now = datetime.now()

    for b in bookings:
        booking_dt = datetime.combine(b["booking_date"], b["booking_time"])
        delta = booking_dt - now

        try:
            if not b["reminder_day_sent"] and timedelta(hours=23) <= delta <= timedelta(hours=25):
                await bot.send_message(
                    b["client_tg_id"],
                    f"🔔 Напоминаем: завтра, {b['booking_date'].strftime('%d.%m')} в "
                    f"{b['booking_time'].strftime('%H:%M')}, у вас запись. Ждём вас!",
                    reply_markup=_cancel_kb(b["id"])
                )
                await db.mark_reminder_sent(b["id"], "day")

            elif not b["reminder_hour_sent"] and timedelta(hours=1.75) <= delta <= timedelta(hours=2.25):
                await bot.send_message(
                    b["client_tg_id"],
                    f"🔔 Напоминаем: сегодня в {b['booking_time'].strftime('%H:%M')} "
                    f"(через 2 часа) у вас запись!",
                    reply_markup=_cancel_kb(b["id"])
                )
                await db.mark_reminder_sent(b["id"], "hour")
        except Exception:
            # если бот заблокирован пользователем и т.п. — просто пропускаем
            continue
