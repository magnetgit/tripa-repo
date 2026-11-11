"""여행지 정보 RAG — 한국관광공사 소개글을 근거로 답하기 (🟩 11/11, 수업 49·50일차 임베딩·RAG)

흐름
  1) 장소 이름 → 관광공사 장소(contentid) 찾기
  2) 소개글(detailCommon2 overview) + 이용 안내(detailIntro2: 이용시간·쉬는 날·입장료·주차)
  3) 300~500자 조각으로 자르기 → 🟧 embed_service.save_chunks('tour', contentid, 조각들, meta)
  4) 질문 → embed_service.search(질문, kind='tour') → 비슷한 조각 3개 (그 장소 조각 먼저)
  5) 에이전트 도구(agent_tools.travel_info)가 조각을 근거로 주고, AI는 답 끝에 출처를 붙임

새 표·마이그레이션 없음 (🟧 embed_chunk 표 그대로, kind='tour')
미리 넣기: python manage.py index_tour  (부산 장소 표 + 데모 여행지 표의 관광지)
안 넣은 곳도 처음 물을 때 그 자리에서 넣음 (한 번 넣으면 다음부턴 바로)
"""
import logging
import re

import requests

from ..models import EmbedChunk
from . import embed_service
from .photo_service import _same_name
from .tour_service import _tour_get, find_tour_item

logger = logging.getLogger(__name__)

KIND = 'tour'
CHUNK_MIN = 300          # 조각 길이 (글자)
CHUNK_MAX = 500
MIN_SCORE = 0.25         # 이보다 덜 비슷한 조각은 근거로 안 씀 (지어내지 않게)


class TourQuotaError(Exception):
    """관광공사 API 하루 사용량 초과 (429). 장소마다 계속 부르지 않고 바로 멈추려고 따로 둠"""


def _tour_call(operation, **params):
    """_tour_get + 429면 TourQuotaError (다른 실패는 RequestException 그대로)"""
    try:
        return _tour_get(operation, **params)
    except requests.HTTPError as error:
        if getattr(error.response, 'status_code', None) == 429:
            raise TourQuotaError('관광공사 API 오늘 사용량을 다 썼어요') from None
        raise

# 이용 안내로 붙일 detailIntro2 칸 (관광지·문화시설·레포츠·쇼핑·음식점 칸 이름이 조금씩 다름)
INTRO_LABELS = (
    ('usetime', '이용시간'), ('usetimeculture', '이용시간'), ('usetimeleports', '이용시간'),
    ('opentime', '영업시간'), ('opentimefood', '영업시간'),
    ('restdate', '쉬는 날'), ('restdateculture', '쉬는 날'), ('restdateleports', '쉬는 날'),
    ('restdateshopping', '쉬는 날'), ('restdatefood', '쉬는 날'),
    ('usefee', '이용요금'), ('usefeeleports', '이용요금'),
    ('parking', '주차'), ('parkingculture', '주차'), ('parkingleports', '주차'),
    ('parkingshopping', '주차'), ('parkingfood', '주차'),
    ('expguide', '체험 안내'), ('infocenter', '문의'), ('infocenterculture', '문의'),
    ('firstmenu', '대표 메뉴'), ('treatmenu', '메뉴'),
)


