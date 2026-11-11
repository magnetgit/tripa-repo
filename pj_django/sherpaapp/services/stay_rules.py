"""장소 체류 시간 범위와 식사 시간대 (TEAM_UPDATES 11/11 📐 공유 정의)

- stay_range(kind, name) → (최소, 보통, 최대) 분
- fit_meal_windows(schedule) → 점심 12~13시·저녁 18~19시 도착에 맞춰 앞 장소 체류를 늘리고 줄임 (2단계)
"""

# (종류에 들어 있을 낱말들, (최소, 보통, 최대)) — 위에서부터 먼저 맞는 것
STAY_RANGES = [
    (('카페', '커피', '디저트', '베이커리'), (20, 50, 90)),
    (('음식', '식당', '맛집'), (40, 60, 90)),
    (('놀이공원', '테마파크', '어드벤처', '워터파크'), (120, 180, 300)), # 롯데월드·이월드 ...
    (('유원지',), (90, 120, 180)),  # 태종대 ...
    (('온천', '스파', '찜질'), (90, 120, 180)), # 허심청 ...
    (('아쿠아리움', '수족관'), (60, 90, 150)),
    (('쇼핑', '백화점', '아울렛'), (40, 90, 180)),
    (('역사', '박물관', '미술관', '전시관'), (40, 80, 120)),
    (('전통', '시장', '문화'), (30, 70, 120)),
    (('랜드마크', '전망'), (30, 60, 120)),
    (('자연', '산책', '섬'), (40, 90, 150)),
    (('바다', '해수욕장', '공원'), (30, 70, 120)),
]


DEFAULT_STAY = (30, 60, 90)      # 모르는 종류


def stay_range(kind, name=''):
    """장소 종류·이름 → (최소, 보통, 최대) 체류 시간(분)"""
    for words, span in STAY_RANGES:
        if any(w in f'{kind or ""} {name or ""}' for w in words):
            return span
    return DEFAULT_STAY


LUNCH = (12 * 60, 13 * 60)      # 점심 도착 12:00~13:00 (분)
DINNER = (18 * 60, 19 * 60)     # 저녁 도착 18:00~19:00


def meal_shift(arrive_min, window):
    """식사 도착 시각이 시간대를 벗어난 만큼(분). 늦으면 음수(앞을 줄여야), 이르면 양수(앞을 늘려야), 안이면 0"""
    start, end = window
    if arrive_min > end:
        return end - arrive_min          # 예: 13:40 도착 → 780 - 820 = -40
    if arrive_min < start:
        return start - arrive_min       # 예: 11:30 도착 → +30
    return 0


def spread(stays, limits, need):
    """need 분만큼 여러 장소에 나눠서 줄이거나(need<0) 늘린다(need>0).
    stays: [지금 체류], limits: [(최소, 최대)] → 새 체류 목록 (범위 밖으로는 안 바꿈)"""
    if need < 0:
        rooms = [max(0, s - lo) for s, (lo, hi) in zip(stays, limits)]      # 줄일 수 있는 만큼
    else:
        rooms = [max(0, hi - s) for s, (lo, hi) in zip(stays, limits)]      # 늘릴 수 있는 만큼
    total = sum(rooms)
    if total <= 0:
        return list(stays)
    take = min(abs(need), total)                                    # 실제로 옮길 분
    sign = 1 if need > 0 else -1
    return [s + sign * round(take * room / total) for s, room in zip(stays, rooms)]
