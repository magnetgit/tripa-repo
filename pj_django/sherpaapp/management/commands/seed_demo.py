"""데모 데이터 만들기 (발표 시연 · 추천 점수 · 리뷰 게시판 시험용)

    python manage.py seed_demo              # 데모 회원 40명 + 여행·일정·리뷰·도움돼요·공유 루트·예산
    python manage.py seed_demo --reset      # 데모 데이터만 지우고 다시 만들기
    python manage.py seed_demo --clear      # 데모 데이터만 지우기 (만들지 않음)
    python manage.py seed_demo --members 30 --seed 7
    python manage.py seed_demo --summaries  # 리뷰 3개 이상 장소는 AI 키워드 요약까지 (LLM 호출, 시간·비용 듦)

- 데모 회원은 아이디가 demo_ 로 시작해요 (demo_01 ~ demo_40). 비밀번호는 모두 아래 DEMO_PASSWORD (시험용).
  demo_01 은 20대 여성, demo_02 는 40대 남성 — 같은 장소라도 추천 카드 순서가 다르게 보여요.
- 장소는 docs/data/busan_spots_draft.csv (팀이 고른 부산 장소, 실제 카카오 장소 번호).
  그래서 채팅 추천 카드에도 데모 리뷰 별점이 붙고, 같은 성별·나이대 가중이 보여요.
- 같은 --seed 값이면 언제나 같은 데이터가 나와요 (발표 화면을 미리 맞춰 둘 수 있게).
- 데모 회원이 아닌 데이터는 건드리지 않아요. 지울 때도 demo_ 회원과 그 회원의 여행·리뷰만 지워요.

새 기능에 데이터가 더 필요하면: 아래 make_* 함수를 하나 더 만들고 handle()의 순서 목록에 한 줄 추가하면 돼요.
"""
import csv
import random
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from sherpaapp.models import (
    AVATAR_CHOICES, Category, Member, Place, Review, ReviewHelpful, RouteComment, RouteRating,
    Schedule, SchedulePlace, SharedRoute, Travel, TravelBudget, TravelCategory,
)

DEMO_PREFIX = 'demo_'
DEMO_PASSWORD = 'Tripa#Demo2026'    # 시험용 (데모 회원 모두 같음)
SPOTS_CSV = Path(settings.BASE_DIR).parent / 'docs' / 'data' / 'busan_spots_draft.csv'

TAGS = ['가족과', '친구와', '연인과', '혼자', '아이와', '다시 가고 싶어요', '사진 맛집', '가성비']   # views.REVIEW_TAGS 와 같게

NICKS = ['바다좋아', '카페투어', '먹방여행', '느린여행자', '역사덕후', '사진찍는곰', '주말부산', '혼행러',
         '가족여행단', '산책왕', '야경사냥꾼', '시장탐방', '빵지순례', '한옥좋아', '드라이브', '뚜벅이',
         '노을맛집', '여행기록', '감성여행', '파도소리', '골목탐험', '맛집지도', '휴가중', '부산사랑']

# (성별, 나이대): 이 그룹이 좋아하는 컨셉 → 별점에 더하는 값. 같은 성별·나이대 가중 추천이 눈에 보이게 일부러 차이를 둠
GROUP_LIKES = {
    ('F', 20): {'카페': 1.2, '랜드마크': 0.7, '바다': 0.5, '역사': -1.2, '전통문화': -0.6},
    ('F', 30): {'카페': 0.8, '음식': 0.6, '자연': 0.4},
    ('M', 20): {'음식': 1.1, '쇼핑': 0.6, '바다': 0.4, '전통문화': -0.4},
    ('M', 30): {'음식': 0.7, '자연': 0.6, '바다': 0.3},
    ('F', 40): {'자연': 0.8, '공원': 0.6, '전통문화': 0.4},
    ('M', 40): {'역사': 1.2, '전통문화': 0.8, '자연': 0.5, '카페': -1.2, '랜드마크': -0.4},
    ('F', 50): {'공원': 0.8, '전통문화': 0.7, '자연': 0.6},
    ('M', 50): {'역사': 0.9, '전통문화': 0.9, '음식': 0.4},
}
# 회원 구성: (성별, 나이대) 순서대로 돌려 씀. None 은 성별·나이대를 안 넣은 회원 (맞춤 가중 없음)
# 시연에 쓰는 두 그룹(20대 여성 · 40대 남성)을 많이 둬서, 한 장소에 같은 그룹 리뷰가 2개 이상 쌓이게 함
MEMBER_GROUPS = [('F', 20), ('M', 40), ('F', 20), ('M', 40), ('M', 20), ('F', 30), ('F', 20), ('M', 40),
                 ('M', 30), ('F', 40), ('F', 20), ('M', 40), (None, None), ('M', 50), ('F', 50), ('M', 20),
                 ('F', 20), ('M', 40), (None, None), ('F', 30)]

