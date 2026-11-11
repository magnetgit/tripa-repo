"""장소 사이 이동비 비교: 대중교통 · 택시 · 자가용 — 🟦

- 택시 요금·통행료·거리: 카카오모빌리티 자동차 길찾기(summary)의 fare.taxi · fare.toll
- 대중교통 요금: transit_service.transit_route 의 1인 요금 (같은 캐시를 씀)
- 자가용: 기름값(거리 ÷ 연비 × 기름 1L 값) + 통행료 (주차비는 모름 → 빼고 안내)
- 같은 구간 자동차 결과는 캐시에 7일 (키 `carfare:위도,경도:위도,경도`)

함수 (TEAM_UPDATES 11/11 공유 정의)
    move_fares(from_lat, from_lon, to_lat, to_lon, people, date=None) → dict
    {
      'people': 2,
      'distance': 19777,                # 자동차 길 거리(m), 모르면 None
      'options': [                      # 값이 있는 것만, 싼 순서
        {'mode': 'car',     'label': '자가용',   'total': 2720,  'per': None, 'note': '기름값 2,720원 (주차비 제외)'},
        {'mode': 'transit', 'label': '대중교통', 'total': 3600,  'per': 1800, 'note': '1인 1,800원 × 2명'},
        {'mode': 'taxi',    'label': '택시',     'total': 19800, 'per': None, 'note': '택시 1대'},
        # date 를 넣으면 먼 구간에 더 붙음 (🟩 11/11): mode 'train'(열차) · 'air'(항공), note에 역·편명·시각
      ],
      'cheapest': 'car',                # 제일 싼 mode, 하나도 없으면 None
      'walk': False,                    # 걸어갈 만한 가까운 구간이면 True (options 는 빈 목록, 0원)
    }
"""
import logging
import math

import requests
from django.conf import settings
from django.core.cache import cache

from . import timetable_service, transit_service

logger = logging.getLogger(__name__)

CAR_URL = 'https://apis-navi.kakaomobility.com/v1/directions'
CACHE_SECONDS = 60 * 60 * 24 * 7
TIMEOUT = 8
WALK_METERS = transit_service.WALK_METERS   # 이 거리 안은 걸어가기 (0원)

FUEL_PRICE = 1700        # 휘발유 1L (원, 대략)
FUEL_KM_PER_L = 12       # 승용차 연비 (km/L, 대략)
TAXI_SEATS = 4           # 택시 한 대에 타는 사람


def _won(n):
    return f'{n:,}원'


def _car_route(a, b):
    """카카오 자동차 길찾기 요약 → {'distance', 'taxi', 'toll'} 또는 None"""
    key = 'carfare:%.4f,%.4f:%.4f,%.4f' % (a[0], a[1], b[0], b[1])
    saved = cache.get(key)
    if saved is not None:
        return saved or None   # {} = 길을 못 찾은 구간

    try:
        response = requests.get(
            CAR_URL,
            headers={'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}'},
            params={'origin': f'{a[1]},{a[0]}', 'destination': f'{b[1]},{b[0]}', 'summary': 'true'},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        route = (response.json().get('routes') or [{}])[0]
    except (requests.RequestException, ValueError):
        logger.warning('자동차 길찾기 실패 %s → %s', a, b, exc_info=True)
        return None   # 실패는 캐시하지 않음 (다음에 다시 시도)

    if route.get('result_code') != 0:
        cache.set(key, {}, CACHE_SECONDS)
        return None

    summary = route.get('summary') or {}
    fare = summary.get('fare') or {}
    result = {
        'distance': summary.get('distance') or 0,
        'taxi': fare.get('taxi') or None,
        'toll': fare.get('toll') or 0,
    }
    cache.set(key, result, CACHE_SECONDS)
    return result


def move_fares(from_lat, from_lon, to_lat, to_lon, people, date=None):
    """date(그날)를 넣으면 80km 넘는 구간에 열차·항공 운임도 붙음 (🟩 timetable_service, 11/11 추가)"""
    a, b = (float(from_lat), float(from_lon)), (float(to_lat), float(to_lon))
    people = max(1, int(people or 1))

    if transit_service.meters(a, b) <= WALK_METERS:
        return {'people': people, 'distance': None, 'options': [], 'cheapest': None, 'walk': True}

    options = []
    car = _car_route(a, b)

    if car and car['distance']:
        fuel = round(car['distance'] / 1000 / FUEL_KM_PER_L * FUEL_PRICE, -1)   # 10원 단위
        fuel = int(fuel)
        note = f'기름값 {_won(fuel)}'
        if car['toll']:
            note += f' + 통행료 {_won(car["toll"])}'
        options.append({
            'mode': 'car', 'label': '자가용', 'total': fuel + car['toll'], 'per': None,
            'note': note + ' (주차비 제외)',
        })

    transit = transit_service.transit_route(*a, *b)
    if transit and not transit.get('walk') and transit.get('fare'):
        per = transit['fare']
        options.append({
            'mode': 'transit', 'label': '대중교통', 'total': per * people, 'per': per,
            'note': f'1인 {_won(per)} × {people}명' if people > 1 else f'1인 {_won(per)}',
        })

    if car and car['taxi']:
        cars = math.ceil(people / TAXI_SEATS)
        one = car['taxi'] + car['toll']   # 통행료는 택시도 손님이 냄
        note = f'택시 {cars}대 × {_won(one)}' if cars > 1 else '택시 1대'
        if car['toll']:
            note += ' (통행료 포함)'
        options.append({'mode': 'taxi', 'label': '택시', 'total': one * cars, 'per': None, 'note': note})

    if date:
        options += timetable_service.fare_options(*a, *b, date, people)

    options.sort(key=lambda o: o['total'])
    return {
        'people': people,
        'distance': car['distance'] if car else None,
        'options': options,
        'cheapest': options[0]['mode'] if options else None,
        'walk': False,
    }
