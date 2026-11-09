"""장소 사이 대중교통 경로 (카카오 대중교통 길찾기, 서버에서 호출) — 🟦

ODsay(브라우저 호출)를 대신한다 (11/06 결정).
- 카카오 REST 키(KAKAO_REST_API_KEY)를 그대로 쓴다. 키는 브라우저로 나가지 않는다.
- 같은 구간 결과는 캐시에 7일 (키 `transit:위도,경도:위도,경도`, 소수 4자리).
- 700m 이내는 부르지 않고 도보로 본다 (호출 아끼기). 카카오가 경로를 못 찾으면 2km 안은 도보, 더 멀면 None.

함수 (TEAM_UPDATES 11/09 공유 정의)
    transit_route(from_lat, from_lon, to_lat, to_lon) → dict 또는 None(호출 실패)
    {
      'walk': False,              # True 면 걸어가는 구간 (아래 steps 는 빈 목록)
      'minutes': 46,              # 전체 걸리는 시간(분)
      'distance': 15356,          # m
      'fare': 1800,               # 1인 요금(원), 모르면 None
      'transfers': 0,             # 환승 횟수
      'label': '지하철 2호선',      # 탄 것들 (예: '버스 141 → 지하철 2호선')
      'steps': [{'mode': 'subway'|'bus'|'train'|'walk'|'transit',
                 'kind': '지하철', 'line': '2호선', 'name': '지하철 2호선',
                 'from': '서면', 'to': '해운대', 'minutes': 31, 'distance': 14500,
                 'stops': ['서면', ...]}],
      'segments': [{'mode': ..., 'points': [[위도, 경도], ...]}],   # 지도에 그릴 선 (처음·끝 걷는 길 포함)
      'url': 'https://map.kakao.com/link/by/traffic/...',          # 카카오맵 길찾기 링크
    }
"""
import logging
import math

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

API_URL = 'https://dapi.kakao.com/v2/routing/publictraffic'
CACHE_SECONDS = 60 * 60 * 24 * 7
WALK_METERS = 700          # 이 거리 안은 부르지 않고 걷기
WALK_M_PER_MIN = 67        # 걷는 속도 약 4km/h
TIMEOUT = 8
NO_ROUTE = {'none': True}  # 카카오가 경로를 못 찾은 먼 구간 (캐시에 저장하는 표시)

# 카카오 step 종류 → (화면 mode, 기본 이름)
STEP_TYPES = {
    'SUBWAY': ('subway', '지하철'),
    'BUS': ('bus', '버스'),
    'EXPRESSBUS': ('bus', '고속버스'),
    'INTERCITYBUS': ('bus', '시외버스'),
    'TRAIN': ('train', '열차'),
    'AIRPLANE': ('air', '항공'),
    'FERRY': ('transit', '배'),
    'WALKING': ('walk', '도보'),
}


