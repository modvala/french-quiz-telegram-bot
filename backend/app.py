from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from uuid import uuid4, UUID
from pathlib import Path
import json

from config import settings


app = FastAPI(title="WordQuiz API")

# === Статика (аудио) ===
# Положи файлы в backend/static/audio/*.ogg | *.mp3
static_dir = Path(settings.AUDIO_OUTPUT_DIR)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# === МОДЕЛИ ДАННЫХ ===


class Option(BaseModel):
    id: int
    text: str
    audio: Optional[str] = None  # путь к аудио варианта (отдаём только при правильном ответе)


class Question(BaseModel):
    id: int
    prompt_text: str
    prompt_audio: Optional[str] = None  # путь к аудио вопроса
    options: List[Option]
    correct_option_id: int


class QuizSession(BaseModel):
    session_id: UUID
    user_id: str
    question_ids: List[int]
    current_index: int = 0
    correct_count: int = 0
    finished: bool = False
    answers: Dict[int, bool] = Field(default_factory=dict)  # question_id -> correct?


SESSIONS: Dict[UUID, QuizSession] = {}


# Data file (matches structure in attachments)
DATA_FILE = Path(__file__).parent / "data" / "nationalies" / "questions.json"


def _audio_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    # If stored path is like "audio/filename.ext" we want to return a URL
    # under /static. Depending on how the static files are mounted the
    # actual files may live in a folder that already is the audio folder
    # (e.g. settings.AUDIO_OUTPUT_DIR == '.../data/audio'). In that case
    # the correct URL is "/static/filename.ext" (not "/static/audio/filename.ext").
    if path.startswith("audio/"):
        # If the static root itself is an "audio" folder, strip the prefix
        static_root = Path(settings.AUDIO_OUTPUT_DIR)
        rel = path.split('/', 1)[1]
        # Check if file exists as given under AUDIO_OUTPUT_DIR
        candidate = static_root / rel
        if candidate.exists():
            # return /static/<rel> when static root is already the audio folder
            if static_root.name == "audio":
                return f"/static/{rel}"
            return f"/static/audio/{rel}"

        # Try common variants: <stem>_country.ext or <stem>_answer.ext
        stem = Path(rel).stem
        ext = Path(rel).suffix
        variants = [f"{stem}_country{ext}", f"{stem}_answer{ext}"]
        for v in variants:
            cand = static_root / v
            if cand.exists():
                if static_root.name == "audio":
                    return f"/static/{v}"
                return f"/static/audio/{v}"

        # Fallback to original URL (may 404)
        if static_root.name == "audio":
            return f"/static/{rel}"
        return f"/static/{path}"
    return path


def load_questions() -> Dict[int, Question]:
    questions: Dict[int, Question] = {}
    if not DATA_FILE.exists():
        return questions
    with DATA_FILE.open(encoding="utf-8") as f:
        raw = json.load(f)
    for item in raw:
        qid = int(item.get("id"))
        # build prompt text from fields present in json
        prompt = item.get("question") or ""
        country = item.get("country")
        if country:
            prompt = f"{prompt} — {country}"
        audio_file = item.get("audio")
        prompt_audio = f"audio/{audio_file}" if audio_file else None

        opts_texts = item.get("options", [])
        answer_text = item.get("answer")

        opts: List[Option] = []
        correct_idx = 1
        for i, text in enumerate(opts_texts, start=1):
            # if this option equals answer, attach prompt audio to option
            opt_audio = prompt_audio if answer_text and text == answer_text else None
            opts.append(Option(id=i, text=text, audio=opt_audio))
            if answer_text and text == answer_text:
                correct_idx = i

        # fallback if answer not found among options
        if not any(o.text == answer_text for o in opts):
            # if answer present but not in options, append it as last option
            if answer_text:
                opts.append(Option(id=len(opts) + 1, text=answer_text, audio=prompt_audio))
                correct_idx = len(opts)

        questions[qid] = Question(
            id=qid,
            prompt_text=prompt,
            prompt_audio=prompt_audio,
            options=opts,
            correct_option_id=correct_idx,
        )
    return questions


# Load QUESTIONS at import time (MVP: in-memory)
QUESTIONS: Dict[int, Question] = load_questions()


def _get_question_or_404(qid: int) -> Question:
    q = QUESTIONS.get(qid)
    if not q:
        raise HTTPException(404, "Question not found")
    return q


