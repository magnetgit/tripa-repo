# TRIPA AI 서버 (FastAPI) — B안

여행 만들기 **채팅 에이전트 전체**(LLM + 도구 호출 + 추천 카드)를 Django 밖 FastAPI 프로세스에서 돌린다.
수업 54·56·61일차 구조: 브라우저 ↔ Django(앱 서버) ↔ FastAPI(AI 서버) ↔ LLM

```
브라우저 → Django :8000  /travel_chat/ (로그인·요청 횟수 제한·미리보기·적용·DB 쓰기)
              │  .env AI_SERVER_URL 이 있으면
              ▼  POST /chat/turn · /llm · /embed   (헤더 X-AI-Token)
           FastAPI :8100 (이 폴더) — django.setup() 으로 sherpaapp.services 그대로 (같은 DB·캐시)
              ▼
           LLM(OpenAI·Ollama) · 카카오 · TourAPI · Open-Meteo
```

## 주소
| 주소 | 하는 일 |
|---|---|
| `GET /health` | `{ok, model, embed_model, db}` |
| `POST /chat/turn` | 채팅 한 턴 = `chat_service.run_chat_turn` (응답은 `/travel_chat/` 와 같음) |
| `POST /llm` | `call_llm` 한 번 (도구 없음: 리뷰 요약·AI 가격) |
| `POST /embed` | `embed_texts` (리뷰 색인·비슷한 장소) |

자동 문서: http://127.0.0.1:8100/docs

## 로컬 실행
```bash
# 저장소 맨 위 폴더에서 (pj_django 가상환경)
venv/Scripts/python.exe -m pip install -r ai_server/requirements.txt
venv/Scripts/python.exe -m uvicorn ai_server.main:app --host 127.0.0.1 --port 8100
```
그다음 `pj_django/.env` 에 `AI_SERVER_URL=http://127.0.0.1:8100` 을 넣고 Django 를 다시 켜면 채팅이 FastAPI 를 거친다.
**비워 두면 예전처럼 Django 가 직접 처리** (팀원 로컬 기본값).

## 설정 (`pj_django/.env`, Django·FastAPI 같은 파일)
- `AI_SERVER_URL` — 비면 Django 직접, 있으면 FastAPI 로
- `AI_SERVER_TOKEN` — 둘이 같은 값. 비면 토큰 검사 안 함(로컬 전용)
- 나머지 AI 설정(`AI_BASE_URL`·`AI_MODEL`·`AI_EMBED_MODEL` …)은 FastAPI 가 그대로 읽음

## 지킬 것
- 채팅 턴 안(`chat_service`·`agent_tools`)에서 `request`·`session` 을 쓰지 않는다 (FastAPI 에는 없음)
- 이 프로세스 안에서는 `TRIPA_AI_SERVER=1` → `call_llm`·`embed_texts` 가 다시 자기 자신을 부르지 않음
