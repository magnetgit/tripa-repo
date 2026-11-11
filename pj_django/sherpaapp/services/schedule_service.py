from datetime import datetime, timedelta, time
import hashlib
import math
import re

import requests
from django.core.cache import cache

from ..models import (
    Category,
    Place,
    Schedule,
    SchedulePlace,
    TravelDayPlan,
)

from . import rain_service
from .place_service import is_junk_kind, kakao_documents, search_places, to_place
from .hours_service import fit_stay, hhmm, place_hours
from .tour_service import _tour_get, find_tour_item
from .stay_rules import stay_range
from .timetable_service import first_trip, last_trip
from .route_service import (
    calculate_distance,
    get_travel_time,
)


# =========================================================
# 기본 설정
# =========================================================

DEFAULT_STAY_TIME = {

    '쇼핑': 120,
    '역사': 90,
    '전통문화': 90,
    '랜드마크': 60,
    '카페': 60,
    '공원': 90,
    '음식': 90,
    '자연': 120,
    '바다': 120,

    # 자동 일정에서 추가 사용
    '숙박': 30,
    '실내': 90,   # 비 오는 날 넣는 박물관·전시관 같은 실내 후보
}


# 하루 관광 장소 최대 개수
# 음식 / 숙박은 포함하지 않음
MAX_ACTIVITY_PER_DAY = 3


# 자동 추천 시간 계산 시 같은 좌표쌍을 반복 조회하지 않도록 캐시한다.
# 여행 하나를 생성하는 동안만 사용하는 메모리 캐시이다.
_TRAVEL_MINUTES_CACHE = {}

# 대중교통은 현재 서버에서 ODsay Web API를 직접 호출하지 않으므로
# 일정 생성 단계에서는 거리 기반의 보수적인 예상시간을 사용한다.
# 실제 화면에서는 ODsay 경로를 받은 뒤 충돌이 생기지 않도록 시간을 다시 밀어낸다.
PUBLIC_TRANSPORT_MIN_BUFFER = 8


# 첫날 시작
FIRST_DAY_START = time(9, 0)


# 2일차 이후 시작
NORMAL_DAY_START = time(9, 0)


# 하루 종료 기준
DAY_END = time(
    21,
    30
)


# 점심 목표시간
LUNCH_TIME = time(
    12,
    30
)


# 저녁 목표시간
DINNER_TIME = time(
    18,
    30
)


# =========================================================
# 선택 카테고리
# =========================================================

def get_selected_categories(travel):

    return (
        Category.objects
        .filter(
            travel_categories__travel=travel
        )
        .distinct()
    )


# =========================================================
# 체류시간
# =========================================================

def get_stay_time(category_name):

    return DEFAULT_STAY_TIME.get(
        category_name,
        60
    )


# 카카오가 '테마파크'로 나눠도 잠깐 타고 끝나는 곳 (이름에 이 말이 있으면 길게 안 잡음)
# 예: '해운대블루라인파크 미포정거장', '스카이라인 루지 부산'
SHORT_RIDE_WORDS = ('정거장', '루지', '케이블카', '레일바이크', '짚라인', '모노레일', '열차')


def get_candidate_stay_time(candidate):
    """후보 하나의 체류 시간(분) = stay_rules.stay_range 의 '보통' 값 (🟩 11/11, 🟧 식사 시간대 맞추기와 같은 기준)
    종류 = 컨셉 + 카카오 분류, 이름도 같이 봄 (예: 롯데월드 → 테마파크 180분, 카페 50분)"""
    concept = candidate.get('selected_category') or ''

    # 잠깐 타는 곳은 카카오 분류(테마파크)를 보지 않고 컨셉만으로
    if any(word in (candidate.get('name') or '') for word in SHORT_RIDE_WORDS):
        return stay_range(concept)[1]

    kind = f"{concept} {candidate.get('kakao_category') or ''}"
    return stay_range(kind, candidate.get('name') or '')[1]


# =========================================================
# 여행 날짜 생성
# =========================================================

def create_travel_dates(travel):

    start_date = travel.t_start
    end_date = travel.t_end


    if isinstance(
        start_date,
        str
    ):

        start_date = (
            datetime.strptime(
                start_date,
                '%Y-%m-%d'
            )
            .date()
        )


    if isinstance(
        end_date,
        str
    ):

        end_date = (
            datetime.strptime(
                end_date,
                '%Y-%m-%d'
            )
            .date()
        )


    dates = []

    current_date = start_date


    while (
        current_date
        <=
        end_date
    ):

        dates.append(
            current_date
        )

        current_date += timedelta(
            days=1
        )


    return dates


# =========================================================
# time 값 정규화
# =========================================================

def normalize_time(value):

    if value is None:

        return None


    if isinstance(
        value,
        time
    ):

        return value


    if isinstance(
        value,
        datetime
    ):

        return value.time()


    if isinstance(
        value,
        str
    ):

        value = value.strip()

        if not value:

            return None


        for format_string in (
            '%H:%M:%S',
            '%H:%M',
        ):

            try:

                return (
                    datetime.strptime(
                        value,
                        format_string
                    )
                    .time()
                )

            except ValueError:

                pass


    return None


# =========================================================
# 숫자 변환
# =========================================================

def to_float(value):

    if value is None:

        return None


    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return None


# =========================================================
# 후보 장소 좌표
#
# Kakao
# x = 경도
# y = 위도
# =========================================================

def get_candidate_coordinate(
    candidate
):

    lat = (
        candidate.get('y')
        or
        candidate.get('lat')
    )

    lon = (
        candidate.get('x')
        or
        candidate.get('lon')
    )


    lat = to_float(
        lat
    )

    lon = to_float(
        lon
    )


    if (
        lat is None
        or
        lon is None
    ):

        return (
            None,
            None
        )


    return (
        lat,
        lon
    )


# =========================================================
# 후보 장소 고유 KEY
# =========================================================

def get_candidate_key(
    candidate
):

    name = (
        candidate
        .get(
            'name',
            ''
        )
        .strip()
    )

    address = (
        candidate
        .get(
            'address',
            ''
        )
        .strip()
    )


    return (
        name,
        address
    )


# =========================================================
# 장소 중복 제거
# =========================================================

def remove_duplicate_places(
    candidates
):

    result = []

    seen = set()


    for candidate in candidates:

        key = get_candidate_key(
            candidate
        )


        if not key[0]:

            continue


        if key in seen:

            continue


        lat, lon = (
            get_candidate_coordinate(
                candidate
            )
        )


        # 지도 / 거리 계산 때문에
        # 좌표 없는 장소는 자동 일정에서 제외
        if (
            lat is None
            or
            lon is None
        ):

            continue


        seen.add(
            key
        )

        result.append(
            candidate
        )


    return result


# =========================================================
# 이동시간
# =========================================================
def normalize_planning_transport(transport):
    value = (
        str(transport or 'car')
        .split(',')[0]
        .strip()
        .lower()
    )

    transport_map = {
        '자동차': 'car',
        '차': 'car',
        'car': 'car',
        '도보': 'walk',
        'walk': 'walk',
        '자전거': 'bike',
        'bike': 'bike',
        '대중교통': 'public_transport',
        'public': 'public_transport',
        'public transport': 'public_transport',
        'public_transport': 'public_transport',
    }

    return transport_map.get(
        value,
        value
    )


