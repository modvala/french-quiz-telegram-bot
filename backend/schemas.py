from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from uuid import UUID
import os


class Option(BaseModel):
    id: int
    text: str
    audio: Optional[str] = None  # путь к аудио варианта


class Question(BaseModel):
    id: int
    prompt_text: str
    country: Optional[str] = None
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
    # per-session Question objects keyed by position index (0..n-1)
    question_map: Dict[int, Question] = Field(default_factory=dict)


class StartQuizIn(BaseModel):
    user_id: str
    # Default number of questions may be set via env N_QUESTIONS
    n_questions: int = int(os.environ.get("N_QUESTIONS", 10))


class StartQuizOut(BaseModel):
    session_id: UUID
    total: int
    first_question_id: int


class OptionResponse(BaseModel):
    number: int  # номер для выбора (1, 2, 3, 4)
    audio_url: Optional[str] = None  # аудио для воспроизведения


class QuestionOut(BaseModel):
    session_id: UUID
    index: int
    total: int
    question_id: int
    prompt_text: str
    prompt_audio_url: Optional[str] = None
    options: List[OptionResponse]  # возвращаем номера с аудио


class AnswerIn(BaseModel):
    session_id: UUID
    question_id: int
    selected_option_id: int


class AnswerOut(BaseModel):
    correct: bool
    correct_option_id: int
    correct_option_text: str
    correct_option_audio_url: Optional[str] = None  # если correct=True и есть аудио
    country: Optional[str] = None
    score: int
    index: int
    total: int
    finished: bool


class SummaryOut(BaseModel):
    session_id: UUID
    total: int
    correct_count: int
    details: List[Dict[str, str]]  # {question_id, result}
