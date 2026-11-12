"""화면 번역 사전에 빠진 한글 문장 찾기 (🟧 11/12)

    python manage.py i18n_missing          # 언어마다 빠진 문장 수
    python manage.py i18n_missing --show   # 빠진 문장을 사전에 붙여 넣기 좋은 모양으로 출력

템플릿·화면 스크립트(static)·views.py 의 한글 문장을 뽑아서 static/sherpaapp/i18n/<언어>.js 와 비교한다.
값이 들어가는 자리({{ }}, ${ }, %s)는 {} 로 바꿔서 본다. 이어 붙이는 문장은 조각으로 나온다.
"""
import ast
import io
import json
import pathlib
import re

from django.core.management.base import BaseCommand

root = pathlib.Path(__file__).resolve().parents[2]      # sherpaapp 폴더
KO = re.compile(r'[가-힣]')
found = {}   # 문장 → 나온 곳 집합


def add(s, where):
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip('\x01').strip()
    if not KO.search(s):
        return
    # 값 자리만 있고 앞뒤에 붙은 기호 정리
    s = s.replace('\x00', '{}')
    if len(s) > 300:
        return
    found.setdefault(s, set()).add(where)


def html_text(src, where):
    """HTML 조각에서 글자 마디와 속성 값을 뽑는다."""
    for m in re.finditer(r'\b(placeholder|title|aria-label|alt|value|data-tip|data-label|data-title|content)\s*=\s*"([^"]*)"', src):
        add(m.group(2), where)
    for m in re.finditer(r"\b(placeholder|title|aria-label|alt|value)\s*=\s*'([^']*)'", src):
        add(m.group(2), where)
    body = re.sub(r'<[^>]*>', '\x01', src)
    for part in body.split('\x01'):
        add(part, where)


def js_strings(src, where):
    src = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)
    src = re.sub(r'(^|[^:\\\'"`])//[^\n]*', r'\1', src)
    pat = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`", re.S)
    for m in pat.finditer(src):
        s = m.group(1) or m.group(2) or m.group(3) or ''
        if not KO.search(s):
            continue
        if m.group(3) is not None:
            # ${ ... } 안쪽은 값 자리 (안에 든 글자는 따로 다시 뽑음)
            depth = 0; out = []; i = 0; inner = []
            while i < len(s):
                if s.startswith('${', i):
                    depth += 1; i += 2
                    if depth == 1:
                        out.append('\x00'); inner.append('')
                    continue
                if depth and s[i] == '{':
                    depth += 1
                elif depth and s[i] == '}':
                    depth -= 1
                    if depth == 0:
                        i += 1; continue
                if depth:
                    inner[-1] += s[i]
                else:
                    out.append(s[i])
                i += 1
            for x in inner:
                if KO.search(x):
                    js_strings(x, where)
            s = ''.join(out)
        s = s.replace("\\'", "'").replace('\\"', '"').replace('\\n', '\n').replace('\\`', '`')
        if '<' in s and '>' in s:
            html_text(s, where)
        else:
            for line in s.split('\n'):
                add(line, where)


def template(path):
    src = io.open(path, encoding='utf-8').read()
    where = path.name
    src = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '', src, flags=re.S)
    src = re.sub(r'\{#.*?#\}', '', src)
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    src = re.sub(r'<style\b.*?</style>', '', src, flags=re.S)

    def script(m):
        body = re.sub(r'\{\{.*?\}\}', '0', m.group(1))
        body = re.sub(r'\{%.*?%\}', ' ', body)
        js_strings(body, where)
        return '\x01'
    src = re.sub(r'<script\b[^>]*>(.*?)</script>', script, src, flags=re.S)
    # on...="…" 안의 글자 (confirm 등)
    for m in re.finditer(r'\bon\w+\s*=\s*"([^"]*)"', src):
        if KO.search(m.group(1)):
            js_strings(re.sub(r'\{\{.*?\}\}', '0', m.group(1)), where)
    # 템플릿 꼬리표 안의 글자 값: with title="…", default:"…"
    for m in re.finditer(r'\{[%{](.*?)[%}]\}', src, flags=re.S):
        for q in re.finditer(r'"([^"]*)"|\'([^\']*)\'', m.group(1)):
            add(q.group(1) or q.group(2) or '', where)
    src = re.sub(r'\{\{.*?\}\}', '\x00', src, flags=re.S)
    src = re.sub(r'\{%.*?%\}', '\x01', src, flags=re.S)
    html_text(src, where)


def python(path):
    where = path.name
    tree = ast.parse(io.open(path, encoding='utf-8').read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module, ast.AsyncFunctionDef)):
            b = getattr(node, 'body', [])
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], 'value', None), ast.Constant):
                docs.add(id(b[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            s = node.value
            if KO.search(s):
                s = re.sub(r'%\([a-z_]+\)[sd]|%[sd]|%\.?\d*f|\{[a-z_0-9]*(?::[^}]*)?\}', '\x00', s)
                for line in s.split('\n'):
                    add(line, where)
        elif isinstance(node, ast.JoinedStr):
            s = ''.join(v.value if isinstance(v, ast.Constant) else '\x00' for v in node.values)
            if KO.search(s):
                for line in s.split('\n'):
                    add(line, where)


def collect():
    found.clear()
    for p in sorted((root / 'templates').rglob('*.html')):
        if 'admin' not in p.parts:
            template(p)
    for p in sorted((root / 'static').rglob('*.js')):
        if 'i18n' in p.parts or p.name == 'i18n.js':
            continue
        js_strings(io.open(p, encoding='utf-8').read(), p.name)
    for name in ('views.py', 'manage_views.py'):
        python(root / name)
    keys = {}
    for k, where in found.items():
        k = re.sub(r"'\);?$", '', re.sub(r"^alert\('", '', k)).strip()
        if r'\s' in k or r'\d' in k or not KO.search(k.replace('{}', '')):
            continue
        keys.setdefault(k, set()).update(where)
    return keys


def load_dict(lang):
    text = io.open(root / 'static' / 'sherpaapp' / 'i18n' / ('%s.js' % lang), encoding='utf-8').read()
    return json.loads(text[text.index('{', text.index('window.TRIPA_DICT')):text.rindex('}') + 1])


class Command(BaseCommand):
    help = '화면 번역 사전(static/sherpaapp/i18n/*.js)에 빠진 한글 문장을 찾는다'

    def add_arguments(self, parser):
        parser.add_argument('--show', action='store_true', help='빠진 문장을 모두 출력')

    def handle(self, *args, **options):
        keys = collect()
        self.stdout.write('화면 문장 %d개' % len(keys))
        for lang in ('en', 'ja', 'zh'):
            have = load_dict(lang)
            missing = sorted(k for k in keys if k not in have)
            self.stdout.write('%s: 사전 %d개, 빠진 문장 %d개' % (lang, len(have), len(missing)))
            if options['show'] and lang == 'en':
                for k in missing:
                    self.stdout.write('%s: "",    // %s' % (json.dumps(k, ensure_ascii=False), ', '.join(sorted(keys[k]))[:60]))
