from aiogram.dispatcher.filters.state import State, StatesGroup


class QuizStates(StatesGroup):
    in_quiz = State()

