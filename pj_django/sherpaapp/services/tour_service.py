"""한국관광공사 TourAPI로 장소의 쉬는 날(휴무) 알아내기

1) 이름 검색(searchKeyword2)으로 같은 장소를 찾는다: 이름이 맞고 300m 안 (photo_service와 같은 기준)
2) 소개 정보(detailIntro2)에서 쉬는 날 문장을 읽는다 (예: '매주 월요일 / 1월 1일')
3) 문장을 규칙으로 바꿔서, 방문 날짜에 쉬는지 판단한다

관광지·박물관뿐 아니라 관광공사에 등록된 식당·시장도 쉬는 날이 있다.
관광공사에 없는 장소는 '모름'(None)으로 둔다.

open 모양 (mock.json): {"closed": true/false, "reason": "weekly_off" | "monthly_off" | "holiday" | null, "text": 원문}
"""

import logging
import re
from datetime import date

import requests
from django.conf import settings
from django.core.cache import cache

from .photo_service import TIMEOUT, TOUR_MAX_DISTANCE_M, _distance_m, _same_name, _to_float


logger = logging.getLogger(__name__)

TOUR_BASE = 'https://apis.data.go.kr/B551011/KorService2/'
CACHE_SECONDS = 60 * 60 * 24 * 7   # 같은 장소는 7일 동안 다시 묻지 않음 (TourAPI 하루 호출 수 제한)

WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일']
NTH_WORDS = {'첫째': 1, '첫번째': 1, '둘째': 2, '두번째': 2, '셋째': 3, '세번째': 3,
             '넷째': 4, '네번째': 4, '다섯째': 5, '다섯번째': 5, '마지막': -1}

# 소개 정보의 쉬는 날 칸 이름 (관광지·문화시설·음식점·쇼핑·레포츠·숙박마다 다름)
REST_KEYS = ('restdate', 'restdateculture', 'restdatefood', 'restdateshopping', 'restdateleports')


# =========================================================
# TourAPI
# =========================================================

def _tour_get(operation, **params):
    key = getattr(settings, 'TOUR_API_KEY', '')
    if not key:
        return []

    response = requests.get(TOUR_BASE + operation, params={
        'serviceKey': key, 'MobileOS': 'ETC', 'MobileApp': 'TRIPA', '_type': 'json', **params,
    }, timeout=TIMEOUT)
    response.raise_for_status()

    try:
        items = response.json()['response']['body']['items']
    except (ValueError, KeyError, TypeError):
        return []

    # 결과가 없으면 items가 빈 문자열로 온다
    items = items.get('item') if isinstance(items, dict) else None
    if isinstance(items, dict):
        items = [items]
    return items or []


def find_tour_item(name, lat=None, lon=None):
    """관광공사에서 같은 장소 하나 (contentid, contenttypeid 등). 없으면 None."""
    for item in _tour_get('searchKeyword2', keyword=name, numOfRows=10, pageNo=1):
        if not _same_name(name, item.get('title')):
            continue

        if lat is not None and lon is not None:
            ty, tx = _to_float(item.get('mapy')), _to_float(item.get('mapx'))
            if ty is None or tx is None or _distance_m(lat, lon, ty, tx) > TOUR_MAX_DISTANCE_M:
                continue

        return item

    return None


def rest_text(name, lat=None, lon=None, kakao_id=None):
    """장소의 쉬는 날 원문. 관광공사에 없거나 실패하면 None, 쉬는 날 칸이 비었으면 ''."""
    cache_key = 'tour_rest:%s' % (kakao_id or '%s:%s:%s' % (name, lat, lon))
    saved = cache.get(cache_key)
    if saved is not None:
        return saved or None

    text = ''
    try:
        item = find_tour_item(name, lat, lon)
        if item:
            intro = _tour_get('detailIntro2', contentId=item.get('contentid'),
                              contentTypeId=item.get('contenttypeid'))
            intro = intro[0] if intro else {}
            text = next((intro.get(k) for k in REST_KEYS if intro.get(k)), '') or ''
            text = re.sub(r'<br\s*/?>', ' / ', text).strip()
    except requests.RequestException:
        logger.warning('관광공사 쉬는 날 조회 실패: %s', name)
        return None   # 실패는 저장하지 않고 다음에 다시 물음

    cache.set(cache_key, text, CACHE_SECONDS)
    return text or None


# =========================================================
# 쉬는 날 문장 → 규칙
# =========================================================

