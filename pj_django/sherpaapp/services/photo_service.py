"""장소 사진 찾기 (카카오 장소 ID당 한 장)

찾는 순서
1) 저장해 둔 사진 (place_photo 테이블)
2) 한국관광공사 TourAPI: 이름이 맞고 300m 안에 있는 곳의 대표 사진
3) 카카오 이미지 검색: '장소 이름 + 시·구'로 검색한 첫 사진
4) 그래도 없으면 사진 없음 → 화면은 기본 이미지

찾은 결과(사진 없음 포함)는 저장해서 같은 장소를 다시 찾지 않는다.
사진 없음은 NONE_RETRY_DAYS가 지나면 다시 찾는다.

응답 모양 (mock.json 의 photo): {"url": "...", "source": "tour" | "kakao"} 또는 None
"""

import math
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from sherpaapp.models import PlacePhoto


TOUR_URL = 'https://apis.data.go.kr/B551011/KorService2/searchKeyword2'
KAKAO_IMAGE_URL = 'https://dapi.kakao.com/v2/search/image'

TIMEOUT = 4                 # 채팅 응답이 늦어지지 않게 짧게
TOUR_MAX_DISTANCE_M = 300   # 관광공사 장소와 이 거리 안이어야 같은 곳으로 봄
NONE_RETRY_DAYS = 30


# =========================================================
# 작은 도우미
# =========================================================

def _squash(text):
    """비교용: 괄호 안 내용·공백·기호를 없애고 소문자로."""
    text = re.sub(r'\(.*?\)|\[.*?\]', '', str(text or ''))
    return re.sub(r'[\s\-·.,]+', '', text).lower()


def _distance_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _https(url):
    if not url:
        return None
    url = str(url).strip()
    if url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    return url if url.startswith('https://') else None


def _region_words(addr):
    """'부산 해운대구 우동 123' → '부산 해운대구' (시·구까지만)."""
    words = str(addr or '').split()
    return ' '.join(words[:2])


def _to_photo(row):
    if not row or row.source == 'none' or not row.url:
        return None
    return {'url': row.url, 'source': row.source}


# =========================================================
# 1) 관광공사 TourAPI
# =========================================================

def _same_name(a, b):
    a, b = _squash(a), _squash(b)
    if not a or not b:
        return False
    if a == b:
        return True
    # 한쪽이 다른 쪽을 포함 (예: '해운대해수욕장' / '해운대해수욕장(부산)')
    shorter = a if len(a) <= len(b) else b
    return len(shorter) >= 3 and (a in b or b in a)


def find_tour_photo(name, lat=None, lon=None):
    key = getattr(settings, 'TOUR_API_KEY', '')
    if not key or not name:
        return None

    response = requests.get(TOUR_URL, params={
        'serviceKey': key,
        'MobileOS': 'ETC',
        'MobileApp': 'TRIPA',
        '_type': 'json',
        'keyword': name,
        'numOfRows': 10,
        'pageNo': 1,
    }, timeout=TIMEOUT)
    response.raise_for_status()

    try:
        items = response.json()['response']['body']['items']
    except (ValueError, KeyError, TypeError):
        return None

    # 결과가 없으면 items가 빈 문자열로 온다
    items = items.get('item') if isinstance(items, dict) else None
    if isinstance(items, dict):
        items = [items]

    for item in items or []:
        url = _https(item.get('firstimage') or item.get('firstimage2'))
        if not url or not _same_name(name, item.get('title')):
            continue

        # 좌표가 있으면 거리도 맞아야 같은 곳 (이름이 같은 다른 지역 장소 거르기)
        if lat is not None and lon is not None:
            ty, tx = _to_float(item.get('mapy')), _to_float(item.get('mapx'))
            if ty is None or tx is None:
                continue
            if _distance_m(lat, lon, ty, tx) > TOUR_MAX_DISTANCE_M:
                continue

        return url

    return None


# =========================================================
# 2) 카카오 이미지 검색
# =========================================================

