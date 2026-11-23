"""사용자·외부에서 받은 주소를 화면에 넣기 전에 검사 (🟧 11/23)

주소 맨 앞(scheme: http·https·javascript …)은 대소문자를 가리지 않는다.
'HTTPS://…' 도 정상 주소이고, 'JavaScript:alert(1)' 도 브라우저는 실행한다.
그래서 startswith('https://') 처럼 소문자 글자로만 비교하지 말고, 앞부분을 소문자로 바꾼 뒤 허용 목록과 비교한다.
"""
from urllib.parse import urlsplit

_BAD_CHARS = ('\r', '\n', '\t', '\x00')


def safe_web_url(value, https_only=False, max_len=1000):
    """http(s) 주소면 앞부분을 소문자로 고쳐 돌려주고, 아니면 ''.
    - 'HTTPS://Example.com/a' → 'https://Example.com/a'
    - 'JavaScript:alert(1)', 'data:…', '//evil.com', 'http:/x' → ''
    - https_only=True 면 http 는 https 로 바꿔 줌 (사진처럼 https 페이지에 넣을 것)
    """
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if not value or len(value) > max_len or any(c in value for c in _BAD_CHARS):
        return ''
    try:
        parts = urlsplit(value)
    except ValueError:
        return ''
    scheme = parts.scheme.lower()
    if scheme not in ('http', 'https') or not parts.netloc:
        return ''
    if https_only:
        scheme = 'https'
    return scheme + value[len(parts.scheme):]
