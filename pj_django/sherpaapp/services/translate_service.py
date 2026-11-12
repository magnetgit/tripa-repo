"""화면 자동 번역 (🟧 11/12)

화면 번역 사전(static/sherpaapp/i18n/*.js)에 없는 글 — 장소 이름·주소·리뷰 본문·운영시간 안내처럼
DB나 외부(카카오·관광공사)에서 오는 글 — 을 AI로 번역한다.
  - 같은 글·같은 언어는 ui_translation 표에 넣어 두고 다음부터는 AI를 부르지 않는다
  - AI 호출은 chat_service.call_llm 을 그대로 쓴다 (AI_SERVER_URL 이 있으면 FastAPI /llm 으로 감)
  - 실패한 글은 None → 화면은 한국어 그대로 둔다
"""
import hashlib
import json
import logging
import re

from django.db import IntegrityError
from django.db.models import Q

from ..models import Member, UiTranslation
from .chat_service import ChatError, _parse_json, call_llm

logger = logging.getLogger(__name__)

LANG_NAMES = {'en': 'English', 'ja': 'Japanese', 'zh': 'Simplified Chinese'}
NAME_RULES = {
    'en': 'romanize it (Revised Romanization) and translate the generic part (e.g. 부산역 → Busan Station, 해운대해수욕장 → Haeundae Beach)',
    'ja': 'use the usual Japanese name, kanji for Sino-Korean place names and katakana otherwise (e.g. 부산역 → 釜山駅, 해운대해수욕장 → 海雲台海水浴場)',
    'zh': 'use the usual Chinese name, Chinese characters for Sino-Korean names and transliteration otherwise (e.g. 부산역 → 釜山站, 해운대해수욕장 → 海云台海水浴场)',
}
KOREAN = re.compile(r'[가-힣]')
MAX_TEXT = 600       # 한 글의 최대 길이
CHUNK = 30           # AI 한 번에 보내는 글 수
MONEY = {'en': 'KRW (e.g. 8,400원 → 8,400 KRW)', 'ja': 'ウォン', 'zh': '韩元'}


def _hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _ask(texts, lang):
    """AI에게 글 목록을 번역시킨다. 개수가 안 맞거나 실패하면 None"""
    name = LANG_NAMES[lang]
    try:
        raw = call_llm([
            {'role': 'system', 'content': (
                'You translate short Korean strings shown on screens of a Korean travel-planning app into %s. '
                'The strings are place names, addresses, opening-hours notes, user reviews, trip titles and labels. '
                'Rules: 1) Translate every Korean part; keep parts already in another language. '
                '2) For a place, shop or station name, %s. Never add explanations or the Korean original in parentheses. '
                '3) Keep numbers, dates, times, prices, emoji, arrows, bullets and punctuation layout as they are. '
                '4) Keep it as short as the original; a label stays a label. '
                '5) The currency unit 원 is written %s. '
                'Answer only JSON: {"texts": [...]} with exactly the same number of strings in the same order.'
            ) % (name, NAME_RULES[lang], MONEY[lang])},
            {'role': 'user', 'content': json.dumps({'texts': texts}, ensure_ascii=False)},
        ])
        out = (_parse_json(raw) or {}).get('texts')
    except ChatError as error:
        logger.warning('화면 번역 실패 (%s): %s', lang, error)
        return None
    if isinstance(out, list) and len(out) == len(texts) and all(isinstance(t, str) for t in out):
        return out
    logger.warning('화면 번역 답 모양이 다름 (%s, %d개)', lang, len(texts))
    return None


def cached(texts, lang):
    """이미 번역해 둔 글만 {원래 글: 번역} 으로"""
    hashes = {_hash(t): t for t in texts}
    rows = UiTranslation.objects.filter(lang=lang, src_hash__in=list(hashes))
    return {hashes[r.src_hash]: r.text for r in rows if r.src_hash in hashes}


def translate_many(texts, lang, budget=None):
    """texts 를 lang 으로. 돌려주는 값은 texts 와 같은 길이의 목록 (못 한 글은 None)

    budget: 새로 AI에 맡길 수 있는 글 수 (None 이면 제한 없음). 넘는 글은 None 으로 남긴다.
    두 번째 값으로 이번에 새로 번역한 글 수를 돌려준다.
    """
    if lang not in LANG_NAMES:
        return [None] * len(texts), 0
    clean = []
    for t in texts:
        t = t.strip() if isinstance(t, str) else ''
        clean.append(t if t and len(t) <= MAX_TEXT and KOREAN.search(t) else None)
    wanted = list(dict.fromkeys(t for t in clean if t))
    # 닉네임·이름은 번역하지 않는다 ('역사덕후' 가 'History Enthusiast' 로 바뀌면 다른 사람처럼 보임)
    names = set()
    for row in Member.objects.filter(Q(nickname__in=wanted) | Q(name__in=wanted)).values_list('nickname', 'name'):
        names.update(row)
    wanted = [t for t in wanted if t not in names]
    done = cached(wanted, lang)
    todo = [t for t in wanted if t not in done]
    if budget is not None:
        todo = todo[:max(budget, 0)]
    made = 0
    again = []          # 번역에 한글이 남은 글 → 한 번만 더 시킨다
    for attempt in (1, 2):
        batch = todo if attempt == 1 else again
        for i in range(0, len(batch), CHUNK):
            part = batch[i:i + CHUNK]
            out = _ask(part, lang)
            if out is None:
                continue
            for src, text in zip(part, out):
                text = text.strip()
                if not text:
                    continue
                if KOREAN.search(text):         # 덜 번역된 답은 쓰지 않는다 (화면은 한국어 그대로)
                    if attempt == 1:
                        again.append(src)
                    continue
                done[src] = text
                made += 1
                try:
                    UiTranslation.objects.create(lang=lang, src_hash=_hash(src), source=src, text=text)
                except IntegrityError:      # 다른 요청이 먼저 넣음
                    pass
        if not again:
            break
    return [done.get(t) if t else None for t in clean], made
