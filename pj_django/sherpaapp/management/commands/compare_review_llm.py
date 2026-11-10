"""리뷰 키워드 요약을 여러 모델(GPT·로컬 Ollama)로 돌려 비교표를 만든다 (DB에 저장하지 않음)

    python manage.py compare_review_llm
    python manage.py compare_review_llm --models gpt-4o-mini,qwen3:8b --places 5 --rounds 2

- 장소: 리뷰가 많은 순으로 --places 곳 (같은 장소·같은 리뷰로 모든 모델 비교)
- 프롬프트·리뷰 글은 review_service.summarize_review 와 같게 만든다 (PROMPT 그대로)
- 모델마다 예비 모델·예비 AI(AI_FALLBACK_MODELS·AI_BACKUP_*)를 끄고 부른다 → 몰래 OpenAI로 넘어가지 않음
- 로컬 모델은 처음 한 번 불러서 GPU에 올린 뒤(시간 제외) 잰다
- 결과: 화면 + --out 마크다운 파일 (기본 docs/reports/review_llm_compare.md)
"""
import re
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.test.utils import override_settings

from sherpaapp.models import Review
from sherpaapp.services.chat_service import ChatError, _parse_json, call_llm
from sherpaapp.services.review_service import PROMPT

OLLAMA_URL = 'http://localhost:11434/v1'
DEFAULT_MODELS = 'gpt-4o-mini,qwen3:8b,exaone3.5:7.8b,llama3.1:8b'
SUMMARY_MAX = 60          # PROMPT: 한 문장 60자 이내
KEYWORD_MAX = 5           # PROMPT: 최대 5개
KEYWORD_LEN = (2, 8)      # PROMPT: 2~8글자


