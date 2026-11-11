"""가는 길·돌아오는 길 실제 시간표: 열차 · 국내항공 · 연안여객선 — 🟩 (TEAM_UPDATES 11/11 📐 공유 정의)

- 열차: 국토부 TAGO 열차정보 `GetStrtpntAlocFndTrainInfo` (편명·출발·도착·어른 1인 운임)
- 항공: 국토부 TAGO 국내항공운항정보 `GetFlightOpratInfoList` (편명·출발·도착·일반석 1인 운임)
- 배: 해양교통안전공단 운항 스케줄 `get-oprt-schd-info-v2` (출항 시각만, 도착·운임 없음 · 오늘·내일 것만 나옴)
- 키는 지금 쓰는 TOUR_API_KEY 하나 (공공데이터포털 같은 키)
- 역·공항·항구 좌표는 아래 표 (API에 좌표가 없어서), 같은 날 같은 구간은 6시간 캐시

함수
    find_trips(from_lat, from_lon, to_lat, to_lon, date, after=None, people=1, limit=3) → dict
    {
      'date': '2026-11-12', 'people': 2, 'distance_km': 325,
      'modes': [                               # 편이 있는 것만, 도착지에 제일 빨리 닿는 순 (reach)
        {'mode': 'train', 'label': '열차',
         'from': {'name': '서울역', 'lat': 37.5541, 'lon': 126.9707, 'access_min': 35},
         'to':   {'name': '부산역', 'lat': 35.1152, 'lon': 129.0415, 'access_min': 30},
         'reach': '08:30',                     # 첫 편으로 도착지(숙소 등)에 닿는 예상 시각 (배는 None)
         'trips': [{'name': 'KTX 001', 'depart': '05:13', 'arrive': '07:50', 'minutes': 157,
                    'per': 54400, 'total': 108800}, ...]},
        ...
      ],
    }
    first_trip(같은 값) → 시간 안에 탈 수 있는 편 중 제일 빨리 도착하는 편 하나 (위 trips 한 줄 + 'mode','label','from','to','reach','exit_min') 또는 None
    last_trip(from_lat, from_lon, to_lat, to_lon, date, arrive_by='22:00', people=1)
        → 돌아오는 길: arrive_by까지 집에 닿는 편 중 제일 늦게 떠나는 편 (first_trip 모양 + 'board_by') 또는 None
    fare_options(from_lat, from_lon, to_lat, to_lon, date, people) → move_fares 'options' 모양 목록 (mode: train|air|ferry)
"""
import logging
import math
from datetime import date as date_type, datetime, timedelta

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TRAIN_URL = 'https://apis.data.go.kr/1613000/TrainInfo/GetStrtpntAlocFndTrainInfo'
AIR_URL = 'https://apis.data.go.kr/1613000/DmstcFlightNvgInfo/GetFlightOpratInfoList'
FERRY_URL = 'https://apis.data.go.kr/B554035/oprt-schd-info-v2/get-oprt-schd-info-v2'

CACHE_SECONDS = 60 * 60 * 6
TIMEOUT = 10
MIN_DISTANCE_KM = 80          # 이보다 가까우면 장거리 시간표를 안 봄 (카카오 대중교통으로 충분)
HUB_COUNT = 2                 # 출발·도착 쪽마다 가까운 역(공항) 몇 곳 + 반경 안 큰 역
# 장거리 열차가 많이 서는 큰 역 (가까운 작은 역보다 편이 많아서 반경 안이면 꼭 같이 봄)
MAJOR_STATIONS = {'서울', '용산', '광명', '수원', '청량리', '천안아산', '오송', '대전', '동대구', '경주', '포항',
                  '울산', '부산', '마산', '진주', '익산', '전주', '광주송정', '목포', '순천', '여수EXPO',
                  '강릉', '원주', '안동', '춘천'}
HUB_RADIUS_KM = {'train': 30, 'air': 60, 'ferry': 30}
BEFORE_MIN = {'train': 15, 'air': 60, 'ferry': 30}   # 타기 전 미리 가 있을 시간 (공항은 수속)
EXIT_MIN = {'train': 10, 'air': 20, 'ferry': 15}     # 내려서 나오는 시간

LABELS = {'train': '열차', 'air': '항공', 'ferry': '배'}