GOOD = {
    '바다': ['바다 전망이 정말 좋아요', '파도 소리 들으며 산책하기 좋아요', '노을 질 때 꼭 가 보세요'],
    '카페': ['커피가 맛있고 분위기가 좋아요', '디저트가 예쁘고 맛있어요', '창가 자리 전망이 최고예요'],
    '음식': ['양이 많고 맛있어요', '현지인 맛집 느낌이에요', '줄 서도 먹을 만해요'],
    '역사': ['설명이 잘 되어 있어 공부가 돼요', '아이와 가기 좋은 역사 공간이에요', '천천히 둘러보기 좋아요'],
    '전통문화': ['한옥 분위기가 멋져요', '전통 체험이 재미있어요', '사진 찍기 좋은 골목이 많아요'],
    '자연': ['숲길 산책이 정말 좋아요', '풍경이 시원하게 트여 있어요', '공기가 맑고 조용해요'],
    '공원': ['산책하기 좋은 공원이에요', '잔디밭에서 쉬기 좋아요', '야경이 예뻐요'],
    '쇼핑': ['구경할 게 많아요', '기념품 사기 좋아요', '시장 먹거리가 다양해요'],
    '랜드마크': ['야경이 정말 멋져요', '전망대에서 본 풍경이 최고예요', '포토 스팟이 많아요'],
}
BAD = ['사람이 너무 많았어요', '주차가 불편했어요', '기대보다는 평범했어요', '가격이 조금 비싸요']
INTROS = ['처음 부산 가는 분께 추천하는 코스예요', '걷기 편하게 동선을 짰어요', '맛집 위주로 다닌 여행이에요',
          '아이와 함께 다녀온 코스예요', '바다를 실컷 본 여행이에요', '사진 찍기 좋은 곳만 모았어요']
COMMENTS = ['동선 참고할게요!', '저도 다음 주에 가요', '여기 카페 저도 좋았어요', '일정 짜는 데 도움 됐어요', '좋은 코스네요']


class Command(BaseCommand):
    help = '데모 회원·여행·리뷰·도움돼요·공유 루트·예산을 만든다 (아이디 demo_ 로 시작하는 회원만)'

    def add_arguments(self, parser):
        parser.add_argument('--members', type=int, default=40, help='데모 회원 수 (기본 40)')
        parser.add_argument('--seed', type=int, default=2026, help='같은 값이면 같은 데이터 (기본 2026)')
        parser.add_argument('--reset', action='store_true', help='데모 데이터를 지우고 다시 만든다')
        parser.add_argument('--clear', action='store_true', help='데모 데이터만 지우고 끝낸다')
        parser.add_argument('--summaries', action='store_true', help='리뷰 3개 이상 장소는 AI 키워드 요약까지 (LLM 호출)')

    def handle(self, *args, **opts):
        if opts['clear'] or opts['reset']:
            n = clear_demo()
            self.stdout.write(f'데모 회원 {n}명과 그 여행·리뷰를 지웠어요.')
            if opts['clear']:
                return
        if Member.objects.filter(user_id__startswith=DEMO_PREFIX).exists():
            self.stdout.write(self.style.WARNING('데모 데이터가 이미 있어요. 다시 만들려면 --reset 을 붙여 주세요.'))
            return

        rnd = random.Random(opts['seed'])
        spots = load_spots()
        if not spots:
            self.stdout.write(self.style.ERROR(f'장소 표를 못 읽었어요: {SPOTS_CSV}'))
            return

        with transaction.atomic():
            members = make_members(rnd, opts['members'])
            travels = make_travels(rnd, members, spots)
            reviews = make_reviews(rnd, travels)
            helpfuls = make_helpfuls(rnd, members, reviews)
            routes = make_routes(rnd, members, travels)
            budgets = make_budgets(rnd, travels)

        summaries = make_summaries(reviews) if opts['summaries'] else 0
        self.stdout.write(self.style.SUCCESS(
            f'데모 데이터: 회원 {len(members)} · 여행 {len(travels)} · 리뷰 {len(reviews)} · 도움돼요 {helpfuls} · '
            f'공유 루트 {routes} · 예산 {budgets}' + (f' · AI 요약 {summaries}' if opts['summaries'] else '')))
        self.stdout.write(f'로그인: {DEMO_PREFIX}01 (20대 여성), {DEMO_PREFIX}02 (40대 남성) / 비밀번호는 이 파일의 DEMO_PASSWORD')


