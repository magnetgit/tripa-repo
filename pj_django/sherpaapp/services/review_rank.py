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

from sherpaapp.models import Review


MIN_REVIEWS = 2     # 이보다 적으면 순서에 반영하지 않음 (별점 표시는 함)
PRIOR = 3.5         # 리뷰가 없거나 적은 곳의 점수
PRIOR_WEIGHT = 3    # 평균을 PRIOR 쪽으로 당기는 정도 (리뷰 3개만큼)


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


def place_score(review):
    if not review or review['count'] < MIN_REVIEWS:
        return PRIOR

    n = review['count']
    return (review['rating'] * n + PRIOR * PRIOR_WEIGHT) / (n + PRIOR_WEIGHT)


def rank_by_reviews(items, keep_first=0):
    """카드마다 review를 붙이고, 앞의 keep_first장(팀이 고른 곳)을 뺀 나머지를 점수 순으로."""
    stats = review_stats(item.get('kakao_id') for item in items)

    for item in items:
        item['review'] = stats.get(str(item.get('kakao_id') or ''))

    head, rest = items[:keep_first], items[keep_first:]
    rest = sorted(rest, key=lambda item: -place_score(item['review']))   # 같은 점수는 원래 순서
    return head + rest