def calculate_travel_minutes(
    start_point,
    end_point,
    transport
):
    """
    자동 일정 '후보 평가'용 빠른 예상 이동시간.

    중요:
    이 함수에서는 Kakao Directions / ODsay 같은 외부 길찾기 API를
    절대로 호출하지 않는다.

    이유:
    fill_activities()는 후보 장소 여러 개를 반복 평가하므로
    여기서 외부 API를 호출하면 여행 생성 한 번에 수십~수백 번의
    네트워크 요청이 발생해 PythonAnywhere 요청 시간이 지나치게 길어진다.

    실제 상세 경로와 실제 이동시간은 여행 상세 페이지에서
    최종 선택된 장소 사이에 대해서만 조회한다.
    """

    if (
        start_point is None
        or end_point is None
    ):
        return 0

    try:
        start_lat = float(start_point[0])
        start_lon = float(start_point[1])
        end_lat = float(end_point[0])
        end_lon = float(end_point[1])
    except (TypeError, ValueError):
        return 0

    normalized_transport = (
        normalize_planning_transport(
            transport
        )
    )

    cache_key = (
        round(start_lat, 6),
        round(start_lon, 6),
        round(end_lat, 6),
        round(end_lon, 6),
        normalized_transport,
    )

    if cache_key in _TRAVEL_MINUTES_CACHE:
        return _TRAVEL_MINUTES_CACHE[
            cache_key
        ]

    try:
        distance = max(
            float(
                calculate_distance(
                    start_lat,
                    start_lon,
                    end_lat,
                    end_lon,
                )
            ),
            0.0
        )
    except Exception as e:
        print(
            '거리 계산 실패:',
            e
        )
        distance = 0.0

    if distance <= 0:
        minutes = 0

    elif normalized_transport == 'walk':
        # 실제 보행 경로가 직선보다 길다는 점을 약 15% 보정
        adjusted_distance = (
            distance * 1.15
        )

        minutes = max(
            int(
                math.ceil(
                    adjusted_distance
                    / 4.0
                    * 60
                )
            ),
            1
        )

    elif normalized_transport == 'bike':
        adjusted_distance = (
            distance * 1.12
        )

        minutes = max(
            int(
                math.ceil(
                    adjusted_distance
                    / 15.0
                    * 60
                )
            ),
            1
        )

    elif normalized_transport == 'public_transport':
        # 대중교통은 환승/도보/대기시간을 포함해 보수적으로 잡는다.
        adjusted_distance = (
            distance * 1.18
        )

        if distance >= 100:
            speed = 65.0
            buffer = 20
        elif distance >= 30:
            speed = 42.0
            buffer = 15
        elif distance >= 5:
            speed = 24.0
            buffer = 10
        else:
            speed = 18.0
            buffer = PUBLIC_TRANSPORT_MIN_BUFFER

        minutes = max(
            int(
                math.ceil(
                    adjusted_distance
                    / speed
                    * 60
                )
            )
            + buffer,
            1
        )

    else:
        # 자동차 및 기타 차량.
        # 후보 평가에서는 실제 Directions API 대신 거리 기반 예상치만 사용한다.
        # 시내 짧은 구간은 신호/교차로 시간을 더 크게 잡고,
        # 장거리는 평균속도를 높인다.
        adjusted_distance = (
            distance * 1.22
        )

        if distance < 2:
            speed = 24.0
            buffer = 3
        elif distance < 10:
            speed = 34.0
            buffer = 4
        elif distance < 50:
            speed = 48.0
            buffer = 6
        elif distance < 150:
            speed = 65.0
            buffer = 8
        else:
            speed = 78.0
            buffer = 12

        minutes = max(
            int(
                math.ceil(
                    adjusted_distance
                    / speed
                    * 60
                )
            )
            + buffer,
            1
        )

    _TRAVEL_MINUTES_CACHE[
        cache_key
    ] = minutes

    return minutes

# =========================================================
# 현재 위치에서 가장 가까운 장소
# =========================================================

# =========================================================
# 운영시간 맞추기 (🟩 11/06 결정, 🟦 hours_service.fit_stay를 그대로 씀)
# =========================================================

# 문 열기 전에 도착하면 이 시간(분)까지는 기다렸다 들어간다. 더 길면 다른 곳을 넣는다.
MAX_OPEN_WAIT = 60

WEEKDAY_KO = '월화수목금토일'

# 여행 하나를 만드는 동안 같은 장소·날짜의 운영시간을 다시 찾지 않도록 (관광공사 결과는 7일 캐시)
_HOURS_CACHE = {}


def candidate_kind(candidate):
    """운영시간 판단용 분류 글자 ('음식 음식점 > 한식' → 음식점 마감 1시간 전 규칙)"""
    return ' '.join(
        str(candidate.get(key) or '')
        for key in ('selected_category', 'kind', 'kakao_category')
    ).strip()


def candidate_hours(candidate, day):
    """후보 장소의 그날 운영시간 (hours_service.place_hours 결과, 모르면 None)"""
    cache_key = (get_candidate_key(candidate), day)

    if cache_key not in _HOURS_CACHE:
        lat, lon = get_candidate_coordinate(candidate)

        try:
            _HOURS_CACHE[cache_key] = place_hours(
                candidate.get('name'),
                candidate_kind(candidate),
                day,
                lat,
                lon,
                candidate.get('kakao_id'),
            )
        except Exception as e:  # 운영시간을 못 읽어도 일정은 만든다
            print(candidate.get('name'), '운영시간 실패:', e)
            _HOURS_CACHE[cache_key] = None

    return _HOURS_CACHE[cache_key]


def fit_opening_hours(candidate, arrival_datetime, stay_minutes):
    """
    도착 시각·체류 시간을 운영시간에 맞춘다.
    → (도착 시각, 체류 분) 또는 None (쉬는 날 · 마감 전에 못 감 · 너무 오래 기다림)
    """
    kind = candidate_kind(candidate)
    hours = candidate_hours(candidate, arrival_datetime.date())
    arrive_min = arrival_datetime.hour * 60 + arrival_datetime.minute

    fit = fit_stay(kind, hours, arrive_min, stay_minutes)

    # 아직 안 열었으면 여는 시각까지 기다린다 (오래 걸리면 포기)
    if fit['status'] == 'early':
        wait = hours['open_min'] - arrive_min

        if wait > MAX_OPEN_WAIT:
            return None

        arrival_datetime = arrival_datetime + timedelta(minutes=wait)
        fit = fit_stay(kind, hours, hours['open_min'], stay_minutes)

    if fit['status'] in ('closed', 'late', 'early'):
        return None

    return arrival_datetime, fit['stay']


def fits_before_limit(
    candidate,
    finish_datetime,
    limit_datetime,
    reach_point,
    transport
):
    """끝나는 시각(+ 다음 고정 장소까지 이동)이 제한 시각 안인지"""
    if reach_point is not None:
        finish_datetime = finish_datetime + timedelta(
            minutes=calculate_travel_minutes(
                get_candidate_coordinate(candidate),
                reach_point,
                transport
            )
        )

    return finish_datetime <= limit_datetime


