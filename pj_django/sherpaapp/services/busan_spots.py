"""부산 장소 표(docs/data/busan_spots_draft.csv)를 추천 후보로 쓰기

팀이 직접 고른 곳('고름' 칸이 O)만 쓴다. 부산 여행에서 추천 종류가 표의 컨셉과 맞으면
카카오 검색 결과 앞에 최대 2곳을 먼저 보여 준다.

표에만 있는 정보(영업시간·입장료·주차·메모)는 카드의 pick 에 담는다 (mock.json).
표의 휴무 요일('월')은 관광공사에 쉬는 날 정보가 없을 때 쓴다 (tour_service.drop_closed).
표를 고치면 서버를 다시 켜야 반영된다.
"""

import csv
import logging
import re
from pathlib import Path

from django.conf import settings


logger = logging.getLogger(__name__)

CSV_PATH = Path(settings.BASE_DIR).parent / 'docs' / 'data' / 'busan_spots_draft.csv'
MAX_PICKS = 2           # 카드 앞에 넣는 최대 개수
NEAR_LIMIT_M = 3000     # '○○ 근처' 추천이면 기준점에서 이 거리 안의 곳만

# 추천 종류(query) → 표의 컨셉
QUERY_CONCEPTS = {
    '바다': '바다', '해수욕장': '바다', '해변': '바다',
    '카페': '카페', '디저트': '카페', '커피': '카페',
    '맛집': '음식', '식당': '음식', '음식': '음식', '음식점': '음식',
    '역사': '역사', '박물관': '역사',
    '전통문화': '전통문화', '시장': '전통문화', '전통시장': '전통문화',
    '자연': '자연', '산책': '자연',
    '쇼핑': '쇼핑', '백화점': '쇼핑',
    '숙소': '숙소', '호텔': '숙소',
    '랜드마크': '랜드마크', '관광지': '랜드마크', '명소': '랜드마크',
    '공원': '공원',
}

WEEKDAY_CHARS = '월화수목금토일'
UNKNOWN_TEXTS = ('', '-', '확인 필요')

_rows = None


def _text(value):
    value = (value or '').strip()
    return None if value in UNKNOWN_TEXTS or '확인 필요' in value else value


def _rest_rule(value):
    """표의 휴무 칸 → tour_service 가 읽는 문장. '월' → '매주 월요일', '토·일' → '매주 토, 일요일'.

    '화(이번 달 11/3)'처럼 매주가 아닌 것과 '없음'·'확인 필요'는 None.
    """
    value = (value or '').strip()
    days = re.findall(r'[월화수목금토일]', value)

    if not days or re.search(r'[^월화수목금토일요\s,·/]', value):
        return None

    return '매주 %s요일' % ', '.join(days)


def _kakao_id(url):
    m = re.search(r'/(\d+)\s*$', url or '')
    return m.group(1) if m else None


def load_rows():
    """표에서 고른 곳만 읽는다 (한 번 읽으면 기억해 둠). 파일이 없으면 빈 목록."""
    global _rows

    if _rows is not None:
        return _rows

    rows = []

    try:
        with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
            for raw in csv.DictReader(f):
                if (raw.get('고름(O)') or '').strip().upper() != 'O':
                    continue

                try:
                    lat, lon = float(raw['위도']), float(raw['경도'])
                except (TypeError, ValueError, KeyError):
                    continue

                inout = (raw.get('실내/실외') or '').strip()

                rows.append({
                    'concept': (raw.get('컨셉') or '').strip(),
                    'name': (raw.get('이름') or '').strip(),
                    'kakao_id': _kakao_id(raw.get('카카오맵')),
                    'kind_text': raw.get('카카오 분류') or '',
                    'addr': _text(raw.get('주소')),
                    'phone': _text(raw.get('전화')),
                    'lat': lat,
                    'lon': lon,
                    'url': _text(raw.get('카카오맵')),
                    # 실내+실외(시장 등)는 모름
                    'indoor': True if inout == '실내' else False if inout == '실외' else None,
                    'pick': {
                        'concept': (raw.get('컨셉') or '').strip(),
                        'hours': _text(raw.get('영업시간')),
                        'fee': _text(raw.get('입장료')),
                        'parking': _text(raw.get('주차(가능/불가/유료)')),
                        'memo': _text(raw.get('메모')),
                        'rest': _rest_rule(raw.get('휴무 요일')),
                    },
                })
    except OSError:
        logger.warning('부산 장소 표를 읽지 못했어요: %s', CSV_PATH)

    _rows = rows
    return rows


def pick_rows(query, place):
    """부산 여행이고 추천 종류가 표의 컨셉과 맞으면 그 컨셉의 장소들. 아니면 빈 목록."""
    if '부산' not in (place or ''):
        return []

    query = (query or '').strip()
    rows = load_rows()

    # 비 오는 날 '실내 추천'은 구경할 곳만 (식당·카페·숙소는 따로 추천)
    if '실내' in query:
        return [r for r in rows if r['indoor'] and r['concept'] not in ('숙소', '음식', '카페')]

    concept = QUERY_CONCEPTS.get(query)
    return [r for r in rows if r['concept'] == concept] if concept else []
