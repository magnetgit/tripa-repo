"""여행 기간과 겹치는 지역 축제·행사 (한국관광공사 TourAPI searchFestival2)

- 여행 첫날 기준으로 '그날 이후에도 열리는' 행사를 받아서
- 여행 마지막 날 전에 시작하는 것만 남기고 (= 여행 기간과 겹침)
- 여행 지역 이름이 주소에 있는 것만 고른다 (지역 이름이 없을 때만 일정 장소 근처 40km로 고름)
- 두 달 넘게 하는 전시·공연·상설 행사는 '상시 행사'(always)로 표시해서 아래쪽에 둔다

TourAPI 하루 호출 수 제한이 있어서 같은 시작일 목록은 6시간 저장한다.
"""

import logging
from datetime import date

import requests
from django.core.cache import cache

from .photo_service import _distance_m, _https, _to_float
from .tour_service import _tour_get


logger = logging.getLogger(__name__)

CACHE_SECONDS = 60 * 60 * 6
NEAR_KM = 40
MAX_FESTIVALS = 30
ALWAYS_DAYS = 60     # 이보다 길게 하면 '상시 행사'

# '부산광역시', '서울특별시' 처럼 붙는 말 (지역 이름만 남겨서 주소와 비교)
_REGION_SUFFIXES = ('특별자치시', '특별자치도', '특별시', '광역시', '자치시', '시', '도', '군', '구')


def _ymd(value):
    """'20261115' -> date, 이상하면 None"""
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except (TypeError, ValueError):
        return None


def _region_word(t_place):
    word = (t_place or '').strip().split()[0] if (t_place or '').strip() else ''
    for suffix in _REGION_SUFFIXES:
        if len(word) > len(suffix) + 1 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _festivals_from(start):
    """시작일 이후에도 열리는 전국 행사 목록 (필요한 칸만, 6시간 저장)"""
    cache_key = 'festival:v1:%s' % start.strftime('%Y%m%d')
    rows = cache.get(cache_key)
    if rows is not None:
        return rows

    try:
        items = _tour_get('searchFestival2', eventStartDate=start.strftime('%Y%m%d'),
                          numOfRows=1000, pageNo=1, arrange='C')
    except requests.RequestException as error:
        logger.warning('축제 조회 실패: %s', error)
        return []

    rows = []
    for item in items:
        begin, end = _ymd(item.get('eventstartdate')), _ymd(item.get('eventenddate'))
        if not begin or not end or not item.get('title'):
            continue
        rows.append({
            'id': str(item.get('contentid') or ''),
            'title': item.get('title').strip(),
            'start': begin.isoformat(),
            'end': end.isoformat(),
            'addr': (item.get('addr1') or '').strip(),
            'lat': _to_float(item.get('mapy')),
            'lon': _to_float(item.get('mapx')),
            'image': _https(item.get('firstimage') or item.get('firstimage2') or ''),
            'tel': (item.get('tel') or '').strip(),
        })

    cache.set(cache_key, rows, CACHE_SECONDS)
    return rows


def festivals_for_travel(travel, places=()):
    """여행 기간과 겹치고 여행 지역에서 열리는 축제·행사 (가까운 기간 먼저)

    places: 일정 장소들 (p_lat, p_lon) - 지역 이름으로 못 찾을 때 거리로 고름
    """
    start, end = travel.t_start, travel.t_end
    if not start or not end:
        return []

    region = _region_word(travel.t_place)
    points = [(_to_float(p.p_lat), _to_float(p.p_lon)) for p in places]
    points = [(y, x) for y, x in points if y is not None and x is not None]
    center = (sum(y for y, _ in points) / len(points), sum(x for _, x in points) / len(points)) if points else None

    picked = []
    for row in _festivals_from(start):
        if date.fromisoformat(row['start']) > end:
            continue

        # 지역 이름이 있으면 주소로만 (근처 다른 도시 행사가 섞이지 않게), 없으면 거리로
        if region:
            if region not in row['addr']:
                continue
        elif not (
            center is not None and row['lat'] is not None and row['lon'] is not None
            and _distance_m(center[0], center[1], row['lat'], row['lon']) <= NEAR_KM * 1000
        ):
            continue

        # 화면에서 쓰기 좋게: 기간 글자, 여행 몇째 날에 열리는지
        b, e = date.fromisoformat(row['start']), date.fromisoformat(row['end'])
        days = [(d - start).days + 1 for d in _each_day(max(b, start), min(e, end))]
        always = (e - b).days > ALWAYS_DAYS
        picked.append({
            **row,
            'period': '%02d.%02d~%02d.%02d' % (b.month, b.day, e.month, e.day),
            'days': days,
            'always': always,
            # 짧게 열리는 진짜 '행사'를 위로(여행 날짜에 가까운 순), 오래 하는 건 아래로(곧 끝나는 순)
            '_sort': (always, b if not always else e),
        })

    picked.sort(key=lambda r: r['_sort'])
    for row in picked:
        row.pop('_sort')
    return picked[:MAX_FESTIVALS]


def _each_day(first, last):
    day = first
    while day <= last:
        yield day
        day = date.fromordinal(day.toordinal() + 1)
