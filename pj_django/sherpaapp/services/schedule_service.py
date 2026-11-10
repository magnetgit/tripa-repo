from datetime import datetime, timedelta, time
import math

from ..models import (
    Category,
    Place,
    Schedule,
    SchedulePlace,
    TravelDayPlan,
)

from .place_service import search_places
from .hours_service import fit_stay, hhmm, place_hours
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
            stay = get_stay_time(
                candidate.get('selected_category') or '기타'
            )

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
        get_stay_time(
            category_name
        )
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
            get_stay_time(
                category_name
            )
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
    reach_point=None
):

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
                get_stay_time(

                    candidate.get(
                        'selected_category'
                    )
                    or
                    '기타'
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
            30
    )



# =========================================================
# 날짜별 숙소 / 시작점 일반화
# =========================================================

DEFAULT_ACCOMMODATION_ARRIVAL = time(20, 0)


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

    used_places = set()

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

        # =================================================
        # 오전 관광
        # =================================================

        morning_limit = min(
            lunch_datetime,
            day_end_datetime,
        )

        (
            current_datetime,
            current_point,
            visit_order,
            activity_count,
        ) = fill_activities(
            travel,
            schedule,
            activity_candidates,
            used_places,
            current_datetime,
            current_point,
            visit_order,
            activity_count,
            morning_limit,
            travel.t_way,
            MAX_ACTIVITY_PER_DAY,
            reach_point=(
                deadline_point
                if morning_limit == day_end_datetime
                else None
            ),
        )

        # =================================================
        # 점심
        # =================================================

        if (
            lunch_datetime
            <
            day_end_datetime
            and current_datetime.time()
            <
            time(15, 0)
        ):

            (
                current_datetime,
                current_point,
                visit_order,
            ) = add_meal_before_deadline(
                travel,
                schedule,
                meal_candidates,
                used_places,
                current_datetime,
                current_point,
                visit_order,
                travel.t_way,
                lunch_datetime,
                fixed_datetime=(
                    deadline_datetime
                ),
                fixed_point=(
                    deadline_point
                ),
            )

        # =================================================
        # 오후 관광
        # =================================================

        afternoon_limit = min(
            dinner_datetime,
            day_end_datetime,
        )

        (
            current_datetime,
            current_point,
            visit_order,
            activity_count,
        ) = fill_activities(
            travel,
            schedule,
            activity_candidates,
            used_places,
            current_datetime,
            current_point,
            visit_order,
            activity_count,
            afternoon_limit,
            travel.t_way,
            MAX_ACTIVITY_PER_DAY,
            reach_point=(
                deadline_point
                if afternoon_limit == day_end_datetime
                else None
            ),
        )

        # =================================================
        # 저녁
        # =================================================

        if (
            dinner_datetime
            <
            day_end_datetime
            and current_datetime.time()
            <
            time(21, 0)
        ):

            (
                current_datetime,
                current_point,
                visit_order,
            ) = add_meal_before_deadline(
                travel,
                schedule,
                meal_candidates,
                used_places,
                current_datetime,
                current_point,
                visit_order,
                travel.t_way,
                dinner_datetime,
                fixed_datetime=(
                    deadline_datetime
                ),
                fixed_point=(
                    deadline_point
                ),
            )

        # =================================================
        # 저녁 이후 / 숙소 전 남는 시간
        # =================================================

        (
            current_datetime,
            current_point,
            visit_order,
            activity_count,
        ) = fill_activities(
            travel,
            schedule,
            activity_candidates,
            used_places,
            current_datetime,
            current_point,
            visit_order,
            activity_count,
            day_end_datetime,
            travel.t_way,
            MAX_ACTIVITY_PER_DAY,
            reach_point=(
                deadline_point
            ),
        )

        # =================================================
        # 해당 DAY 숙소 도착
        # =================================================

        if (
            accommodation
            and accommodation_datetime
        ):

            (
                current_datetime,
                current_point,
                visit_order,
            ) = add_accommodation_arrival(
                travel,
                schedule,
                accommodation,
                current_datetime,
                current_point,
                visit_order,
                travel.t_way,
                accommodation_datetime,
            )

    print()
    print('날짜별 자동 일정 생성 완료')
    print('=================================')

    return schedules
