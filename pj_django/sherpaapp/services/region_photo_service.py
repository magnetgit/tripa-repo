"""
여행 루트 카드 표지: 여행 지역(Travel.t_place)을 대표하는 사진

1) 주요 지역은 대표 명소를 정해 두고, 관광공사(searchKeyword2)에서 그 명소 사진을 찾는다
   예: 수원 → 수원화성, 부산 → 해운대해수욕장
2) 목록에 없는 지역은 관광공사 관광지(contentTypeId=12) 중
   주소에 지역 이름이 들어 있고 사진이 있는 곳을 고른다 (이름에 지역 이름이 들어가면 먼저)
3) 둘 다 없으면 '' → 화면은 루트 안 장소 사진을 쓴다

같은 지역은 7일 동안 캐시해서 게시판을 열 때마다 API를 부르지 않는다.
"""

import logging

from django.core.cache import cache

from .tour_service import _tour_get

logger = logging.getLogger(__name__)

CACHE_SECONDS = 60 * 60 * 24 * 7
TOURIST_SPOT = 12  # 관광공사 관광지 타입

# 지역 → 대표 명소 (관광공사에 있는 이름)
LANDMARKS = {
    '서울': '경복궁', '부산': '해운대해수욕장', '인천': '월미도', '대구': '이월드',
    '대전': '엑스포과학공원', '광주': '무등산', '울산': '대왕암공원', '세종': '세종호수공원',
    '제주': '성산일출봉', '서귀포': '천지연폭포',
    '수원': '수원화성', '용인': '에버랜드', '가평': '남이섬', '파주': '임진각',
    '강릉': '경포해변', '속초': '설악산국립공원', '춘천': '소양강스카이워크', '양양': '낙산사',
    '평창': '대관령양떼목장', '동해': '추암해변', '삼척': '환선굴',
    '경주': '불국사', '안동': '하회마을', '포항': '호미곶', '통영': '동피랑',
    '거제': '바람의언덕', '남해': '독일마을', '여수': '오동도', '순천': '순천만습지',
    '전주': '전주한옥마을', '군산': '경암동 철길마을', '목포': '목포해상케이블카',
    '담양': '죽녹원', '보성': '대한다원', '공주': '공산성', '부여': '부소산성',
    '태안': '꽃지해수욕장', '단양': '도담삼봉', '청주': '청남대',
}


def _image(item):
    return (item.get('firstimage') or item.get('firstimage2') or '').strip()


def _region_word(t_place):
    """'부산 해운대' → '부산', '제주도' → '제주', '서울특별시' → '서울'"""
    word = (t_place or '').strip().split()[0] if (t_place or '').strip() else ''
    for tail in ('특별자치도', '특별자치시', '특별시', '광역시', '시', '군', '도'):
        if len(word) > len(tail) + 1 and word.endswith(tail):
            return word[:-len(tail)]
    if word == '제주도':
        return '제주'
    return word


def _landmark_photo(name):
    items = _tour_get('searchKeyword2', keyword=name, contentTypeId=TOURIST_SPOT,
                      arrange='O', numOfRows=10, pageNo=1)
    # 이름이 똑같은 곳 먼저, 없으면 이름이 들어간 곳 (띄어쓰기는 무시)
    key = name.replace(' ', '')
    for match in (lambda t: t == key, lambda t: key in t):
        for item in items:
            if match((item.get('title') or '').replace(' ', '')) and _image(item):
                return _image(item)
    return ''


def _search_photo(region):
    items = _tour_get('searchKeyword2', keyword=region, contentTypeId=TOURIST_SPOT,
                      arrange='O', numOfRows=30, pageNo=1)
    in_region = [i for i in items if region in (i.get('addr1') or '') and _image(i)]
    # 이름에 지역 이름이 들어가고 괄호(○○고택(가평) 같은 것)가 없는 곳 먼저
    in_region.sort(key=lambda i: (region not in (i.get('title') or ''), '(' in (i.get('title') or '')))
    return _image(in_region[0]) if in_region else ''


def region_cover(t_place):
    """여행 지역을 대표하는 사진 주소. 못 찾으면 ''."""
    region = _region_word(t_place)
    if not region:
        return ''

    cache_key = 'region_cover:v1:%s' % region
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = ''
    try:
        landmark = LANDMARKS.get(region)
        if landmark:
            url = _landmark_photo(landmark)
        if not url:
            url = _search_photo(region)
    except Exception:  # API가 느리거나 막혀도 게시판은 떠야 한다
        logger.warning('region cover lookup failed: %s', region, exc_info=True)
        return ''

    if url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    cache.set(cache_key, url, CACHE_SECONDS)
    return url
