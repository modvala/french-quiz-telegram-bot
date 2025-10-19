import os
import asyncio
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from fastapi import FastAPI, Request
from aiogram.types import Update

from config import settings

import httpx

# Заменено: берём настройки из отдельного модуля конфигурации
from config import settings

# ===== FSM состояния для хранения прогресса =====
class QuizState(StatesGroup):
    active = State()  # в процессе квиза
    idle = State()    # ожидание / конец

# В state будем хранить:
# {
#   "session_id": "...",
#   "index": 0,
#   "total": 10,
#   "last_question_id": 1,
#   "last_options": ["...", "...", "...", "..."]
# }

dp = Dispatcher(storage=MemoryStorage())
bot = Bot(settings.BOT_TOKEN)  # убрал deprecated аргумент parse_mode

# ===== HTTP клиент =====
def build_url(path: str) -> str:
    # backend отдаёт /static/... и т.д. — нормализуем
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return settings.API_BASE.rstrip("/") + "/" + path.lstrip("/")


async def api_get(path: str) -> Dict[str, Any]:
	headers = {}
	if settings.API_TOKEN:
		headers["Authorization"] = f"Bearer {settings.API_TOKEN}"
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.get(build_url(path), headers=headers)
		r.raise_for_status()
		return r.json()


async def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
	headers = {}
	if settings.API_TOKEN:
		headers["Authorization"] = f"Bearer {settings.API_TOKEN}"
	async with httpx.AsyncClient(timeout=20.0) as client:
		r = await client.post(build_url(path), json=payload, headers=headers)
		r.raise_for_status()
		return r.json()


async def fetch_bytes(url_or_path: Optional[str]) -> Optional[bytes]:
	if not url_or_path:
		return None
	url = build_url(url_or_path)
	headers = {}
	if settings.API_TOKEN:
		headers["Authorization"] = f"Bearer {settings.API_TOKEN}"
	async with httpx.AsyncClient(timeout=30.0) as client:
		r = await client.get(url, headers=headers)
		r.raise_for_status()
		return r.content


# ===== UI helpers =====
def options_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    # кнопки с callback_data вида "pick:INDEX" (0..3)
    rows = []
    row = []
    for i, text in enumerate(options):
        row.append(InlineKeyboardButton(text=text, callback_data=f"pick:{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сыграть снова", callback_data="restart")]
    ])


# ====== Показ вопроса ======
async def show_question(chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    session_id = data["session_id"]
    index = data["index"]

    # GET /quiz/question/{session_id}/{index}
    q = await api_get(f"/quiz/question/{session_id}/{index}")

    # сохраним данные для ответа
    await state.update_data(
        last_question_id=q["question_id"],
        last_options=q["options"],
        total=q["total"],
    )

    # сначала аудио вопроса (если есть)
    if q.get("prompt_audio_url"):
        audio_bytes = await fetch_bytes(q["prompt_audio_url"])
        if audio_bytes:
            await bot.send_audio(
                chat_id,
                types.BufferedInputFile(audio_bytes, filename="question.ogg"),
                caption=f"<b>Вопрос {q['index']+1}/{q['total']}</b>\n{q['prompt_text']}",
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                chat_id,
                f"<b>Вопрос {q['index']+1}/{q['total']}</b>\n{q['prompt_text']}",
                parse_mode="HTML",
            )
    else:
        await bot.send_message(
            chat_id,
            f"<b>Вопрос {q['index']+1}/{q['total']}</b>\n{q['prompt_text']}",
            parse_mode="HTML",
        )

    # затем варианты
    kb = options_keyboard(q["options"])
    await bot.send_message(chat_id, "Выберите вариант:", reply_markup=kb)


# ====== START ======
@dp.message(CommandStart())
async def start_cmd(m: types.Message, state: FSMContext):
    await state.clear()
    user_id = str(m.from_user.id)

    # POST /quiz/start
    started = await api_post("/quiz/start", {
        "user_id": user_id,
        "n_questions": settings.N_QUESTIONS
    })

    session_id = started["session_id"]
    await state.set_state(QuizState.active)
    await state.update_data(session_id=session_id, index=0, total=started["total"])

    await m.answer("🚀 Начинаем квиз!")
    await show_question(m.chat.id, state)


# ====== Выбор варианта ======
@dp.callback_query(F.data.startswith("pick:"))
async def pick_option(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()  # мгновенная реакция

    data = await state.get_data()
    if not data or "session_id" not in data:
        await cb.message.answer("Сессия не найдена, нажмите /start")
        return

    session_id = data["session_id"]
    index = data["index"]
    question_id = data["last_question_id"]
    options = data["last_options"]

    try:
        selected_idx = int(cb.data.split(":")[1])  # 0..3
    except Exception:
        await cb.message.answer("Некорректный выбор.")
        return

    if selected_idx < 0 or selected_idx >= len(options):
        await cb.message.answer("Некорректный выбор.")
        return

    # Наш бекенд принимает selected_option_id как 1..4 (позиция)
    selected_option_id = selected_idx + 1

    # POST /quiz/answer
    ans = await api_post("/quiz/answer", {
        "session_id": session_id,
        "question_id": question_id,
        "selected_option_id": selected_option_id
    })

    if ans["correct"]:
        await cb.message.answer("✅ Правильно!")
        # если есть аудио правильного варианта — проиграем
        if ans.get("correct_option_audio_url"):
            audio_bytes = await fetch_bytes(ans["correct_option_audio_url"])
            if audio_bytes:
                await bot.send_audio(
                    cb.message.chat.id,
                    types.BufferedInputFile(audio_bytes, filename="answer.ogg"),
                    caption=f"🔊 {ans['correct_option_text']}",
                )
    else:
        await cb.message.answer(
            f"❌ Неправильно. Правильный ответ: <b>{ans['correct_option_text']}</b>",
            parse_mode="HTML",
        )

    # Продолжение или итог
    if ans["finished"]:
        # GET /quiz/summary/{session_id}
        summary = await api_get(f"/quiz/summary/{session_id}")
        await state.set_state(QuizState.idle)
        await cb.message.answer(
            f"🏁 Квиз завершён!\n"
            f"Правильных ответов: <b>{summary['correct_count']}</b> из <b>{summary['total']}</b>",
            reply_markup=restart_keyboard(),
            parse_mode="HTML",
        )
        return
    else:
        # перейти к следующему индексу
        await state.update_data(index=index + 1)
        await show_question(cb.message.chat.id, state)


# ====== Рестарт ======
@dp.callback_query(F.data == "restart")
async def restart(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await start_cmd(cb.message, state)

app = FastAPI(title="WordQuiz Bot Webhook")

@app.on_event("startup")
async def _on_startup():
    async with bot:
        await bot.set_webhook(settings.WEBHOOK_URL, drop_pending_updates=True)

@app.on_event("shutdown")
async def _on_shutdown():
    async with bot:
        await bot.delete_webhook(drop_pending_updates=True)

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/tg/webhook")
async def tg_webhook(request: Request):
    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return {"ok": True}


# ====== Точка входа ======
async def main():
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Set it in .env")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
