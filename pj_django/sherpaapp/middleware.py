"""관리자 '회원 화면 보기'를 읽기 전용으로 (🟩 11/12, /manage/)

관리자가 /manage/ 에서 회원을 고르면 세션에 MANAGE_KEY 가 생기고, 그 회원으로 로그인한 것처럼 화면을 본다.
그동안은
  - GET·HEAD·OPTIONS 말고 다른 요청(POST 저장·삭제·채팅 …)은 전부 403 (끝내기·관리자 페이지만 예외)
  - HTML 화면 맨 위에 '관리자 보기 · 읽기 전용 [끝내기]' 띠를 붙인다
장고 관리자 로그인(is_staff)이 풀리면 보기도 바로 끝낸다.
"""
import hashlib

from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils.html import escape

MANAGE_KEY = 'manage_view'          # {'user_id', 'name', 'prev_user'}
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
# 보기 중에도 POST 되는 곳: /manage/ (다른 회원으로 바꾸기·끝내기, 관리자만 쓰는 주소) · /admin/
ALLOWED_PREFIXES = ('/manage/', '/admin/')


def end_manage_view(session):
    """관리자 보기를 끝내고 원래 로그인 상태로 되돌린다"""
    view = session.pop(MANAGE_KEY, None)
    if view is None:
        return None
    if view.get('prev_user'):
        session['login_ok_user'] = view['prev_user']
    else:
        session.pop('login_ok_user', None)
    return view


def _banner(request, view):
    return (
        '<div id="tripa-manage-banner" style="position:sticky;top:0;z-index:99999;display:flex;gap:12px;'
        'align-items:center;justify-content:center;flex-wrap:wrap;padding:8px 16px;background:#7c3aed;color:#fff;'
        'font:600 14px/1.4 system-ui,sans-serif">'
        '<span>관리자 보기 · %s (%s) 님 화면 · 읽기 전용 (저장·수정은 막혀 있어요)</span>'
        '<form method="post" action="/manage/stop/" style="margin:0">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="%s">'
        '<button type="submit" style="border:0;border-radius:6px;padding:4px 12px;background:#fff;color:#7c3aed;'
        'font-weight:700;cursor:pointer">끝내기</button></form></div>'
    ) % (escape(view.get('name') or ''), escape(view.get('user_id') or ''), get_token(request))


class ManageReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        view = request.session.get(MANAGE_KEY)
        if view is None:
            return self.get_response(request)

        # 관리자 로그인이 풀렸으면 보기도 끝 (회원 세션이 남지 않게)
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated and user.is_staff):
            end_manage_view(request.session)
            return self.get_response(request)

        if request.method not in SAFE_METHODS and not request.path.startswith(ALLOWED_PREFIXES):
            message = '관리자 보기(읽기 전용) 중이라 저장·수정할 수 없어요.'
            wants_json = (
                'application/json' in request.headers.get('Accept', '')
                or request.headers.get('X-Requested-With') in ('XMLHttpRequest', 'fetch')
                or request.content_type == 'application/json'
            )
            if wants_json:
                return JsonResponse({'success': False, 'message': message, 'read_only': True}, status=403)
            return HttpResponse(
                '<p style="font:16px system-ui;padding:24px">%s <a href="javascript:history.back()">돌아가기</a></p>' % message,
                status=403, content_type='text/html; charset=utf-8',
            )

        response = self.get_response(request)

        # 회원 화면(HTML)에만 띠를 붙임 (관리자 페이지·JSON·파일은 그대로)
        if (
            response.status_code == 200
            and 'text/html' in response.get('Content-Type', '')
            and not request.path.startswith('/admin/')
            and not getattr(response, 'streaming', False)
        ):
            content = response.content.decode(response.charset or 'utf-8', errors='replace')
            if '<body' in content and 'tripa-manage-banner' not in content:
                at = content.find('>', content.find('<body')) + 1
                content = content[:at] + _banner(request, view) + content[at:]
                response.content = content.encode(response.charset or 'utf-8')
                if response.has_header('Content-Length'):
                    response['Content-Length'] = str(len(response.content))
        return response


# ---- 비밀번호를 바꾸면 다른 기기 로그인도 풀기 (🟧 11/19) ----
PW_TAG_KEY = 'login_pw'      # 로그인할 때의 비밀번호(암호화된 값)로 만든 짧은 표시


def pw_tag(saved_pwd):
    """DB 에 저장된 비밀번호 값(암호화된 것) → 짧은 표시. 비밀번호를 바꾸면 값이 달라진다"""
    return hashlib.sha256((saved_pwd or '').encode('utf-8')).hexdigest()[:16]


class LoginPasswordMiddleware:
    """세션에 적어 둔 비밀번호 표시와 지금 DB 값이 다르면(다른 기기에서 비밀번호를 바꿈) 로그아웃.
    표시가 없는 예전 세션은 지금 값으로 한 번 적어 둔다. 관리자 '회원 화면 보기' 중에는 건너뜀"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = request.session
        user_id = session.get('login_ok_user')
        if user_id and MANAGE_KEY not in session:
            from .models import Member
            saved = Member.objects.filter(user_id=user_id).values_list('pwd', flat=True).first()
            if saved is None:
                session.flush()                       # 탈퇴한 회원
            else:
                tag = pw_tag(saved)
                if session.get(PW_TAG_KEY) is None:
                    session[PW_TAG_KEY] = tag
                elif session[PW_TAG_KEY] != tag:
                    session.flush()
        return self.get_response(request)
