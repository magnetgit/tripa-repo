"""
예산 AI (🟦): 장소 가격 → 인원 기준 예상 비용 → 분류별 예산

1) 가격 찾기 (한국관광공사 TourAPI에 나와 있는 요금 문장)
   - 관광지(12): detailInfo2 '입장료'      예) '- 개인 대인 3,000원 ...'
   - 문화시설(14)·레포츠(28)·축제(15): detailIntro2 usefee·usefeeleports·usetimefestival
   - 숙박(32): detailInfo2 객실 요금(roomoffseasonminfee1 등) 중 가장 싼 방, 방 기준 인원(roombasecount)
   - 성인·어른·대인·일반 요금을 먼저 읽고, 없으면 처음 나온 금액. '무료'만 있으면 0원
2) 관광공사에 요금이 없으면 분류별 보통 가격으로 '예상'(source='estimate')
   - 식당은 메뉴 종류(횟집·고기·분식 …)로, 카페는 음료 한 잔, 숙소는 방 하나 하룻밤
3) 인원 계산
   - 1인 요금(unit='person'): 1인 요금 × 인원
   - 방 요금(unit='room'): 방 요금 × 방 개수(인원 ÷ 방 기준 인원, 올림) — 하룻밤 기준
4) 분류(TravelBudget.category): sight 관광지 · food 식비 · cafe 카페 · move 교통 · stay 숙박 · shop 쇼핑 · etc 기타

같은 장소 가격은 7일 동안 캐시한다 (TourAPI 하루 호출 수 제한, 카드 → 초안 → 적용 때 다시 안 부름).
"""

import hashlib
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from django.core.cache import cache

from .tour_service import _tour_get, find_tour_item

logger = logging.getLogger(__name__)

CACHE_SECONDS = 60 * 60 * 24 * 7
WORKERS = 6
MAX_PEOPLE = 30
CATEGORIES = ('sight', 'food', 'cafe', 'move', 'stay', 'shop', 'etc')

# 관광공사 분류 번호
SPOT, CULTURE, FESTIVAL, LEPORTS, STAY, SHOP, FOOD = '12', '14', '15', '28', '32', '38', '39'
FEE_KEYS = ('usefee', 'usefeeleports', 'usetimefestival')

# 관광공사에 요금이 없을 때 쓰는 보통 가격 (이름·분류 글자에 이 말이 들어가면, 위에서부터)
TYPICAL_FOOD = (
    (('횟집', '회센터', '해산물', '조개', '대게', '랍스터', '오마카세'), 35000),
    (('뷔페',), 30000),
    (('한우', '소고기', '갈비', '삼겹', '고기', '구이', '스테이크', '흑돼지'), 20000),
    (('일식', '초밥', '스시', '양식', '이탈리안', '파스타', '레스토랑'), 20000),
    (('중식', '중국', '짬뽕', '짜장'), 12000),
    (('국밥', '국수', '칼국수', '냉면', '밀면', '해장국', '백반', '한식'), 11000),
    (('햄버거', '패스트푸드', '버거', '피자', '치킨'), 12000),
    (('분식', '김밥', '떡볶이', '만두'), 7000),
)
FOOD_DEFAULT = 13000
CAFE_DEFAULT = 7000
# 숙소: (말, 방 하나 하룻밤 가격, 방 하나에 자는 인원)
TYPICAL_STAY = (
    (('게스트하우스', '게하', '호스텔'), 35000, 1),     # 침대 하나 = 1명
    (('펜션', '풀빌라', '독채'), 150000, 4),
    (('리조트', '콘도'), 150000, 4),
    (('호텔',), 120000, 2),
    (('모텔',), 60000, 2),
)
STAY_DEFAULT = (90000, 2)
# 이런 곳은 보통 입장료가 없다
FREE_WORDS = ('해수욕장', '해변', '해안', '공원', '시장', '거리', '마을', '산책로', '둘레길', '전망대', '광장', '항구', '포구')

_AMOUNT = re.compile(r'(\d{1,3}(?:,\d{3})+|\d+)\s*원')
_MAN = re.compile(r'(\d+)\s*만\s*(?:(\d)\s*천)?\s*원')
_ADULT = re.compile(r'(성인|어른|대인|일반|개인)')
_GROUP_WORDS = ('단체', '10인', '20인', '30인')


# =========================================================
# 요금 문장 → 1인 금액
# =========================================================

def _amounts(text):
    """문장 안의 금액들 (원). '1만 5천원'도 읽는다."""
    found = []
    for m in _MAN.finditer(text):
        found.append((m.start(), int(m.group(1)) * 10000 + int(m.group(2) or 0) * 1000))
    for m in _AMOUNT.finditer(text):
        if not any(start <= m.start() < start + 8 for start, _ in found):
            found.append((m.start(), int(m.group(1).replace(',', ''))))
    found.sort()
    return [amount for _, amount in found if 0 < amount < 5000000]


