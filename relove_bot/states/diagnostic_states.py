from aiogram.fsm.state import State, StatesGroup

class DiagnosticStates(StatesGroup):
    """Состояния для процесса диагностики"""
    STARTING_DIAGNOSTICS = State()  # Начало диагностики
    WAITING_FOR_TYPE = State()  # Ожидание выбора психологического типа
    WAITING_FOR_JOURNEY_STAGE = State()  # Ожидание выбора этапа путешествия
    ANSWERING = State()  # Процесс ответа на вопросы
    COMPLETED = State()  # Диагностика завершена