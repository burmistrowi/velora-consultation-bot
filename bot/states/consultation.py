from aiogram.fsm.state import State, StatesGroup

class ConsultationStates(StatesGroup):
    # Write admin flow (kept)
    waiting_for_message = State()


class BookingFlowStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    choosing_service = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_confirm = State()


class RescheduleStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    confirming = State()