# (이름, 역 코드, 위도, 경도) — TAGO 역 코드 + 카카오 좌표 (11/11)
STATIONS = [
    ('서울', 'NAT010000', 37.5541, 126.9707), ('용산', 'NAT010032', 37.5301, 126.9648),
    ('영등포', 'NAT010091', 37.5157, 126.9079), ('광명', 'NATH10219', 37.4162, 126.8847),
    ('수원', 'NAT010415', 37.2658, 127.0001), ('청량리', 'NAT130126', 37.5800, 127.0477),
    ('상봉', 'NAT020040', 37.5969, 127.0857), ('천안아산', 'NATH10960', 36.7943, 127.1044),
    ('천안', 'NAT010971', 36.8091, 127.1468), ('오송', 'NAT050044', 36.6201, 127.3276),
    ('조치원', 'NAT011298', 36.6011, 127.2963), ('대전', 'NAT011668', 36.3323, 127.4346),
    ('서대전', 'NAT030057', 36.3225, 127.4033), ('김천구미', 'NATH12383', 36.1135, 128.1810),
    ('구미', 'NAT012775', 36.1283, 128.3310), ('동대구', 'NAT013271', 35.8793, 128.6284),
    ('대구', 'NAT013239', 35.8762, 128.5958), ('서대구', 'NAT013189', 35.8813, 128.5400),
    ('경주', 'NATH13421', 35.7984, 129.1390), ('포항', 'NAT8B0351', 36.0716, 129.3419),
    ('울산', 'NATH13717', 35.5514, 129.1386), ('태화강', 'NAT750726', 35.5388, 129.3533),
    ('부산', 'NAT014445', 35.1152, 129.0415), ('구포', 'NAT014281', 35.2055, 128.9971),
    ('부전', 'NAT750046', 35.1647, 129.0601), ('센텀', 'NAT750161', 35.1793, 129.1246),
    ('신해운대', 'NAT750189', 35.1816, 129.1771), ('기장', 'NAT750329', 35.2439, 129.2186),
    ('밀양', 'NAT013841', 35.4745, 128.7712), ('창원중앙', 'NAT880281', 35.2424, 128.7013),
    ('창원', 'NAT880310', 35.2575, 128.6066), ('마산', 'NAT880345', 35.2361, 128.5770),
    ('진주', 'NAT881014', 35.1507, 128.1179), ('익산', 'NAT030879', 35.9405, 126.9457),
    ('전주', 'NAT040257', 35.8499, 127.1618), ('정읍', 'NAT031314', 35.5755, 126.8422),
    ('광주송정', 'NAT031857', 35.1377, 126.7908), ('광주', 'NAT883012', 35.1653, 126.9093),
    ('나주', 'NAT031998', 35.0141, 126.7172), ('목포', 'NAT032563', 34.7911, 126.3866),
    ('순천', 'NAT041595', 34.9458, 127.5031), ('여천', 'NAT041866', 34.7791, 127.6642),
    ('여수EXPO', 'NAT041993', 34.7531, 127.7486), ('남원', 'NAT040868', 35.4112, 127.3614),
    ('곡성', 'NAT041072', 35.2836, 127.3037), ('보성', 'NAT882328', 34.7670, 127.0816),
    ('강릉', 'NAT601936', 37.7645, 128.8996), ('정동진', 'NAT601774', 37.6914, 129.0327),
    ('동해', 'NAT601485', 37.4982, 129.1238), ('삼척', 'NAT630129', 37.4301, 129.1787),
    ('평창', 'NATN10625', 37.5624, 128.4297), ('진부', 'NATN10787', 37.6427, 128.5745),
    ('원주', 'NAT020947', 37.3159, 127.9219), ('만종', 'NAT021033', 37.3537, 127.8930),
    ('제천', 'NAT021549', 37.1279, 128.2055), ('단양', 'NAT021784', 36.9732, 128.3437),
    ('영주', 'NAT022188', 36.8111, 128.6250), ('안동', 'NAT022558', 36.5745, 128.6749),
    ('춘천', 'NAT140873', 37.8845, 127.7167), ('남춘천', 'NAT140840', 37.8641, 127.7238),
    ('공주', 'NATH20438', 36.3325, 127.0968), ('논산', 'NAT030508', 36.2073, 127.0925),
    ('군산', 'NAT081388', 35.9993, 126.7598), ('김제', 'NAT031056', 35.7925, 126.9030),
    ('홍성', 'NAT080622', 36.5994, 126.6805), ('온양온천', 'NAT080147', 36.7805, 127.0032),
    ('점촌', 'NAT300600', 36.5955, 128.2034), ('영천', 'NAT023449', 35.9595, 128.9392),
    ('하양', 'NAT830200', 35.9099, 128.8182),
]

