from aiogram.fsm.state import State, StatesGroup

class JobStart(StatesGroup):
    waiting_date = State()

class AddEvent(StatesGroup):
    waiting_title = State()
    waiting_datetime = State()
    waiting_reminder = State()

class UniWizard(StatesGroup):
    mode = State()
    waiting_pair_id = State()
    waiting_dow = State()
    waiting_start = State()
    waiting_end = State()
    waiting_subject_room = State()

class DeleteById(StatesGroup):
    waiting_event_id = State()
    waiting_pair_id = State()