def meters(a, b):
    """두 점 (위도, 경도) 사이 직선 거리(m)"""
    rad = math.pi / 180
    d_lat = (b[0] - a[0]) * rad
    d_lon = (b[1] - a[1]) * rad
    h = math.sin(d_lat / 2) ** 2 + math.cos(a[0] * rad) * math.cos(b[0] * rad) * math.sin(d_lon / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def _key(a, b):
    return 'transit:%.4f,%.4f:%.4f,%.4f' % (a[0], a[1], b[0], b[1])


def _link(a, b):
    return 'https://map.kakao.com/link/by/traffic/출발,%f,%f/도착,%f,%f' % (a[0], a[1], b[0], b[1])


def _walk(a, b, url=''):
    dist = round(meters(a, b) * 1.2)   # 길은 직선보다 조금 돌아감
    return {
        'walk': True,
        'minutes': max(1, math.ceil(dist / WALK_M_PER_MIN)),
        'distance': dist,
        'fare': 0,
        'transfers': 0,
        'label': '도보',
        'steps': [],
        'segments': [{'mode': 'walk', 'points': [list(a), list(b)]}],
        'url': url or _link(a, b),
    }


def _thin(points, gap=12):
    """[[경도, 위도], ...] → [[위도, 경도], ...], 가까운 점(약 gap m)은 빼서 크기를 줄임"""
    out = []
    for p in points or []:
        try:
            pt = [round(float(p[1]), 6), round(float(p[0]), 6)]
        except (TypeError, ValueError, IndexError):
            continue
        if out and meters(out[-1], pt) < gap:
            continue
        out.append(pt)
    if points and out:
        try:
            last = [round(float(points[-1][1]), 6), round(float(points[-1][0]), 6)]
            if out[-1] != last:
                out.append(last)
        except (TypeError, ValueError, IndexError):
            pass
    return out


def _step(step):
    prop = step.get('properties') or {}
    mode, kind = STEP_TYPES.get(prop.get('type'), ('transit', '대중교통'))
    vehicles = [v for v in prop.get('vehicles') or [] if isinstance(v, dict)]
    stops = [s.get('name') for s in prop.get('stops') or [] if isinstance(s, dict) and s.get('name')]

    line = ' / '.join([v.get('name') for v in vehicles if v.get('name')][:3])
    if mode == 'bus' and vehicles and vehicles[0].get('type') and vehicles[0]['type'] != '일반':
        kind = '%s버스' % vehicles[0]['type']   # 간선·지선·급행·좌석 …
    if mode == 'walk':
        name = '도보'
    else:
        name = ('%s %s' % (kind, line)).strip()

    return {
        'mode': mode,
        'kind': kind,
        'line': line,
        'name': name,
        'from': stops[0] if stops else '',
        'to': stops[-1] if len(stops) > 1 else '',
        'minutes': round((prop.get('time') or 0) / 60),
        'distance': prop.get('distance') or 0,
        'stops': stops,
        'guidance': prop.get('guidance') or '',
    }, _thin((step.get('path') or {}).get('points'))


def _parse(data, a, b):
    routes = data.get('routes') or []
    if data.get('status') != 'OK' or not routes:
        return None
    route = routes[0]   # 카카오 추천 순서 첫 번째
    prop = route.get('properties') or {}

    steps, segments = [], []
    last = list(a)
    for raw in route.get('steps') or []:
        step, pts = _step(raw)
        steps.append(step)
        if len(pts) < 2:
            continue
        if step['mode'] != 'walk' and meters(last, pts[0]) > 15:
            segments.append({'mode': 'walk', 'points': [last, pts[0]]})   # 정류장까지 걷는 길
        segments.append({'mode': step['mode'], 'points': pts})
        last = pts[-1]
    if meters(last, list(b)) > 15:
        segments.append({'mode': 'walk', 'points': [last, list(b)]})

    rides = [s['name'] for s in steps if s['mode'] != 'walk']
    fare = (prop.get('fare') or {}).get('value')
    return {
        'walk': False,
        'minutes': round((prop.get('totalTime') or 0) / 60),
        'distance': prop.get('totalDistance') or 0,
        'fare': fare if isinstance(fare, int) else None,
        'transfers': prop.get('transfers') or 0,
        'label': ' → '.join(rides) or '대중교통',
        'steps': steps,
        'segments': segments,
        'url': ((data.get('properties') or {}).get('landingURL')) or _link(a, b),
    }


def transit_route(from_lat, from_lon, to_lat, to_lon):
    """두 장소 사이 대중교통 경로 (위 설명의 dict). 키가 없거나 호출이 실패하면 None"""
    try:
        a = (float(from_lat), float(from_lon))
        b = (float(to_lat), float(to_lon))
    except (TypeError, ValueError):
        return None

    if meters(a, b) <= WALK_METERS:
        return _walk(a, b)

    key = _key(a, b)
    saved = cache.get(key)
    if saved:
        return None if saved == NO_ROUTE else saved

    api_key = getattr(settings, 'KAKAO_REST_API_KEY', '')
    if not api_key:
        return None
    try:
        res = requests.get(
            API_URL,
            params={'start_x': a[1], 'start_y': a[0], 'end_x': b[1], 'end_y': b[0]},
            headers={'Authorization': 'KakaoAK ' + api_key},
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        data = res.json()
    except Exception:
        logger.warning('카카오 대중교통 경로 호출 실패 %s', key, exc_info=True)
        return None

    route = _parse(data, a, b)
    if route is None:
        # 경로 없음(NO_RESULTS 등): 2km 안이면 걷기, 더 멀면 None (화면은 예상 시간으로)
        # 어느 쪽이든 저장해서 같은 구간을 다시 부르지 않음
        route = _walk(a, b, (data.get('properties') or {}).get('landingURL')) if meters(a, b) <= 2000 else NO_ROUTE
    cache.set(key, route, CACHE_SECONDS)
    return None if route == NO_ROUTE else route