def pick_open_candidate(
    possible,
    used_places,
    current_datetime,
    current_point,
    transport,
    stay_minutes=None,
    target_datetime=None,
    limit_datetime=None,
    reach_point=None
):
    """
    가까운 순서로 보면서 운영시간에 맞는 첫 후보를 고른다.
    → (후보, 도착 시각, 체류 분) 또는 (None, None, None)

    stay_minutes: 정해진 체류(식사 90분), 없으면 분류별 기본 체류
    target_datetime: 이 시각 전에는 도착하지 않음 (점심 12:30 같은 목표 시각)
    """
    remaining = list(possible)

    while remaining:
        candidate = find_nearest_candidate(
            remaining,
            used_places,
            current_point
        )

        if candidate is None:
            break

        remaining.remove(candidate)

        arrival = current_datetime + timedelta(
            minutes=calculate_travel_minutes(
                current_point,
                get_candidate_coordinate(candidate),
                transport
            )
        )

        if target_datetime and arrival < target_datetime:
            arrival = target_datetime

        stay = stay_minutes

        if stay is None:
            stay = get_candidate_stay_time(candidate)

        fitted = fit_opening_hours(candidate, arrival, stay)

        if fitted is None:
            print(candidate.get('name'), '운영시간이 안 맞아 건너뜀:', arrival.strftime('%m-%d %H:%M'))
            continue

        arrival, stay = fitted

        # 기다리느라 늦게 끝나면 숙소·귀가 시각을 넘을 수 있어서 다시 확인
        if limit_datetime is not None and not fits_before_limit(
            candidate,
            arrival + timedelta(minutes=stay),
            limit_datetime,
            reach_point,
            transport
        ):
            continue

        return candidate, arrival, stay

    return None, None, None


def move_closed_pins(travel, pins):
    """
    담은 장소(사용자가 고른 곳)가 그날 쉬면 여행 중 여는 날로 옮긴다.
    → (새 pins 목록, {DAY 번호: {'moved': [...], 'excluded': [...]}})
       응답 키 모양은 TEAM_UPDATES 11/10 '운영시간 안내 응답 키' (mock.json plan.days[])
    """
    total_days = (travel.t_end - travel.t_start).days + 1
    result = []
    notes = {}

    for pin in pins or []:
        try:
            day = int(pin.get('day'))
        except (TypeError, ValueError):
            result.append(pin)
            continue

        if not 1 <= day <= total_days or not pin.get('name'):
            result.append(pin)
            continue

        def hours_on(number):
            try:
                return place_hours(
                    pin.get('name'),
                    pin.get('kind') or '',
                    travel.t_start + timedelta(days=number - 1),
                    to_float(pin.get('lat')),
                    to_float(pin.get('lon')),
                    pin.get('kakao_id'),
                )
            except Exception:
                return None

        hours = hours_on(day)

        if not hours or not hours.get('closed'):
            result.append(pin)
            continue

        # 가까운 날부터 (2일차면 1·3·4일차 순서)
        others = sorted(
            (number for number in range(1, total_days + 1) if number != day),
            key=lambda number: (abs(number - day), number)
        )
        open_days = [
            number for number in others
            if not (hours_on(number) or {}).get('closed')
        ]

        day_date = travel.t_start + timedelta(days=day - 1)
        closed_text = '%s요일 휴무' % WEEKDAY_KO[day_date.weekday()]
        note = notes.setdefault(day, {'moved': [], 'excluded': []})

        if open_days:
            to_day = open_days[0]
            to_date = travel.t_start + timedelta(days=to_day - 1)
            moved_pin = dict(pin, day=to_day)
            moved_pin.pop('time', None)   # 원래 날의 시각은 옮긴 날에 안 맞을 수 있어서
            result.append(moved_pin)

            note['moved'].append({
                'name': pin['name'],
                'from_day': day,
                'to_day': to_day,
                'message': '%s라 DAY %d(%s)로 옮겼어요' % (
                    closed_text, to_day, WEEKDAY_KO[to_date.weekday()]
                ),
            })
        else:
            note['excluded'].append({
                'name': pin['name'],
                'reason': 'closed',
                'message': '%s예요 · 이 여행 기간에는 여는 날이 없어요' % closed_text,
                'open_days': [],
            })

    return result, notes


def hours_badge(kind, hours, arrive_min, stay_min, wait_min=0):
    """
    미리보기 장소 한 곳의 운영시간 안내 (응답 키 items[].hours)
    → {open, close, estimated, status, wait, message} 또는 None
    """
    if not hours or '숙' in (kind or ''):
        return None

    fit = fit_stay(kind, hours, arrive_min, stay_min)

    # 운영시간 글은 있는데 시각을 못 읽은 곳 (쉬는 날도 아님) → 안내할 게 없음
    if fit['status'] == 'unknown' and not hours.get('open'):
        return None
    message = fit['message']
    wait = wait_min if wait_min and wait_min > 0 else 0

    if fit['status'] == 'early':
        message = '%s에 문을 열어요 · 늦게 도착하게 옮겨 보세요' % hours.get('open')
    elif wait and fit['status'] == 'ok':
        message = '%s 문 여는 시각까지 %d분 기다려요' % (hours.get('open'), wait)

    return {
        'open': hours.get('open') or None,
        'close': hours.get('close') or None,
        'estimated': bool(hours.get('estimated')),
        'status': fit['status'],
        'wait': wait,
        'message': message,
    }


# =========================================================
# 숙소 체크인 시각 안내 (🟩 11/11, 11/05 결정: 막지 않고 안내만)
# =========================================================

CHECKIN_CACHE_SECONDS = 60 * 60 * 24 * 7   # 같은 숙소는 7일 동안 다시 묻지 않음

# '15:00', '15시', '오후 3시', '15:00 이후' 같은 글에서 첫 시각
_CHECKIN_TIME = re.compile(r'(오후|PM|pm)?\s*(\d{1,2})\s*(?::\s*(\d{2})|시\s*(\d{2})?)')


def parse_checkin_time(text):
    """체크인 글 → 'HH:MM' (못 읽으면 None)"""
    m = _CHECKIN_TIME.search(str(text or ''))
    if not m:
        return None
    hour, minute = int(m.group(2)), int(m.group(3) or m.group(4) or 0)
    if m.group(1) and hour < 12:
        hour += 12
    if hour > 23 or minute > 59:
        return None
    return '%02d:%02d' % (hour, minute)


def stay_checkin_time(name, lat=None, lon=None, kakao_id=None):
    """관광공사 숙소 소개(detailIntro2 checkintime) → 'HH:MM'. 관광공사에 없거나 못 읽으면 None"""
    cache_key = 'tour_checkin:v1:%s' % hashlib.md5(
        str(kakao_id or '%s:%s:%s' % (name, lat, lon)).encode('utf-8')
    ).hexdigest()
    saved = cache.get(cache_key)
    if saved is not None:
        return saved or None

    found = ''
    try:
        item = find_tour_item(name, lat, lon)
        if item:
            intro = _tour_get('detailIntro2', contentId=item.get('contentid'),
                              contentTypeId=item.get('contenttypeid'))
            found = parse_checkin_time((intro[0] if intro else {}).get('checkintime')) or ''
    except requests.RequestException:
        print('관광공사 체크인 시각 조회 실패:', name)
        return None   # 실패는 저장하지 않고 다음에 다시 물음

    cache.set(cache_key, found, CHECKIN_CACHE_SECONDS)
    return found or None


def checkin_badge(checkin, arrive):
    """
    숙소 줄의 체크인 안내 (응답 키 items[].checkin)
    → {'from': 'HH:MM', 'early': 체크인 전 도착인지, 'message': ...} 또는 None
    """
    if not checkin:
        return None
    early = bool(arrive) and arrive < checkin
    message = '체크인 %s부터' % checkin
    if early:
        message += ' · 그 전엔 짐 맡기기만 될 수 있어요'
    return {'from': checkin, 'early': early, 'message': message}


# =========================================================
# 비 오는 날 실내 먼저 (🟩 11/06 결정, 🟦 rain_service 함수를 그대로 씀)
# =========================================================

def rainy_trip_dates(travel):
    """여행 날짜 중 비·눈 예보(또는 이미 지난 날 실제로 온 날) → {date, ...}"""
    try:
        weather = rain_service.trip_days_weather(
            travel.t_place,
            travel.t_start,
            travel.t_end,
        )
    except Exception as e:  # 날씨를 못 읽어도 일정은 만든다
        print('날씨 조회 실패:', e)
        return set()

    return {
        datetime.strptime(day, '%Y-%m-%d').date()
        for day, info in weather.items()
        if info and info.get('rainy')
    }


