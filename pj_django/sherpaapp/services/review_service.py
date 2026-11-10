"""리뷰 키워드 요약(LLM)

1) 장소의 최신 리뷰 30개를 모은다
2) 리뷰 수가 저장된 요약과 같으면 LLM 없이 저장값을 쓴다
3) 다르면 call_llm으로 키워드·한 줄 요약을 만들어 review_summary 테이블에 저장한다
"""
from ..models import Review, ReviewSummary
from .chat_service import call_llm, ChatError, _parse_json
# LLM에게 주는 규칙
PROMPT = """
여행 장소 리뷰를 읽고 JSON으로만 답할것,
keywords는 2~8글자 명사구 최대 5개,
keywords에 리뷰 문장을 그대로 쓰지 말 것 ('~요', '~고', '~도'로 끝나면 안 됨. 예: '양이 많고' → '푸짐한 양', '줄 서도' → '긴 대기 줄'),
summary는 한국어 한 문장 60자 이내,
리뷰에 없는 내용은 지어내지 말 것
예 : {"keywords": ["바다 전망", "사진 맛집"], "summary": "..."}
"""


def summarize_review(kakao_id):
    """
    리뷰 내용을 요약하는 함수
    리뷰가 없으면 None, LLM 실패 시 예전 요약
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
        keywords = [k.strip() for k in keywords
                    if isinstance(k, str) and k.strip() and not k.strip().endswith(('요', '다', '고', '도'))]
        keywords = keywords[:5]
    summary = data.get('summary')
    if not isinstance(summary, str):
        summary = ''
    summary = summary.strip()[:60]
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