"""화면 언어 바꾸기 (🟧 11/12)

모든 HTML 화면의 </head> 앞에 언어 스크립트를 붙인다. 템플릿은 고치지 않는다.
  - 쿠키 tripa_lang (ko·en·ja·zh, 없으면 ko) 를 읽어 window.TRIPA_LANG 으로 알려 주고
  - 한국어가 아니면 그 언어 사전 static/sherpaapp/i18n/<언어>.js 를 먼저,
  - 그다음 static/sherpaapp/js/i18n.js (언어 버튼 + 화면 글자 바꾸기) 를 붙인다
관리자(/admin/)·관리자 보기(/manage/) 화면에는 붙이지 않는다.
"""
import os

from django.contrib.staticfiles import finders
from django.templatetags.static import static

LANG_COOKIE = 'tripa_lang'
LANGS = ('ko', 'en', 'ja', 'zh')
SKIP_PREFIXES = ('/admin/', '/manage/', '/static/', '/media/')


def request_lang(request):
    """요청 쿠키의 화면 언어. 모르는 값·없음은 'ko'"""
    lang = request.COOKIES.get(LANG_COOKIE)
    return lang if lang in LANGS else 'ko'


def _versioned(path):
    """정적 파일 주소 뒤에 고친 시각을 붙인다 (사전을 고치면 브라우저가 새로 받게)"""
    url = static(path)
    found = finders.find(path)
    if found:
        url += '?v=%d' % int(os.path.getmtime(found))
    return url


def head_snippet(lang):
    parts = ['<script>window.TRIPA_LANG="%s";</script>' % lang]
    if lang != 'ko':
        # 번역이 끝날 때까지 본문을 잠깐 숨겨서 한국어가 번쩍 보였다 바뀌는 것을 막는다
        parts.append('<style>html.i18n-wait body{visibility:hidden}</style>'
                     '<script>document.documentElement.classList.add("i18n-wait");</script>')
        parts.append('<script src="%s"></script>' % _versioned('sherpaapp/i18n/%s.js' % lang))
    parts.append('<script src="%s"></script>' % _versioned('sherpaapp/js/i18n.js'))
    return ''.join(parts)


class LangScriptMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(SKIP_PREFIXES) or getattr(response, 'streaming', False):
            return response
        if not response.get('Content-Type', '').startswith('text/html'):
            return response
        marker = b'</head>'
        body = response.content
        at = body.find(marker)
        if at < 0:
            # <head> 없이 <script>alert('…')</script> 만 돌려주는 응답: 맨 앞에 붙여서 알림 글자도 번역되게
            if b'<script' not in body:
                return response
            at = 0
        snippet = head_snippet(request_lang(request)).encode(response.charset or 'utf-8')
        response.content = body[:at] + snippet + body[at:]
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response
