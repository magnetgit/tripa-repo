"""장거리 자차 구간의 고속도로 휴게소 찾기 (🟧 11/18)

여행지까지 가는 길(access_service)에서 차로 2시간 넘게 가는 구간이면 중간에 쉬어 갈 휴게소를 넣는다.

  find(a, b, count) → [{'name', 'lat', 'lon', 'addr', 'at'(0~1, 구간의 어디쯤)}, ...]   (못 찾으면 [])

어떻게 찾나
  1) 카카오 자동차 길찾기로 실제 도로 경로를 받는다 (점을 약 400m 간격으로 줄여 7일 저장)
  2) 경로의 1/2 지점(2곳이면 1/3·2/3 …) 근처에서 카카오 장소 검색 '휴게소'
  3) 경로에서 600m 안에 있는 고속도로 휴게소만 남기고, 이름의 '○○방향'이 가는 방향과 맞는 것을 고른다
     (상행·하행 휴게소는 길 양쪽에 따로 있어서, 반대 방향 휴게소는 들어갈 수 없음)
길찾기가 안 되면(키 없음·실패) 휴게소를 넣지 않는다 — 직선으로 어림해서 엉뚱한 휴게소를 넣지 않으려고.
"""
import logging
import math
import re

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CAR_URL = 'https://apis-navi.kakaomobility.com/v1/directions'
SEARCH_URL = 'https://dapi.kakao.com/v2/local/search/keyword.json'
ADDRESS_URL = 'https://dapi.kakao.com/v2/local/search/address.json'
TIMEOUT = 8
CACHE_SECONDS = 60 * 60 * 24 * 7
STEP_M = 400            # 경로 점 간격 (이보다 촘촘한 점은 버림)
NEAR_ROUTE_M = 600      # 경로에서 이 거리 안이어야 '가는 길에 있는' 휴게소
SEARCH_RADIUS_M = 20000
REST_MINUTES = 15       # 휴게소에서 쉬는 시간
MIN_DRIVE_MINUTES = 120  # 이보다 오래 운전하는 구간에만 넣는다
MAX_STOPS = 3
_DIRECTION_RE = re.compile(r'([가-힣]{2,6})\s*방향')