# ---------------------------------------------------------------------------
# 지우기
# ---------------------------------------------------------------------------
def clear_demo():
    """demo_ 회원을 지우면 그 회원의 여행·일정·장소·리뷰·도움돼요·공유 루트·예산이 같이 지워진다 (CASCADE)."""
    qs = Member.objects.filter(user_id__startswith=DEMO_PREFIX)
    n = qs.count()
    qs.delete()
    return n


# ---------------------------------------------------------------------------
# 장소 표 읽기
# ---------------------------------------------------------------------------
def load_spots():
    """부산 장소 표 → [{concept, name, kind, addr, lat, lon, kakao_id}] (숙소는 일정 장소에서 뺌)"""
    if not SPOTS_CSV.exists():
        return []
    spots = []
    with open(SPOTS_CSV, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            concept = (row.get('컨셉') or '').strip()
            m = re.search(r'/(\d+)\s*$', row.get('카카오맵') or '')
            if not concept or concept == '숙소' or not m:
                continue
            try:
                lat, lon = float(row['위도']), float(row['경도'])
            except (TypeError, ValueError):
                continue
            spots.append({'concept': concept, 'name': row['이름'].strip(), 'addr': (row.get('주소') or '').strip(),
                          'lat': lat, 'lon': lon, 'kakao_id': m.group(1)})
    return spots


# ---------------------------------------------------------------------------
# 회원
# ---------------------------------------------------------------------------
def make_members(rnd, count):
    pwd = make_password(DEMO_PASSWORD)
    avatars = [a[0] for a in AVATAR_CHOICES]
    members = []
    for i in range(count):
        gender, age = MEMBER_GROUPS[i % len(MEMBER_GROUPS)]
        no = f'{i + 1:02d}'
        members.append(Member.objects.create(
            user_id=f'{DEMO_PREFIX}{no}', email=f'{DEMO_PREFIX}{no}@example.com', pwd=pwd,
            nickname=NICKS[i % len(NICKS)] + ('' if i < len(NICKS) else no), name=f'데모{no}',
            gender=gender, age_group=age, profile_img=rnd.choice(avatars),
        ))
    return members


# ---------------------------------------------------------------------------
# 여행 · 일정 · 장소 (지난 여행 2개 + 다가오는 여행 1개)
# ---------------------------------------------------------------------------
DAY_SLOTS = [(time(10, 0), 90), (time(12, 30), 60), (time(14, 30), 90), (time(17, 0), 60)]


def make_travels(rnd, members, spots):
    by_concept = {}
    for s in spots:
        by_concept.setdefault(s['concept'], []).append(s)
    concepts = list(by_concept)
    categories = {c.c_name: c for c in Category.objects.all()}
    today = date.today()
    travels = []
    for m in members:
        likes = GROUP_LIKES.get((m.gender, m.age_group), {})
        favorite = [c for c, v in sorted(likes.items(), key=lambda x: -x[1]) if v > 0] or concepts
        starts = [today - timedelta(days=rnd.randint(30, 70)), today - timedelta(days=rnd.randint(5, 25)),
                  today + timedelta(days=rnd.randint(7, 40))]
        for start in starts:
            days = rnd.choice([2, 2, 3])
            main = rnd.choice(favorite[:2]) if rnd.random() < .4 else rnd.choice(concepts)
            picks = [main, rnd.choice(concepts)]
            t = Travel.objects.create(
                member=m, t_day=start - timedelta(days=rnd.randint(3, 20)), t_place='부산',
                t_title=f'부산 {days - 1}박 {days}일 {main} 여행', t_way=rnd.choice(['CAR', 'public_transport']),
                t_start=start, t_end=start + timedelta(days=days - 1),
                t_budget=rnd.randrange(300000, 800001, 10000), start_time=time(9, 0),
            )
            for name in set(picks):
                if name in categories:
                    TravelCategory.objects.get_or_create(travel=t, category=categories[name])
            used = set()
            for d in range(days):
                sched = Schedule.objects.create(travel=t, s_day=start + timedelta(days=d))
                for order, (at, stay) in enumerate(DAY_SLOTS, start=1):
                    pool = by_concept.get('음식' if order == 2 else (main if order == 1 else rnd.choice(picks)), spots)
                    pool = [s for s in pool if s['kakao_id'] not in used] or [s for s in spots if s['kakao_id'] not in used]
                    if not pool:
                        break
                    s = rnd.choice(pool)
                    used.add(s['kakao_id'])
                    p = Place.objects.create(travel=t, p_name=s['name'], p_addr=s['addr'], p_lat=s['lat'], p_lon=s['lon'],
                                             p_kind=s['concept'], p_kakao_id=s['kakao_id'])
                    SchedulePlace.objects.create(schedule=sched, place=p, visit_order=order, stay_time=stay,
                                                 arrive_time=at, start_time=at, travel_time=rnd.choice([10, 15, 20, 25]))
            travels.append(t)
    return travels


# ---------------------------------------------------------------------------
# 리뷰 (다녀온 여행의 장소만, 회원·카카오 장소당 1개)
# ---------------------------------------------------------------------------
def _rating(rnd, member, concept):
    like = GROUP_LIKES.get((member.gender, member.age_group), {}).get(concept, 0)
    return max(1, min(5, round(3.6 + like + rnd.gauss(0, .7))))


def make_reviews(rnd, travels):
    today = date.today()
    reviews = []
    seen = set()
    for t in travels:
        if t.t_end >= today:
            continue
        for p in Place.objects.filter(travel=t):
            key = (t.member_id, p.p_kakao_id)
            if key in seen or rnd.random() > .85:
                continue
            seen.add(key)
            r = _rating(rnd, t.member, p.p_kind)
            text = rnd.choice(GOOD.get(p.p_kind, ['좋았어요']))
            if r <= 2:
                text = rnd.choice(BAD)
            elif r == 3:
                text = f'{text}. 다만 {rnd.choice(BAD)}'
            tags = rnd.sample(TAGS, rnd.choice([1, 1, 2]))
            if p.p_kind in ('카페', '랜드마크', '바다') and '사진 맛집' not in tags and rnd.random() < .5:
                tags.append('사진 맛집')
            rv = Review.objects.create(member=t.member, place=p, kakao_id=p.p_kakao_id, place_name=p.p_name,
                                       rating=r, content=text, tags=tags)
            # 작성일: 여행 끝난 뒤 1~7일 (auto_now_add라 만든 뒤 따로 고침)
            written = datetime.combine(t.t_end + timedelta(days=rnd.randint(1, 7)), time(rnd.randint(9, 22), rnd.randint(0, 59)))
            Review.objects.filter(pk=rv.pk).update(created_at=written)
            reviews.append(rv)
    return reviews


# ---------------------------------------------------------------------------
# 도움돼요 (별점 높은 리뷰일수록 많이)
# ---------------------------------------------------------------------------
def make_helpfuls(rnd, members, reviews):
    rows = []
    for rv in reviews:
        others = [m for m in members if m.m_id != rv.member_id]
        n = min(len(others), max(0, rv.rating * 2 - 3 + rnd.randint(-2, 3)))
        for m in rnd.sample(others, n):
            rows.append(ReviewHelpful(member=m, review=rv))
    ReviewHelpful.objects.bulk_create(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# 공유 루트 (다녀온 여행의 1/3쯤) + 별점·댓글
# ---------------------------------------------------------------------------
def make_routes(rnd, members, travels):
    today = date.today()
    count = 0
    for t in travels:
        if t.t_end >= today or rnd.random() > .35:
            continue
        route = SharedRoute.objects.create(travel=t, member=t.member, intro=rnd.choice(INTROS))
        others = [m for m in members if m.m_id != t.member_id]
        for m in rnd.sample(others, rnd.randint(0, 5)):
            RouteRating.objects.create(route=route, member=m, rating=rnd.choice([3, 4, 4, 5, 5]))
        for m in rnd.sample(others, rnd.randint(0, 3)):
            RouteComment.objects.create(route=route, member=m, content=rnd.choice(COMMENTS))
        count += 1
    return count


# ---------------------------------------------------------------------------
# 분류별 예산 (총예산을 분류로 나눔)
# ---------------------------------------------------------------------------
BUDGET_SPLIT = {'sight': .15, 'food': .30, 'cafe': .08, 'move': .17, 'stay': .25, 'shop': .05}


def make_budgets(rnd, travels):
    rows = []
    for t in travels:
        for cat, ratio in BUDGET_SPLIT.items():
            amount = int(t.t_budget * ratio * rnd.uniform(.8, 1.2)) // 1000 * 1000
            rows.append(TravelBudget(travel=t, category=cat, amount=amount))
    TravelBudget.objects.bulk_create(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# (선택) AI 키워드 요약 — 리뷰 3개 이상 장소만
# ---------------------------------------------------------------------------
def make_summaries(reviews):
    from sherpaapp.services.review_service import summarize_review
    counts = {}
    for rv in reviews:
        counts[rv.kakao_id] = counts.get(rv.kakao_id, 0) + 1
    done = 0
    for kid, n in counts.items():
        if n >= 3 and summarize_review(kid):
            done += 1
    return done