def _get_session_or_404(sid: UUID) -> QuizSession:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


# === SCHEMAS для API ===


class StartQuizIn(BaseModel):
    user_id: str
    n_questions: int = 10


class StartQuizOut(BaseModel):
    session_id: UUID
    total: int
    first_question_id: int


class QuestionOut(BaseModel):
    session_id: UUID
    index: int
    total: int
    question_id: int
    prompt_text: str
    prompt_audio_url: Optional[str] = None
    options: List[str]  # возвращаем только тексты опций


class AnswerIn(BaseModel):
    session_id: UUID
    question_id: int
    selected_option_id: int


class AnswerOut(BaseModel):
    correct: bool
    correct_option_id: int
    correct_option_text: str
    correct_option_audio_url: Optional[str] = None  # если correct=True и есть аудио
    score: int
    index: int
    total: int
    finished: bool


class SummaryOut(BaseModel):
    session_id: UUID
    total: int
    correct_count: int
    details: List[Dict[str, str]]  # {question_id, result}


# === ЭНДПОИНТЫ ===


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/quiz/start", response_model=StartQuizOut)
def start_quiz(payload: StartQuizIn):
    # возьмём первые N вопросов (или можно рандомизировать)
    all_ids = list(QUESTIONS.keys())
    if not all_ids:
        raise HTTPException(500, "No questions configured on the server")
    n = max(1, min(payload.n_questions, len(all_ids)))
    question_ids = all_ids[:n]

    session = QuizSession(
        session_id=uuid4(),
        user_id=payload.user_id,
        question_ids=question_ids,
    )
    SESSIONS[session.session_id] = session
    return StartQuizOut(
        session_id=session.session_id,
        total=len(question_ids),
        first_question_id=question_ids[0],
    )


@app.get("/quiz/question/{session_id}/{index}", response_model=QuestionOut)
def get_question(session_id: UUID, index: int):
    session = _get_session_or_404(session_id)
    if session.finished:
        raise HTTPException(400, "Quiz already finished")
    if not (0 <= index < len(session.question_ids)):
        raise HTTPException(400, "Index out of range")

    qid = session.question_ids[index]
    q = _get_question_or_404(qid)
    return QuestionOut(
        session_id=session.session_id,
        index=index,
        total=len(session.question_ids),
        question_id=q.id,
        prompt_text=q.prompt_text,
        prompt_audio_url=_audio_url(q.prompt_audio),
        options=[opt.text for opt in q.options],
    )


@app.post("/quiz/answer", response_model=AnswerOut)
def submit_answer(payload: AnswerIn):
    session = _get_session_or_404(payload.session_id)
    if session.finished:
        raise HTTPException(400, "Quiz already finished")

    # проверяем, что это ожидаемый вопрос
    if not (0 <= session.current_index < len(session.question_ids)):
        raise HTTPException(400, "Invalid session index")
    expected_qid = session.question_ids[session.current_index]
    if expected_qid != payload.question_id:
        raise HTTPException(400, "Question order mismatch")

    q = _get_question_or_404(payload.question_id)
    is_correct = (payload.selected_option_id == q.correct_option_id)
    session.answers[q.id] = is_correct
    if is_correct:
        session.correct_count += 1

    # продвигаем индекс/завершаем при необходимости
    session.current_index += 1
    if session.current_index >= len(session.question_ids):
        session.finished = True

    # готовим ответ
    correct_opt = next(o for o in q.options if o.id == q.correct_option_id)
    return AnswerOut(
        correct=is_correct,
        correct_option_id=correct_opt.id,
        correct_option_text=correct_opt.text,
        correct_option_audio_url=_audio_url(correct_opt.audio) if is_correct else None,
        score=session.correct_count,
        index=min(session.current_index, len(session.question_ids) - 1),
        total=len(session.question_ids),
        finished=session.finished,
    )


@app.get("/quiz/summary/{session_id}", response_model=SummaryOut)
def summary(session_id: UUID):
    session = _get_session_or_404(session_id)
    return SummaryOut(
        session_id=session.session_id,
        total=len(session.question_ids),
        correct_count=session.correct_count,
        details=[
            {"question_id": str(qid), "result": "correct" if session.answers.get(qid) else "wrong"}
            for qid in session.question_ids
        ],
    )

