"""TRIPA AI 서버 (FastAPI) — B안: 채팅 에이전트 전체 (TEAM_UPDATES 11/11 공유 정의)

수업 54·56·61일차 구조: 브라우저 ↔ Django(앱 서버) ↔ FastAPI(AI 서버) ↔ LLM
- Django 의 sherpaapp.services(chat_service·embed_service)를 django.setup() 으로 그대로 불러 쓴다 (같은 DB·같은 캐시)
- Django 는 .env 의 AI_SERVER_URL 이 있을 때만 여기로 보낸다 (비우면 Django 가 직접 처리 = 예전과 같음)
- 헤더 X-AI-Token 이 AI_SERVER_TOKEN 과 같아야 한다 (토큰이 비어 있으면 검사 안 함 → 로컬 전용)
- 이 프로세스 안에서는 TRIPA_AI_SERVER=1 → call_llm·embed_texts 가 다시 자기 자신을 부르지 않음

실행 (저장소 맨 위 폴더에서):
    pj_django 가상환경의 python -m uvicorn ai_server.main:app --host 127.0.0.1 --port 8100
문서: http://127.0.0.1:8100/docs
"""
import os
import sys
from datetime import date
from pathlib import Path

os.environ['TRIPA_AI_SERVER'] = '1'          # call_llm·embed_texts 가 서버로 다시 보내지 않게 (django.setup 전에)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'pj_django'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pj_django.settings')

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import close_old_connections, connection  # noqa: E402
from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402

from sherpaapp.services import chat_service, embed_service  # noqa: E402

from .schemas import ChatTurnIn, EmbedIn, EmbedOut, Health, LlmIn, LlmOut  # noqa: E402

app = FastAPI(
    title='TRIPA AI 서버',
    version='1.0',
    description='여행 만들기 채팅 에이전트(LLM + 도구) · LLM 한 번 호출 · 임베딩. Django 만 부른다.',
)


def check_token(x_ai_token: str = Header(default='')):
    expected = getattr(settings, 'AI_SERVER_TOKEN', '') or ''
    if expected and x_ai_token != expected:
        raise HTTPException(status_code=401, detail='토큰이 올바르지 않아요.')


def _in_thread(work):
    """Django ORM 은 동기 → 스레드에서 돌리고, 끝나면 그 스레드의 DB 연결을 정리"""
    def run():
        close_old_connections()
        try:
            return work()
        finally:
            close_old_connections()
    return run_in_threadpool(run)


@app.get('/health', response_model=Health)
async def health():
    def work():
        try:
            connection.ensure_connection()
            db = True
        except Exception:
            db = False
        return Health(ok=True, model=getattr(settings, 'AI_MODEL', '') or '',
                      embed_model=getattr(settings, 'AI_EMBED_MODEL', '') or '', db=db)
    return await _in_thread(work)


@app.post('/chat/turn', dependencies=[Depends(check_token)])
async def chat_turn(body: ChatTurnIn):
    """여행 만들기 채팅 한 턴 → Django /travel_chat/ 와 같은 응답"""
    def work():
        return chat_service.run_chat_turn(
            [m.model_dump() for m in body.messages],
            body.draft,
            body.category_names,
            today=date.fromisoformat(body.today) if body.today else None,
            profile=body.profile,
        )
    try:
        return await _in_thread(work)
    except chat_service.ChatError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.post('/llm', response_model=LlmOut, dependencies=[Depends(check_token)])
async def llm(body: LlmIn):
    """도구 없는 LLM 한 번 (리뷰 요약·AI 가격 어림)"""
    def work():
        return chat_service.call_llm([m.model_dump() for m in body.messages])
    try:
        return LlmOut(text=await _in_thread(work))
    except chat_service.ChatError as error:
        raise HTTPException(status_code=502, detail=str(error))


@app.post('/embed', response_model=EmbedOut, dependencies=[Depends(check_token)])
async def embed(body: EmbedIn):
    """글 목록 → 벡터 목록"""
    def work():
        return embed_service.embed_texts(body.texts)
    try:
        vectors = await _in_thread(work)
    except embed_service.EmbedError as error:
        raise HTTPException(status_code=502, detail=str(error))
    return EmbedOut(model=settings.AI_EMBED_MODEL, vectors=vectors)
