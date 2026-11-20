"""정적 파일 주소 뒤에 고친 시각을 붙이는 태그 (🟧 11/20)

    {% load tripa_static %}
    <script type="module" src="{% vstatic 'budget/budget.js' %}"></script>
    → /static/budget/budget.js?v=1795140000

React 빌드 결과(static/chat/, static/budget/)는 다시 빌드해도 파일 이름이 같아서,
배포 뒤에도 브라우저가 예전 파일을 쓰는 일이 있었음 (access.js 인원 버그 때 확인).
파일이 바뀌면 ?v= 값이 달라져서 바로 새 파일을 받는다. 버전 번호를 손으로 올릴 필요 없음.
"""
from django import template

from sherpaapp.i18n_middleware import _versioned

register = template.Library()


@register.simple_tag
def vstatic(path):
    return _versioned(path)
