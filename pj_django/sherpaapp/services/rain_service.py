"""
비 오는 날 실내 / 실외 (🟦)

1) 날씨: 여행 날짜별 예보 (agent_tools.trip_weather, 16일 안만). 비·눈이거나 비 올 확률 60% 이상이면 '비 오는 날'
2) 일정 장소가 실내인지: indoor_service.is_indoor (🟩) 를 그대로 쓴다
   - 우리 Place 의 p_kind 는 '랜드마크'·'음식'처럼 컨셉 이름이라, 모르면 카카오에서 그 장소의 분류 이름을 찾아 판단
   - 식당·카페·숙소·쇼핑은 실내
3) 실내 대안: 비 오는 날 실외 장소 근처(5km)의 박물관·미술관·전시관·아쿠아리움·쇼핑몰
   - 예상 비용(budget_service)·사진(photo_service)도 붙여서 카드처럼 보여준다

같은 장소의 실내 판단은 7일 캐시 (카카오 호출 줄이기).
"""

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from django.core.cache import cache

from .indoor_service import is_indoor

logger = logging.getLogger(__name__)

RAIN_PCT = 60                     # 비 올 확률이 이 이상이면 비 오는 날로 본다
CACHE_SECONDS = 60 * 60 * 24 * 7
WORKERS = 6
INDOOR_KINDS = ('음식', '카페', '숙', '쇼핑')   # 우리 장소 종류(p_kind)가 이러면 실내

# 🟩 is_indoor 가 모르는 분류·이름 보충 (카카오 분류 예: '관광,명소 > 자연휴양림', '도보여행 > 올레길')
MORE_OUTDOOR = ('휴양림', '숲', '도보여행', '올레', '정원', '민속촌', '읍성', '오름', '해안도로', '자연', '바다', '캠핑')
MORE_INDOOR = ('전시', '展', '소장품', '공연', '뮤지컬', '콘서트', '갤러리', '체험관', '실내')
FESTIVAL_KINDS = ('축제', '행사')   # 축제·행사는 보통 야외 (전시·공연이면 실내)


def _more_words(text):
    """보충 단어로 판단: 실내 True / 실외 False / 모름 None"""
    text = text or ''
    if any(word in text for word in MORE_INDOOR):
        return True
    if any(word in text for word in MORE_OUTDOOR):
        return False
    return None

# 실내 대안으로 찾을 것 (검색어, 카카오 분류 코드)
INDOOR_QUERIES = (
    ('박물관', 'CT1'), ('미술관', 'CT1'), ('전시관', 'CT1'),
    ('아쿠아리움', ''), ('복합쇼핑몰', ''),
)
INDOOR_RADIUS = 5000
INDOOR_LIMIT = 3


def is_rainy(weather):
    """날씨 하나({kind, rain_pct})가 비 오는 날인지"""
    if not isinstance(weather, dict):
        return False
    return weather.get('kind') in ('rain', 'snow') or (weather.get('rain_pct') or 0) >= RAIN_PCT


FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'          # 예보 (지난 92일까지도 됨)
ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive'      # 지난 기록 (며칠 전까지)
FORECAST_DAYS = 16
RECENT_PAST_DAYS = 90
RAIN_MM = 1.0             # 지난 날: 하루 강수량이 이 이상이면 비 온 날
MAX_TRIP_DAYS = 31


