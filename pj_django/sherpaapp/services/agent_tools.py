"""AI 대화가 쓰는 도구들 (LangChain 도구 호출)

AI는 답을 쓰기 전에 필요하면 도구를 부른다. 서버가 도구를 실행해서 결과를 AI에게 돌려주고,
AI는 그 결과를 보고 최종 답(JSON)을 쓴다. (chat_service.call_llm 의 tools 인자)

도구를 새로 만들 때
1) 아래처럼 @tool 함수를 만들고 docstring에 '언제 쓰는지'를 적는다 (AI가 이 설명을 읽고 고름)
2) 결과는 dict 하나로 돌려준다. 실패해도 예외를 내지 말고 {'error': '...'} 를 돌려준다
3) CHAT_TOOLS 목록에 넣는다
"""

import logging
from datetime import date, timedelta

import requests
from django.core.cache import cache
from langchain_core.tools import tool


logger = logging.getLogger(__name__)

WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
WEATHER_DAYS = 16      # 무료 예보는 오늘부터 16일까지
TIMEOUT = 6
WEATHER_CACHE_SECONDS = 60 * 60   # 같은 곳·같은 날짜 예보는 1시간 동안 다시 묻지 않음


# =========================================================
# 날씨
# =========================================================

def _weather_kind(code):
    """WMO 날씨 코드 → mock.json 의 weather.kind (sun / cloud / rain / snow)."""
    if code is None:
        return None
    if code == 0:
        return 'sun'
    if code in (71, 73, 75, 77, 85, 86):
        return 'snow'
    if 51 <= code <= 67 or 80 <= code <= 82 or code >= 95:
        return 'rain'
    return 'cloud'


KIND_LABELS = {'sun': '맑음', 'cloud': '흐림', 'rain': '비', 'snow': '눈'}


def _parse_day(value):
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def forecast(lat, lon, start, end):
    """좌표의 날짜별 예보 목록. 예보 범위를 벗어난 날은 빠진다."""
    today = date.today()
    last = today + timedelta(days=WEATHER_DAYS - 1)
    start, end = max(start, today), min(end, last)

    if start > end:
        return []

    cache_key = 'weather:%.2f:%.2f:%s:%s' % (float(lat), float(lon), start, end)
    saved = cache.get(cache_key)
    if saved is not None:
        return saved

    response = requests.get(WEATHER_URL, params={
        'latitude': lat,
        'longitude': lon,
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
        'timezone': 'Asia/Seoul',
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
    }, timeout=TIMEOUT)
    response.raise_for_status()

    daily = response.json().get('daily') or {}
    days = []

    for i, day in enumerate(daily.get('time') or []):
        def pick(key):
            values = daily.get(key) or []
            return values[i] if i < len(values) else None

        t_max, t_min = pick('temperature_2m_max'), pick('temperature_2m_min')
        kind = _weather_kind(pick('weather_code'))
        days.append({
            'date': day,
            'kind': kind,                                              # mock.json 의 weather.kind
            'label': KIND_LABELS.get(kind),
            'temp': round(t_max) if t_max is not None else None,       # mock.json 의 temp (낮 최고 기온)
            'temp_min': round(t_min) if t_min is not None else None,
            'rain_pct': pick('precipitation_probability_max'),         # 비 올 확률(%), 비의 양이 아님
        })

    cache.set(cache_key, days, WEATHER_CACHE_SECONDS)
    return days


def trip_weather(place, start, end, center=None):
    """여행 날짜의 날씨 목록. 위치는 center(lat, lon) → 없으면 지역 이름으로 찾음. 실패하면 None."""
    # 순환 import 를 피하려고 여기서 불러온다
    from .chat_service import kakao_first_place

    first, last = _parse_day(start), _parse_day(end) or _parse_day(start)
    if not place or not first:
        return None

    if isinstance(center, dict) and center.get('lat') is not None:
        lat, lon = center['lat'], center['lon']
    else:
        found = kakao_first_place(place)
        if not found:
            return None
        lat, lon = found['lat'], found['lon']

    try:
        return forecast(lat, lon, first, max(first, last))
    except (requests.RequestException, ValueError):
        logger.warning('날씨 조회 실패: %s', place)
        return None


def rainy_note(days, start=None):
    """비·눈 오는 날이 있으면 안내 한 줄, 없으면 None.

    start(여행 출발일)를 주면 '2일차 실내 추천'처럼 바로 따라 말할 수 있는 예를 붙인다.
    """
    bad = [d for d in days or [] if d.get('kind') in ('rain', 'snow')]
    if not bad:
        return None
    when = ', '.join('%s(%s)' % (d['date'][5:].replace('-', '/'), d['label']) for d in bad)

    first, trip_start = _parse_day(bad[0]['date']), _parse_day(start)
    if first and trip_start and first >= trip_start:
        return "%s 예보가 있어요. 실내 장소가 필요하면 '%d일차 실내 추천'처럼 말해 주세요." % (
            when, (first - trip_start).days + 1)

    return '%s 예보가 있어요. 실내 장소도 함께 추천해 드릴까요?' % when


@tool
def get_weather(place: str, start: str, end: str) -> dict:
    """여행 지역의 날짜별 날씨 예보를 알려 준다.

    여행 지역과 날짜가 정해졌을 때, 사용자가 날씨를 묻거나 날짜가 처음 정해졌을 때 부른다.
    비(rain)·눈(snow) 소식이 있으면 사용자에게 알리고 실내 장소를 권한다.
    오늘부터 16일 안의 날짜만 예보가 있다.

    place: 여행 지역 (예: 부산, 강릉)
    start: 시작 날짜 YYYY-MM-DD
    end: 끝 날짜 YYYY-MM-DD
    """
    if not place or not _parse_day(start):
        return {'error': '지역과 날짜가 필요해요.'}

    days = trip_weather(place, start, end)

    if days is None:
        return {'error': '날씨 정보를 가져오지 못했어요.'}

    if not days:
        return {'place': place, 'days': [], 'note': '아직 예보가 없는 날짜예요 (16일 이내만 예보).'}

    return {'place': place, 'days': days}


# =========================================================
# 쉬는 날
# =========================================================

@tool
def check_open(place: str, date: str) -> dict:
    """장소가 그 날짜에 문을 여는지(정기 휴무인지) 알려 준다. 한국관광공사 정보 기준.

    사용자가 '○○ 월요일에 열어?', '그날 ○○ 가도 돼?'처럼 특정 장소의 영업 여부를 물을 때 부른다.
    관광공사에 없는 장소는 unknown 으로 온다.

    place: 장소 이름 (지역을 붙이면 더 정확함, 예: 부산 부산박물관)
    date: 방문 날짜 YYYY-MM-DD
    """
    from .chat_service import kakao_first_place
    from .tour_service import place_open

    day = _parse_day(date)
    if not place or not day:
        return {'error': '장소와 날짜가 필요해요.'}

    found = kakao_first_place(place)
    if not found:
        return {'error': "'%s'을(를) 찾지 못했어요." % place}

    status = place_open(found['name'], day, found['lat'], found['lon'])
    if status is None:
        return {'place': found['name'], 'date': day.isoformat(), 'unknown': True}

    return {'place': found['name'], 'date': day.isoformat(), **status}


# AI에게 주는 도구 목록
CHAT_TOOLS = [get_weather, check_open]
