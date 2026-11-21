from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


QuestionType = Literal["multiple_choice", "short_answer"]
DifficultyLevel = Literal["easy", "medium", "hard"]


class QuizGenerateRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=100, description="과목명")
    unit: str = Field(..., min_length=1, max_length=150, description="단원명")
    question_type: QuestionType = Field(default="multiple_choice", description="문제 유형")
    count: int = Field(default=5, ge=1, le=10, description="문항 수 (1~10)")
    difficulty: DifficultyLevel = Field(default="medium", description="난이도")

    @field_validator("subject", "unit")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("공백만 입력할 수 없습니다.")
        return cleaned


class QuizQuestion(BaseModel):
    id: int
    type: QuestionType
    question: str
    options: Optional[List[str]] = None
    answer: str
    explanation: str


class QuizGenerateResponse(BaseModel):
    subject: str
    unit: str
    question_type: QuestionType
    difficulty: DifficultyLevel
    questions: List[QuizQuestion]