def _daily(url, lat, lon, start, end):
    """open-meteo 날짜별 날씨 → {'YYYY-MM-DD': {kind, label, temp, temp_min, rain_mm}} (실패하면 {})"""
    from .agent_tools import KIND_LABELS, _weather_kind

    key = 'wxday:%s:%.2f:%.2f:%s:%s' % ('a' if 'archive' in url else 'f', float(lat), float(lon), start, end)
    saved = cache.get(key)
    if saved is not None:
        return saved
    try:
        res = requests.get(url, params={
            'latitude': lat, 'longitude': lon, 'timezone': 'Asia/Seoul',
            'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum',
            'start_date': start.isoformat(), 'end_date': end.isoformat(),
        }, timeout=6)
        res.raise_for_status()
        daily = res.json().get('daily') or {}
    except (requests.RequestException, ValueError):
        logger.warning('지난 날씨 조회 실패: %s~%s', start, end)
        return {}

    def pick(name, i):
        values = daily.get(name) or []
        return values[i] if i < len(values) else None

    days = {}
    for i, day in enumerate(daily.get('time') or []):
        kind = _weather_kind(pick('weather_code', i))
        if not kind:
            continue
        t_max, t_min = pick('temperature_2m_max', i), pick('temperature_2m_min', i)
        days[day] = {
            'kind': kind, 'label': KIND_LABELS.get(kind),
            'temp': round(t_max) if t_max is not None else None,
            'temp_min': round(t_min) if t_min is not None else None,
            'rain_mm': pick('precipitation_sum', i),
        }
    cache.set(key, days, 60 * 60 * 24 * 7)   # 지난 날씨는 안 바뀜
    return days


def _coords(place, center):
    if isinstance(center, dict) and center.get('lat') is not None:
        return center['lat'], center['lon']
    from .chat_service import kakao_first_place
    found = kakao_first_place(place) if place else None
    return (found['lat'], found['lon']) if found else (None, None)


def _last_year(day):
    try:
        return day.replace(year=day.year - 1)
    except ValueError:            # 2월 29일
        return day.replace(year=day.year - 1, day=28)


def trip_days_weather(place, start, end, center=None):
    """
    {'2026-11-12': {date, kind, label, temp, temp_min, rain_pct, rainy, source}}
    source: 'forecast' 예보(16일 안) · 'past' 지난 날 실제 날씨 · 'last_year' 16일보다 먼 날은 작년 같은 날 날씨(참고용, rainy=False)
    """
    from datetime import date, timedelta

    from .agent_tools import trip_weather

    try:
        days = trip_weather(place, start, end, center) or []
    except Exception:
        logger.warning('날씨 조회 실패: %s', place, exc_info=True)
        days = []
    result = {d['date']: dict(d, rainy=is_rainy(d), source='forecast') for d in days if d.get('date')}

    try:
        first, last = date.fromisoformat(str(start)[:10]), date.fromisoformat(str(end)[:10])
    except ValueError:
        return result
    dates = [first + timedelta(days=i) for i in range(min((last - first).days + 1, MAX_TRIP_DAYS))]
    missing = [d for d in dates if d.isoformat() not in result]
    if not missing:
        return result

    lat, lon = _coords(place, center)
    if lat is None:
        return result

    today = date.today()
    past = [d for d in missing if d < today]
    future = [d for d in missing if d >= today + timedelta(days=FORECAST_DAYS)]

    # 지난 날: 최근이면 예보 주소(지난 92일), 오래됐으면 기록 주소
    if past:
        recent = (today - past[0]).days <= RECENT_PAST_DAYS
        got = _daily(FORECAST_URL if recent else ARCHIVE_URL, lat, lon, past[0], past[-1])
        if not got and recent:
            got = _daily(ARCHIVE_URL, lat, lon, past[0], past[-1])
        for d in past:
            w = got.get(d.isoformat())
            if w:
                result[d.isoformat()] = dict(w, date=d.isoformat(), rain_pct=None, source='past',
                                             rainy=w['kind'] in ('rain', 'snow') or (w.get('rain_mm') or 0) >= RAIN_MM)

    # 16일보다 먼 날: 작년 같은 날 (참고용이라 실내 대안은 안 띄움)
    if future:
        got = _daily(ARCHIVE_URL, lat, lon, _last_year(future[0]), _last_year(future[-1]))
        for d in future:
            w = got.get(_last_year(d).isoformat())
            if w:
                result[d.isoformat()] = dict(w, date=d.isoformat(), rain_pct=None, source='last_year', rainy=False,
                                             last_year_rain=w['kind'] in ('rain', 'snow') or (w.get('rain_mm') or 0) >= RAIN_MM)
    return result


def _key(*parts):
    raw = ':'.join(str(p) for p in parts)
    return 'indoor:v2:%s' % hashlib.md5(raw.encode('utf-8')).hexdigest()


