"""요청·응답 모양 (Pydantic) — 수업 61일차 schemas(DTO)와 같은 역할. TEAM_UPDATES 11/11 공유 정의"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str = Field(pattern='^(system|user|assistant)$')
    content: str = Field(max_length=20000)


class ChatTurnIn(BaseModel):
    """채팅 한 턴 = Django /travel_chat/ 가 받는 것 + Django 가 붙여 주는 값"""
    messages: list[Message] = Field(min_length=1, max_length=60)
    draft: Optional[dict[str, Any]] = None
    category_names: list[str] = []
    profile: Optional[dict[str, Any]] = None       # {gender, age_group} (같은 성별·나이대 리뷰 가중)
    today: Optional[str] = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')


class LlmIn(BaseModel):
    """call_llm 대신 (리뷰 요약·_ai_price). 도구 없는 한 번 호출"""
    messages: list[Message] = Field(min_length=1, max_length=60)
    json_mode: bool = Field(default=False, alias='json')
    max_tokens: Optional[int] = None


class LlmOut(BaseModel):
    text: str


class EmbedIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=256)


class EmbedOut(BaseModel):
    model: str
    vectors: list[list[float]]


class Health(BaseModel):
    ok: bool
    model: str
    embed_model: str
    db: bool