def parse_rest(text):
    """'매주 월요일 / 1월 1일' 같은 문장을 규칙으로.

    돌려주는 값: {'weekly': {0}, 'monthly': [(n번째, 요일)], 'dates': [(월, 일)], 'always_open': bool}
    설날·추석처럼 해마다 바뀌는 날은 읽지 않는다.
    """
    rules = {'weekly': set(), 'monthly': [], 'dates': [], 'always_open': False}
    text = str(text or '')

    if not text.strip():
        return rules

    # '(단, 월요일이 공휴일인 경우 다음날 휴관)' 같은 괄호 안 예외는 빼고 읽는다
    main = re.sub(r'\(.*?\)', ' ', text)

    if re.search(r'연중\s*무휴|휴무\s*없음|무휴', main):
        rules['always_open'] = True

    # 매월 첫째, 셋째 화요일 / 둘째·넷째 주 일요일
    nth = '|'.join(sorted(NTH_WORDS, key=len, reverse=True))
    monthly_re = re.compile(r'((?:%s)(?:\s*(?:주)?\s*[,·및]\s*(?:%s))*)\s*(?:주\s*)?([월화수목금토일])\s*요일' % (nth, nth))

    for match in monthly_re.finditer(main):
        day = WEEKDAYS.index(match.group(2))
        for word in re.findall(nth, match.group(1)):
            rules['monthly'].append((NTH_WORDS[word], day))

    # 매주 월요일, 월·화요일 (몇째 주 표현은 위에서 읽었으니 지우고 읽음)
    weekly_part = monthly_re.sub(' ', main)
    for match in re.finditer(r'([월화수목금토일](?:\s*(?:요일)?\s*[,·및]\s*[월화수목금토일])*)\s*요일', weekly_part):
        for ch in re.findall(r'[월화수목금토일]', match.group(1)):
            rules['weekly'].add(WEEKDAYS.index(ch))

    # 1월 1일
    for match in re.finditer(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', main):
        rules['dates'].append((int(match.group(1)), int(match.group(2))))

    if rules['weekly'] or rules['monthly']:
        rules['always_open'] = False

    return rules


def _nth_weekday(day):
    """그 달의 몇 번째 같은 요일인지, 그리고 마지막인지."""
    nth = (day.day - 1) // 7 + 1
    is_last = (day.day + 7) > _month_days(day)
    return nth, is_last


def _month_days(day):
    nxt = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return (nxt - date(day.year, day.month, 1)).days


def closed_on(text, day):
    """그 날짜에 쉬는지. {'closed', 'reason', 'text'} / 쉬는 날 정보가 없으면 None."""
    if not text or not day:
        return None

    rules = parse_rest(text)
    nth, is_last = _nth_weekday(day)

    if day.weekday() in rules['weekly']:
        return {'closed': True, 'reason': 'weekly_off', 'text': text}

    for n, weekday in rules['monthly']:
        if weekday == day.weekday() and (n == nth or (n == -1 and is_last)):
            return {'closed': True, 'reason': 'monthly_off', 'text': text}

    if (day.month, day.day) in rules['dates']:
        return {'closed': True, 'reason': 'holiday', 'text': text}

    return {'closed': False, 'reason': None, 'text': text}


def place_open(name, day, lat=None, lon=None, kakao_id=None):
    """장소가 그 날짜에 여는지 (open 모양). 모르면 None."""
    return closed_on(rest_text(name, lat, lon, kakao_id), day)


REASON_LABELS = {'weekly_off': '정기 휴무', 'monthly_off': '정기 휴무', 'holiday': '휴무일'}


def drop_closed(items, day):
    """추천 카드마다 open을 붙이고, 그 날 쉬는 곳은 뺀다. (남은 카드, 뺀 카드) 를 돌려준다."""
    kept, closed = [], []

    for item in items:
        status = place_open(item.get('name'), day, item.get('lat'), item.get('lon'), item.get('kakao_id')) if day else None

        # 관광공사에 없으면 부산 장소 표의 휴무 요일로 본다 ('매주 월요일')
        rest = (item.get('pick') or {}).get('rest')
        if status is None and day and rest:
            status = closed_on(rest, day)

        item['open'] = status

        if status and status['closed']:
            closed.append(item)
        else:
            kept.append(item)

    # 이름은 다르지만 쉬는 곳과 같은 곳이면 같이 뺀다
    # ('부산박물관 동래관'은 카카오 이름일 뿐, 주소가 부산박물관과 같음 → 관광공사에서 못 찾음)
    for item in list(kept):
        same = next((c for c in closed if _same_place(item, c)), None)

        if same:
            item['open'] = dict(same['open'])
            kept.remove(item)
            closed.append(item)

    return kept, closed


def _squash_name(text):
    return re.sub(r'[\s()\[\]·.,-]+', '', str(text or '')).lower()


def _same_place(a, b):
    """주소가 같고 이름 앞부분(3글자 이상)이 같으면 같은 곳으로 본다."""
    addr_a, addr_b = _squash_name(a.get('addr')), _squash_name(b.get('addr'))

    if not addr_a or addr_a != addr_b:
        return False

    name_a, name_b = _squash_name(a.get('name')), _squash_name(b.get('name'))
    common = 0

    for x, y in zip(name_a, name_b):
        if x != y:
            break
        common += 1

    return common >= 3