def _plain(text):
    """관광공사 글의 <br>·태그·여러 칸 띄어쓰기 정리"""
    text = re.sub(r'<br\s*/?>', ' ', str(text or ''), flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _squash(text):
    return re.sub(r'\s+', '', str(text or ''))


def split_text(text, size=CHUNK_MAX, least=CHUNK_MIN):
    """긴 글 → 문장 단위로 묶은 조각들 (조각마다 least~size 글자쯤). 짧은 글은 한 조각"""
    text = _plain(text)
    if not text:
        return []
    if len(text) <= size:
        return [text]

    sentences = re.split(r'(?<=[.!?다요])\s+', text)
    chunks, current = [], ''
    for sentence in sentences:
        while len(sentence) > size:                 # 마침표 없이 아주 긴 문장은 잘라서
            chunks.append(sentence[:size])
            sentence = sentence[size:]
        if current and len(current) + 1 + len(sentence) > size and len(current) >= least:
            chunks.append(current)
            current = sentence
        else:
            current = (current + ' ' + sentence).strip()
    if current:
        if chunks and len(current) < least // 2:    # 끝 조각이 너무 짧으면 앞 조각에 붙임
            chunks[-1] = chunks[-1] + ' ' + current
        else:
            chunks.append(current)
    return chunks


TRIM_WORDS = ('유원지', '정거장', '해변열차', '스카이워크')   # 관광공사 이름에 없는 경우가 많은 꼬리말


def _keywords(name):
    """검색어 후보: 그대로 → 첫 낱말('해운대블루라인파크 미포정거장' → '해운대블루라인파크') → 꼬리말 뺀 것('태종대유원지' → '태종대')"""
    words = [name]
    if ' ' in name.strip():
        words.append(name.split()[0])
    for tail in TRIM_WORDS:
        if _squash(name).endswith(tail) and len(_squash(name)) > len(tail) + 1:
            words.append(_squash(name)[: -len(tail)])
    return list(dict.fromkeys(w for w in words if w))


def find_item(name, lat=None, lon=None):
    """관광공사 장소 하나 (이름이 다른 곳이 끼어들지 않게 이름이 똑같거나 '부산 감천문화마을'처럼 끝이 같은 것만)
    다 없으면 tour_service.find_tour_item (좌표 1km 안일 때만)"""
    for keyword in _keywords(name):
        try:
            items = _tour_call('searchKeyword2', keyword=keyword, numOfRows=30, pageNo=1)
        except TourQuotaError:
            raise
        except requests.RequestException:
            logger.warning('관광공사 검색 실패: %s', keyword)
            return None
        key = _squash(keyword)
        for same in (lambda t: t == key, lambda t: t.endswith(key)):
            for item in items:
                if same(_squash(item.get('title'))):
                    return item

    if lat is None or lon is None:
        return None
    try:
        return find_tour_item(name, lat, lon)
    except requests.RequestException:
        return None


def place_texts(item):
    """관광공사 장소 → 조각 글 목록 (소개글 조각들 + 이용 안내 한 조각). 앞에 장소 이름을 붙여 검색이 잘 되게"""
    content_id = item.get('contentid')
    title = _plain(item.get('title'))
    try:
        common = (_tour_call('detailCommon2', contentId=content_id) or [{}])[0]
        intro = (_tour_call('detailIntro2', contentId=content_id,
                            contentTypeId=item.get('contenttypeid')) or [{}])[0]
    except TourQuotaError:
        raise
    except requests.RequestException:
        logger.warning('관광공사 소개글 실패: %s', title)
        return []

    texts = ['[%s] %s' % (title, part) for part in split_text(common.get('overview'))]

    lines, seen = [], set()
    for key, label in INTRO_LABELS:
        value = _plain(intro.get(key))
        if value and label not in seen:
            seen.add(label)
            lines.append('%s: %s' % (label, value))
    if lines:
        texts.append('[%s 이용 안내] %s' % (title, ' / '.join(lines)))
    return texts


def index_place(name, lat=None, lon=None):
    """장소 하나를 관광공사 글로 넣기 → {'content_id', 'name', 'chunks'} 또는 None(관광공사에 없음)"""
    item = find_item(name, lat, lon)
    if not item:
        return None
    texts = place_texts(item)
    if not texts:
        return None
    meta = {
        'name': _plain(item.get('title')),
        'addr': _plain(item.get('addr1')),
        'source': '한국관광공사',
    }
    saved = embed_service.save_chunks(KIND, item.get('contentid'), texts, meta=meta)
    return {'content_id': str(item.get('contentid')), 'name': meta['name'], 'chunks': saved}


def indexed_id(name):
    """이미 넣은 장소면 contentid (지금 임베딩 모델 기준), 없으면 None"""
    rows = list(EmbedChunk.objects.filter(kind=KIND, model=embed_service._model(), seq=0).only('ref_id', 'meta'))
    for same in (lambda a, b: _squash(a) == _squash(b), _same_name):   # 똑같은 이름 먼저
        for row in rows:
            if same(name, (row.meta or {}).get('name')):
                return row.ref_id
    return None


def ask(question, place=None, top_k=3):
    """질문 → 근거 조각 (그 장소 조각을 먼저, 덜 비슷한 건 뺌)
    → {'place', 'found', 'chunks': [{'name', 'text', 'score'}], 'indexed_now', 'error'}  (EmbedError 는 부른 쪽에서)"""
    content_id, indexed_now, error = None, False, None
    if place:
        content_id = indexed_id(place)
        if not content_id:
            try:
                done = index_place(place)
            except TourQuotaError as quota:
                done, error = None, str(quota)
            if done:
                content_id, indexed_now = done['content_id'], True

    found = embed_service.search(('%s %s' % (place or '', question)).strip(), kind=KIND, top_k=30)
    mine = [f for f in found if content_id and f['ref_id'] == content_id]
    others = [f for f in found if not (content_id and f['ref_id'] == content_id) and f['score'] >= MIN_SCORE]
    # 장소를 물었으면 그 장소 조각만 (다른 곳 얘기가 섞이지 않게, 관광공사에 없는 곳이면 빈 목록)
    # 장소 없이 물었으면 ('바다 보이는 절') 비슷한 곳들
    picked = (mine if place else others)[:top_k]

    return {
        'place': place,
        'found': bool(picked),
        'chunks': [{
            'name': (f['meta'] or {}).get('name'),
            'text': f['text'],
            'score': f['score'],
        } for f in picked],
        'indexed_now': indexed_now,
        'error': error,              # 관광공사 사용량 초과 등 (없으면 None)
    }