# (이름, 공항 코드, 위도, 경도) — TAGO GetArprtList 15곳
AIRPORTS = [
    ('김포공항', 'NAARKSS', 37.5583, 126.7906), ('인천공항', 'NAARKSI', 37.4602, 126.4407),
    ('제주공항', 'NAARKPC', 33.5070, 126.4929), ('김해공항', 'NAARKPK', 35.1795, 128.9382),
    ('대구공항', 'NAARKTN', 35.8941, 128.6588), ('청주공항', 'NAARKTU', 36.7166, 127.4991),
    ('광주공항', 'NAARKJJ', 35.1264, 126.8089), ('무안공항', 'NAARKJB', 34.9914, 126.3828),
    ('여수공항', 'NAARKJY', 34.8424, 127.6161), ('울산공항', 'NAARKPU', 35.5935, 129.3518),
    ('포항경주공항', 'NAARKTH', 35.9879, 129.4204), ('사천공항', 'NAARKPS', 35.0886, 128.0703),
    ('양양공항', 'NAARKNY', 38.0613, 128.6692), ('군산공항', 'NAARKJK', 35.9038, 126.6158),
    ('원주공항', 'NAARKNW', 37.4381, 127.9604),
]

# (운항 스케줄의 항구 이름, 위도, 경도) — 섬으로 가는 큰 항로만
PORTS = [
    ('제주', 33.5200, 126.5430), ('목포', 34.7810, 126.3870), ('완도', 34.3150, 126.7570),
    ('진도', 34.3770, 126.3080), ('녹동', 34.5260, 127.1430), ('여수', 34.7400, 127.7480),
    ('삼천포', 34.9260, 128.0700), ('인천', 37.4630, 126.6000), ('백령', 37.9670, 124.7180),
    ('강릉', 37.7710, 128.9480), ('묵호', 37.5500, 129.1170), ('포항', 36.0360, 129.3720),
    ('영일만신항', 36.0880, 129.4310), ('울릉', 37.4840, 130.9060), ('울릉(사동)', 37.4640, 130.8880),
    ('울릉(도동)', 37.4840, 130.9060), ('울릉(저동)', 37.4980, 130.9130), ('통영', 34.8420, 128.4230),
]


# ---------------------------------------------------------
# 작은 도우미
# ---------------------------------------------------------