def _meters(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def _headers():
    return {'Authorization': 'KakaoAK %s' % getattr(settings, 'KAKAO_REST_API_KEY', '')}


def stops_for(minutes):
    """운전 시간(분) → 쉬어 갈 휴게소 수: 2시간마다 한 번 (2시간 미만 0, 2~4시간 1, 4~6시간 2, 그 이상 3)"""
    if minutes < MIN_DRIVE_MINUTES:
        return 0
    return min(MAX_STOPS, int(minutes // MIN_DRIVE_MINUTES))


def route_points(a, b):
    """실제 도로 경로의 점들 [(위도, 경도, 출발지부터 거리 m), ...]. 못 구하면 []"""
    if not getattr(settings, 'KAKAO_REST_API_KEY', ''):
        return []
    key = 'restpath:%.3f,%.3f:%.3f,%.3f' % (a[0], a[1], b[0], b[1])
    saved = cache.get(key)
    if saved is not None:
        return saved
    try:
        response = requests.get(CAR_URL, headers=_headers(), timeout=TIMEOUT,
                                params={'origin': '%s,%s' % (a[1], a[0]), 'destination': '%s,%s' % (b[1], b[0])})
        response.raise_for_status()
        route = (response.json().get('routes') or [{}])[0]
    except (requests.RequestException, ValueError):
        logger.warning('휴게소용 길찾기 실패 %s → %s', a, b, exc_info=True)
        return []          # 실패는 저장하지 않음 (다음에 다시 시도)
    points = []
    if route.get('result_code') == 0:
        total, last, kept = 0.0, None, None
        for section in route.get('sections') or []:
            for road in section.get('roads') or []:
                v = road.get('vertexes') or []
                for i in range(0, len(v) - 1, 2):
                    here = (v[i + 1], v[i])
                    if last is not None:
                        total += _meters(last, here)
                    last = here
                    if kept is None or total - kept >= STEP_M:
                        points.append((round(here[0], 5), round(here[1], 5), int(total)))
                        kept = total
        if last is not None and points and points[-1][2] < int(total):
            points.append((round(last[0], 5), round(last[1], 5), int(total)))
    cache.set(key, points, CACHE_SECONDS)
    return points


def _place_point(word):
    """'강릉'·'하남' 같은 방향 이름 → (위도, 경도) 또는 None (주소 검색, 7일 저장)"""
    key = 'restdir:%s' % word
    saved = cache.get(key)
    if saved is not None:
        return tuple(saved) if saved else None
    point = None
    try:
        response = requests.get(ADDRESS_URL, headers=_headers(), params={'query': word, 'size': 1}, timeout=TIMEOUT)
        response.raise_for_status()
        docs = response.json().get('documents') or []
        if docs:
            point = (float(docs[0]['y']), float(docs[0]['x']))
    except (requests.RequestException, ValueError, KeyError):
        return None
    cache.set(key, list(point) if point else [], CACHE_SECONDS)
    return point


def _direction_score(name, a, b):
    """이름의 '○○방향'이 가는 방향(a → b)과 맞으면 0, 모르면 300, 반대면 100000 (경로까지 거리 m 에 더하는 벌점)"""
    match = _DIRECTION_RE.search(name or '')
    if not match:
        return 300
    toward = _place_point(match.group(1))
    if not toward:
        return 300
    return 0 if _meters(toward, b) < _meters(toward, a) else 100000


def _search(point):
    """그 지점 근처의 휴게소 후보 (카카오 장소 검색, 가까운 순)
    '휴게소'만 찾으면 이름이 ○○휴게소인 식당·매점이 앞을 채워서, '고속도로 휴게소'로 찾는다"""
    try:
        response = requests.get(SEARCH_URL, headers=_headers(), timeout=TIMEOUT, params={
            'query': '고속도로 휴게소', 'y': point[0], 'x': point[1], 'radius': SEARCH_RADIUS_M,
            'sort': 'distance', 'size': 15})
        response.raise_for_status()
        return response.json().get('documents') or []
    except (requests.RequestException, ValueError):
        logger.warning('휴게소 검색 실패 %s', point, exc_info=True)
        return []


def _candidates(points, target):
    """목표 지점과 그 앞뒤 25km 지점 세 군데에서 찾은 후보를 합친다 (한 군데만 보면 휴게소가 드문 구간에서 못 찾음)"""
    seen, out = set(), []
    for shift in (0, -25000, 25000):
        near = min(points, key=lambda p: abs(p[2] - (target + shift)))
        for doc in _search((near[0], near[1])):
            if doc.get('id') not in seen:
                seen.add(doc.get('id'))
                out.append(doc)
    return out


def _is_rest_area(doc):
    """고속도로 휴게소만 (이름만 '○○휴게소'인 식당·주유소·졸음쉼터·간이 화장실은 뺌)"""
    kind = doc.get('category_name') or ''
    name = doc.get('place_name') or ''
    if '휴게소' not in name or any(w in name for w in ('졸음', '화물차', '라운지', '주유소', '충전소', '주차장', '화장실')):
        return False
    return '고속도로휴게소' in kind or ('휴게소' in kind and '교통' in kind)


def _nearest(points, spot):
    """경로에서 가장 가까운 점까지 거리(m)와 그 점이 출발지부터 몇 m 지점인지"""
    best = (float('inf'), 0)
    for lat, lon, along in points:
        d = _meters((lat, lon), spot)
        if d < best[0]:
            best = (d, along)
    return best


def find(a, b, count):
    """a → b 로 차를 몰고 갈 때 쉬어 갈 휴게소 count 곳 (가는 순서대로). a·b = (위도, 경도)"""
    if count <= 0:
        return []
    key = 'reststops:%.3f,%.3f:%.3f,%.3f:%d' % (a[0], a[1], b[0], b[1], count)
    saved = cache.get(key)
    if saved is not None:
        return saved
    points = route_points(a, b)
    if len(points) < 3:
        return []
    total = points[-1][2] or 1
    found, used = [], set()
    for n in range(1, count + 1):
        target = total * n / (count + 1)
        best = None
        for doc in _candidates(points, target):
            if not _is_rest_area(doc) or doc.get('id') in used:
                continue
            try:
                spot = (float(doc['y']), float(doc['x']))
            except (KeyError, TypeError, ValueError):
                continue
            off, along = _nearest(points, spot)
            if off > NEAR_ROUTE_M:
                continue
            # 이미 고른 휴게소보다 뒤에 있어야 하고, 출발·도착 바로 앞(10%)은 쉬는 곳으로 안 씀
            if along < total * 0.1 or along > total * 0.9 or (found and along <= found[-1]['_along']):
                continue
            score = off + _direction_score(doc.get('place_name'), a, b) + abs(along - target) / 50
            if best is None or score < best[0]:
                best = (score, doc, spot, along)
        if best and best[0] < 50000:
            _, doc, spot, along = best
            used.add(doc.get('id'))
            found.append({'name': doc.get('place_name'), 'lat': round(spot[0], 6), 'lon': round(spot[1], 6),
                          'addr': doc.get('road_address_name') or doc.get('address_name') or '',
                          'at': round(along / total, 3), '_along': along})
    for item in found:
        item.pop('_along', None)
    cache.set(key, found, CACHE_SECONDS)
    return found
