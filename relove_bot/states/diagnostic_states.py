from aiogram.fsm.state import State, StatesGroup

class DiagnosticStates(StatesGroup):
    """Состояния для процесса диагностики"""
    STARTING_DIAGNOSTICS = State()  # Начало диагностики
    ANSWERING = State()  # Процесс ответа на вопросы
    COMPLETED = State()  # Диагностика завершена 