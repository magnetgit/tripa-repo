"""Django → FastAPI AI 서버 (ai_server/) 호출 — B안 (TEAM_UPDATES 11/11 공유 정의)

- .env 의 AI_SERVER_URL 이 비어 있으면 enabled() 가 False → 지금처럼 Django 가 직접 처리
- FastAPI 프로세스 안(TRIPA_AI_SERVER=1)에서는 remote() 가 False → call_llm·embed_texts 가 자기 자신을 다시 부르지 않음
- 실패하면 사용자에게 보여 줘도 되는 ChatError / EmbedError 로 바꿔 던짐 (지금 화면 오류 처리 그대로)
"""
import os

import requests
from django.conf import settings


def enabled():
    return bool((getattr(settings, 'AI_SERVER_URL', '') or '').strip())


def remote():
    """이 프로세스(Django)가 AI 일을 FastAPI 에 맡겨야 하는지"""
    return enabled() and os.environ.get('TRIPA_AI_SERVER') != '1'


def _post(path, payload, timeout):
    url = settings.AI_SERVER_URL.rstrip('/') + path
    try:
        response = requests.post(
            url, json=payload, timeout=timeout,
            headers={'X-AI-Token': getattr(settings, 'AI_SERVER_TOKEN', '') or ''},
        )
    except requests.RequestException as error:
        raise ConnectionError('AI 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.') from error
    if response.status_code != 200:
        try:
            detail = response.json().get('detail')
        except ValueError:
            detail = None
        raise RuntimeError(detail if isinstance(detail, str) else 'AI 서버 오류 (%d)' % response.status_code)
    return response.json()


def _timeout():
    return getattr(settings, 'AI_TIMEOUT', 40) + 20


def chat_turn(messages, draft, category_names, today=None, profile=None):
    """chat_service.run_chat_turn 과 같은 인자·같은 응답"""
    from .chat_service import ChatError
    try:
        return _post('/chat/turn', {
            'messages': messages, 'draft': draft, 'category_names': list(category_names),
            'profile': profile, 'today': today.isoformat() if today else None,
        }, _timeout() * 2)                 # 도구 호출·사진·비용까지 한 턴
    except (ConnectionError, RuntimeError) as error:
        raise ChatError(str(error)) from error


def llm(messages):
    """chat_service.call_llm(messages) 와 같은 답 문자열 (도구 없음)"""
    from .chat_service import ChatError
    try:
        return _post('/llm', {'messages': messages}, _timeout())['text']
    except (ConnectionError, RuntimeError, KeyError) as error:
        raise ChatError(str(error)) from error


def embed(texts):
    """embed_service.embed_texts(texts) 와 같은 벡터 목록"""
    from .embed_service import EmbedError
    try:
        return _post('/embed', {'texts': list(texts)}, _timeout())['vectors']
    except (ConnectionError, RuntimeError, KeyError) as error:
        raise EmbedError(str(error)) from error
