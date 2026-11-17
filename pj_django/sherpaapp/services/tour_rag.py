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
from .photo_service import _distance_m, _same_name, _to_float
from .tour_service import _tour_get, find_tour_item

logger = logging.getLogger(__name__)

KIND = 'tour'
CHUNK_MIN = 300          # 조각 길이 (글자)
CHUNK_MAX = 500
MIN_SCORE = 0.25         # 이보다 덜 비슷한 조각은 근거로 안 씀 (지어내지 않게)
# 이름으로 찾은 관광공사 장소가 우리 장소 좌표에서 이 거리 안이어야 같은 곳으로 봄 (🟧 11/16)
# 이름만 보면 '전주 신중앙시장'에 '목포 신중앙시장', '전주 서부시장'에 '강릉 서부시장'이 붙었음 (끝 글자가 같아서).
# 넓은 공원·산은 대표 좌표가 몇 km 떨어질 수 있어서 넉넉히 20km (같은 도시 안), 다른 도시는 그보다 훨씬 멂
NAME_MATCH_MAX_M = 20000
EXACT_BONUS_M = 2000     # 이름이 똑같은 후보는 이만큼 가깝게 쳐 준다


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


def _item_distance(item, lat, lon):
    """관광공사 장소와 (lat, lon) 사이 거리(m). 관광공사 쪽 좌표가 없으면 None"""
    ty, tx = _to_float(item.get('mapy')), _to_float(item.get('mapx'))
    if ty is None or tx is None:
        return None
    return _distance_m(lat, lon, ty, tx)


def _near_enough(item, lat, lon, exact):
    """좌표를 알 때: 같은 도시 안(NAME_MATCH_MAX_M)이어야 함. 관광공사에 좌표가 없으면 이름이 똑같을 때만 인정"""
    if lat is None or lon is None:
        return True                      # 좌표 없이 물은 경우(채팅)는 예전처럼 이름만
    distance = _item_distance(item, lat, lon)
    if distance is None:
        return exact
    return distance <= NAME_MATCH_MAX_M


