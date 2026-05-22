from aiogram.fsm.state import State, StatesGroup


class AdminSlotStates(StatesGroup):
    waiting_for_slot = State()
    waiting_for_time = State()
    waiting_for_service = State()


class AdminServiceStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_duration = State()
    waiting_for_confirm = State()


class AdminDiscountStates(StatesGroup):
    waiting_for_type = State()
    waiting_for_amount = State()
    waiting_for_username = State()
    waiting_for_confirm = State()


class AdminAdminsStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_confirm = State()


class AdminBookingMoveStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    confirming = State()


class AdminBookingsSearchStates(StatesGroup):
    waiting_for_query = State()


class AdminScheduleTemplateStates(StatesGroup):
    waiting_for_template_name = State()
    choosing_template = State()

    choosing_rule_day = State()
    waiting_for_rule_start = State()
    waiting_for_rule_end = State()
    waiting_for_rule_duration = State()
    waiting_for_rule_break = State()
    choosing_rule_service = State()


class AdminScheduleGenerateStates(StatesGroup):
    choosing_template = State()
    choosing_weeks = State()
    choosing_overwrite = State()


class AdminScheduleExceptionStates(StatesGroup):
    choosing_exception_type = State()
    waiting_for_exception_date = State()
    waiting_for_exception_window = State()
    waiting_for_exception_duration = State()
    choosing_exception_service = State()
    waiting_for_exception_reason = State()

