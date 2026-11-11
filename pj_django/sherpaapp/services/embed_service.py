# 임베딩: 글을 숫자 목록(벡터)으로 바꿔 저장하고 비슷한 글 찾기 (TEAM_UPDATES 11/09 공유 정의)
import math
import requests
from django.conf import settings
from django.db import transaction
from sherpaapp.models import EmbedChunk, Review


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
    from . import ai_client          # AI_SERVER_URL 이 있으면 FastAPI /embed 에 맡김 (🟧 B안)
    if ai_client.remote():
        return ai_client.embed(texts)
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


# 장소별 리뷰를 한 덩어리 글로 묶어 임베딩해 저장 (kind='review'). 저장한 장소 수를 돌려준다
# kakao_ids를 주면 그 장소만, 안 주면 리뷰 2개 이상인 모든 장소
def index_reviews(kakao_ids=None, min_reviews=2):
    rows = Review.objects.exclude(kakao_id__isnull=True)
    if kakao_ids:
        rows = rows.filter(kakao_id__in=[str(k) for k in kakao_ids])

    # 1) 장소별로 리뷰 모으기  {kakao_id: {'name': 이름, 'texts': [글, …]}}
    places = {}
    for r in rows.values('kakao_id', 'place_name', 'content', 'tags'):
        p = places.setdefault(r['kakao_id'], {'name': r['place_name'], 'texts': []})
        p['texts'].append(r['content'] + ' ' + ' '.join(r['tags'] or []))

    # 2) 장소마다 한 덩어리 글로 저장
    done = 0
    for kid, p in places.items():
        if len(p['texts']) < min_reviews:
            continue
        text = p['name'] + ': ' + ' / '.join(p['texts'])[:2000]
        save_chunks('review', kid, [text], meta={'name': p['name'], 'count': len(p['texts'])})
        done += 1
    return done


# 이 장소와 리뷰가 비슷한 장소 top_k개 (리뷰 묶음 조각끼리 코사인). 아직 저장 안 된 장소면 []
def similar_places(kakao_id, top_k=5):
    # 1) 이 장소의 조각 (지금 모델로 저장된 것)
    me = EmbedChunk.objects.filter(kind='review', ref_id=str(kakao_id), model=_model()).first()
    if not me:
        return []

    # 2) 나를 뺀 다른 장소들과 비교
    found = []
    others = EmbedChunk.objects.filter(kind='review', model=_model()).exclude(ref_id=me.ref_id)
    for r in others:
        found.append({
            'kakao_id': r.ref_id,
            'name': r.meta.get('name'),
            'score': round(_cosine(me.vector, r.vector), 3),
        })

    # 3) 점수 높은 순 → 앞에서 top_k개
    found.sort(key=lambda d: d['score'], reverse=True)
    return found[:top_k]