def place_indoor(name, kind='', lat=None, lon=None, kakao_id=None):
    """일정 장소 하나가 실내면 True, 실외면 False, 모르면 None"""
    kind = kind or ''
    if any(word in kind for word in INDOOR_KINDS):
        return True

    said = is_indoor(kind, '', name or '')
    if said is not None:
        return said

    # 축제·행사: 전시·공연이면 실내, 아니면 야외
    if any(word in kind for word in FESTIVAL_KINDS):
        return True if _more_words(name) else False

    key = _key(kakao_id or '%s:%s:%s' % (name, lat, lon))
    saved = cache.get(key)
    if saved is not None:
        return saved.get('v')

    said = None
    if name and lat is not None and lon is not None:
        from .place_service import kakao_documents
        try:
            docs = kakao_documents(name, 5, '', x=lon, y=lat, radius=1000, sort='distance')
        except requests.RequestException:
            return None   # 실패는 저장하지 않음
        doc = next((d for d in docs if kakao_id and str(d.get('id')) == str(kakao_id)), None)
        doc = doc or next((d for d in docs if d.get('place_name') == name), None) or (docs[0] if docs else None)
        if doc:
            said = is_indoor(doc.get('category_name'), doc.get('category_group_code'), name)
            if said is None:
                said = _more_words(doc.get('category_name'))
    if said is None:
        said = _more_words(name)

    cache.set(key, {'v': said}, CACHE_SECONDS)
    return said


def attach_indoor(items):
    """장소 목록(dict: name, kind, lat, lon, kakao_id)에 'indoor' 키를 붙인다 (숙소 줄은 실내)"""
    def one(item):
        if item.get('is_stay'):
            return True
        try:
            return place_indoor(item.get('name'), item.get('kind'), item.get('lat'), item.get('lon'), item.get('kakao_id'))
        except Exception:
            logger.warning('실내 판단 실패: %s', item.get('name'), exc_info=True)
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        values = list(pool.map(one, items))
    for item, value in zip(items, values):
        item['indoor'] = value
    return items


def indoor_options(name, lat, lon, people=None, skip_names=(), limit=INDOOR_LIMIT):
    """
    실외 장소 근처의 실내 대안 (가까운 순)
    → [{name, addr, kind, category, lat, lon, kakao_id, url, phone, distance, cost, photo}]
    """
    from .budget_service import place_price, to_cost
    from .photo_service import attach_photos
    from .place_service import is_junk_kind, kakao_documents

    if lat is None or lon is None:
        return []

    skip = set(skip_names) | {name}
    found, seen = [], set()
    for query, group in INDOOR_QUERIES:
        try:
            docs = kakao_documents(query, 8, group, x=lon, y=lat, radius=INDOOR_RADIUS, sort='distance')
        except requests.RequestException:
            logger.warning('실내 대안 검색 실패: %s', query)
            continue
        for doc in docs:
            if doc.get('id') in seen or doc.get('place_name') in skip or is_junk_kind(doc.get('category_name')):
                continue
            if is_indoor(doc.get('category_name'), doc.get('category_group_code'), doc.get('place_name')) is not True:
                continue
            seen.add(doc.get('id'))
            found.append(doc)

    found.sort(key=lambda d: int(d.get('distance') or 0))
    found = found[:limit]

    def price(doc):
        try:
            return place_price(doc.get('place_name'), '관광', float(doc['y']), float(doc['x']),
                               doc.get('id'), doc.get('category_name'))
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        prices = list(pool.map(price, found))

    options = []
    for doc, p in zip(found, prices):
        options.append({
            'name': doc.get('place_name'),
            'addr': doc.get('road_address_name') or doc.get('address_name') or '',
            'kind': '관광',
            'category': doc.get('category_name') or '',
            'lat': float(doc['y']),
            'lon': float(doc['x']),
            'kakao_id': doc.get('id'),
            'url': doc.get('place_url') or '',
            'phone': doc.get('phone') or '',
            'distance': int(doc.get('distance') or 0),
            'cost': to_cost(p, people) if p else None,
            'indoor': True,
        })

    try:
        attach_photos(options, max_new=limit)
    except Exception:
        logger.warning('실내 대안 사진 실패', exc_info=True)
    return options