def candidate_indoor(candidate):
    """후보가 실내면 True (실외 False, 모름 None). 한 번 판단하면 후보에 적어 둔다."""
    if '_indoor' not in candidate:
        lat, lon = get_candidate_coordinate(candidate)

        try:
            candidate['_indoor'] = rain_service.place_indoor(
                candidate.get('name'),
                candidate.get('kakao_category') or candidate.get('selected_category') or '',
                lat,
                lon,
                candidate.get('kakao_id'),
            )
        except Exception:
            candidate['_indoor'] = None

    return candidate['_indoor']


def indoor_candidates(travel):
    """비 오는 날에 넣을 여행지 근처 실내 후보 (박물관·미술관·전시관·아쿠아리움·복합쇼핑몰)"""
    lat, lon = rain_service._coords(travel.t_place, None)

    if lat is None:
        return []

    found = []
    seen = set()
    # '벡스코 제1전시장'·'벡스코 제2전시장'처럼 같은 건물은 한 곳만 (이름 첫 낱말로 봄)
    seen_heads = set()

    for query, group in rain_service.INDOOR_QUERIES:
        try:
            docs = kakao_documents(
                query, 8, group,
                x=lon, y=lat, radius=10000, sort='accuracy',
            )
        except Exception as e:
            print(query, '실내 후보 검색 실패:', e)
            continue

        for doc in docs:
            if doc.get('id') in seen or is_junk_kind(doc.get('category_name')):
                continue

            seen.add(doc.get('id'))
            head = (doc.get('place_name') or '').split(' ')[0]

            if head in seen_heads:
                continue

            seen_heads.add(head)
            candidate = to_place(doc, '실내')
            candidate['selected_category'] = '실내'

            if candidate_indoor(candidate) is True:
                found.append(candidate)

    print('비 오는 날 실내 후보:', len(found))
    return remove_duplicate_places(found)


def prefer_indoor(possible):
    """실내 후보가 있으면 실내만, 하나도 없으면 그대로 (그날이 비지 않게)"""
    indoor = [
        candidate for candidate in possible
        if candidate_indoor(candidate) is True
    ]

    return indoor or possible


def find_nearest_candidate(
    candidates,
    used_places,
    current_point=None
):

    available = []


    for candidate in candidates:

        key = get_candidate_key(
            candidate
        )


        if key in used_places:

            continue


        lat, lon = (
            get_candidate_coordinate(
                candidate
            )
        )


        if (
            lat is None
            or
            lon is None
        ):

            continue


        available.append(
            candidate
        )


    if not available:

        return None


    # 출발 위치가 없으면
    # 첫 번째 후보
    if current_point is None:

        return available[0]


    def distance(candidate):

        lat, lon = (
            get_candidate_coordinate(
                candidate
            )
        )


        try:

            return calculate_distance(

                current_point[0],
                current_point[1],

                lat,
                lon
            )

        except Exception:

            return 999999


    return min(
        available,
        key=distance
    )


# =========================================================
# 체크인 전 해당 장소를 방문할 수 있는지 계산
# =========================================================

def can_visit_before_fixed_time(
    candidate,
    current_datetime,
    current_point,
    fixed_datetime,
    fixed_point,
    transport
):

    candidate_point = (
        get_candidate_coordinate(
            candidate
        )
    )


    category_name = (
        candidate.get(
            'selected_category'
        )
        or
        '기타'
    )


    stay_time = (
        get_candidate_stay_time(candidate)
    )


    # 현재 장소 -> 후보 장소
    first_travel = (
        calculate_travel_minutes(

            current_point,
            candidate_point,
            transport
        )
    )


    candidate_finish = (

        current_datetime

        +

        timedelta(
            minutes=
                first_travel
                +
                stay_time
        )
    )


    # 후보 장소 -> 체크인 장소
    second_travel = (
        calculate_travel_minutes(

            candidate_point,
            fixed_point,
            transport
        )
    )


    final_arrival = (

        candidate_finish

        +

        timedelta(
            minutes=
                second_travel
        )
    )


    return (
        final_arrival
        <=
        fixed_datetime
    )


# =========================================================
# DB PLACE 생성 / 조회
# =========================================================

def get_or_create_place(
    travel,
    candidate
):

    lat, lon = (
        get_candidate_coordinate(
            candidate
        )
    )


    category_name = (
        candidate.get(
            'selected_category'
        )
        or
        candidate.get(
            'category'
        )
        or
        '기타'
    )


    place_obj, created = (
        Place.objects
        .get_or_create(

            travel=travel,

            p_name=
                candidate.get(
                    'name'
                ),

            defaults={

                'p_addr':
                    candidate.get(
                        'address'
                    )
                    or '',

                'p_lat':
                    lat,

                'p_lon':
                    lon,

                'p_kind':
                    category_name,

                # 사진·리뷰 별점을 붙일 때 씀
                'p_kakao_id':
                    str(candidate.get('kakao_id') or '')
                    or None,
            }
        )
    )


    # 기존 장소인데 좌표 등이 비어 있으면 갱신
    changed = False


    if (
        not place_obj.p_addr
        and
        candidate.get(
            'address'
        )
    ):

        place_obj.p_addr = (
            candidate.get(
                'address'
            )
        )

        changed = True


    if (
        not place_obj.p_lat
        and
        lat is not None
    ):

        place_obj.p_lat = lat

        changed = True


    if (
        not place_obj.p_lon
        and
        lon is not None
    ):

        place_obj.p_lon = lon

        changed = True


    if (
        not place_obj.p_kakao_id
        and
        candidate.get(
            'kakao_id'
        )
    ):

        place_obj.p_kakao_id = str(
            candidate.get(
                'kakao_id'
            )
        )

        changed = True


    if changed:

        place_obj.save()


    return place_obj


# =========================================================
# SchedulePlace 하나 저장
# =========================================================

def save_schedule_place(
    travel,
    schedule,
    candidate,
    visit_order,
    current_datetime,
    current_point,
    transport,
    forced_arrival=None,
    stay_time_override=None
):

    candidate_point = (
        get_candidate_coordinate(
            candidate
        )
    )


    travel_time = (
        calculate_travel_minutes(

            current_point,
            candidate_point,
            transport
        )
    )


    calculated_arrival = (

        current_datetime

        +

        timedelta(
            minutes=
                travel_time
        )
    )


    # 점심 / 저녁 / 체크인처럼
    # 목표시간이 있는 경우
    if (
        forced_arrival
        and
        calculated_arrival
        <
        forced_arrival
    ):

        arrival_datetime = (
            forced_arrival
        )

    else:

        arrival_datetime = (
            calculated_arrival
        )


    category_name = (
        candidate.get(
            'selected_category'
        )
        or
        '기타'
    )


    if stay_time_override is None:

        stay_time = (
            get_candidate_stay_time(candidate)
        )

    else:

        stay_time = (
            stay_time_override
        )


    departure_datetime = (

        arrival_datetime

        +

        timedelta(
            minutes=
                stay_time
        )
    )


    place_obj = (
        get_or_create_place(
            travel,
            candidate
        )
    )


    SchedulePlace.objects.create(

        schedule=
            schedule,

        place=
            place_obj,

        visit_order=
            visit_order,

        stay_time=
            stay_time,

        arrive_time=
            arrival_datetime.time(),

        start_time=
            departure_datetime.time(),

        travel_time=
            travel_time
    )


    print(
        schedule.s_day,
        visit_order,
        candidate.get('name'),
        '도착:',
        arrival_datetime.time(),
        '이동:',
        travel_time,
        '체류:',
        stay_time
    )


    return (
        departure_datetime,
        candidate_point,
        visit_order + 1
    )