def _km(lat1, lon1, lat2, lon2):
    """두 좌표 사이 직선 거리(km)"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _access_minutes(km):
    """역·공항까지 이동 예상(분): 처음 10km는 시속 24km(시내), 그 뒤는 시속 45km(버스·전철 급행) + 10분"""
    road = km * 1.18
    near = min(road, 10)
    return int(math.ceil(near / 24 * 60 + max(road - 10, 0) / 45 * 60)) + 10


def _nearby(hubs, lat, lon, radius):
    """가까운 순 [(거리 km, 허브)] — 반경 안 가까운 HUB_COUNT 곳 + 반경 안 큰 역 (최대 4곳)"""
    found = [(d, h) for d, h in sorted((_km(lat, lon, h[-2], h[-1]), h) for h in hubs) if d <= radius]
    picked = found[:HUB_COUNT] + [(d, h) for d, h in found[HUB_COUNT:] if h[0] in MAJOR_STATIONS]
    return picked[:4]


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date_type):
        return value
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _hm(minutes):
    return '%02d:%02d' % divmod(int(minutes) % (24 * 60), 60)


def _clock_min(text):
    """'202611120705' · '20261112070500' · '705' → 하루 안 분(425). 못 읽으면 None"""
    digits = ''.join(ch for ch in str(text or '') if ch.isdigit())
    if len(digits) >= 12:
        digits = digits[8:12]
    if not 3 <= len(digits) <= 4:
        return None
    hour, minute = int(digits[:-2]), int(digits[-2:])
    return hour * 60 + minute if hour < 24 and minute < 60 else None


def _items(response_json):
    """공공데이터 응답 → item 목록 (한 개면 dict로 와서 목록으로 바꿈)"""
    try:
        items = response_json['response']['body']['items']
    except (KeyError, TypeError):
        return []
    items = (items or {}).get('item', []) if isinstance(items, dict) else []
    return [items] if isinstance(items, dict) else list(items or [])


def _get(url, cache_key, params):
    """공공데이터 호출 + 6시간 캐시. 실패하면 [] (실패는 캐시 안 함)"""
    saved = cache.get(cache_key)
    if saved is not None:
        return saved
    key = getattr(settings, 'TOUR_API_KEY', '')
    if not key:
        return []
    try:
        response = requests.get(url, params={'serviceKey': key, 'pageNo': 1, **params}, timeout=TIMEOUT)
        response.raise_for_status()
        items = _items(response.json())
    except (requests.RequestException, ValueError):
        logger.warning('시간표 호출 실패 %s', cache_key, exc_info=True)
        return []
    cache.set(cache_key, items, CACHE_SECONDS)
    return items


# ---------------------------------------------------------
# 수단별 그날 편
# ---------------------------------------------------------

def _train_trips(dep, arr, day):
    items = _get(TRAIN_URL, 'tt_train:v1:%s:%s:%s' % (dep[1], arr[1], day.strftime('%Y%m%d')), {
        '_type': 'json', 'numOfRows': 300,
        'depPlaceId': dep[1], 'arrPlaceId': arr[1], 'depPlandTime': day.strftime('%Y%m%d'),
    })
    trips = []
    for it in items:
        start, end = _clock_min(it.get('depplandtime')), _clock_min(it.get('arrplandtime'))
        if start is None or end is None:
            continue
        per = int(it.get('adultcharge') or 0) or None
        number = str(it.get('trainno') or '').lstrip('0') or '-'
        trips.append({'name': '%s %s' % (it.get('traingradename') or '열차', number),
                      'start': start, 'end': end if end >= start else end + 24 * 60, 'per': per})
    return trips


def _air_trips(dep, arr, day):
    items = _get(AIR_URL, 'tt_air:v1:%s:%s:%s' % (dep[1], arr[1], day.strftime('%Y%m%d')), {
        '_type': 'json', 'numOfRows': 300,
        'depAirportId': dep[1], 'arrAirportId': arr[1], 'depPlandTime': day.strftime('%Y%m%d'),
    })
    trips = []
    for it in items:
        start, end = _clock_min(it.get('depPlandTime')), _clock_min(it.get('arrPlandTime'))
        if start is None or end is None:
            continue
        per = int(it.get('economyCharge') or 0) or None
        trips.append({'name': '%s %s' % (it.get('airlineNm') or '항공', it.get('vihicleId') or ''),
                      'start': start, 'end': end if end >= start else end + 24 * 60, 'per': per})
    return trips


def _ferry_trips(dep, arr, day):
    """배는 그날 전체(700여 편)를 한 번 받아 항구 이름으로 고름. 도착·운임은 없음"""
    items = _get(FERRY_URL, 'tt_ferry:v1:%s' % day.strftime('%Y%m%d'), {
        'dataType': 'JSON', 'numOfRows': 1500, 'rlvtYmd': day.strftime('%Y%m%d'),
    })
    trips = []
    for it in items:
        if it.get('oport_nm') != dep[0] or it.get('dest_nm') != arr[0]:
            continue
        start = _clock_min(it.get('sail_tm'))
        if start is None or it.get('nvg_se_cd') not in (None, '1'):   # 1 = 정상 운항
            continue
        trips.append({'name': it.get('psnshp_nm') or '여객선', 'start': start, 'end': None, 'per': None})
    return trips


MODES = [
    ('train', STATIONS, _train_trips),
    ('air', AIRPORTS, _air_trips),
    ('ferry', [(name, name, lat, lon) for name, lat, lon in PORTS], _ferry_trips),
]


def _hub_name(mode, hub):
    return hub[0] + '역' if mode == 'train' else hub[0] + ('항' if mode == 'ferry' else '')


# ---------------------------------------------------------
# 공유 함수
# ---------------------------------------------------------

def find_trips(from_lat, from_lon, to_lat, to_lon, date, after=None, people=1, limit=3):
    """출발지 → 도착지 그날 열차·항공·배 편. after('09:00' 또는 time)가 있으면 그때 집에서 나가서 탈 수 있는 편만"""
    day = _as_date(date)
    people = max(int(people or 1), 1)
    try:
        a = (float(from_lat), float(from_lon))
        b = (float(to_lat), float(to_lon))
    except (TypeError, ValueError):
        return {'date': None, 'people': people, 'distance_km': None, 'modes': []}

    distance = _km(a[0], a[1], b[0], b[1])
    result = {'date': day.isoformat() if day else None, 'people': people,
              'distance_km': round(distance), 'modes': []}
    if day is None or distance < MIN_DISTANCE_KM:
        return result

    leave = _clock_min(after.strftime('%H%M') if hasattr(after, 'strftime') else str(after or '').replace(':', ''))

    for mode, hubs, fetch in MODES:
        best = None
        for d1, dep in _nearby(hubs, a[0], a[1], HUB_RADIUS_KM[mode]):
            for d2, arr in _nearby(hubs, b[0], b[1], HUB_RADIUS_KM[mode]):
                if dep[1] == arr[1]:
                    continue
                access = _access_minutes(d1)
                ready = None if leave is None else leave + access + BEFORE_MIN[mode]
                trips = [t for t in fetch(dep, arr, day) if ready is None or t['start'] >= ready]
                if not trips:
                    continue
                # 도착이 빠른 순 (배는 도착을 몰라서 출발 순)
                trips.sort(key=lambda t: (t['end'] if t['end'] is not None else t['start'] + 24 * 60, t['start']))
                # 역마다 도착지까지 가는 시간이 달라서, 그 역 첫 편으로 "도착지에 닿는 시각"이 빠른 쪽을 고름
                score = (trips[0]['end'] if trips[0]['end'] is not None else 10 ** 6) + EXIT_MIN[mode] + _access_minutes(d2)
                if best is None or score < best[0]:
                    best = (score, dep, arr, access, _access_minutes(d2), trips)
        if not best:
            continue
        score, dep, arr, access, onward, trips = best
        result['modes'].append({
            'mode': mode, 'label': LABELS[mode],
            'from': {'name': _hub_name(mode, dep), 'lat': dep[-2], 'lon': dep[-1], 'access_min': access},
            'to': {'name': _hub_name(mode, arr), 'lat': arr[-2], 'lon': arr[-1], 'access_min': onward},
            'reach': _hm(score) if score < 10 ** 6 else None,
            'trips': [{
                'name': t['name'],
                'depart': _hm(t['start']),
                'arrive': _hm(t['end']) if t['end'] is not None else None,
                'minutes': (t['end'] - t['start']) if t['end'] is not None else None,
                'per': t['per'],
                'total': t['per'] * people if t['per'] else None,
            } for t in trips[:limit]],
        })

    result['modes'].sort(key=lambda m: m['reach'] or '99:99')
    return result


def first_trip(from_lat, from_lon, to_lat, to_lon, date, after=None, people=1):
    """탈 수 있는 편 중 제일 빨리 도착하는 편 하나 (도착 시각을 아는 열차·항공만). 없으면 None"""
    found = find_trips(from_lat, from_lon, to_lat, to_lon, date, after=after, people=people, limit=1)
    for mode in found['modes']:
        trip = mode['trips'][0]
        if trip['arrive']:
            return {**trip, 'mode': mode['mode'], 'label': mode['label'],
                    'from': mode['from'], 'to': mode['to'], 'reach': mode['reach'], 'exit_min': EXIT_MIN[mode['mode']]}
    return None


def last_trip(from_lat, from_lon, to_lat, to_lon, date, arrive_by=None, people=1):
    """돌아오는 길: arrive_by('22:00')까지 집(to)에 닿는 편 중 제일 늦게 떠나는 편 하나. 없으면 None
    → 같은 모양 + 'board_by': 그 역(공항)에 가 있어야 하는 시각"""
    limit = _clock_min(arrive_by.strftime('%H%M') if hasattr(arrive_by, 'strftime')
                       else str(arrive_by or '22:00').replace(':', ''))
    found = find_trips(from_lat, from_lon, to_lat, to_lon, date, people=people, limit=300)
    best = None
    for mode in found['modes']:
        onward = EXIT_MIN[mode['mode']] + mode['to']['access_min']
        for trip in mode['trips']:
            if not trip['arrive']:
                continue
            start = _clock_min(trip['depart'].replace(':', ''))
            end = start + trip['minutes']
            if limit is not None and end + onward > limit:
                continue
            board = start - BEFORE_MIN[mode['mode']]
            if best is None or board > best[0]:
                best = (board, {**trip, 'mode': mode['mode'], 'label': mode['label'], 'from': mode['from'],
                                'to': mode['to'], 'reach': _hm(end + onward), 'board_by': _hm(board)})
    return best[1] if best else None


def fare_options(from_lat, from_lon, to_lat, to_lon, date, people=1):
    """fare_service.move_fares 'options'에 붙일 모양: 수단마다 그날 제일 싼 편 하나"""
    found = find_trips(from_lat, from_lon, to_lat, to_lon, date, people=people, limit=300)
    options = []
    for mode in found['modes']:
        priced = [t for t in mode['trips'] if t['per']]
        if not priced:
            continue
        cheap = min(priced, key=lambda t: t['per'])
        options.append({
            'mode': mode['mode'], 'label': mode['label'], 'total': cheap['total'], 'per': cheap['per'],
            'note': '%s %s %s→%s · 1인 %s원 × %d명' % (
                mode['from']['name'], cheap['name'], cheap['depart'], cheap['arrive'] or '?',
                format(cheap['per'], ','), found['people']),
        })
    return options
