from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData
import aiohttp
import asyncio
from ..states import QuizStates
import logging

logger = logging.getLogger(__name__)

# Simple in-memory per-user quiz sessions. For production use persistent storage.
SESSIONS = {}

# callback data factory: q{index}_{option}
quiz_cb = CallbackData("quiz", "idx", "opt")


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(start_quiz, lambda m: m.text == "Начать викторину")
    dp.register_callback_query_handler(handle_answer, lambda c: c.data and c.data.startswith("quiz:"))


async def fetch_quiz_questions(api_url: str, count: int = 10):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{api_url.rstrip('/')}/quiz/start?count={count}") as resp:
            if resp.status != 200:
                raise RuntimeError(f"Failed to fetch quiz questions: {resp.status}")
            return await resp.json()


async def start_quiz(message: types.Message):
    """Start quiz: fetch questions from backend and send first question with audio + inline options."""
    api_base = message.bot.get('backend_api') if hasattr(message.bot, 'get') else None
    # allow optional override via bot['backend_api'] attribute, else default to http://127.0.0.1:8000
    api_url = api_base or "http://127.0.0.1:8000"

    try:
        payload = await fetch_quiz_questions(api_url, count=10)
    except Exception as e:
        logger.exception("Failed to fetch quiz questions")
        await message.answer("Не удалось получить вопросы. Попробуйте позже.")
        return

    questions = payload.get("questions") if isinstance(payload, dict) else payload
    if not questions:
        await message.answer("Нет доступных вопросов.")
        return

    user_id = message.from_user.id
    # initialize session
    SESSIONS[user_id] = {
        "questions": questions,
        "current": 0,
        "correct": 0,
        "answers": [],
    }

    await QuizStates.in_quiz.set()
    await send_question(message.chat.id, message.bot, user_id)


async def send_question(chat_id: int, bot: types.Bot, user_id: int):
    session = SESSIONS.get(user_id)
    if not session:
        return
    idx = session["current"]
    questions = session["questions"]
    if idx >= len(questions):
        # finished
        await send_summary(chat_id, bot, user_id)
        return

    q = questions[idx]
    # send audio if present
    audio_url = q.get("audio_url")
    if audio_url:
        try:
            await bot.send_audio(chat_id, audio=audio_url)
        except Exception:
            # fallback to text if audio fails
            await bot.send_message(chat_id, f"[Аудио недоступно] {q.get('country')}")
    else:
        await bot.send_message(chat_id, f"{q.get('country')}")

    # build inline keyboard with four options
    kb = InlineKeyboardMarkup()
    opts = q.get("options", [])
    for opt in opts:
        cb = quiz_cb.new(idx=idx, opt=opt)
        kb.add(InlineKeyboardButton(opt, callback_data=cb))

    await bot.send_message(chat_id, f"Вопрос {idx+1}: {q.get('question')}", reply_markup=kb)


async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data  # format produced by CallbackData, e.g. "quiz:0:Américain"
    # handle restart
    if data == "quiz:restart":
        # simulate user sending 'Начать викторину'
        await callback.answer()
        fake_msg = types.Message(**{"chat": callback.message.chat, "from_user": callback.from_user, "message_id": callback.message.message_id})
        await start_quiz(fake_msg)
        return

    try:
        parts = data.split(":", 2)
        if len(parts) < 3:
            await callback.answer("Неправильный ответ")
            return
        _, idx_s, opt = parts
        idx = int(idx_s)
    except Exception:
        await callback.answer("Неправильные данные")
        return

    user_id = callback.from_user.id
    session = SESSIONS.get(user_id)
    if not session:
        await callback.answer("Сессия не найдена. Нажмите 'Начать викторину' чтобы начать.")
        return

    # Ensure the callback is for the current question
    if idx != session["current"]:
        await callback.answer("Этот вопрос уже обработан или не текущий.")
        return

    q = session["questions"][idx]
    correct = q.get("answer")
    chosen = opt

    # record answer
    is_correct = (chosen == correct)
    session["answers"].append({"idx": idx, "chosen": chosen, "correct": correct, "ok": is_correct})
    if is_correct:
        session["correct"] += 1

    # Provide immediate feedback by editing the message or sending a new one
    if is_correct:
        await callback.message.answer("✔️ Правильно!")
    else:
        await callback.message.answer(f"❌ Неправильно. Правильный ответ: {correct}")

    # increment and send next question or summary
    session["current"] += 1
    await callback.answer()  # remove 'loading' on button

    # small delay to avoid flooding
    await asyncio.sleep(0.3)

    if session["current"] < len(session["questions"]):
        await send_question(callback.message.chat.id, callback.bot, user_id)
    else:
        await send_summary(callback.message.chat.id, callback.bot, user_id)


async def send_summary(chat_id: int, bot: types.Bot, user_id: int):
    session = SESSIONS.get(user_id)
    if not session:
        return
    correct = session["correct"]
    total = len(session["questions"])
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Пройти снова", callback_data="quiz:restart"))

    await bot.send_message(chat_id, f"Квиз завершён. Правильных ответов: {correct}/{total}", reply_markup=kb)

    # clear session
    del SESSIONS[user_id]
    # finish FSM
    try:
        await QuizStates.in_quiz.finish()
    except Exception:
        pass
