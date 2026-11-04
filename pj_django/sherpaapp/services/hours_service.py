"""
일정 장소 운영시간 + 축제 진행 시간 (한국관광공사 TourAPI detailIntro2)

1) 장소: 이름 검색으로 같은 장소를 찾고(tour_service.find_tour_item) 소개 정보에서
   운영시간 문장(usetime·opentimefood 등)과 쉬는 날 문장을 읽는다
2) 문장 → 여는 시각·닫는 시각 (분)
   - '[11월~2월] 06:00~18:00 [3월~5월] 05:00~19:00' 처럼 계절마다 다르면 방문 달에 맞는 칸만 읽는다
   - 여러 시간이 있으면 가장 이른 시작 ~ 가장 늦은 끝 (요일마다 다른 것은 넉넉하게 봄)
   - '브레이크타임 15:00~17:00' 같은 쉬는 시간은 뺀다
   - '24시간'은 00:00~24:00, '11:00~02:00'처럼 새벽에 닫으면 끝을 다음날(26:00)로 본다
3) 관광공사에 없는 식당·카페는 분류별 보통 영업시간을 '예상'(estimated)으로 준다

같은 장소·축제는 7일 동안 캐시한다 (TourAPI 하루 호출 수 제한).
"""

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from django.core.cache import cache

from .tour_service import REST_KEYS, _tour_get, closed_on, find_tour_item

logger = logging.getLogger(__name__)

CACHE_SECONDS = 60 * 60 * 24 * 7
WORKERS = 6

# 관광지·문화시설·음식점·쇼핑·레포츠·숙박·축제마다 운영시간 칸 이름이 다름
HOURS_KEYS = ('usetime', 'usetimeculture', 'opentimefood', 'opentime', 'usetimeleports', 'playtime')

# 관광공사에 없을 때 쓰는 보통 영업시간 (분류 글자에 이 말이 들어가면)
TYPICAL_HOURS = (
    (('카페', '커피', '디저트', '베이커리'), (10 * 60, 22 * 60)),
    (('음식', '식당', '맛집', '한식', '중식', '일식', '양식', '분식', '고기', '횟집'), (11 * 60, 21 * 60)),
)

_RANGE = re.compile(r'(\d{1,2})\s*[:시]\s*(\d{2})?\s*분?\s*[~\-–～]\s*(\d{1,2})\s*[:시]\s*(\d{2})?')
_SEASON = re.compile(r'\[([^\]]*월[^\]]*)\]')
# 괄호 없이 '10월/11월 10:00~18:00' 처럼 쓴 계절 칸
_SEASON_BARE = re.compile(r'((?:\d{1,2}\s*월\s*[~/,·\-]\s*)*\d{1,2}\s*월)\s*[:\-]?\s*(?=\d{1,2}\s*:)')
_BREAK_WORDS = ('브레이크', '휴게', 'break', 'Break', '쉬는 시간', '점심시간', '준비')


# =========================================================
# 문장 → 여는·닫는 시각
# =========================================================

def _months_in(header):
    """'1월~2월/11월~12월' → {1,2,11,12}, '11월~2월' → {11,12,1,2}"""
    months = set()
    for part in re.split(r'[/,·]', header):
        nums = [int(n) for n in re.findall(r'(\d{1,2})\s*월', part)]
        if len(nums) >= 2 and re.search(r'월\s*[~\-–～]', part):
            a, b = nums[0], nums[1]
            m = a
            while True:
                months.add(m)
                if m == b:
                    break
                m = m % 12 + 1
        else:
            months.update(nums)
    return {m for m in months if 1 <= m <= 12}


def _season_text(text, month):
    """계절 칸이 있으면 방문 달 칸의 글자만, 없으면 전체"""
    if not month:
        return text
    marks = list(_SEASON.finditer(text)) or list(_SEASON_BARE.finditer(text))
    if not marks:
        return text
    for i, mark in enumerate(marks):
        if month in _months_in(mark.group(1)):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            return text[mark.end():end]
    return text


def parse_hours(text, month=None):
    """운영시간 문장 → (여는 분, 닫는 분). 못 읽으면 None."""
    if not text:
        return None
    if re.search(r'24\s*시간', text):
        return (0, 24 * 60)

    text = _season_text(text, month)
    opens, closes = [], []
    for m in _RANGE.finditer(text):
        before = text[max(0, m.start() - 12):m.start()]
        if any(w in before for w in _BREAK_WORDS):
            continue
        h1, m1, h2, m2 = int(m.group(1)), int(m.group(2) or 0), int(m.group(3)), int(m.group(4) or 0)
        if h1 > 24 or h2 > 30 or m1 > 59 or m2 > 59:
            continue
        start, end = h1 * 60 + m1, h2 * 60 + m2
        if end <= start:
            end += 24 * 60          # 새벽에 닫음
        opens.append(start)
        closes.append(end)

    if not opens:
        return None
    return (min(opens), max(closes))


