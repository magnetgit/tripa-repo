"""
회원 통계 (🟩 관리자 통계 화면 · 🟧 Streamlit 운영 대시보드가 같이 씀, TEAM_UPDATES 11/11 공유 정의)

- 장고 ORM만 쓴다 (request·HTML 모름) → Streamlit은 django.setup() 뒤 그대로 불러 쓴다
- 걸러 보기: gender = 'M' · 'F' · 'none'(안 넣음) · None(전체)
             age_group = 10 · 20 · … · 60 · 'none' · None(전체)
- 방문 = 일정에 들어간 장소(schedule_places) 수, 리뷰 = review 수, 별점 = 리뷰 별점 평균
- 같은 장소는 kakao_id로 묶는다 (없으면 이름). 숙소는 장소 순위에서 뺀다
- 돌려주는 값은 list·dict·숫자·글자만 (pandas DataFrame(rows)로 바로 바꿀 수 있게)
"""

from collections import Counter, defaultdict

from django.db.models import Count, Q, Sum

from ..models import (
    AGE_GROUP_CHOICES,
    GENDER_CHOICES,
    BudgetLog,
    Member,
    Review,
    SchedulePlace,
    TravelBudgetItem,
)

NONE = 'none'               # 성별·나이대를 안 넣은 회원
MIN_REVIEWS_FOR_RATING = 3  # 별점 순위는 리뷰가 이만큼 있는 곳만 (리뷰 1개 5점이 1등이 되지 않게)


# =========================================================
# 작은 도우미
# =========================================================

def _group_value(value):
    """회원 칸 값 → 통계 열쇠 (None·빈 글자는 'none')"""
    return NONE if value in (None, '') else value


def _member_q(prefix, gender=None, age_group=None):
    """회원 걸러 보기 조건. prefix는 회원까지 가는 길 (예: 'member__', 'schedule__travel__member__')"""
    q = Q()
    if gender == NONE:
        q &= Q(**{prefix + 'gender__isnull': True}) | Q(**{prefix + 'gender': ''})
    elif gender:
        q &= Q(**{prefix + 'gender': gender})

    if age_group == NONE:
        q &= Q(**{prefix + 'age_group__isnull': True})
    elif age_group:
        q &= Q(**{prefix + 'age_group': int(age_group)})
    return q


def _place_key(kakao_id, name):
    """같은 장소를 묶는 열쇠 (kakao_id가 없으면 이름)"""
    return kakao_id or 'name:%s' % (name or '')


def _is_stay(kind):
    return '숙' in (kind or '')


def _rating(total, count):
    return round(total / count, 1) if count else None


# =========================================================
# 공유 함수 (이름·모양은 TEAM_UPDATES 11/11)
# =========================================================

def labels():
    """화면에 쓸 이름 {'gender': {'M': '남성', …, 'none': '안 넣음'}, 'age': {10: '10대', …, 'none': '안 넣음'}}"""
    return {
        'gender': {**dict(GENDER_CHOICES), NONE: '안 넣음'},
        'age': {**dict(AGE_GROUP_CHOICES), NONE: '안 넣음'},
    }


def member_summary():
    """{'members': 전체 회원 수, 'by_gender': {'M': n, 'F': n, 'none': n}, 'by_age': {10: n, …, 'none': n}}"""
    by_gender = {code: 0 for code, _ in GENDER_CHOICES}
    by_gender[NONE] = 0
    for row in Member.objects.values('gender').annotate(n=Count('m_id')):
        key = _group_value(row['gender'])
        by_gender[key] = by_gender.get(key, 0) + row['n']

    by_age = {code: 0 for code, _ in AGE_GROUP_CHOICES}
    by_age[NONE] = 0
    for row in Member.objects.values('age_group').annotate(n=Count('m_id')):
        key = _group_value(row['age_group'])
        by_age[key] = by_age.get(key, 0) + row['n']

    return {
        'members': Member.objects.count(),
        'by_gender': by_gender,
        'by_age': by_age,
    }


