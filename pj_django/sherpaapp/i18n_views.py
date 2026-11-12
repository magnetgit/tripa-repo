"""화면 자동 번역 API (🟧 11/12) — mock.json 의 translate

POST /api/translate/   {"lang": "en"|"ja"|"zh", "texts": ["한글 문장", …]}
→ {"success": true, "lang": "en", "texts": ["번역" 또는 null, …]}   (texts 와 같은 길이·순서, 못 한 글은 null)

화면 스크립트(static/sherpaapp/js/i18n.js)가 사전에 없는 글을 모아서 부른다.
AI 비용이 드는 주소라서 막아 둔 것
  - 같은 사이트 화면에서 부른 요청만 (Origin·Referer 확인)
  - 한 번에 40개, 한 글 600자까지
  - 새로 번역하는 글 수: 접속 주소(IP)마다 1시간 400개, 사이트 전체 하루 6000개 (넘으면 그 글은 null → 한국어 그대로)
    이미 번역해 둔 글은 세지 않는다
"""
import json
from datetime import date
from urllib.parse import urlparse

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import translate_service

MAX_TEXTS = 40
IP_LIMIT = 400          # 1시간
DAY_LIMIT = 6000        # 사이트 전체 하루


def _same_site(request):
    source = request.headers.get('Origin') or request.headers.get('Referer') or ''
    return bool(source) and urlparse(source).netloc == request.get_host()


def _client_ip(request):
    forwarded = request.headers.get('X-Forwarded-For', '')
    return (forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')) or 'unknown'


@csrf_exempt
@require_POST
def api_translate(request):
    if not _same_site(request):
        return JsonResponse({'success': False, 'message': '이 화면에서만 쓸 수 있어요.'}, status=403)
    try:
        body = json.loads(request.body or '{}')
    except ValueError:
        body = {}
    lang = body.get('lang')
    texts = body.get('texts')
    if lang not in translate_service.LANG_NAMES or not isinstance(texts, list):
        return JsonResponse({'success': False, 'message': 'lang(en·ja·zh)과 texts 목록이 필요합니다.'}, status=400)
    texts = texts[:MAX_TEXTS]

    ip_key = 'tr_ip_%s' % _client_ip(request)
    day_key = 'tr_day_%s' % date.today().isoformat()
    used_ip = cache.get(ip_key, 0)
    used_day = cache.get(day_key, 0)
    budget = max(min(IP_LIMIT - used_ip, DAY_LIMIT - used_day), 0)

    out, made = translate_service.translate_many(texts, lang, budget=budget)
    if made:
        cache.set(ip_key, used_ip + made, 3600)
        cache.set(day_key, used_day + made, 86400)
    return JsonResponse({'success': True, 'lang': lang, 'texts': out},
                        json_dumps_params={'ensure_ascii': False})