def find_item(name, lat=None, lon=None):
    """관광공사 장소 하나 (이름이 다른 곳이 끼어들지 않게 이름이 똑같거나 '부산 감천문화마을'처럼 끝이 같은 것만)
    좌표(lat, lon)를 주면 그 근처(같은 도시 안) 것만 — 다른 도시의 같은 이름 장소가 붙지 않게 (🟧 11/16)
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
        if lat is None or lon is None:
            # 좌표 없이 물은 경우(채팅): 예전처럼 이름이 똑같은 것 먼저, 그다음 끝이 같은 것
            for same in (lambda t: t == key, lambda t: t.endswith(key)):
                for item in items:
                    if same(_squash(item.get('title'))):
                        return item
            continue
        # 좌표를 알면: 이름이 맞는 후보 가운데 **가장 가까운 곳** (🟧 11/16)
        # '여수 장도'는 이름이 똑같은 보성 '장도'(19.8km)보다 바로 옆 '예술의 섬 장도'(0km)가 맞음
        # 이름이 똑같은 후보는 2km 만큼 가깝게 쳐 준다 (같은 동네에 비슷한 이름이 있으면 똑같은 이름 쪽)
        best, best_score = None, None
        for item in items:
            title = _squash(item.get('title'))
            exact = title == key
            if not (exact or title.endswith(key)) or not _near_enough(item, lat, lon, exact):
                continue
            distance = _item_distance(item, lat, lon)
            score = NAME_MATCH_MAX_M if distance is None else distance - (EXACT_BONUS_M if exact else 0)
            if best is None or score < best_score:
                best, best_score = item, score
        if best is not None:
            return best

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
        # 🟧 11/16 관광공사 좌표도 남김 (추가만) → indexed_id 가 같은 이름의 다른 도시 장소를 걸러 냄
        'lat': _to_float(item.get('mapy')),
        'lon': _to_float(item.get('mapx')),
    }
    saved = embed_service.save_chunks(KIND, item.get('contentid'), texts, meta=meta)
    return {'content_id': str(item.get('contentid')), 'name': meta['name'], 'chunks': saved}


def _row_far(meta, lat, lon):
    """저장해 둔 장소(meta)가 (lat, lon)에서 너무 먼지. 어느 한쪽 좌표를 모르면 False (판단 못 함 → 예전처럼 이름만)"""
    if lat is None or lon is None:
        return False
    my, mx = _to_float((meta or {}).get('lat')), _to_float((meta or {}).get('lon'))
    if my is None or mx is None:
        return False
    return _distance_m(lat, lon, my, mx) > NAME_MATCH_MAX_M


def _row_other_region(meta, region):
    """좌표 없이 넣은 예전 줄: 주소에 여행 지역 앞 두 글자('전주')가 없으면 다른 지역 (🟩 11/17, wrong_region 과 같은 규칙)"""
    if not region or _to_float((meta or {}).get('lat')) is not None:
        return False
    addr = (meta or {}).get('addr') or ''
    return bool(addr) and region[:2] not in addr


def indexed_id(name, lat=None, lon=None, region=None):
    """이미 넣은 장소면 contentid (지금 임베딩 모델 기준), 없으면 None
    좌표를 주면 너무 먼 곳(다른 도시의 같은 이름)은 건너뜀 (🟧 11/16, 좌표를 저장해 둔 줄만)
    region(여행 지역)을 주면 좌표가 없는 예전 줄도 주소로 거름 (🟩 11/17)"""
    rows = list(EmbedChunk.objects.filter(kind=KIND, model=embed_service._model(), seq=0).only('ref_id', 'meta'))
    for same in (lambda a, b: _squash(a) == _squash(b), _same_name):   # 똑같은 이름 먼저
        for row in rows:
            if (same(name, (row.meta or {}).get('name')) and not _row_far(row.meta, lat, lon)
                    and not _row_other_region(row.meta, region)):
                return row.ref_id
    return None


def wrong_region(region, name, lat=None, lon=None):
    """이미 넣은 줄이 다른 지역 장소인지 → 그 줄의 (contentid, 저장된 이름, 주소) 또는 None  (🟧 11/16, index_tour --fix-wrong)

    11/16 전에 넣은 줄에는 좌표가 없어서 주소로 본다: 주소에 지역 이름 앞 두 글자('전주'·'울릉')가 없으면 의심.
    좌표가 있는 줄은 거리로 본다.
    """
    content_id = indexed_id(name)                 # 좌표 없이: 예전 규칙으로 붙은 줄을 그대로 찾음
    if not content_id:
        return None
    row = EmbedChunk.objects.filter(kind=KIND, ref_id=content_id, seq=0).only('meta').first()
    meta = (row.meta if row else None) or {}
    if _to_float(meta.get('lat')) is not None and lat is not None:
        wrong = _row_far(meta, lat, lon)
    else:
        addr = meta.get('addr') or ''
        wrong = bool(addr) and (region or '')[:2] not in addr
    return (content_id, meta.get('name'), meta.get('addr')) if wrong else None


def ask(question, place=None, top_k=3, lat=None, lon=None, region=None):
    """질문 → 근거 조각 (그 장소 조각을 먼저, 덜 비슷한 건 뺌)
    → {'place', 'found', 'chunks': [{'name', 'text', 'score'}], 'indexed_now', 'error'}  (EmbedError 는 부른 쪽에서)
    lat·lon(그 장소 좌표)·region(여행 지역)을 주면 다른 도시의 같은 이름 장소를 안 씀 (🟩 11/17, 인자 추가만)"""
    content_id, indexed_now, error = None, False, None
    if place:
        content_id = indexed_id(place, lat, lon, region)
        if not content_id:
            try:
                done = index_place(place, lat, lon)
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