def favorite_places(gender=None, age_group=None, limit=5, order='visits'):
    """
    많이 간 장소 순위 → [{'kakao_id', 'name', 'kind', 'visits', 'reviews', 'rating'}]
    order: 'visits'(방문 많은 순, 같으면 리뷰 수) · 'reviews' · 'rating'(리뷰 3개 이상만)
    """
    places = {}

    def place(kakao_id, name, kind):
        key = _place_key(kakao_id, name)
        if key not in places:
            places[key] = {'kakao_id': kakao_id, 'name': name, 'kind': kind,
                           'visits': 0, 'reviews': 0, '_rating_sum': 0}
        elif not places[key]['kind'] and kind:
            places[key]['kind'] = kind
        return places[key]

    # 방문: 일정 장소 → 여행 → 회원
    visits = (
        SchedulePlace.objects
        .filter(_member_q('schedule__travel__member__', gender, age_group))
        .values('place__p_kakao_id', 'place__p_name', 'place__p_kind')
        .annotate(n=Count('sp_id'))
    )
    for row in visits:
        if _is_stay(row['place__p_kind']):
            continue
        place(row['place__p_kakao_id'], row['place__p_name'], row['place__p_kind'])['visits'] += row['n']

    # 리뷰: 쓴 회원 기준
    reviews = (
        Review.objects
        .filter(_member_q('member__', gender, age_group))
        .values('kakao_id', 'place_name', 'place__p_kind')
        .annotate(n=Count('rv_id'), total=Sum('rating'))
    )
    for row in reviews:
        if _is_stay(row['place__p_kind']):
            continue
        p = place(row['kakao_id'], row['place_name'], row['place__p_kind'])
        p['reviews'] += row['n']
        p['_rating_sum'] += row['total'] or 0

    rows = []
    for p in places.values():
        p['rating'] = _rating(p.pop('_rating_sum'), p['reviews'])
        rows.append(p)

    if order == 'rating':
        rows = [r for r in rows if r['reviews'] >= MIN_REVIEWS_FOR_RATING]
        rows.sort(key=lambda r: (-r['rating'], -r['reviews']))
    elif order == 'reviews':
        rows.sort(key=lambda r: (-r['reviews'], -r['visits']))
    else:
        rows.sort(key=lambda r: (-r['visits'], -r['reviews']))

    return rows[:limit] if limit else rows


def group_preferences():
    """성별 × 나이대 × 장소 종류 → [{'gender', 'age_group', 'kind', 'visits', 'reviews', 'rating'}] (0인 칸은 없음)"""
    cells = defaultdict(lambda: {'visits': 0, 'reviews': 0, '_rating_sum': 0})

    visits = (
        SchedulePlace.objects
        .values('schedule__travel__member__gender', 'schedule__travel__member__age_group', 'place__p_kind')
        .annotate(n=Count('sp_id'))
    )
    for row in visits:
        kind = row['place__p_kind'] or ''
        if _is_stay(kind):
            continue
        key = (_group_value(row['schedule__travel__member__gender']),
               _group_value(row['schedule__travel__member__age_group']), kind)
        cells[key]['visits'] += row['n']

    reviews = (
        Review.objects
        .values('member__gender', 'member__age_group', 'place__p_kind')
        .annotate(n=Count('rv_id'), total=Sum('rating'))
    )
    for row in reviews:
        kind = row['place__p_kind'] or ''
        if _is_stay(kind):
            continue
        key = (_group_value(row['member__gender']), _group_value(row['member__age_group']), kind)
        cells[key]['reviews'] += row['n']
        cells[key]['_rating_sum'] += row['total'] or 0

    rows = []
    for (gender, age_group, kind), cell in cells.items():
        rows.append({
            'gender': gender,
            'age_group': age_group,
            'kind': kind,
            'visits': cell['visits'],
            'reviews': cell['reviews'],
            'rating': _rating(cell['_rating_sum'], cell['reviews']),
        })

    # 성별 → 나이대 → 방문 많은 순 ('none'은 뒤로)
    rows.sort(key=lambda r: (
        r['gender'] == NONE, str(r['gender']),
        r['age_group'] == NONE, r['age_group'] if r['age_group'] != NONE else 0,
        -r['visits'],
    ))
    return rows


def place_spending(limit=10):
    """
    회원이 비용 관리에서 고친 금액 → [{'kakao_id', 'name', 'edited_total', 'edited_avg', 'edits'}] (합계 많은 순)
    edited_total·edited_avg = travel_budget_item.amount 합계·평균(원), edits = budget_log 줄 수
    """
    places = {}
    items = (
        TravelBudgetItem.objects
        .values('schedule_place__place__p_kakao_id', 'schedule_place__place__p_name')
        .annotate(total=Sum('amount'), n=Count('tbi_id'))
    )
    for row in items:
        kakao_id, name = row['schedule_place__place__p_kakao_id'], row['schedule_place__place__p_name']
        key = _place_key(kakao_id, name)
        p = places.setdefault(key, {'kakao_id': kakao_id, 'name': name,
                                    'edited_total': 0, '_count': 0, 'edits': 0})
        p['edited_total'] += row['total'] or 0
        p['_count'] += row['n']

    # 바뀐 기록: sp_id로 장소를 찾고, 지워진 자리는 기록에 남은 이름으로
    logs = list(BudgetLog.objects.values_list('sp_id', 'p_name'))
    sp_place = {
        sp_id: _place_key(kakao_id, name)
        for sp_id, kakao_id, name in SchedulePlace.objects
        .filter(sp_id__in={sp_id for sp_id, _ in logs})
        .values_list('sp_id', 'place__p_kakao_id', 'place__p_name')
    }
    edits = Counter(sp_place.get(sp_id) or _place_key(None, name) for sp_id, name in logs)

    rows = []
    for key, p in places.items():
        count = p.pop('_count')
        p['edited_avg'] = round(p['edited_total'] / count) if count else 0
        p['edits'] = edits.get(key, 0)
        rows.append(p)

    rows.sort(key=lambda r: (-r['edited_total'], -r['edits']))
    return rows[:limit] if limit else rows
