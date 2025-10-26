from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from uuid import uuid4, UUID
from pathlib import Path
import random
import json
import os

from config import settings
from ...schemas import (
    Card,
    Question,
    QuizSession,
    StartQuizIn,
    StartQuizOut,
    OptionResponse,
    QuestionOut,
    AnswerIn,
    AnswerOut,
    SummaryOut,
)

router = APIRouter()

# Session storage is module-local
SESSIONS: Dict[UUID, QuizSession] = {}

# Data file for this module
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "nationalies" / "questions.json"


def _audio_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith("audio/"):
        static_root = Path(settings.AUDIO_OUTPUT_DIR)
        rel = path.split('/', 1)[1]
        candidate = static_root / rel
        if candidate.exists():
            if static_root.name == "audio":
                return f"/static/{rel}"
            return f"/static/audio/{rel}"
        stem = Path(rel).stem
        ext = Path(rel).suffix
        variants = [f"{stem}_country{ext}", f"{stem}_answer{ext}"]
        for v in variants:
            cand = static_root / v
            if cand.exists():
                if static_root.name == "audio":
                    return f"/static/{v}"
                return f"/static/audio/{v}"
        if static_root.name == "audio":
            return f"/static/{rel}"
        return f"/static/{path}"
    return path


def load_questions() -> Dict[int, dict]:
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
        prompt = f"{base_prompt}:" if country else base_prompt
        answer_text = it.get("answer")
        prompt_audio = it.get("audio")
        raw_questions[qid] = {
            "id": qid,
            "default_options": raw.get("default_options", 4),
            "prompt_text": prompt,
            "prompt_audio": prompt_audio,
            "answer": answer_text,
            "country": country,
        }
    return raw_questions


RAW_QUESTIONS = load_questions()


def _get_session_or_404(sid: UUID) -> QuizSession:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.post("/quiz/start", response_model=StartQuizOut)
def start_quiz(payload: StartQuizIn):
    all_ids = list(RAW_QUESTIONS.keys())
    if not all_ids:
        raise HTTPException(500, "No questions configured on the server")
    n = max(1, int(payload.n_questions))
    chosen_ids = random.choices(all_ids, k=n)

    session = QuizSession(
        session_id=uuid4(),
        user_id=payload.user_id,
        question_ids=chosen_ids,
    )

    for pos, qid in enumerate(chosen_ids):
        r = RAW_QUESTIONS[qid]
        prompt = r.get("prompt_text")

        try:
            default_options = int(r.get("default_options", 4))
        except Exception:
            default_options = 4

        option_ids = [qid]
        remaining_ids = [other for other in all_ids if other != qid]
        random.shuffle(remaining_ids)
        option_ids.extend(remaining_ids[: max(0, default_options - 1)])
        random.shuffle(option_ids)

        opts: List[Card] = []
        correct_idx = 1
        for idx, option_qid in enumerate(option_ids, start=1):
            answer_data = RAW_QUESTIONS.get(option_qid, {})
            option_text = answer_data.get("answer")
            audio_path = f"audio/q{option_qid}_answer.mp3" if option_qid else None
            opts.append(Card(id=idx, text=option_text, audio=audio_path))
            if option_qid == qid:
                correct_idx = idx

        prompt_card = Card(id=qid, text=prompt, audio=r.get("prompt_audio"))
        session.question_map[pos] = Question(
            id=qid,
            prompt_text=prompt,
            question=prompt_card,
            options=opts,
            correct_option_id=correct_idx,
        )

    SESSIONS[session.session_id] = session
    return StartQuizOut(
        session_id=session.session_id,
        total=len(chosen_ids),
        first_question_id=chosen_ids[0],
    )


@router.get("/quiz/question/{session_id}/{index}", response_model=QuestionOut)
def get_question(session_id: UUID, index: int):
    session = _get_session_or_404(session_id)
    if session.finished:
        raise HTTPException(400, "Quiz already finished")
    if not (0 <= index < len(session.question_ids)):
        raise HTTPException(400, "Index out of range")
    q = session.question_map.get(index)
    if not q:
        raise HTTPException(500, "Session question not prepared")
    option_responses = []
    for opt in q.options:
        audio_path = opt.audio
        option_responses.append(OptionResponse(
            number=opt.id,
            audio_url=_audio_url(audio_path)
        ))
    return QuestionOut(
        session_id=session.session_id,
        index=index,
        total=len(session.question_ids),
        question_id=q.id,
        prompt_text=q.prompt_text,
        prompt_audio_url=_audio_url(q.question.audio),
        options=option_responses,
    )


@router.post("/quiz/answer", response_model=AnswerOut)
def submit_answer(payload: AnswerIn):
    session = _get_session_or_404(payload.session_id)
    if session.finished:
        raise HTTPException(400, "Quiz already finished")
    if not (0 <= session.current_index < len(session.question_ids)):
        raise HTTPException(400, "Invalid session index")
    expected_qid = session.question_ids[session.current_index]
    if expected_qid != payload.question_id:
        raise HTTPException(400, "Question order mismatch")
    q = session.question_map.get(session.current_index)
    if not q:
        raise HTTPException(400, "Question not found in session")
    is_correct = (payload.selected_option_id == q.correct_option_id)
    session.answers[q.id] = is_correct
    if is_correct:
        session.correct_count += 1
    session.current_index += 1
    if session.current_index >= len(session.question_ids):
        session.finished = True
    correct_opt = next(o for o in q.options if o.id == q.correct_option_id)
    country = None
    raw_q = RAW_QUESTIONS.get(q.id)
    if raw_q:
        country = raw_q.get("country")
    return AnswerOut(
        correct=is_correct,
        correct_option_id=correct_opt.id,
        correct_option_text=correct_opt.text,
        correct_option_audio_url=_audio_url(correct_opt.audio),
        country=country,
        score=session.correct_count,
        index=min(session.current_index, len(session.question_ids) - 1),
        total=len(session.question_ids),
        finished=session.finished,
    )


@router.get("/quiz/summary/{session_id}", response_model=SummaryOut)
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
