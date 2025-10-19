from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, CommandStart())


async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Начать викторину"))
    await message.answer("Добро пожаловать! Нажмите кнопку ниже, чтобы начать викторину.", reply_markup=kb)
