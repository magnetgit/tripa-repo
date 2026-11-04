from ..models import Review, ReviewSummary
from .chat_service import call_llm, ChatError, _parse_json
PROMPT = """
여행 장소 리뷰를 읽고 JSON으로만 답할것,
keywords는 2~8글자 명사구 최대 5개,
summary는 한국어 한 문장 60자 이내,
리뷰에 없는 내용은 지어내지 말 것
예 : {"keywords": ["바다 전망", "사진 맛집"], "summary": "..."}
"""


def summarize_review(kakao_id):
    """
    리뷰 내용을 요약하는 함수
    """
    total = Review.objects.filter(kakao_id=kakao_id).count()
    review_contents = Review.objects.filter(kakao_id=kakao_id).order_by('-created_at')[:30]
    if total == 0:
        return None
    review_summary = ReviewSummary.objects.filter(kakao_id=kakao_id).first()
    if review_summary and review_summary.review_count == total:
        return {'keywords': review_summary.keywords, 'summary':review_summary.summary, 'count':total}
    review_text = '\n'.join(f'★{r.rating} {r.tags} {r.content}' for r in review_contents)
    messages = [
        {
            "role": "system",
            "content": PROMPT,
        },
        {
            "role": "user",
            "content": review_text,
        },
    ]
    try:
        text = call_llm(messages)
        data = _parse_json(text)
        if not data:
            print(f"Error parsing JSON for kakao_id {kakao_id}: {text}")
            return {'keywords': review_summary.keywords, 'summary':review_summary.summary, 'count':total} if review_summary else None
    except ChatError as e:
        print(f"Error summarizing review for kakao_id {kakao_id}: {e}")
        return {'keywords': review_summary.keywords, 'summary':review_summary.summary, 'count':total} if review_summary else None
    keywords = data.get('keywords')
    if not isinstance(keywords, list):
        keywords = []
    else:
        keywords = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
        keywords = keywords[:5]
    summary = data.get('summary')
    if not isinstance(summary, str):
        summary = ''
    summary = summary.strip()[:100]
    ReviewSummary.objects.update_or_create(
        kakao_id=kakao_id,
        defaults={
            'keywords': keywords,
            'summary': summary,
            'review_count': total
            }
    )
    return {'keywords': keywords,
            'summary': summary,
            'count': total
            }