def find_kakao_photo(name, addr=None):
    """카카오 이미지 검색 결과에는 장소 이름이 없어서 결과를 이름으로 확인할 수 없다.
    대신 '이름 + 시·구'로 좁혀 검색하고, 너무 짧은 이름은 찾지 않는다.
    """
    key = getattr(settings, 'KAKAO_REST_API_KEY', '')
    name = str(name or '').strip()

    if not key or len(_squash(name)) < 2:
        return None

    region = _region_words(addr)
    if not region:
        return None

    response = requests.get(
        KAKAO_IMAGE_URL,
        headers={'Authorization': f'KakaoAK {key}'},
        params={'query': f'{name} {region}', 'size': 1},
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    documents = response.json().get('documents') or []
    if not documents:
        return None

    # thumbnail_url 은 카카오 https 주소라 화면에서 안전하게 열린다
    return _https(documents[0].get('thumbnail_url'))


# =========================================================
# 찾기 + 저장
# =========================================================

def _is_fresh(row):
    if row.source != 'none':
        return True
    return row.checked_at and row.checked_at > timezone.now() - timedelta(days=NONE_RETRY_DAYS)


def lookup_photo(kakao_id, name, addr=None, lat=None, lon=None):
    """사진을 찾아 저장하고 photo 모양으로 돌려준다. 찾지 못하면 None."""
    kakao_id = str(kakao_id or '').strip()[:20]
    if not kakao_id:
        return None

    url, source = None, 'none'

    try:
        url = find_tour_photo(name, lat, lon)
        if url:
            source = 'tour'
    except requests.RequestException:
        pass

    if not url:
        try:
            url = find_kakao_photo(name, addr)
            if url:
                source = 'kakao'
        except requests.RequestException:
            pass

    row, _ = PlacePhoto.objects.update_or_create(
        kakao_id=kakao_id,
        defaults={'url': url, 'source': source},
    )
    return _to_photo(row)


def get_photo(kakao_id, name, addr=None, lat=None, lon=None):
    """장소 하나의 사진 (저장된 값이 있으면 그것을 씀)."""
    kakao_id = str(kakao_id or '').strip()
    if not kakao_id:
        return None

    row = PlacePhoto.objects.filter(kakao_id=kakao_id).first()
    if row and _is_fresh(row):
        return _to_photo(row)

    return lookup_photo(kakao_id, name, addr, lat, lon)


def attach_photos(items, max_new=None):
    """추천 카드 목록(dict)에 photo 키를 붙인다. 카드에 kakao_id·name·addr·lat·lon이 있어야 함.

    저장된 사진은 한 번에 읽고, 없는 것만 새로 찾는다.
    max_new: 새로 찾는 장소 수 상한 (일정 미리보기처럼 장소가 많을 때 응답이 늦어지지 않게).
             넘는 장소는 이번에는 photo=None, 다음에 다시 찾는다.
    """
    ids = [str(item.get('kakao_id')) for item in items if item.get('kakao_id')]
    saved = {row.kakao_id: row for row in PlacePhoto.objects.filter(kakao_id__in=ids)}
    new_count = 0

    for item in items:
        kakao_id = str(item.get('kakao_id') or '')
        row = saved.get(kakao_id)

        if not kakao_id:
            item['photo'] = None
        elif row and _is_fresh(row):
            item['photo'] = _to_photo(row)
        elif max_new is not None and new_count >= max_new:
            item['photo'] = None
        else:
            new_count += 1
            item['photo'] = lookup_photo(
                kakao_id, item.get('name'), item.get('addr'),
                item.get('lat'), item.get('lon'),
            )

    return items


def place_photo_url(place):
    """일정의 장소(Place)에 쓸 사진 주소. 카카오 ID가 없거나 사진을 못 찾으면 ''."""
    photo = get_photo(place.p_kakao_id, place.p_name, place.p_addr, place.p_lat, place.p_lon)
    return photo['url'] if photo else ''
