"""장소가 실내인지 야외인지 (비·눈 오는 날 추천에 씀)

카카오 분류 이름(category_name, 예: '여행 > 관광,명소 > 해수욕장,해변')을 뒤쪽(자세한 분류)부터 읽어서
실내 단어가 있으면 True, 야외 단어가 있으면 False, 둘 다 없으면 이름을 보고, 그래도 모르면 None.

전망대·시장·체험장처럼 곳마다 다른 곳은 None(모름)으로 둔다.
추천 카드의 indoor (mock.json): true / false / null
"""


# 실내 단어 (분류 이름 안에 들어 있으면 실내)
INDOOR_WORDS = (
    '실내', '박물관', '미술관', '전시관', '기념관', '과학관', '아쿠아리움', '수족관',
    '공연장', '극장', '영화관', '도서관', '문화시설',
    '복합쇼핑몰', '쇼핑몰', '백화점', '아울렛', '상설할인매장', '면세점', '서점',
    '카페', '음식점', '숙박', '호텔', '찜질방', '목욕탕', '사우나', '온천', '스파',
    '볼링', '스크린', '키즈카페', '방탈출', '노래방', '공방',
)

# 야외 단어
OUTDOOR_WORDS = (
    '해수욕장', '해변', '해안', '공원', '테마파크', '놀이공원', '동물원', '수목원', '식물원',
    '절,사찰', '사찰', '문화유적', '유적지', '성곽', '고궁', '케이블카', '테마거리', '카페거리', '먹자골목',
    '호수', '계곡', '폭포', '등산', '둘레길', '산책로', '캠핑', '야영', '등대', '항구', '포구',
    '골프장', '스키', '테니스장', '풋살장', '축구장', '야구장', '페스티벌', '체험마을',
)

# 짧아서 다른 말에 섞이기 쉬운 단어는 분류 칸 전체가 같을 때만 본다 ('산'이 '산업'에 걸리지 않게)
OUTDOOR_EXACT = ('산', '섬', '길', '성', '마을', '해수욕장,해변')

# 분류로 모를 때 이름으로 본다
INDOOR_NAME_WORDS = ('박물관', '미술관', '전시관', '기념관', '과학관', '아쿠아리움', '백화점', '아울렛', '쇼핑몰')
OUTDOOR_NAME_WORDS = ('해수욕장', '공원', '해변', '수목원', '유원지', '둘레길', '전망대')

# 카카오 분류 코드: 카페·음식점·숙박은 실내
INDOOR_GROUPS = ('CE7', 'FD6', 'AD5')


def _segment_says(segment):
    # 야외 단어를 먼저 본다 ('카페거리'는 카페가 아니라 거리)
    if segment in OUTDOOR_EXACT or any(word in segment for word in OUTDOOR_WORDS):
        return False
    if any(word in segment for word in INDOOR_WORDS):
        return True
    return None


def is_indoor(category_name, group_code='', name=''):
    """실내면 True, 야외면 False, 모르면 None."""
    segments = [s.strip() for s in (category_name or '').split('>') if s.strip()]

    # 자세한 분류(뒤쪽)가 먼저: '테마파크 > 아쿠아리움'은 실내
    for segment in reversed(segments):
        said = _segment_says(segment)
        if said is not None:
            return said

    if group_code in INDOOR_GROUPS:
        return True

    name = name or ''
    if any(word in name for word in INDOOR_NAME_WORDS):
        return True
    if any(word in name for word in OUTDOOR_NAME_WORDS):
        return False

    return None


def indoor_first(items):
    """실내(True) → 모름(None) → 야외(False) 순으로 다시 세운다. 같은 무리 안의 순서는 그대로."""
    rank = {True: 0, None: 1, False: 2}
    return sorted(items, key=lambda item: rank.get(item.get('indoor'), 1))