# =========================================================
# 숙소 후보
# =========================================================

def get_accommodation_candidate(
    travel
):

    accommodation = (
        getattr(
            travel,
            'accommodation',
            None
        )
    )


    if not accommodation:

        return None


    lat = to_float(
        getattr(
            travel,
            'accommodation_lat',
            None
        )
    )

    lon = to_float(
        getattr(
            travel,
            'accommodation_lon',
            None
        )
    )


    # DB에 좌표까지 있으면
    # 바로 사용
    if (
        lat is not None
        and
        lon is not None
    ):

        return {

            'name':
                accommodation,

            'address':
                accommodation,

            'x':
                lon,

            'y':
                lat,

            'selected_category':
                '숙박',
        }


    # 숙소명만 있으면
    # 카카오에서 검색
    try:

        results = search_places(
            travel.t_place,
            accommodation
        )

    except Exception as e:

        print(
            '숙소 검색 실패:',
            e
        )

        results = []


    if not results:

        return None


    candidate = (
        results[0].copy()
    )


    candidate[
        'selected_category'
    ] = '숙박'


    return candidate


# =========================================================
# 첫날 출발 위치
# =========================================================

def get_start_point(
    travel
):

    lat = to_float(
        getattr(
            travel,
            'start_lat',
            None
        )
    )

    lon = to_float(
        getattr(
            travel,
            'start_lon',
            None
        )
    )


    if (
        lat is None
        or
        lon is None
    ):

        return None


    return (
        lat,
        lon
    )


# =========================================================
# 활동 장소 후보 + 음식 후보
# =========================================================

# 컨셉과 안 맞는 종류(카페/음식점/숙소)는 관광 후보에서 제외
# 예) '랜드마크' 검색에 걸린 스타벅스
_KIND_GROUPS = {
    'CE7': ('카페',),
    'FD6': ('음식', '맛집'),
    'AD5': ('숙박', '숙소'),
}


def filter_by_real_kind(places, concept):

    kept = []

    for place in places:

        allowed = _KIND_GROUPS.get(
            place.get('kakao_group')
        )

        if allowed and concept not in allowed:
            continue

        kept.append(place)

    # 전부 걸러지면 원래 결과를 그대로 사용
    return kept or places


def build_place_candidates(
    travel,
    categories
):

    activity_candidates = []

    meal_candidates = []


    # ==========================================
    # 사용자가 고른 컨셉
    # ==========================================

    for category in categories:

        try:

            searched_places = (
                search_places(

                    travel.t_place,

                    category.c_name
                )

                or
                []
            )

        except Exception as e:

            print(
                category.c_name,
                '장소 검색 실패:',
                e
            )

            continue


        print(
            category.c_name,
            '검색:',
            len(
                searched_places
            )
        )


        searched_places = filter_by_real_kind(
            searched_places,
            category.c_name
        )

        for place in searched_places:

            candidate = (
                place.copy()
            )


            candidate[
                'selected_category'
            ] = category.c_name


            # 음식은 관광 후보가 아니라
            # 점심/저녁 후보로 사용
            if (
                category.c_name
                ==
                '음식'
            ):

                meal_candidates.append(
                    candidate
                )

            else:

                activity_candidates.append(
                    candidate
                )


    # ==========================================
    # 음식 카테고리를 선택하지 않았더라도
    # 점심/저녁은 추천
    # ==========================================

    try:

        restaurant_results = (
            search_places(

                travel.t_place,

                '맛집'
            )

            or
            []
        )

    except Exception as e:

        print(
            '맛집 검색 실패:',
            e
        )

        restaurant_results = []


    for place in restaurant_results:

        candidate = (
            place.copy()
        )

        candidate[
            'selected_category'
        ] = '음식'

        meal_candidates.append(
            candidate
        )


    return (

        remove_duplicate_places(
            activity_candidates
        ),

        remove_duplicate_places(
            meal_candidates
        )
    )


# =========================================================
# 일정 구간에 관광지 자동 채우기
# =========================================================

def fill_activities(
    travel,
    schedule,
    candidates,
    used_places,
    current_datetime,
    current_point,
    visit_order,
    activity_count,
    limit_datetime,
    transport,
    max_activity_count,
    reach_point=None,
    rainy=False
):
    """rainy: 비 오는 날이면 넣을 수 있는 곳 중 실내를 먼저 고른다"""

    while (
        activity_count
        <
        max_activity_count
    ):

        if (
            current_datetime
            >=
            limit_datetime
        ):

            break


        possible = []


        # ======================================
        # 시간 안에 들어갈 수 있는 장소만 필터
        # ======================================

        for candidate in candidates:

            key = get_candidate_key(
                candidate
            )


            if key in used_places:

                continue


            candidate_point = (
                get_candidate_coordinate(
                    candidate
                )
            )


            travel_time = (
                calculate_travel_minutes(

                    current_point,
                    candidate_point,
                    transport
                )
            )


            stay_time = (
                get_candidate_stay_time(
                    candidate
                )
            )


            finish_datetime = (

                current_datetime

                +

                timedelta(
                    minutes=
                        travel_time
                        +
                        stay_time
                )
            )


            # 단순 시간 제한
            if reach_point is None:

                if (
                    finish_datetime
                    <=
                    limit_datetime
                ):

                    possible.append(
                        candidate
                    )


            # 체크인 장소까지
            # 이동시간까지 포함해서 계산
            else:

                if (
                    can_visit_before_fixed_time(

                        candidate,
                        current_datetime,
                        current_point,
                        limit_datetime,
                        reach_point,
                        transport
                    )
                ):

                    possible.append(
                        candidate
                    )


        if not possible:

            break


        # 비 오는 날은 실내 먼저 (실내가 없으면 그대로)
        if rainy:

            possible = prefer_indoor(
                possible
            )


        # ======================================
        # 현재 위치에서 가장 가까운 장소
        # ======================================

        # (쉬는 날 · 마감 전에 못 감 · 오래 기다림이면 다음으로 가까운 곳)
        candidate, arrival, stay = pick_open_candidate(
            possible,
            used_places,
            current_datetime,
            current_point,
            transport,
            limit_datetime=limit_datetime,
            reach_point=reach_point,
        )


        if candidate is None:

            break


        used_places.add(
            get_candidate_key(
                candidate
            )
        )


        (
            current_datetime,
            current_point,
            visit_order
        ) = save_schedule_place(

            travel,
            schedule,
            candidate,
            visit_order,
            current_datetime,
            current_point,
            transport,
            forced_arrival=arrival,
            stay_time_override=stay
        )


        activity_count += 1


    return (
        current_datetime,
        current_point,
        visit_order,
        activity_count
    )


# =========================================================
# 점심 / 저녁 추가
# =========================================================

def add_meal(
    travel,
    schedule,
    meal_candidates,
    used_places,
    current_datetime,
    current_point,
    visit_order,
    transport,
    target_datetime
):

    candidate, arrival, stay = pick_open_candidate(
        meal_candidates,
        used_places,
        current_datetime,
        current_point,
        transport,
        stay_minutes=90,
        target_datetime=target_datetime,
    )


    if candidate is None:

        print(
            '추천 가능한 음식점이 없습니다.'
        )

        return (
            current_datetime,
            current_point,
            visit_order
        )


    used_places.add(
        get_candidate_key(
            candidate
        )
    )


    return save_schedule_place(

        travel,
        schedule,
        candidate,
        visit_order,
        current_datetime,
        current_point,
        transport,

        forced_arrival=
            arrival,

        stay_time_override=
            stay
    )