def hhmm(minutes):
    """분 → 'HH:MM' (24시 넘으면 그대로 26:00 → '02:00')"""
    minutes = int(minutes) % (24 * 60) if minutes != 24 * 60 else 24 * 60
    return '%02d:%02d' % (minutes // 60, minutes % 60)


def _clean(text):
    return re.sub(r'\s+', ' ', re.sub(r'<br\s*/?>', ' / ', text or '')).strip()


# =========================================================
# 관광공사 소개 정보 (캐시)
# =========================================================

def _key(prefix, *parts):
    # 이름에 한글·띄어쓰기가 있어도 되는 캐시 열쇠
    raw = ':'.join(str(p) for p in parts)
    return '%s:%s' % (prefix, hashlib.md5(raw.encode('utf-8')).hexdigest())


def _intro(content_id, content_type):
    items = _tour_get('detailIntro2', contentId=content_id, contentTypeId=content_type)
    return items[0] if items else {}


def place_intro(name, lat=None, lon=None, kakao_id=None):
    """장소의 운영시간·쉬는 날 원문 {'hours': ..., 'rest': ...}. 관광공사에 없으면 둘 다 ''. 실패하면 None."""
    cache_key = _key('tour_hours:v1', kakao_id or '%s:%s:%s' % (name, lat, lon))
    saved = cache.get(cache_key)
    if saved is not None:
        return saved

    found = {'hours': '', 'rest': ''}
    try:
        item = find_tour_item(name, lat, lon)
        if item:
            intro = _intro(item.get('contentid'), item.get('contenttypeid'))
            found['hours'] = _clean(next((intro.get(k) for k in HOURS_KEYS if intro.get(k)), ''))
            found['rest'] = _clean(next((intro.get(k) for k in REST_KEYS if intro.get(k)), ''))
    except requests.RequestException:
        logger.warning('관광공사 운영시간 조회 실패: %s', name)
        return None

    cache.set(cache_key, found, CACHE_SECONDS)
    return found


def festival_playtime(content_id):
    """축제 진행 시간 원문 (예: '15:00 ~ 21:00 (금 17:00 ~ 21:00)'). 모르면 ''."""
    if not content_id:
        return ''
    cache_key = _key('tour_playtime:v1', content_id)
    saved = cache.get(cache_key)
    if saved is not None:
        return saved
    try:
        text = _clean(_intro(content_id, 15).get('playtime') or '')
    except requests.RequestException:
        logger.warning('관광공사 축제 시간 조회 실패: %s', content_id)
        return ''
    cache.set(cache_key, text, CACHE_SECONDS)
    return text


def festival_times(festivals, month=None):
    """축제 목록 각각에 'time'(원문)·'open'·'close'('HH:MM' 또는 '')를 붙여 돌려준다 (month: 여행 달)"""
    ids = [f.get('id') for f in festivals]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        texts = list(pool.map(festival_playtime, ids))
    for f, text in zip(festivals, texts):
        span = parse_hours(text, month)
        f['time'] = text
        f['open'] = hhmm(span[0]) if span else ''
        f['close'] = hhmm(span[1]) if span else ''
        f['open_min'] = span[0] if span else None
        f['close_min'] = span[1] if span else None
    return festivals


# =========================================================
# 일정 장소 하나의 운영 정보
# =========================================================

def _typical(kind):
    for words, span in TYPICAL_HOURS:
        if any(w in (kind or '') for w in words):
            return span
    return None


def place_hours(name, kind, day, lat=None, lon=None, kakao_id=None):
    """
    {'text': 원문, 'open': 'HH:MM', 'close': 'HH:MM', 'open_min': 분, 'close_min': 분,
     'estimated': 보통 영업시간으로 짐작했는지, 'closed': 그날 쉬는지, 'rest': 쉬는 날 원문}
    아무것도 모르면 None
    """
    intro = place_intro(name, lat, lon, kakao_id) or {'hours': '', 'rest': ''}
    month = day.month if day else None

    span = parse_hours(intro['hours'], month)
    estimated = False
    if not span and not intro['hours']:
        span = _typical(kind)
        estimated = bool(span)

    closed = False
    if intro['rest'] and day:
        closed = bool(closed_on(intro['rest'], day).get('closed'))

    if not span and not intro['hours'] and not closed:
        return None

    return {
        'text': intro['hours'],
        'open': hhmm(span[0]) if span else '',
        'close': hhmm(span[1]) if span else '',
        'open_min': span[0] if span else None,
        'close_min': span[1] if span else None,
        'estimated': estimated,
        'closed': closed,
        'rest': intro['rest'],
    }


def schedule_hours(schedule_places, day):
    """일정 장소들(SchedulePlace) → {sp_id: place_hours(...)} (모르는 장소는 빠짐)"""
    def one(sp):
        p = sp.place
        lat = float(p.p_lat) if p.p_lat is not None else None
        lon = float(p.p_lon) if p.p_lon is not None else None
        try:
            return sp.sp_id, place_hours(p.p_name, p.p_kind, day, lat, lon, p.p_kakao_id)
        except Exception:  # 한 곳이 실패해도 나머지는 보여준다
            logger.warning('운영시간 계산 실패: %s', p.p_name, exc_info=True)
            return sp.sp_id, None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = list(pool.map(one, list(schedule_places)))
    return {sp_id: info for sp_id, info in rows if info}