def parse_fee(text):
    """요금 문장 → 1인 금액(원). '무료'면 0, 못 읽으면 None."""
    text = re.sub(r'<br\s*/?>', '\n', text or '')
    if not text.strip():
        return None

    # 줄(또는 '-' 항목)마다 나눠서, 단체 요금 줄은 뺀다
    lines = [x.strip() for x in re.split(r'[\n/]|(?<!\d)-\s', text) if x.strip()]
    lines = [x for x in lines if not any(w in x for w in _GROUP_WORDS)] or lines

    for line in lines:          # 성인 요금 먼저
        if _ADULT.search(line) and _amounts(line):
            return _amounts(line)[0]

    for line in lines:          # 없으면 처음 나온 금액
        if _amounts(line) and '주차' not in line:
            return _amounts(line)[0]

    if '무료' in text:
        return 0
    return None


# =========================================================
# 관광공사 요금 (캐시)
# =========================================================

def _key(*parts):
    raw = ':'.join(str(p) for p in parts)
    return 'place_price:v1:%s' % hashlib.md5(raw.encode('utf-8')).hexdigest()


def _tour_price(name, lat, lon):
    """관광공사 요금 → {'per', 'unit', 'cap', 'text'} 또는 None (요금 정보 없음)"""
    item = find_tour_item(name, lat, lon)
    if not item:
        return None

    content_id, content_type = item.get('contentid'), str(item.get('contenttypeid') or '')

    if content_type == STAY:
        rooms = _tour_get('detailInfo2', contentId=content_id, contentTypeId=STAY)
        best = None
        for room in rooms:
            fees = [int(room.get(k) or 0) for k in ('roomoffseasonminfee1', 'roomoffseasonminfee2',
                                                    'roompeakseasonminfee1', 'roompeakseasonminfee2')
                    if str(room.get(k) or '').isdigit()]
            fees = [f for f in fees if f > 0]
            if fees and (best is None or min(fees) < best[0]):
                cap = int(room.get('roombasecount') or 2) if str(room.get('roombasecount') or '').isdigit() else 2
                # 기준 인원이 1로 적힌 호텔 방이 많아서, 도미토리(게스트하우스)가 아니면 방 하나 2명으로 본다
                dorm = any(w in (item.get('title') or '') for w in ('게스트하우스', '호스텔'))
                best = (min(fees), cap if dorm else max(cap, 2), (room.get('roomtitle') or '').strip())
        if best:
            return {'per': best[0], 'unit': 'room', 'cap': best[1], 'text': '%s 1박' % (best[2] or '객실')}
        return None

    text = ''
    if content_type == SPOT:
        for row in _tour_get('detailInfo2', contentId=content_id, contentTypeId=SPOT):
            if '입장료' in (row.get('infoname') or '').replace(' ', ''):
                text = row.get('infotext') or ''
                break
    elif content_type in (CULTURE, FESTIVAL, LEPORTS):
        intro = _tour_get('detailIntro2', contentId=content_id, contentTypeId=content_type)
        intro = intro[0] if intro else {}
        text = next((intro.get(k) for k in FEE_KEYS if intro.get(k)), '') or ''

    fee = parse_fee(text)
    if fee is None:
        return None
    short = re.sub(r'\s+', ' ', re.sub(r'<br\s*/?>', ' ', text)).strip()[:80]
    return {'per': fee, 'unit': 'person', 'cap': 1, 'text': short}


def _typical_price(name, kind):
    """보통 가격으로 짐작 → {'per', 'unit', 'cap'} 또는 None"""
    words = '%s %s' % (name or '', kind or '')

    if '카페' in (kind or '') or any(w in words for w in ('카페', '커피', '디저트', '베이커리')):
        return {'per': CAFE_DEFAULT, 'unit': 'person', 'cap': 1}

    if '숙박' in (kind or ''):
        for keys, per, cap in TYPICAL_STAY:
            if any(w in words for w in keys):
                return {'per': per, 'unit': 'room', 'cap': cap}
        return {'per': STAY_DEFAULT[0], 'unit': 'room', 'cap': STAY_DEFAULT[1]}

    if '음식' in (kind or '') or any(w in words for keys, _ in TYPICAL_FOOD for w in keys):
        for keys, per in TYPICAL_FOOD:
            if any(w in words for w in keys):
                return {'per': per, 'unit': 'person', 'cap': 1}
        return {'per': FOOD_DEFAULT, 'unit': 'person', 'cap': 1}

    if any(w in words for w in FREE_WORDS):
        return {'per': 0, 'unit': 'person', 'cap': 1}

    return None