# =========================================================
# 체크인
# =========================================================

def add_checkin(
    travel,
    schedule,
    accommodation,
    current_datetime,
    current_point,
    visit_order,
    transport,
    checkin_datetime
):

    if accommodation is None:

        return (
            current_datetime,
            current_point,
            visit_order
        )


    print(
        '체크인:',
        accommodation.get(
            'name'
        ),
        checkin_datetime.time()
    )


    return save_schedule_place(

        travel,
        schedule,
        accommodation,
        visit_order,
        current_datetime,
        current_point,
        transport,

        forced_arrival=
            checkin_datetime,

        stay_time_override=
            CHECKIN_STAY_MINUTES
    )



# =========================================================
# 날짜별 숙소 / 시작점 일반화
# =========================================================

DEFAULT_ACCOMMODATION_ARRIVAL = time(20, 0)

# 체크인하고 다시 나가는 날, 귀가 시각을 안 정했으면 (저녁까지 먹고 들어오게)
CHECKIN_RETURN_DEFAULT = time(21, 30)

# 체크인(짐 두기)에 머무는 시간
CHECKIN_STAY_MINUTES = 30


def build_accommodation_candidate(
    name,
    address=None,
    lat=None,
    lon=None,
):
    """TravelDayPlan/Travel 숙소 정보를 일정 후보 형식으로 변환한다."""

    name = (name or '').strip()

    if not name:
        return None

    lat = to_float(lat)
    lon = to_float(lon)

    if lat is None or lon is None:
        return None

    return {
        'name': name,
        'address': (address or name).strip(),
        'x': lon,
        'y': lat,
        'selected_category': '숙박',
        'category': '숙박',
    }


def get_legacy_accommodation_candidate(travel):
    """기존 Travel 숙소 컬럼을 임시 fallback으로 유지한다."""

    return build_accommodation_candidate(
        getattr(travel, 'accommodation', None),
        getattr(travel, 'accommodation', None),
        getattr(travel, 'accommodation_lat', None),
        getattr(travel, 'accommodation_lon', None),
    )


def get_travel_day_plans(travel):
    """날짜를 key로 하는 TravelDayPlan dict를 반환한다."""

    return {
        plan.plan_date: plan
        for plan in (
            TravelDayPlan.objects
            .filter(travel=travel)
            .order_by('plan_date', 'tdp_id')
        )
    }


def resolve_effective_accommodations(
    travel,
    travel_dates,
    day_plan_map,
):
    """
    숙소가 비어 있는 날은 이전 숙소를 그대로 사용한다.

    DAY 1 숙소 = DAY 1 일정 종료 지점
    DAY 2 시작점 = DAY 1 숙소
    """

    effective = {}

    current_accommodation = (
        get_legacy_accommodation_candidate(travel)
    )

    for travel_date in travel_dates:

        plan = day_plan_map.get(
            travel_date
        )

        if plan:
            candidate = build_accommodation_candidate(
                plan.accommodation_name,
                plan.accommodation_addr,
                plan.accommodation_lat,
                plan.accommodation_lon,
            )

            if candidate:
                current_accommodation = candidate

        effective[travel_date] = (
            current_accommodation.copy()
            if current_accommodation
            else None
        )

    return effective


def get_day_start_time(
    travel,
    travel_date,
    day_index,
    day_plan_map,
):
    """사용자 입력 시간이 없으면 09:00을 사용한다."""

    if day_index == 0:
        return (
            normalize_time(
                getattr(
                    travel,
                    'start_time',
                    None,
                )
            )
            or FIRST_DAY_START
        )

    plan = day_plan_map.get(
        travel_date
    )

    return (
        normalize_time(
            getattr(
                plan,
                'departure_time',
                None,
            )
            if plan
            else None
        )
        or NORMAL_DAY_START
    )


def get_day_accommodation_arrival_time(
    travel_date,
    day_plan_map,
):
    """숙소 도착 시간이 없으면 20:00을 사용한다."""

    plan = day_plan_map.get(
        travel_date
    )

    return (
        normalize_time(
            getattr(
                plan,
                'arrival_time',
                None,
            )
            if plan
            else None
        )
        or DEFAULT_ACCOMMODATION_ARRIVAL
    )


def get_day_checkin_time(
    travel_date,
    day_plan_map,
):
    """그날 숙소에 들렀다 다시 나갈 시각 (TravelDayPlan.checkin_time, 없으면 None)"""

    plan = day_plan_map.get(
        travel_date
    )

    return normalize_time(
        getattr(plan, 'checkin_time', None)
        if plan
        else None
    )


def get_first_day_start_candidate(travel):
    """지도 경로 계산에서도 재사용하기 쉬운 출발지 후보 정보."""

    name = (
        getattr(
            travel,
            'start_place',
            None,
        )
        or '출발지'
    )

    lat = to_float(
        getattr(
            travel,
            'start_lat',
            None,
        )
    )

    lon = to_float(
        getattr(
            travel,
            'start_lon',
            None,
        )
    )

    if lat is None or lon is None:
        return None

    return {
        'name': name,
        'address': (
            getattr(
                travel,
                'start_addr',
                None,
            )
            or name
        ),
        'x': lon,
        'y': lat,
        'selected_category': '출발지',
        'category': '출발지',
    }


def add_meal_before_deadline(
    travel,
    schedule,
    meal_candidates,
    used_places,
    current_datetime,
    current_point,
    visit_order,
    transport,
    target_datetime,
    fixed_datetime=None,
    fixed_point=None,
):
    """
    숙소 도착 시간이 정해져 있으면
    식사 후 숙소까지 갈 수 있는 음식점만 선택한다.
    """

    possible = []

    for candidate in meal_candidates:

        key = get_candidate_key(
            candidate
        )

        if key in used_places:
            continue

        if (
            fixed_datetime is not None
            and fixed_point is not None
        ):

            if not can_visit_before_fixed_time(
                candidate,
                current_datetime,
                current_point,
                fixed_datetime,
                fixed_point,
                transport,
            ):
                continue

        possible.append(
            candidate
        )

    # 가까운 곳부터, 운영시간에 맞는 음식점 (마감 1시간 전까지 도착)
    candidate, arrival, stay = pick_open_candidate(
        possible,
        used_places,
        current_datetime,
        current_point,
        transport,
        stay_minutes=90,
        target_datetime=target_datetime,
        limit_datetime=fixed_datetime if fixed_point is not None else None,
        reach_point=fixed_point,
    )

    if candidate is None:
        return (
            current_datetime,
            current_point,
            visit_order,
        )

    used_places.add(
        get_candidate_key(
            candidate
        )
    )

    return save_schedule_place(
        travel,
        schedule,
        candidate,
        visit_order,
        current_datetime,
        current_point,
        transport,
        forced_arrival=arrival,
        stay_time_override=stay,
    )


def add_accommodation_arrival(
    travel,
    schedule,
    accommodation,
    current_datetime,
    current_point,
    visit_order,
    transport,
    arrival_datetime,
):
    """
    숙소는 '숙박 체류'가 아니라 '숙소 도착 이벤트'로 저장한다.
    다음 날의 시작점은 TravelDayPlan에서 별도로 계산한다.
    """

    if accommodation is None:
        return (
            current_datetime,
            current_point,
            visit_order,
        )

    return save_schedule_place(
        travel,
        schedule,
        accommodation,
        visit_order,
        current_datetime,
        current_point,
        transport,
        forced_arrival=arrival_datetime,
        stay_time_override=0,
    )



