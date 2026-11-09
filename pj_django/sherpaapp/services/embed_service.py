# 임베딩: 글을 숫자 목록(벡터)으로 바꿔 저장하고 비슷한 글 찾기 (TEAM_UPDATES 11/09 공유 정의)
import math
import requests
from django.conf import settings
from django.db import transaction
from sherpaapp.models import EmbedChunk


TIMEOUT = 30


# 임베딩이 실패했을 때 던지는 오류 (주소·키가 틀림, 응답 실패 등)
# 🟩 등 다른 곳에서는 except EmbedError 로 잡아서 처리
class EmbedError(Exception):
    """임베딩 실패"""


# 지금 쓰는 임베딩 모델 이름 (.env의 AI_EMBED_MODEL, 설정 A: text-embedding-3-small / 설정 B: bge-m3)
# 모델이 다르면 숫자끼리 비교할 수 없어서, 저장·검색 때 이 이름으로 거른다
def _model():
    return settings.AI_EMBED_MODEL


# 글 목록 → 숫자 목록(벡터) 목록
# 예: ['해운대 바다', '자갈치시장'] → [[0.002, 0.01, ...], [...]]  (OpenAI는 1536개, bge-m3는 1024개)
# OpenAI 호환 /embeddings 주소로 보낸다 (Ollama도 같은 방식). 실패하면 EmbedError
def embed_texts(texts):
    if not texts:
        return []
    base = (getattr(settings, 'AI_BASE_URL', '') or '').rstrip('/')
    api_key = getattr(settings, 'AI_API_KEY', '') or ''
    headers = {'Authorization': 'Bearer ' + api_key} if api_key else {}
    res = requests.post(f'{base}/embeddings', json={'model': _model(), 'input': texts}, headers=headers, timeout=TIMEOUT)
    if not res.ok:
        raise EmbedError('임베딩 실패: '+ str(res.status_code))
    result = [d['embedding'] for d in res.json()['data']]
    return result


# 글 조각들을 벡터로 바꿔 embed_chunk 표에 저장하고, 저장한 개수를 돌려준다
# kind: 'review'(리뷰 묶음) / 'tour'(관광공사 소개글), ref_id: kakao_id 또는 관광공사 contentid
# 같은 kind·ref_id·모델의 옛 조각은 지우고 다시 저장 (임베딩이 실패하면 옛 조각은 그대로 남음)
def save_chunks(kind, ref_id, texts, meta=None):
    texts = [t for t in texts if t and t.strip()]
    if not texts:
        return 0
    vectors = embed_texts(texts)
    with transaction.atomic():
        EmbedChunk.objects.filter(
            kind=kind,
            ref_id=str(ref_id),
            model=_model()
            ).delete()
        rows = []
        for n, (text, vec) in enumerate(zip(texts, vectors)):
            rows.append(EmbedChunk(kind=kind, ref_id=str(ref_id), seq=n, text=text, vector=vec, model=_model(), meta=meta or {}))
        EmbedChunk.objects.bulk_create(rows)
    return len(texts)


# 질문과 가장 비슷한 조각 top_k개를 점수 높은 순으로 돌려준다
# 돌려주는 모양: [{kind, ref_id, seq, text, score, meta}, ...]  (TEAM_UPDATES 11/09 공유 정의)
# kind를 주면 그 종류만 (예: 🟩 여행지 RAG는 kind='tour'), 지금 모델로 저장한 것만 찾는다
def search(query, kind=None, top_k=3):
    if not query:
        return []
    q = embed_texts([query])[0]
    rows = EmbedChunk.objects.filter(model=_model())
    if kind:
        rows = rows.filter(kind=kind)
    found = []
    for r in rows:
        found.append({
            'kind': r.kind,
            'ref_id': r.ref_id,
            'seq': r.seq,
            'text': r.text,
            'score': round(_cosine(q, r.vector), 3),
            'meta': r.meta
        })
    found.sort(key=lambda d: d['score'], reverse=True)
    return found[:top_k]


# 두 벡터가 얼마나 비슷한지 (-1~1, 1에 가까울수록 비슷). 크기가 0이면 0
def _cosine(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(y*y for y in b))
    if not na or not nb:
        return 0
    return dot / (na * nb)