def category_of(kind, name=''):
    """장소 종류 → 예산 분류 키"""
    words = '%s %s' % (kind or '', name or '')
    if any(w in words for w in ('카페', '커피', '디저트', '베이커리', '제과', '빵집')):
        return 'cafe'
    if '숙박' in words or any(w in words for keys, _, _ in TYPICAL_STAY for w in keys):
        return 'stay'
    if '음식' in words or any(w in words for keys, _ in TYPICAL_FOOD for w in keys):
        return 'food'
    if '쇼핑' in words or '마트' in words or '백화점' in words:
        return 'shop'
    if any(w in words for w in ('교통', '기차역', '지하철역', '터미널', '공항', '주차장')):
        return 'move'
    return 'sight'


def place_price(name, kind, lat=None, lon=None, kakao_id=None, category=None, fee_text=None):
    """
    장소 하나의 가격 (인원 계산 전)
    {'per': 금액, 'unit': 'person'|'room', 'cap': 방 기준 인원, 'cat': 분류, 'source': 'tour'|'estimate', 'text': 원문}
    모르면 None.  category: 카카오 분류 원문(있으면 식당 종류 짐작에 씀), fee_text: 팀 장소 표의 입장료 원문
    """
    # 카드(카카오 ID 있음)에서 계산한 값을 숙소 칸(ID 없음)에서도 같게 쓰려고 두 열쇠에 저장
    name_key = _key('%s:%s:%s' % (name, lat, lon))
    cache_key = _key(kakao_id) if kakao_id else name_key
    for key in (cache_key, name_key):
        saved = cache.get(key)
        if saved is not None:
            return saved or None

    words = '%s %s' % (kind or '', category or '')
    cat = category_of(words, name)
    found = None

    # 팀이 고른 장소 표에 입장료가 적혀 있으면 그것 먼저
    fee = parse_fee(fee_text) if fee_text else None
    if fee is not None:
        found = {'per': fee, 'unit': 'person', 'cap': 1, 'source': 'tour', 'text': fee_text[:80]}

    if found is None and cat in ('sight', 'stay', 'etc'):
        try:
            tour = _tour_price(name, lat, lon)
        except requests.RequestException:
            logger.warning('관광공사 요금 조회 실패: %s', name)
            tour = 'fail'
        if tour == 'fail':
            typical = _typical_price(name, words)
            return dict(typical, cat=cat, source='estimate', text='') if typical else None  # 실패는 저장 안 함
        if tour:
            found = dict(tour, source='tour')

    if found is None:
        typical = _typical_price(name, words)
        if typical:
            found = dict(typical, source='estimate', text='')

    if found:
        found['cat'] = cat
    cache.set(cache_key, found or {}, CACHE_SECONDS)
    if cache_key != name_key:
        cache.set(name_key, found or {}, CACHE_SECONDS)
    return found


# =========================================================
# 인원 기준 계산
# =========================================================

def clean_people(value):
    try:
        people = int(value)
    except (TypeError, ValueError):
        return 1
    return min(max(people, 1), MAX_PEOPLE)


def cost_for(price, people, nights=1):
    """가격 하나 → 인원 기준 금액 (방 요금은 방 개수 × 박 수)"""
    if not price:
        return 0
    people = clean_people(people)
    if price.get('unit') == 'room':
        rooms = math.ceil(people / max(int(price.get('cap') or 2), 1))
        return int(price['per']) * rooms * max(int(nights or 1), 1)
    return int(price['per']) * people


def to_cost(price, people):
    """추천 카드 'cost' 키 (mock.json: amount·cat·source + 인원 계산용 per·unit·cap·people·text)"""
    if not price:
        return None
    people = clean_people(people)
    return {
        'amount': cost_for(price, people),
        'cat': price['cat'],
        'source': price['source'],
        'per': int(price['per']),
        'unit': price['unit'],
        'cap': int(price.get('cap') or 1),
        'people': people,
        'text': price.get('text') or '',
    }


def attach_costs(items, people=None):
    """추천 카드 목록에 cost 키를 붙인다 (모르면 None). 카드의 '_category'(카카오 분류)는 쓰고 지운다."""
    def one(item):
        try:
            return place_price(item.get('name'), item.get('kind'), item.get('lat'), item.get('lon'),
                               item.get('kakao_id'), item.get('_category'),
                               (item.get('pick') or {}).get('fee'))
        except Exception:  # 한 곳이 실패해도 카드는 보여준다
            logger.warning('가격 계산 실패: %s', item.get('name'), exc_info=True)
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        prices = list(pool.map(one, items))
    for item, price in zip(items, prices):
        item.pop('_category', None)
        item['cost'] = to_cost(price, people)
    return items


