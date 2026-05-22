from aiogram.fsm.state import State, StatesGroup


class UserSupportStates(StatesGroup):
    waiting_for_message = State()


class AdminSupportStates(StatesGroup):
    waiting_for_reply = State()