# =========================================================
# 메인 자동 일정 생성
# =========================================================

def go_trip_for(travel, travel_date, after=None):
    """첫날 가는 길 실제 편 (🟩 11/11) — 일정 만들기와 시간 다시 계산(views)이 같은 편을 쓰게 한 곳에서.
    대중교통 여행 · 집 → 첫날 숙소가 80km 넘을 때만, 없으면 None (timetable_service.first_trip 모양)"""
    if normalize_planning_transport(travel.t_way) != 'public_transport':
        return None

    start = get_first_day_start_candidate(travel)
    accommodation = resolve_effective_accommodations(
        travel, [travel_date], get_travel_day_plans(travel),
    ).get(travel_date)

    start_point = get_candidate_coordinate(start) if start else None
    stay_point = get_candidate_coordinate(accommodation) if accommodation else None
    if start_point is None or stay_point is None:
        return None

    return first_trip(
        start_point[0], start_point[1], stay_point[0], stay_point[1],
        travel_date, after=after or getattr(travel, 'start_time', None) or FIRST_DAY_START,
    )


def generate_schedule(
    travel,
    reset_existing=True,
):
    """
    날짜별 시작점/숙소를 반영해 일정을 생성한다.

    DAY 1:
        Travel.start_* -> 관광/식사 -> DAY 1 숙소

    DAY 2 이후:
        전날 숙소 -> 관광/식사 -> 해당 DAY 숙소

    TravelDayPlan의 숙소가 비어 있으면 이전 숙소를 그대로 사용한다.
    출발시간 미입력: 09:00
    숙소 도착시간 미입력: 20:00
    """

    # 여행마다 좌표/이동시간 캐시를 새로 시작한다.
    _TRAVEL_MINUTES_CACHE.clear()
    _HOURS_CACHE.clear()

    print()
    print('=================================')
    print('날짜별 자동 일정 생성 시작')
    print('여행:', travel.t_title)
    print('지역:', travel.t_place)

    # =====================================================
    # 1. 날짜 / DAY Schedule
    # =====================================================

    travel_dates = create_travel_dates(
        travel
    )

    schedules = []

    for travel_date in travel_dates:

        schedule, created = (
            Schedule.objects
            .get_or_create(
                travel=travel,
                s_day=travel_date,
            )
        )

        schedules.append(
            schedule
        )

        if reset_existing:
            (
                SchedulePlace.objects
                .filter(
                    schedule=schedule
                )
                .delete()
            )

        print(
            'Schedule:',
            schedule.s_id,
            schedule.s_day,
            'created:',
            created,
        )

    # =====================================================
    # 2. 컨셉 / 장소 후보
    # =====================================================

    categories = list(
        get_selected_categories(
            travel
        )
    )

    if not categories:
        print('선택된 카테고리가 없습니다.')
        return schedules

    (
        activity_candidates,
        meal_candidates,
    ) = build_place_candidates(
        travel,
        categories,
    )

    # =====================================================
    # 3. TravelDayPlan 해석
    # =====================================================

    day_plan_map = get_travel_day_plans(
        travel
    )

    effective_accommodations = (
        resolve_effective_accommodations(
            travel,
            travel_dates,
            day_plan_map,
        )
    )

    first_start_candidate = (
        get_first_day_start_candidate(
            travel
        )
    )

    # 대중교통 여행이면 가는 길·돌아오는 길에 실제 열차·비행기 시간표를 씀 (🟩 11/11)
    is_public_transport_trip = (
        normalize_planning_transport(travel.t_way) == 'public_transport'
    )

    used_places = set()

    # 비 오는 날 (예보 16일 안 · 지난 날 실제 날씨). 그날은 실내 후보를 더해서 실내 먼저
    rainy_dates = rainy_trip_dates(
        travel
    )
    rainy_candidates = (
        activity_candidates + indoor_candidates(travel)
        if rainy_dates
        else activity_candidates
    )
    print('비 오는 날:', sorted(rainy_dates))

    # =====================================================
    # 4. DAY별 일정
    # =====================================================

    for day_index, schedule in enumerate(
        schedules
    ):

        travel_date = schedule.s_day

        start_time = get_day_start_time(
            travel,
            travel_date,
            day_index,
            day_plan_map,
        )

        current_datetime = datetime.combine(
            travel_date,
            start_time,
        )

        # ---------------------------------------------
        # DAY 시작점
        # ---------------------------------------------

        if day_index == 0:

            current_point = (
                get_candidate_coordinate(
                    first_start_candidate
                )
                if first_start_candidate
                else get_start_point(
                    travel
                )
            )

        else:

            previous_date = (
                travel_dates[
                    day_index - 1
                ]
            )

            previous_accommodation = (
                effective_accommodations.get(
                    previous_date
                )
            )

            current_point = (
                get_candidate_coordinate(
                    previous_accommodation
                )
                if previous_accommodation
                else None
            )

        # ---------------------------------------------
        # 해당 DAY 종료 숙소
        #
        # 마지막 날은 기본적으로 숙박 일정이 없다.
        # ---------------------------------------------

        is_last_day = (
            day_index
            ==
            len(schedules) - 1
        )

        accommodation = None
        accommodation_point = None
        accommodation_datetime = None

        if not is_last_day:

            accommodation = (
                effective_accommodations.get(
                    travel_date
                )
            )

            if accommodation:

                accommodation_point = (
                    get_candidate_coordinate(
                        accommodation
                    )
                )

                accommodation_datetime = (
                    datetime.combine(
                        travel_date,
                        get_day_accommodation_arrival_time(
                            travel_date,
                            day_plan_map,
                        ),
                    )
                )

        # ---------------------------------------------
        # 가는 길 실제 시간표 (🟩 11/11)
        # 대중교통 여행이고 집 → 첫날 숙소가 멀면(80km~) 그날 실제 열차·비행기 편을 찾아
        # 도착역(공항)에서 내린 시각부터 일정을 시작한다. 편이 없으면 지금처럼 예상 시간
        # ---------------------------------------------
        if (
            day_index == 0
            and is_public_transport_trip
            and current_point is not None
            and accommodation_point is not None
        ):
            go_trip = go_trip_for(
                travel,
                travel_date,
                after=current_datetime.time(),
            )

            if go_trip:
                arrive = datetime.strptime(go_trip['arrive'], '%H:%M').time()
                current_datetime = datetime.combine(travel_date, arrive) + timedelta(
                    minutes=go_trip['exit_min']
                )
                current_point = (go_trip['to']['lat'], go_trip['to']['lon'])
                print('가는 길:', go_trip['label'], go_trip['name'], go_trip['depart'], '→', go_trip['to']['name'], go_trip['arrive'])

        # ---------------------------------------------
        # 체크인하고 다시 나가기 (🟩 11/11)
        # 출발 → 관광 → 체크인(짐 두기) → 관광·식사 → 숙소로 귀가
        # 체크인 시각은 막지 않음 (11/05 결정, 체크인 전 짐 맡기기)
        # ---------------------------------------------
        checkin_datetime = None

        if accommodation and accommodation_point is not None:

            checkin_time = get_day_checkin_time(
                travel_date,
                day_plan_map,
            )

            if checkin_time:

                checkin_datetime = datetime.combine(
                    travel_date,
                    checkin_time,
                )

                plan = day_plan_map.get(travel_date)

                # 귀가 시각을 안 정했으면 저녁까지 먹고 21:30
                if not normalize_time(getattr(plan, 'arrival_time', None)):

                    accommodation_datetime = datetime.combine(
                        travel_date,
                        CHECKIN_RETURN_DEFAULT,
                    )

                # 출발 전이거나 귀가보다 늦은 체크인은 무시 (지금처럼 숙소 도착 = 하루 끝)
                if not (
                    current_datetime
                    < checkin_datetime
                    < accommodation_datetime
                ):

                    checkin_datetime = None

        # ---------------------------------------------
        # 마지막 DAY은 사용자가 지정한 RETURN_TIME까지
        # 최초 출발지로 돌아갈 수 있어야 한다.
        # ---------------------------------------------
        return_point = None
        return_datetime = None

        if is_last_day:
            return_point = get_start_point(
                travel
            )

            return_time = (
                normalize_time(
                    getattr(
                        travel,
                        'return_time',
                        None,
                    )
                )
                or time(22, 0)
            )

            if return_point is not None:
                return_datetime = (
                    datetime.combine(
                        travel_date,
                        return_time,
                    )
                )

            # 돌아오는 길 실제 시간표 (🟩 11/11): 귀가 시각까지 집에 닿는 제일 늦은 편을 찾아
            # 그 역(공항)에 탈 시각까지 가 있으면 되게 한다 (마감 장소·시각을 역으로 바꿈)
            if (
                is_public_transport_trip
                and return_point is not None
                and return_datetime is not None
                and current_point is not None
            ):
                back_trip = last_trip(
                    current_point[0], current_point[1],
                    return_point[0], return_point[1],
                    travel_date,
                    arrive_by=return_time,
                )

                if back_trip:
                    return_point = (back_trip['from']['lat'], back_trip['from']['lon'])
                    return_datetime = datetime.combine(
                        travel_date,
                        datetime.strptime(back_trip['board_by'], '%H:%M').time(),
                    )
                    print('돌아오는 길:', back_trip['label'], back_trip['name'], back_trip['from']['name'], back_trip['depart'], '→', back_trip['arrive'])

        deadline_point = (
            accommodation_point
            if accommodation_point is not None
            else return_point
        )

        deadline_datetime = (
            accommodation_datetime
            if accommodation_datetime is not None
            else return_datetime
        )

        day_end_datetime = (
            deadline_datetime
            or datetime.combine(
                travel_date,
                DAY_END,
            )
        )

        lunch_datetime = datetime.combine(
            travel_date,
            LUNCH_TIME,
        )

        dinner_datetime = datetime.combine(
            travel_date,
            DINNER_TIME,
        )

        visit_order = 1
        activity_count = 0

        rainy = travel_date in rainy_dates
        day_candidates = (
            rainy_candidates
            if rainy
            else activity_candidates
        )

        print()
        print(
            f'DAY {day_index + 1}',
            travel_date,
            '출발:',
            start_time,
            '숙소:',
            accommodation.get('name')
            if accommodation
            else None,
            '숙소도착:',
            accommodation_datetime.time()
            if accommodation_datetime
            else None,
        )

        # 한 DAY 동안 바뀌는 값 (아래 도우미 함수들이 같이 고침)
        day = {
            'datetime': current_datetime,
            'point': current_point,
            'visit_order': visit_order,
            'activity_count': activity_count,
            'checkin_pending': checkin_datetime is not None,
        }

        # 체크인하고 나가는 날은 관광 한 곳 더 (저녁 시간이 생겨서)
        max_activity = (
            MAX_ACTIVITY_PER_DAY + 1
            if checkin_datetime
            else MAX_ACTIVITY_PER_DAY
        )

        def fill(limit, reach):
            (
                day['datetime'],
                day['point'],
                day['visit_order'],
                day['activity_count'],
            ) = fill_activities(
                travel,
                schedule,
                day_candidates,
                used_places,
                day['datetime'],
                day['point'],
                day['visit_order'],
                day['activity_count'],
                limit,
                travel.t_way,
                max_activity,
                reach_point=reach,
                rainy=rainy,
            )

        def do_checkin():
            """숙소에 들러 짐 두기 (그 시각보다 일찍 오면 기다림). 귀가 줄과 같은 숙소 Place를 씀"""
            (
                day['datetime'],
                day['point'],
                day['visit_order'],
            ) = add_checkin(
                travel,
                schedule,
                accommodation,
                day['datetime'],
                day['point'],
                day['visit_order'],
                travel.t_way,
                checkin_datetime,
            )
            day['checkin_pending'] = False

        def fill_until(limit, reach):
            """limit 까지 관광을 채운다. 그 안에 체크인 시각이 있으면 체크인까지 채우고, 체크인하고, 나머지를 채운다"""
            if day['checkin_pending'] and checkin_datetime <= limit:
                fill(checkin_datetime, accommodation_point)
                do_checkin()

            fill(limit, reach)

        def meal(target):
            """점심·저녁. 식사 뒤 갈 곳(체크인 전이면 숙소 체크인, 아니면 숙소 귀가·집)까지 갈 수 있는 음식점만"""
            if day['checkin_pending']:
                fixed_datetime, fixed_point = checkin_datetime, accommodation_point
            else:
                fixed_datetime, fixed_point = deadline_datetime, deadline_point

            (
                day['datetime'],
                day['point'],
                day['visit_order'],
            ) = add_meal_before_deadline(
                travel,
                schedule,
                meal_candidates,
                used_places,
                day['datetime'],
                day['point'],
                day['visit_order'],
                travel.t_way,
                target,
                fixed_datetime=fixed_datetime,
                fixed_point=fixed_point,
            )

        # =================================================
        # 오전 관광
        # =================================================

        morning_limit = min(
            lunch_datetime,
            day_end_datetime,
        )

        fill_until(
            morning_limit,
            deadline_point
            if morning_limit == day_end_datetime
            else None,
        )

        # =================================================
        # 점심
        # =================================================

        if (
            lunch_datetime
            <
            day_end_datetime
            and day['datetime'].time()
            <
            time(15, 0)
        ):
            before = day['visit_order']
            meal(lunch_datetime)

            # 체크인이 점심 바로 뒤라 점심이 안 들어갔으면 → 체크인부터 하고 점심
            if (
                day['visit_order'] == before
                and day['checkin_pending']
                and checkin_datetime.time() < time(15, 0)
            ):
                do_checkin()
                meal(lunch_datetime)

        # =================================================
        # 오후 관광
        # =================================================

        afternoon_limit = min(
            dinner_datetime,
            day_end_datetime,
        )

        fill_until(
            afternoon_limit,
            deadline_point
            if afternoon_limit == day_end_datetime
            else None,
        )

        # =================================================
        # 저녁
        # =================================================

        if (
            dinner_datetime
            <
            day_end_datetime
            and day['datetime'].time()
            <
            time(21, 0)
        ):
            # 저녁 시각보다 체크인이 먼저면 체크인부터
            if day['checkin_pending'] and checkin_datetime <= dinner_datetime:
                do_checkin()

            meal(dinner_datetime)

        # =================================================
        # 저녁 이후 / 숙소 전 남는 시간
        # =================================================

        fill_until(
            day_end_datetime,
            deadline_point,
        )

        # 그래도 체크인을 못 했으면(장소가 없던 날) 귀가 전에 체크인
        if day['checkin_pending']:
            do_checkin()

        # =================================================
        # 해당 DAY 숙소 도착 (체크인한 날은 '귀가' 줄, 같은 숙소 Place)
        # =================================================

        if (
            accommodation
            and accommodation_datetime
        ):

            (
                day['datetime'],
                day['point'],
                day['visit_order'],
            ) = add_accommodation_arrival(
                travel,
                schedule,
                accommodation,
                day['datetime'],
                day['point'],
                day['visit_order'],
                travel.t_way,
                accommodation_datetime,
            )

    print()
    print('날짜별 자동 일정 생성 완료')
    print('=================================')

    return schedules