# =========================================================
# 초안 전체 예상 예산 (담은 장소 + 숙소)
# =========================================================

def draft_budget(draft):
    """
    초안의 담은 장소(pins)·숙소(stays)로 예상 예산을 계산한다.
    {'people', 'planned', 'by': {분류: 금액}, 'items': [{name, day, cat, amount, per, unit, source}], 'unknown': [이름]}
    """
    people = clean_people(draft.get('people'))
    places = []
    for pin in draft.get('pins') or []:
        if isinstance(pin, dict) and pin.get('name'):
            places.append((pin, pin.get('kind'), pin.get('day')))
    for stay in draft.get('stays') or []:
        if isinstance(stay, dict) and (stay.get('name') or stay.get('query')):
            stay = dict(stay, name=stay.get('name') or stay.get('query'))
            places.append((stay, '숙박', stay.get('date')))

    def one(row):
        p, kind, _ = row
        try:
            return place_price(p.get('name'), kind, p.get('lat'), p.get('lon'), p.get('kakao_id'))
        except Exception:
            logger.warning('가격 계산 실패: %s', p.get('name'), exc_info=True)
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        prices = list(pool.map(one, places))

    by = {c: 0 for c in CATEGORIES}
    items, unknown = [], []
    for (p, _, day), price in zip(places, prices):
        if not price:
            unknown.append(p['name'])
            continue
        amount = cost_for(price, people)
        by[price['cat']] += amount
        items.append({'name': p['name'], 'day': day, 'cat': price['cat'], 'amount': amount,
                      'per': int(price['per']), 'unit': price['unit'], 'source': price['source']})

    return {'people': people, 'planned': sum(by.values()), 'by': by, 'items': items, 'unknown': unknown}


def plan_budget(days, people):
    """
    일정 미리보기(날짜별 장소 목록) 전체의 예상 예산. 자동으로 들어간 식당·카페·관광지·숙소 체크인까지 모두 센다.
    days: [{'day', 'items': [{name, kind, lat, lon, kakao_id, is_stay}]}] — 장소마다 'cost' 키를 붙인다 (mock.json stops[].cost)
    돌려주는 모양은 draft_budget과 같음
    """
    people = clean_people(people)
    rows = [(day.get('day'), item) for day in days or [] for item in day.get('items') or []]

    def one(row):
        _, item = row
        kind = '숙박' if item.get('is_stay') else item.get('kind')
        try:
            return place_price(item.get('name'), kind, item.get('lat'), item.get('lon'), item.get('kakao_id'))
        except Exception:
            logger.warning('가격 계산 실패: %s', item.get('name'), exc_info=True)
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        prices = list(pool.map(one, rows))

    by = {c: 0 for c in CATEGORIES}
    items, unknown = [], []
    for (day, item), price in zip(rows, prices):
        item['cost'] = to_cost(price, people)
        if not price:
            unknown.append(item.get('name'))
            continue
        amount = item['cost']['amount']
        by[price['cat']] += amount
        items.append({'name': item.get('name'), 'day': day, 'cat': price['cat'], 'amount': amount,
                      'per': int(price['per']), 'unit': price['unit'], 'source': price['source']})

    return {'people': people, 'planned': sum(by.values()), 'by': by, 'items': items, 'unknown': unknown}


# =========================================================
# 카테고리 예산 저장 (travel_budget 표)
# =========================================================

def clean_limits(data):
    """{'sight': 30000, ...} → 분류 키·0 이상 정수만 (잘못된 값은 뺌)"""
    limits = {}
    if not isinstance(data, dict):
        return limits
    for cat in CATEGORIES:
        if cat not in data:
            continue
        try:
            amount = int(str(data[cat]).replace(',', ''))
        except (TypeError, ValueError):
            continue
        if 0 <= amount <= 100000000:
            limits[cat] = amount
    return limits


def save_limits(travel, limits):
    """여행의 분류별 예산을 저장한다 (있으면 고치고 없으면 만듦). 저장 후 전체 {분류: 금액}"""
    from ..models import TravelBudget

    for cat, amount in clean_limits(limits).items():
        TravelBudget.objects.update_or_create(travel=travel, category=cat, defaults={'amount': amount})
    return load_limits(travel)


def load_limits(travel):
    from ..models import TravelBudget

    limits = {c: 0 for c in CATEGORIES}
    for row in TravelBudget.objects.filter(travel=travel):
        if row.category in limits:
            limits[row.category] = row.amount or 0
    return limits