def review_messages(kakao_id):
    """review_service.summarize_review 와 같은 입력 (최신 리뷰 30개)"""
    rows = Review.objects.filter(kakao_id=kakao_id).order_by('-created_at')[:30]
    text = '\n'.join(f'★{r.rating} {r.tags} {r.content}' for r in rows)
    return [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': text}], text


def route_for(model):
    """모델 이름 → 이 모델만 부르는 설정 (gpt 는 OpenAI, 나머지는 이 PC의 Ollama)"""
    if model.startswith('gpt'):
        base, key = 'https://api.openai.com/v1', getattr(settings, 'OPENAI_API_KEY', '') or settings.AI_API_KEY
    else:
        base, key = OLLAMA_URL, 'ollama'
    return dict(AI_BASE_URL=base, AI_API_KEY=key, AI_MODEL=model, AI_FALLBACK_MODELS='',
                AI_BACKUP_BASE_URL='', AI_BACKUP_MODEL='', AI_BACKUP_API_KEY='', AI_TIMEOUT=180)


def check(text, source):
    """모델 답 하나 → 규칙 검사 결과"""
    data = _parse_json(text)
    if not isinstance(data, dict):
        return {'json': False, 'keywords': [], 'summary': '', 'rules': False, 'grounded': 0.0, 'problems': ['JSON 깨짐']}

    keywords = data.get('keywords') if isinstance(data.get('keywords'), list) else []
    keywords = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
    summary = data.get('summary').strip() if isinstance(data.get('summary'), str) else ''

    problems = []
    if not keywords:
        problems.append('키워드 없음')
    if len(keywords) > KEYWORD_MAX:
        problems.append('키워드 %d개' % len(keywords))
    bad_len = [k for k in keywords if not KEYWORD_LEN[0] <= len(k.replace(' ', '')) <= KEYWORD_LEN[1]]
    if bad_len:
        problems.append('길이 밖: %s' % ', '.join(bad_len))
    sentences = [k for k in keywords if re.search(r'(요|다|고|도)$', k)]   # PROMPT: 명사구 (문장·리뷰 문구 그대로는 X)
    if sentences:
        problems.append('명사구 아님: %s' % ', '.join(sentences))
    if not summary:
        problems.append('요약 없음')
    elif len(summary) > SUMMARY_MAX:
        problems.append('요약 %d자' % len(summary))
    if re.search(r'[A-Za-z]{4,}', summary + ''.join(keywords)):
        problems.append('영어 섞임')

    # 키워드 낱말이 리뷰 글에 실제로 나오는지 (지어냈는지 대략 보기)
    plain = source.replace(' ', '')
    grounded = [k for k in keywords if any(w in plain for w in re.split(r'\s+', k) if len(w) >= 2)]
    return {'json': True, 'keywords': keywords, 'summary': summary, 'rules': not problems,
            'grounded': len(grounded) / len(keywords) if keywords else 0.0, 'problems': problems}


class Command(BaseCommand):
    help = '리뷰 키워드 요약을 GPT·로컬 모델로 돌려 비교표를 만든다 (DB 저장 안 함)'

    def add_arguments(self, parser):
        parser.add_argument('--models', default=DEFAULT_MODELS, help='쉼표로 구분 (gpt* 는 OpenAI, 나머지는 Ollama)')
        parser.add_argument('--places', type=int, default=5, help='비교할 장소 수 (리뷰 많은 순)')
        parser.add_argument('--rounds', type=int, default=1, help='장소마다 몇 번씩 (흔들림 보기)')
        parser.add_argument('--out', default='../docs/reports/review_llm_compare.md', help='마크다운 저장 위치 (manage.py 기준)')

    def handle(self, *args, **opts):
        models = [m.strip() for m in opts['models'].split(',') if m.strip()]
        # 리뷰 많은 순으로, 장소 종류(음식·카페·랜드마크…)가 겹치지 않게 먼저 고르고 모자라면 채운다
        ranked = list(
            Review.objects.exclude(kakao_id__isnull=True).exclude(kakao_id='')
            .values('kakao_id', 'place_name', 'place__p_kind').annotate(n=Count('pk')).filter(n__gte=3).order_by('-n')
        )
        places, kinds = [], set()
        for row in ranked:
            if len(places) < opts['places'] and row['place__p_kind'] not in kinds:
                places.append(row)
                kinds.add(row['place__p_kind'])
        places += [r for r in ranked if r not in places][:opts['places'] - len(places)]
        if not places:
            self.stderr.write('리뷰가 3개 이상인 장소가 없어요. seed_demo 를 먼저 돌려 주세요.')
            return

        inputs = {p['kakao_id']: review_messages(p['kakao_id']) for p in places}
        results = {}   # (model, kakao_id) → [run, ...]

        for model in models:
            with override_settings(**route_for(model)):
                if not model.startswith('gpt'):
                    self.stdout.write('%s 올리는 중...' % model)
                    try:
                        call_llm([{'role': 'user', 'content': '안녕'}])
                    except ChatError as e:
                        self.stderr.write('%s 를 부를 수 없어요: %s (ollama list 확인)' % (model, e))
                        continue

                for p in places:
                    messages, source = inputs[p['kakao_id']]
                    for _ in range(opts['rounds']):
                        started = time.time()
                        try:
                            text = call_llm(messages)
                            run = check(text, source)
                        except ChatError as e:
                            text, run = '', {'json': False, 'keywords': [], 'summary': '', 'rules': False,
                                             'grounded': 0.0, 'problems': ['호출 실패: %s' % e]}
                        run['seconds'] = time.time() - started
                        results.setdefault((model, p['kakao_id']), []).append(run)
                        self.stdout.write('  %-16s %-14s %4.1f초 %s %s' % (
                            model, p['place_name'][:12], run['seconds'],
                            'OK ' if run['rules'] else 'X  ', ' / '.join(run['problems']) or ', '.join(run['keywords'])))

        report = self.render(models, places, results, opts['rounds'])
        out = Path(opts['out'])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS('저장: %s' % out.resolve()))

    def render(self, models, places, results, rounds):
        lines = ['# 리뷰 키워드 요약: GPT vs 로컬 모델', '',
                 '`python manage.py compare_review_llm` 결과 (DB 저장 안 함). 장소 %d곳 × %d번, 프롬프트는 `review_service.PROMPT` 그대로.' % (len(places), rounds),
                 '', '## 모델별', '',
                 '| 모델 | JSON 정상 | 규칙 지킴 | 키워드 근거 | 키워드 수 | 요약 길이 | 평균 시간 |', '|---|---|---|---|---|---|---|']
        for model in models:
            runs = [r for p in places for r in results.get((model, p['kakao_id']), [])]
            if not runs:
                lines.append('| `%s` | 실행 안 됨 | | | | | |' % model)
                continue
            n = len(runs)
            lines.append('| `%s` | %d/%d | %d/%d | %.0f%% | %.1f개 | %.0f자 | %.1f초 |' % (
                model, sum(r['json'] for r in runs), n, sum(r['rules'] for r in runs), n,
                100 * sum(r['grounded'] for r in runs) / n, sum(len(r['keywords']) for r in runs) / n,
                sum(len(r['summary']) for r in runs) / n, sum(r['seconds'] for r in runs) / n))
        lines += ['', '- 규칙: 키워드 1~5개·2~8글자·명사구(…요/…다/…고/…도로 끝나지 않음), 요약 60자 이내, 영어 섞이지 않음',
                  '- 키워드 근거: 키워드 낱말이 리뷰 글에 실제로 나오는 비율 (지어냈는지 대략)', '']

        lines += ['## 장소별', '']
        for p in places:
            lines += ['### %s (리뷰 %d개)' % (p['place_name'], p['n']), '', '| 모델 | 키워드 | 요약 | 문제 |', '|---|---|---|---|']
            for model in models:
                for r in results.get((model, p['kakao_id']), []):
                    lines.append('| `%s` | %s | %s | %s |' % (
                        model, ', '.join(r['keywords']) or '-', (r['summary'] or '-').replace('|', '/'),
                        ' / '.join(r['problems']) or '-'))
            lines.append('')
        return '\n'.join(lines)
