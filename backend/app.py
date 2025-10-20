from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import random
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
    question_map: Dict[int, Question] = Field(default_factory=dict)  # per-session Question objects


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


def load_questions() -> Dict[int, dict]:
    # Return raw question data (id -> dict) from JSON
    raw_questions: Dict[int, dict] = {}
    if not DATA_FILE.exists():
        return raw_questions

    with DATA_FILE.open(encoding="utf-8") as f:
        raw = json.load(f)

    base_prompt = raw.get("base_question", "Назови национальность в стране")
    items = raw.get("questions", [])

    for it in items:
        qid = int(it.get("id"))
        country = it.get("country")
        prompt = f"{base_prompt} — {country}" if country else base_prompt
        answer_text = it.get("answer")
        prompt_audio = it.get("audio")
        raw_questions[qid] = {
            "id": qid,
            "prompt_text": prompt,
            "prompt_audio": prompt_audio,
            "answer": answer_text,
        }

    return raw_questions


# Load RAW questions at import time
RAW_QUESTIONS: Dict[int, dict] = load_questions()


def _get_question_or_404(qid: int) -> Question:
    q = RAW_QUESTIONS.get(qid)
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
    # choose N random questions from RAW_QUESTIONS
    all_ids = list(RAW_QUESTIONS.keys())
    if not all_ids:
        raise HTTPException(500, "No questions configured on the server")
    n = max(1, min(payload.n_questions, len(all_ids)))
    chosen_ids = random.sample(all_ids, n)

    session = QuizSession(
        session_id=uuid4(),
        user_id=payload.user_id,
        question_ids=chosen_ids,
    )

    # Build per-session Question objects with randomized options
    # Pool of answers for distractors: extract masculine base from RAW answers
    pool = []
    for rid, rdata in RAW_QUESTIONS.items():
        ans = rdata.get("answer")
        if not ans:
            continue
        # try to extract masculine base
        if ans.startswith("un ") and " et" in ans:
            base = ans[len("un "):].split(" et")[0].strip()
        else:
            parts = ans.split()
            base = parts[1] if len(parts) > 1 else parts[0]
        pool.append(base)

    for qid in chosen_ids:
        r = RAW_QUESTIONS[qid]
        prompt = r.get("prompt_text")
        correct = r.get("answer")

        # build options: correct (combined) + (default_options-1) distractors
        default_options = int(json.load(DATA_FILE.open()).get("default_options", 4))
        opts_texts = [correct]
        candidates = [p for p in pool if p != (correct.split()[1] if len(correct.split())>1 else correct)]
        random.shuffle(candidates)
        for cand in candidates:
            if len(opts_texts) >= default_options:
                break
            opts_texts.append(f"un {cand}")

        # pad if needed
        i = 0
        while len(opts_texts) < default_options:
            opts_texts.append(f"{correct}_alt{i}")
            i += 1

        # shuffle options so correct isn't always first
        enumerated = opts_texts[:]
        random.shuffle(enumerated)

        opts: List[Option] = []
        correct_idx = 1
        for idx, text in enumerate(enumerated, start=1):
            opts.append(Option(id=idx, text=text, audio=None))
            if text == correct:
                correct_idx = idx

        session.question_map[qid] = Question(
            id=qid,
            prompt_text=prompt,
            prompt_audio=r.get("prompt_audio"),
            options=opts,
            correct_option_id=correct_idx,
        )

    SESSIONS[session.session_id] = session
    return StartQuizOut(
        session_id=session.session_id,
        total=len(chosen_ids),
        first_question_id=chosen_ids[0],
    )


@app.get("/quiz/question/{session_id}/{index}", response_model=QuestionOut)
def get_question(session_id: UUID, index: int):
    session = _get_session_or_404(session_id)
    if session.finished:
        raise HTTPException(400, "Quiz already finished")
    if not (0 <= index < len(session.question_ids)):
        raise HTTPException(400, "Index out of range")
    qid = session.question_ids[index]
    # get per-session question
    q = session.question_map.get(qid)
    if not q:
        # fallback to raw
        raw = RAW_QUESTIONS.get(qid)
        raise HTTPException(500, "Session question not prepared")
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

    # Use per-session prepared question
    q = session.question_map.get(payload.question_id)
    if not q:
        raise HTTPException(400, "Question not found in session")
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

