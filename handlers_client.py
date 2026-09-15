from datetime import date as date_cls, datetime, time as time_cls

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import db
from states import BookingStates
from config import ADMIN_IDS
from keyboards import (
    client_menu, admin_menu, dates_keyboard, times_keyboard,
    confirm_booking_keyboard, cancel_confirm_keyboard
)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("👨‍💼 Привет, админ! Панель управления ниже 👇", reply_markup=admin_menu)
        return

    client = await db.get_or_create_client(message.from_user.id, message.from_user.full_name)
    if client["blacklisted"]:
        await message.answer("🚫 К сожалению, доступ к записи для вас ограничен.")
        return
    await message.answer(
        "Привет! 👋 Я помогу записаться на приём и не забыть о нём.\n\n"
        "Выбирай действие в меню ниже 👇",
        reply_markup=client_menu
    )


@router.message(F.text == "📅 Записаться")
async def start_booking(message: Message, state: FSMContext):
    client = await db.get_or_create_client(message.from_user.id, message.from_user.full_name)
    if client["blacklisted"]:
        await message.answer("🚫 Запись недоступна.")
        return

    existing = await db.get_active_booking(client["id"])
    if existing:
        await message.answer(
            f"⚠️ У вас уже есть активная запись на "
            f"{existing['booking_date'].strftime('%d.%m')} в {existing['booking_time'].strftime('%H:%M')}.\n"
            f"Сначала отмените её, если хотите записаться на другое время."
        )
        return

    await state.set_state(BookingStates.choosing_date)
    await message.answer("Выбери удобную дату 📅", reply_markup=dates_keyboard())


@router.callback_query(F.data.startswith("date:"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    date_iso = callback.data.split(":", 1)[1]
    chosen_date = date_cls.fromisoformat(date_iso)

    available = await db.get_available_slots(chosen_date)
    await state.update_data(chosen_date=date_iso)
    await state.set_state(BookingStates.choosing_time)

    if not available:
        await callback.message.edit_text(
            f"😔 На {chosen_date.strftime('%d.%m')} свободных слотов нет.\n"
            f"Выбери другую дату 📅",
            reply_markup=dates_keyboard()
        )
        await state.set_state(BookingStates.choosing_date)
        await callback.answer()
        return

    await callback.message.edit_text(
        f"Дата: {chosen_date.strftime('%d.%m')}\nТеперь выбери время 🕐",
        reply_markup=times_keyboard(date_iso, available)
    )
    await callback.answer()


@router.callback_query(F.data == "booking_back_to_date")
async def back_to_date(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text("Выбери удобную дату 📅", reply_markup=dates_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("time:"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    _, date_iso, time_str = callback.data.split(":", 2)
    await state.update_data(chosen_time=time_str)
    await state.set_state(BookingStates.confirming)

    chosen_date = date_cls.fromisoformat(date_iso)
    await callback.message.edit_text(
        f"Записать вас на {chosen_date.strftime('%d.%m')} в {time_str}?",
        reply_markup=confirm_booking_keyboard(date_iso, time_str)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:"))
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    _, date_iso, time_str = callback.data.split(":", 2)
    chosen_date = date_cls.fromisoformat(date_iso)
    chosen_time = datetime.strptime(time_str, "%H:%M").time()

    client = await db.get_or_create_client(callback.from_user.id, callback.from_user.full_name)

    # проверка, что слот всё ещё свободен (мог занять кто-то другой, или админ его закрыл)
    available = await db.get_available_slots(chosen_date)
    if chosen_time not in available:
        await callback.message.edit_text("😔 Это время только что стало недоступно. Выбери другое.")
        await state.set_state(BookingStates.choosing_date)
        await callback.message.answer("Выбери дату заново 📅", reply_markup=dates_keyboard())
        await callback.answer()
        return

    await db.create_booking(client["id"], chosen_date, chosen_time)
    await state.clear()

    await callback.message.edit_text(
        f"✅ Готово! Вы записаны на {chosen_date.strftime('%d.%m')} в {time_str}.\n"
        f"Напомним об этом заранее 🔔"
    )
    await callback.answer()


@router.callback_query(F.data == "booking_cancel")
async def cancel_booking_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.answer()


@router.message(F.text == "📋 Моя запись")
async def my_booking(message: Message):
    client = await db.get_or_create_client(message.from_user.id, message.from_user.full_name)
    booking = await db.get_active_booking(client["id"])
    if not booking:
        await message.answer("У вас пока нет активных записей.")
        return
    await message.answer(
        f"📋 Ваша запись: {booking['booking_date'].strftime('%d.%m')} в "
        f"{booking['booking_time'].strftime('%H:%M')}"
    )


@router.message(F.text == "❌ Отменить запись")
async def cancel_booking_request(message: Message):
    client = await db.get_or_create_client(message.from_user.id, message.from_user.full_name)
    booking = await db.get_active_booking(client["id"])
    if not booking:
        await message.answer("У вас нет активных записей для отмены.")
        return

    await message.answer(
        f"Отменить запись на {booking['booking_date'].strftime('%d.%m')} в "
        f"{booking['booking_time'].strftime('%H:%M')}?",
        reply_markup=cancel_confirm_keyboard(booking["id"])
    )


@router.callback_query(F.data.startswith("do_cancel:"))
async def do_cancel(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    await db.cancel_booking(booking_id)
    await callback.message.edit_text("✅ Запись отменена.")
    await callback.answer()


@router.callback_query(F.data == "keep_booking")
async def keep_booking(callback: CallbackQuery):
    await callback.message.edit_text("Запись оставлена в силе 👍")
    await callback.answer()
