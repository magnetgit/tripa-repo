"""추천 카드에 게시판 리뷰 별점 붙이기 + 리뷰 좋은 곳을 앞으로

카드의 review: {"rating": 4.6, "count": 23} 또는 None (mock.json)
review_summary API(🟧 views.review_summary)와 같은 값을 한 번의 쿼리로 읽는다.

점수 (place_score)
- 리뷰가 MIN_REVIEWS개 미만이면 보통 점수(PRIOR) → 순서를 바꾸지 않음
- 그 이상이면 평균 별점을 PRIOR 쪽으로 조금 당긴 값 (리뷰 2개짜리 5점이 리뷰 30개짜리 4.6점보다 앞서지 않게)
- 같은 점수끼리는 원래 순서(가까운 순·검색 순) 그대로
🟧 추천 점수(키워드·같은 성별·나이대 가중)가 생기면 place_score만 바꾸면 된다.
"""

from django.db.models import Avg, Count

from sherpaapp.models import Review, ReviewSummary


MIN_REVIEWS = 2       # 이보다 적으면 순서에 반영하지 않음 (별점 표시는 함)
PRIOR = 3.5           # 리뷰가 없거나 적은 곳의 점수
PRIOR_WEIGHT = 3      # 평균을 PRIOR 쪽으로 당기는 정도 (리뷰 3개만큼)
GROUP_WEIGHT = 0.4    # 같은 성별·나이대 점수를 섞는 비율 (0.4 = 40%)
KEYWORD_BONUS = 0.15  # 컨셉과 리뷰 키워드가 겹치면 더하는 점수

# 컨셉 → 리뷰 키워드에서 찾을 말 (컨셉 이름이 키워드에 그대로 안 나오는 경우가 많아서)
CONCEPT_WORDS = {
    '음식': ['맛집', '음식', '식사', '밥'],
    '카페': ['카페', '커피', '디저트', '빵'],
    '바다': ['바다', '해변', '오션', '파도'],
    '자연': ['자연', '숲', '산', '풍경', '계곡'],
    '공원': ['공원', '산책', '잔디'],
    '역사': ['역사', '유적', '박물관'],
    '전통문화': ['전통', '한옥', '문화'],
    '쇼핑': ['쇼핑', '시장', '기념품'],
    '랜드마크': ['랜드마크', '야경', '전망', '포토'],
}

def review_stats(kakao_ids):
    """{kakao_id: {"rating", "count"}}. 리뷰 없는 장소는 빠진다."""
    ids = [str(k) for k in kakao_ids if k]
    if not ids:
        return {}

    rows = (
        Review.objects.filter(kakao_id__in=ids)
        .values('kakao_id')
        .annotate(rating=Avg('rating'), count=Count('rv_id'))
    )
    return {r['kakao_id']: {'rating': round(r['rating'], 1), 'count': r['count']} for r in rows}


def group_review_stats(kakao_ids, gender, age_group):
    """같은 성별·나이대 회원 리뷰만 센 {kakao_id: {rating, count}}. 하나만 있으면 그것만으로, 둘다 없으면 {}"""
    filters = {}
    if gender:
        filters['member__gender'] = gender
    if age_group:
        filters['member__age_group'] = age_group
    if not filters:
        return {}
    ids = [str(k) for k in kakao_ids if k]
    if not ids:
        return {}

    rows = (
        Review.objects.filter(kakao_id__in=ids, **filters)
        .values('kakao_id')
        .annotate(rating=Avg('rating'), count=Count('rv_id'))
    )
    return {r['kakao_id']: {'rating': round(r['rating'], 1), 'count': r['count']} for r in rows}


def keyword_hits(kakao_ids, concepts):
    words = []
    for c in concepts:
        words += CONCEPT_WORDS.get(c, [c])
    ids = [str(k) for k in kakao_ids if k]
    if not words or not ids:
        return set()
    rows = ReviewSummary.objects.filter(kakao_id__in=ids).values('kakao_id', 'keywords')
    hits = set()    # 집합: 같은 값을 한 번만 담는 상자, add로 넣음
    for r in rows:
        if any(w in k for k in (r['keywords'] or []) for w in words):
            hits.add(r['kakao_id'])
    return hits


def place_score(review, same=None):
    if not review or review['count'] < MIN_REVIEWS:
        return PRIOR

    n = review['count']
    score = (review['rating'] * n + PRIOR * PRIOR_WEIGHT) / (n + PRIOR_WEIGHT)
    if same and same['count'] >= MIN_REVIEWS:
        group = (same['rating'] * same['count'] + PRIOR * PRIOR_WEIGHT) / (same['count'] + PRIOR_WEIGHT)
        score = score * (1 - GROUP_WEIGHT) + group * GROUP_WEIGHT
    return score


def rank_by_reviews(items, keep_first=0, profile=None, draft=None):
    """카드마다 review를 붙이고, 앞의 keep_first장(팀이 고른 곳)을 뺀 나머지를 점수 순으로."""
    stats = review_stats(item.get('kakao_id') for item in items)
    group = {}
    if profile:
        group = group_review_stats(
            (item.get('kakao_id') for item in items),
            profile.get('gender'),
            profile.get('age_group')
        )
    hits = keyword_hits((item.get('kakao_id') for item in items), (draft or {}).get('categories') or [])

    for item in items:
        item['review'] = stats.get(str(item.get('kakao_id') or ''))

    head, rest = items[:keep_first], items[keep_first:]
    def score_of(item):
        kid = str(item.get('kakao_id') or '')
        score = place_score(item['review'], group.get(kid))
        if kid in hits:
            score += KEYWORD_BONUS
        return -score
    rest = sorted(rest, key=score_of)   # 같은 점수는 원래 순서
    return head + rest
