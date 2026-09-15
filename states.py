from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    confirming = State()
