from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password, check_password
from datetime import datetime, timedelta, time, date
import hashlib
import json
import logging
import random
import re
import secrets
from decimal import Decimal
import requests
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Exists, F, OuterRef, Prefetch, Q, Sum
from collections import Counter
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import Member, Review, ReviewHelpful
from .models import AVATAR_CHOICES, AVATAR_KEYS
from .models import AGE_GROUP_CHOICES
from .models import Travel
from .models import Place
from .models import Schedule
from .models import Pay
from .models import Category
from .models import SchedulePlace
from .services.schedule_service import (
    build_accommodation_candidate,
    generate_schedule,
    get_or_create_place,
    get_day_start_time,
    get_travel_day_plans,
    hours_badge as schedule_hours_badge,
    move_closed_pins,
    resolve_effective_accommodations,
)
from .services.review_service import summarize_review
from .services import chat_service
from .services import embed_service
from .services import transit_service
from .services import fare_service
from .services.photo_service import attach_photos, place_photo_url
from .services import festival_service
from .services import region_photo_service
from .services import hours_service
from .services import stay_rules
from .services import budget_service
from .services import rain_service
from .services import transit_service

logger = logging.getLogger(__name__)
from .services.route_service import get_kakao_route, get_travel_time
from .models import TravelCategory
from .models import TravelDayPlan
from .models import TravelBudget
from .models import TravelBudgetItem
from .models import BudgetLog
from .models import SharedRoute, RouteRating, RouteComment

# ==============================================
# 카카오 이미지 검색 공통 함수
# ==============================================
def _search_kakao_image(query):
    """장소명으로 대표 이미지 URL 1개를 조회한다."""
    query = (query or '').strip()
    if not query:
        return None

    headers = {
        'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}'
    }

    response = requests.get(
        'https://dapi.kakao.com/v2/search/image',
        headers=headers,
        params={'query': query, 'size': 1},
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    documents = data.get('documents', [])

    if not documents:
        return None

    return (
        documents[0].get('thumbnail_url')
        or documents[0].get('image_url')
    )


# ==============================================
# 카카오 장소 검색 공통 함수
# ==============================================
def _search_kakao_places(query, size=5):
    """카카오 장소 검색 + 대표 이미지 검색 결과를 공통 형식으로 반환한다."""
    query = (query or '').strip()
    if not query:
        return []

    headers = {
        'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}'
    }

    place_response = requests.get(
        'https://dapi.kakao.com/v2/local/search/keyword.json',
        headers=headers,
        params={'query': query, 'size': size},
        timeout=10,
    )
    place_response.raise_for_status()
    place_data = place_response.json()

    places = []

    for item in place_data.get('documents', []):
        place_name = item.get('place_name', '')
        image = None

        if place_name:
            try:
                image = _search_kakao_image(place_name)
            except requests.RequestException:
                # 이미지 조회 실패는 장소 검색 자체를 실패시키지 않는다.
                image = None

        places.append({
            'name': place_name,
            'kakao_id': item.get('id'),
            'address': item.get('road_address_name') or item.get('address_name'),
            'category': item.get('category_name'),
            'phone': item.get('phone'),
            'place_url': item.get('place_url'),
            'x': item.get('x'),
            'y': item.get('y'),
            'image': image,
        })

    return places


# 회원가입
def join(request):
    template = loader.get_template('sherpaapp/join.html')
    return HttpResponse(
        template.render({'avatars': AVATAR_CHOICES}, request))

# 로그인
def login(request):
    template = loader.get_template('sherpaapp/login.html')
    return HttpResponse(template.render({},request))


# 여행 생성
def travel_create(request):
    login_user = request.session.get('login_ok_user')

    # 로그인 확인
    if not login_user:
        return redirect('login')

    try:
        member = Member.objects.get(user_id=login_user)
    except Member.DoesNotExist:
        return redirect('login')

    return render(
        request,
        'sherpaapp/travel_create.html',
        {
            'member': member,
            **_parse_plan_query(request),
        }
    )

# 여행 목록
def travel_list(request):
    login_user = request.session.get('login_ok_user')
    if not login_user:
        return redirect('login')
    try:
        member = Member.objects.get(user_id=login_user)
    except Member.DoesNotExist:
        return redirect('login')
    travels = (Travel.objects.filter(member=member).order_by('-t_id'))
    return render(request,'sherpaapp/travel_list.html',{'member':member,'travels':travels})

# ==============================================
# 리뷰 게시판
# ==============================================

REVIEW_TAGS = ['가족과', '친구와', '연인과', '혼자', '아이와', '다시 가고 싶어요', '사진 맛집', '가성비']
REVIEW_PAGE_SIZE = 10
REVIEW_BEST_COUNT = 5
REVIEW_GROUPS = [
    ('place', '장소', 'place_name'),
    ('kind', '카테고리', 'place__p_kind'),
    ('region', '지역', 'place__travel__t_place'),
    ('tag', '태그', None),
]


# 거르는 함수
def _filter_reviews(reviews, by, v):
    if not by or not v:
        return reviews
    if by == 'tag':
        return reviews.filter(tags__contains=[v])
    for key, label, field in REVIEW_GROUPS:
        if key == by and field:
            return reviews.filter(**{field: v})
    return reviews


# 기준별 칩(값·개수) 목록
def _group_chips(by):
    if by == 'tag':
        counter = Counter()
        for tags in Review.objects.values_list('tags', flat=True):
            counter.update(tags or [])
        return [{'value': t, 'label': t, 'count': n} for t, n in counter.most_common()]

    # 2) 장소·카테고리·지역: DB에서 묶어서 센다 (GROUP BY)
    for key, label, field in REVIEW_GROUPS:
        if key == by and field:
            rows = (
                Review.objects
                .exclude(**{field + '__isnull': True})
                .values(field)
                .annotate(count=Count('rv_id'))
                .order_by('-count')
            )
            return [{'value': r[field], 'label': r[field], 'count': r['count']} for r in rows]

    # 3) 모르는 기준이면 칩 없음
    return []


def _login_member(request):
    login_user = request.session.get('login_ok_user')
    if not login_user:
        return None
    return Member.objects.filter(user_id=login_user).first()


def _reviews_with_counts(member):
    # 추천 수(helpful_count)와 내가 추천했는지(is_helped)를 함께 붙인 리뷰 목록
    return (
        Review.objects
        .select_related('member', 'place__travel')
        .annotate(
            helpful_count=Count('helpfuls', distinct=True),
            is_helped=Exists(
                ReviewHelpful.objects.filter(review=OuterRef('pk'), member=member)
            ),
        )
    )


# 리뷰 게시판 (사이드바 메뉴): 전체 리뷰 목록 + 옆에 추천 많은 리뷰
def review_board(request):
    member = _login_member(request)
    if not member:
        return redirect('login')

    # 기본은 '여행 루트' 탭, ?tab=places 면 예전 '장소 리뷰'
    if request.GET.get('tab') != 'places':
        return render(request, 'sherpaapp/review.html', {
            'member': member,
            'message': request.session.pop('review_message', ''),
            **_review_board_routes(request, member),
        })

    by = request.GET.get('by', '')
    v = request.GET.get('v', '')
    sort = request.GET.get('sort','helpful')
    reviews = _reviews_with_counts(member)
    reviews = _filter_reviews(reviews, by, v)
    if sort == 'new':
        reviews = reviews.order_by('-created_at', '-rv_id')
    elif sort == 'rating':
        reviews = reviews.order_by('-rating', '-helpful_count', '-created_at', '-rv_id')
    else:
        reviews = reviews.order_by('-helpful_count', '-created_at', '-rv_id')
    page = Paginator(reviews, REVIEW_PAGE_SIZE).get_page(request.GET.get('page'))
    page_numbers = page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1)
    best_reviews = (
        _reviews_with_counts(member)
        .filter(helpful_count__gt=0)
        .order_by('-helpful_count', '-rating', '-created_at')[:REVIEW_BEST_COUNT]
    )

    return render(request, 'sherpaapp/review.html', {
        'member': member,
        'page': page,
        'best_reviews': best_reviews,
        'review_total': page.paginator.count,
        'message': request.session.pop('review_message', ''),
        'tab': 'places',
        'tags': REVIEW_TAGS,   # 내 리뷰 고치기 창의 태그
        'groups': REVIEW_GROUPS,
        'by': by,
        'v': v,
        'sort': sort,
        'page_numbers': page_numbers,
        'chips': _group_chips(by),
    })


# ==============================================
# 여행 루트 공유 (리뷰 게시판 '여행 루트' 탭)
# ==============================================

ROUTE_PAGE_SIZE = 12
ROUTE_INTRO_MAX = 200
ROUTE_COMMENT_MAX = 300


def _trip_length_text(travel):
    if not travel.t_start or not travel.t_end:
        return ''
    days = (travel.t_end - travel.t_start).days + 1
    return '당일치기' if days <= 1 else '%d박 %d일' % (days - 1, days)


def _routes_with_stats():
    return (
        SharedRoute.objects
        .select_related('travel', 'member')
        .annotate(
            avg_rating=Avg('ratings__rating'),
            rating_count=Count('ratings', distinct=True),
            comment_count=Count('comments', distinct=True),
        )
    )


def _route_cards(routes):
    """게시판 카드에 쓸 값: 기간 글자, 장소 수, 앞쪽 장소 이름 몇 개, 표지 사진"""
    travel_ids = [r.travel_id for r in routes]
    by_travel = {}
    rows = (
        SchedulePlace.objects
        .filter(schedule__travel_id__in=travel_ids)
        .select_related('place', 'schedule')
        .order_by('schedule__s_day', 'visit_order', 'sp_id')
    )
    for sp in rows:
        by_travel.setdefault(sp.schedule.travel_id, []).append(sp.place)

    cards = []
    for r in routes:
        places = by_travel.get(r.travel_id, [])
        # 표지: 여행 지역 대표 사진 (없으면 루트 안 첫 장소 사진)
        cover = region_photo_service.region_cover(r.travel.t_place) or next(
            (p.p_image for p in places if p.p_image and str(p.p_image).startswith('http')), '')
        cards.append({
            'route': r,
            'travel': r.travel,
            'length': _trip_length_text(r.travel),
            'place_count': len(places),
            'preview': [p.p_name for p in places[:4]],
            'more': max(len(places) - 4, 0),
            'cover': cover,
            'avg': ('%.1f' % r.avg_rating) if r.avg_rating else '',
        })
    return cards


def _review_board_routes(request, member):
    sort = request.GET.get('sort') or 'new'
    q = (request.GET.get('q') or '').strip()

    routes = _routes_with_stats()
    if q:
        routes = routes.filter(Q(travel__t_place__icontains=q) | Q(travel__t_title__icontains=q))
    if sort == 'best':
        routes = routes.order_by(F('avg_rating').desc(nulls_last=True), '-rating_count', '-created_at')
    elif sort == 'talk':
        routes = routes.order_by('-comment_count', '-created_at')
    else:
        sort = 'new'
        routes = routes.order_by('-created_at', '-sr_id')

    page = Paginator(routes, ROUTE_PAGE_SIZE).get_page(request.GET.get('page'))
    return {
        'tab': 'routes',
        'sort': sort,
        'q': q,
        'route_page': page,
        'route_cards': _route_cards(list(page.object_list)),
        'route_total': page.paginator.count,
        # '내 여행 공유하기' 목록 (공유 중인지 표시)
        'my_travels': (
            Travel.objects.filter(member=member)
            .annotate(is_shared=Exists(SharedRoute.objects.filter(travel=OuterRef('pk'))))
            .order_by('-t_start', '-t_id')[:20]
        ),
    }


def _route_days(travel):
    """루트 상세: 날짜별 장소(방문·출발 시간, 머무는 시간, 이동 시간) + 그날 숙소"""
    stays = {dp.plan_date: dp for dp in TravelDayPlan.objects.filter(travel=travel)}
    days = []
    schedules = Schedule.objects.filter(travel=travel).order_by('s_day')
    for index, schedule in enumerate(schedules, start=1):
        items = []
        sps = (
            SchedulePlace.objects.filter(schedule=schedule)
            .select_related('place')
            .order_by('visit_order', 'sp_id')
        )
        for sp in sps:
            p = sp.place
            items.append({
                'name': p.p_name,
                'kind': p.p_kind or '',
                'addr': p.p_addr or '',
                'image': p.p_image if p.p_image and str(p.p_image).startswith('http') else '',
                'arrive': sp.arrive_time.strftime('%H:%M') if sp.arrive_time else '',
                'leave': sp.start_time.strftime('%H:%M') if sp.start_time else '',
                'stay': sp.stay_time_display if sp.stay_time else '',
                'move': sp.travel_time or 0,
                'lat': float(p.p_lat) if p.p_lat is not None else None,
                'lon': float(p.p_lon) if p.p_lon is not None else None,
            })
        stay = stays.get(schedule.s_day)
        days.append({
            'no': index,
            'date': schedule.s_day,
            'weekday': '월화수목금토일'[schedule.s_day.weekday()],
            'items': items,
            'stay': stay.accommodation_name if stay and stay.accommodation_name else '',
        })
    return days


# 홈 '여행 루트 추천' 카드: 별점 높고 반응 많은 공유 루트 몇 개
def build_route_picks(limit=3):
    routes = list(
        _routes_with_stats()
        .order_by(F('avg_rating').desc(nulls_last=True), '-rating_count', '-comment_count', '-created_at')[:limit]
    )
    picks = []
    for c in _route_cards(routes):
        r = c['route']
        picks.append({
            'title': c['travel'].t_title,
            'region': c['travel'].t_place,
            'length': c['length'],
            'rating': c['avg'],
            'rating_count': r.rating_count,
            'comment_count': r.comment_count,
            'owner': r.member.nickname,
            'route': ' → '.join(c['preview']) + (' 외 %d곳' % c['more'] if c['more'] else ''),
            'url': reverse('route_detail', args=[r.sr_id]),
        })
    return picks


# 여행 루트 상세 (게시판 카드를 누르면): DAY별 루트 + 지도 + 별점 + 댓글
def route_detail(request, sr_id):
    member = _login_member(request)
    if not member:
        return redirect('login')

    route = get_object_or_404(_routes_with_stats(), sr_id=sr_id)
    travel = route.travel
    days = _route_days(travel)
    mine = RouteRating.objects.filter(route=route, member=member).first()

    map_days = [
        {'no': d['no'], 'points': [
            {'name': it['name'], 'lat': it['lat'], 'lon': it['lon']}
            for it in d['items'] if it['lat'] is not None and it['lon'] is not None
        ]}
        for d in days
    ]

    return render(request, 'sherpaapp/route_detail.html', {
        'member': member,
        'route': route,
        'travel': travel,
        'length': _trip_length_text(travel),
        'days': days,
        'place_count': sum(len(d['items']) for d in days),
        'map_days': map_days,
        'avg': ('%.1f' % route.avg_rating) if route.avg_rating else '',
        'my_rating': mine.rating if mine else 0,
        'is_owner': route.member_id == member.m_id,
        'comments': route.comments.select_related('member').order_by('created_at'),
        'comment_max': ROUTE_COMMENT_MAX,
        'message': request.session.pop('route_message', ''),
        'KAKAO_MAP_API_KEY': settings.KAKAO_MAP_API_KEY,
    })


# 내 여행을 게시판에 공유 / 소개 수정 / 공유 취소 (여행 상세의 '게시판에 공유' 창, JSON)
@require_POST
def route_share(request, travel_id):
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    travel = Travel.objects.filter(t_id=travel_id).first()
    if not travel:
        return JsonResponse({'success': False, 'message': '여행을 찾을 수 없습니다.'}, status=404)
    if travel.member_id != member.m_id:
        return JsonResponse({'success': False, 'message': '내 여행만 공유할 수 있어요.'}, status=403)

    if request.POST.get('action') == 'unshare':
        SharedRoute.objects.filter(travel=travel).delete()
        return JsonResponse({'success': True, 'shared': False})

    intro = (request.POST.get('intro') or '').strip()
    if len(intro) > ROUTE_INTRO_MAX:
        return JsonResponse({'success': False, 'message': '소개는 %d자까지 쓸 수 있어요.' % ROUTE_INTRO_MAX}, status=400)
    if not SchedulePlace.objects.filter(schedule__travel=travel).exists():
        return JsonResponse({'success': False, 'message': '일정에 장소를 하나 이상 넣어야 공유할 수 있어요.'}, status=400)

    route, _ = SharedRoute.objects.update_or_create(
        travel=travel, defaults={'member': member, 'intro': intro}
    )
    return JsonResponse({
        'success': True, 'shared': True, 'sr_id': route.sr_id,
        'url': reverse('route_detail', args=[route.sr_id]),
    })


# 별점 주기/바꾸기 (한 사람 1개, 내 루트에는 못 줌, JSON)
@require_POST
def route_rate(request, sr_id):
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    route = SharedRoute.objects.filter(sr_id=sr_id).first()
    if not route:
        return JsonResponse({'success': False, 'message': '공유된 루트를 찾을 수 없습니다.'}, status=404)
    if route.member_id == member.m_id:
        return JsonResponse({'success': False, 'message': '내 루트에는 별점을 줄 수 없어요.'}, status=400)

    try:
        rating = int(request.POST.get('rating') or 0)
    except ValueError:
        rating = 0
    if not 1 <= rating <= 5:
        return JsonResponse({'success': False, 'message': '별점은 1~5점이에요.'}, status=400)

    RouteRating.objects.update_or_create(route=route, member=member, defaults={'rating': rating})
    stats = route.ratings.aggregate(avg=Avg('rating'), count=Count('rr_id'))
    return JsonResponse({
        'success': True, 'mine': rating,
        'avg': '%.1f' % (stats['avg'] or 0), 'count': stats['count'],
    })


# 댓글 쓰기 (폼 POST → 상세로 돌아감)
@require_POST
def route_comment(request, sr_id):
    member = _login_member(request)
    if not member:
        return redirect('login')

    route = get_object_or_404(SharedRoute, sr_id=sr_id)
    content = (request.POST.get('content') or '').strip()
    if not content:
        request.session['route_message'] = '댓글 내용을 적어 주세요.'
    elif len(content) > ROUTE_COMMENT_MAX:
        request.session['route_message'] = '댓글은 %d자까지 쓸 수 있어요.' % ROUTE_COMMENT_MAX
    else:
        RouteComment.objects.create(route=route, member=member, content=content)
    return redirect(reverse('route_detail', args=[route.sr_id]) + '#comments')


# 댓글 지우기 (내 댓글, 또는 내 루트에 달린 댓글)
@require_POST
def route_comment_delete(request, rc_id):
    member = _login_member(request)
    if not member:
        return redirect('login')

    comment = get_object_or_404(RouteComment.objects.select_related('route'), rc_id=rc_id)
    if member.m_id not in (comment.member_id, comment.route.member_id):
        return HttpResponseForbidden('권한이 없습니다.')
    sr_id = comment.route.sr_id
    comment.delete()
    return redirect(reverse('route_detail', args=[sr_id]) + '#comments')


# 내가 다녀온 곳(시작한 여행의 장소) 중 아직 리뷰 안 쓴 곳
def _reviewable_places(member):
    reviewed = Review.objects.filter(member=member, place__isnull=False).values('place_id')
    # 같은 카카오 장소는 한 사람당 리뷰 1개 (다른 여행에서 또 간 곳도 빠짐)
    reviewed_kakao = (
        Review.objects.filter(member=member, kakao_id__isnull=False)
        .exclude(kakao_id='')
        .values_list('kakao_id', flat=True)
    )
    # 두 표의 글자 정렬 방식(collation)이 달라 SQL 안에서 비교하면 오류 -> 목록으로 먼저 꺼냄
    reviewed_kakao = list(reviewed_kakao)
    return (
        Place.objects
        .filter(travel__member=member, travel__t_start__lte=date.today())
        .exclude(p_id__in=reviewed)
        .exclude(p_kakao_id__in=reviewed_kakao)
        .select_related('travel')
        .order_by('-travel__t_start', 'travel_id', 'p_name')
    )


# 리뷰 쓰기: GET 화면, POST 저장
def review_write(request):
    member = _login_member(request)
    if not member:
        return redirect('login')

    places = list(_reviewable_places(member))
    form = {'place_id': '', 'rating': '', 'content': '', 'tags': []}
    error = ''

    if request.method == 'POST':
        form = {
            'place_id': (request.POST.get('place_id') or '').strip(),
            'rating': (request.POST.get('rating') or '').strip(),
            'content': (request.POST.get('content') or '').strip(),
            'tags': [t for t in request.POST.getlist('tags') if t in REVIEW_TAGS],
        }
        place = next((p for p in places if str(p.p_id) == form['place_id']), None)

        try:
            rating = int(form['rating'])
        except ValueError:
            rating = 0

        if not place:
            error = '리뷰를 쓸 장소를 골라 주세요.'
        elif not 1 <= rating <= 5:
            error = '별점을 1~5개 중에서 골라 주세요.'
        elif not form['content']:
            error = '리뷰 내용을 적어 주세요.'
        elif len(form['content']) > 100:
            error = '리뷰는 100자까지 쓸 수 있어요.'
        else:
            Review.objects.create(
                member=member,
                place=place,
                kakao_id=place.p_kakao_id or None,
                place_name=place.p_name,
                rating=rating,
                content=form['content'],
                tags=form['tags'],
            )
            request.session['review_message'] = "'%s' 리뷰를 올렸어요." % place.p_name
            return redirect('review_board')

    # 여행별로 묶어서 고르기 쉽게
    groups = []
    for p in places:
        if not groups or groups[-1]['travel'].t_id != p.travel.t_id:
            groups.append({'travel': p.travel, 'places': []})
        groups[-1]['places'].append(p)

    return render(request, 'sherpaapp/review_write.html', {
        'member': member,
        'groups': groups,
        'tags': REVIEW_TAGS,
        'form': form,
        'error': error,
    })


def _review_back(request):
    """장소 리뷰 탭의 보던 페이지로 돌아가는 주소"""
    url = reverse('review_board') + '?tab=places'
    page = (request.POST.get('page') or '').strip()
    return url + ('&page=%s' % page if page.isdigit() else '')


# 내 장소 리뷰 고치기 (폼 POST → 게시판으로). 남의 리뷰는 고칠 수 없음
@require_POST
def review_update(request, rv_id):
    member = _login_member(request)
    if not member:
        return redirect('login')

    review = get_object_or_404(Review, rv_id=rv_id)
    if review.member_id != member.m_id:
        return HttpResponseForbidden('내 리뷰만 고칠 수 있어요.')

    try:
        rating = int(request.POST.get('rating') or 0)
    except ValueError:
        rating = 0
    content = (request.POST.get('content') or '').strip()
    tags = [t for t in request.POST.getlist('tags') if t in REVIEW_TAGS]

    if not 1 <= rating <= 5:
        message = '별점을 1~5개 중에서 골라 주세요.'
    elif not content:
        message = '리뷰 내용을 적어 주세요.'
    elif len(content) > 100:
        message = '리뷰는 100자까지 쓸 수 있어요.'
    else:
        review.rating = rating
        review.content = content
        review.tags = tags
        review.save(update_fields=['rating', 'content', 'tags'])
        message = "'%s' 리뷰를 고쳤어요." % review.place_name

    request.session['review_message'] = message
    return redirect(_review_back(request))


# 내 장소 리뷰 지우기 (추천도 같이 지워짐). 남의 리뷰는 지울 수 없음
@require_POST
def review_delete(request, rv_id):
    member = _login_member(request)
    if not member:
        return redirect('login')

    review = get_object_or_404(Review, rv_id=rv_id)
    if review.member_id != member.m_id:
        return HttpResponseForbidden('내 리뷰만 지울 수 있어요.')

    name = review.place_name
    review.delete()
    request.session['review_message'] = "'%s' 리뷰를 지웠어요." % name
    return redirect(_review_back(request))


# 홈 '여행 리뷰 추천' 카드: 지역별로 묶어 평점 높고 리뷰 많은 순
def build_review_picks(limit=3):
    regions = (
        Review.objects
        .filter(place__isnull=False)
        .values('place__travel__t_place')
        .annotate(avg=Avg('rating'), n=Count('rv_id'))
        .order_by('-avg', '-n', 'place__travel__t_place')[:limit]
    )

    picks = []
    for row in regions:
        region = row['place__travel__t_place']
        in_region = Review.objects.filter(place__travel__t_place=region)

        # 그 지역에서 리뷰가 가장 많은 장소
        top_place = (
            in_region.values('place_name')
            .annotate(n=Count('rv_id'))
            .order_by('-n', 'place_name')
            .first()
        )

        # 한 줄 후기: 추천 많고 별점 높은 리뷰
        best = (
            in_region.annotate(helpful_count=Count('helpfuls'))
            .order_by('-helpful_count', '-rating', '-created_at')
            .first()
        )

        picks.append({
            'region': region,
            'place': top_place['place_name'] if top_place else '',
            'rating': '%.1f' % row['avg'],
            'count': row['n'],
            'quote': best.content if best else '',
            'url': reverse('review_board'),
        })

    return picks


# 리뷰 추천 누르기/취소 (POST, JSON)
@require_POST
def review_helpful(request, rv_id):
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    review = Review.objects.filter(rv_id=rv_id).first()
    if not review:
        return JsonResponse({'success': False, 'message': '없는 리뷰예요.'}, status=404)
    if review.member_id == member.m_id:
        return JsonResponse({'success': False, 'message': '내 리뷰는 추천할 수 없어요.'}, status=400)

    mine = ReviewHelpful.objects.filter(member=member, review=review)
    if mine.exists():
        mine.delete()
        helped = False
    else:
        ReviewHelpful.objects.get_or_create(member=member, review=review)
        helped = True

    return JsonResponse({
        'success': True,
        'helped': helped,
        'count': ReviewHelpful.objects.filter(review=review).count(),
    })

# 일정 관리 (사이드바 메뉴)
# 가장 최근 여행의 일정으로 보내고, 여행이 하나도 없으면 안내 카드를 보여준다.
def schedule_manage(request):
    login_user = request.session.get('login_ok_user')
    if not login_user:
        return redirect('login')
    try:
        member = Member.objects.get(user_id=login_user)
    except Member.DoesNotExist:
        return redirect('login')

    travel = Travel.objects.filter(member=member).order_by('-t_id').first()
    if travel:
        return redirect('travel_detail', travel_id=travel.t_id)

    return render(request, 'sherpaapp/schedule_empty.html', {'member': member})

# 여행 상세
def travel_detail(request, travel_id):
    travel = get_object_or_404(Travel, t_id=travel_id)

    login_user = request.session.get('login_ok_user')
    member = None
    if login_user:
        try:
            member = Member.objects.get(user_id=login_user)
        except Member.DoesNotExist:
            member = None

    # DAY 단위 일정. 장소 정보는 SchedulePlace를 통해 조회한다.
    schedules = (
        Schedule.objects
        .filter(travel=travel)
        .order_by('s_day', 's_id')
    )

    schedule_places = (
        SchedulePlace.objects
        .filter(schedule__travel=travel)
        .select_related('schedule', 'place')
        .order_by('schedule__s_day', 'visit_order', 'sp_id')
    )

    # 여행 기간별 DAY 정보 생성
    days = []
    travel_days = 0

    if travel.t_start and travel.t_end:
        current_date = travel.t_start
        day_number = 1

        while current_date <= travel.t_end:
            day_schedules = [
                schedule
                for schedule in schedules
                if schedule.s_day == current_date
            ]

            days.append({
                'day_number': day_number,
                'date': current_date,
                'schedules': day_schedules,
            })

            current_date += timedelta(days=1)
            day_number += 1

        travel_days = len(days)

    # 중복 없이 방문 장소 목록 생성
    visited_places = []
    visited_place_ids = set()

    for schedule_place in schedule_places:
        place = schedule_place.place
        if place and place.p_id not in visited_place_ids:
            visited_place_ids.add(place.p_id)
            visited_places.append(place)

    context = {
        'travel': travel,
        'member': member,
        # 리뷰 게시판 '여행 루트'에 공유했는지 (공유 버튼·창)
        'shared_route': SharedRoute.objects.filter(travel=travel).first(),
        # 위쪽 '다른 여행으로 이동' 선택 칸 (내 여행만, 최근 출발 순)
        'my_travels': (
            Travel.objects.filter(member=member).order_by('-t_start', '-t_id')
            if member else Travel.objects.none()
        ),
        'schedules': schedules,
        'days': days,
        'visited_places': visited_places,
        'travel_days': travel_days,
        'place_count': len(visited_places),
        'KAKAO_MAP_API_KEY': settings.KAKAO_MAP_API_KEY,
        # 대중교통 경로는 서버(/transit_route/, 카카오)에서 받으므로 ODsay 키는 더 이상 넘기지 않음 (11/06 결정)
    }

    return render(request, 'sherpaapp/travel_detail.html', context)


# ==============================================
# 여행 DAY 상세 AJAX
# ==============================================

def travel_detail_day(
    request,
    travel_id,
    day
):

    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )


    schedules = (
        Schedule.objects
        .filter(
            travel=travel
        )
        .order_by(
            's_day'
        )
    )


    # 일정 없음
    if not schedules.exists():

        return JsonResponse({
            'success':
                False,

            'message':
                '등록된 여행 일정이 없습니다.'
        })


    # DAY 범위 확인
    if (
        day < 1
        or
        day > schedules.count()
    ):

        return JsonResponse({
            'success':
                False,

            'message':
                '존재하지 않는 DAY입니다.'
        })


    schedule = schedules[
        day - 1
    ]


    # ==========================================
    # 일정 장소
    # ==========================================

    schedule_places = (
        SchedulePlace.objects
        .filter(
            schedule=schedule
        )
        .select_related(
            'place'
        )
        .order_by(
            'visit_order'
        )
    )


    # ==========================================
    # 해당 DAY 비용
    # ==========================================

    pays = (
        Pay.objects
        .filter(
            schedule=schedule
        )
        .select_related(
            'place'
        )
    )


    total_pay = sum(
        pay.pay_pay or 0
        for pay in pays
    )


    # ==========================================
    # 장소 데이터
    # ==========================================

    places = []


    for sp in schedule_places:

        place = sp.place
        place_image = getattr(place, 'p_image', '') or ''

        # 자동 생성 일정처럼 이미지가 비어 있는 장소는
        # DAY 조회 시 카카오 이미지 API로 한 번 조회하고 DB에 캐시한다.
        if not place_image and place.p_name:
            try:
                image_query = (
                    f"{place.p_name} {place.p_addr or ''}"
                ).strip()

                if place.p_kakao_id:
                    place_image = place_photo_url(place)
                else:
                    place_image = (
                        _search_kakao_image(image_query)
                        or _search_kakao_image(place.p_name)
                        or ''
                    )

                if place_image and hasattr(place, 'p_image'):
                    place.p_image = place_image
                    place.save(update_fields=['p_image'])

            except requests.RequestException:
                place_image = ''

        places.append({

            'sp_id':
                sp.sp_id,

            'visit_order':
                sp.visit_order,

            'arrive_time': (
                sp.arrive_time.strftime(
                    '%H:%M'
                )
                if sp.arrive_time
                else ''
            ),

            'stay_time':
                sp.stay_time,

            'start_time': (
                sp.start_time.strftime(
                    '%H:%M'
                )
                if sp.start_time
                else ''
            ),

            'travel_time':
                sp.travel_time,

            'place_id':
                sp.place.p_id,

            'place_name':
                sp.place.p_name,

            'place_addr':
                sp.place.p_addr,

            'place_kind':
                sp.place.p_kind,

            'place_image':
                place_image,

            # 비 오는 날 근처 실내 대안을 찾을 때 씀 (🟦, 추가 키)
            'place_lat':
                _float_or_none(sp.place.p_lat),

            'place_lon':
                _float_or_none(sp.place.p_lon),
        })


    # ==========================================
    # 비용 데이터
    # ==========================================

    payments = []


    for pay in pays:

        payments.append({

            'pay_id':
                pay.pay_id,

            'pay_context':
                pay.pay_context,

            'pay_pay':
                pay.pay_pay,

            'place_id': (
                pay.place.p_id
                if pay.place
                else None
            ),

            'place_name': (
                pay.place.p_name
                if pay.place
                else ''
            )
        })


    return JsonResponse({

        'success':
            True,

        'travel_id':
            travel_id,

        'day':
            day,

        'schedule_id':
            schedule.s_id,

        's_day':
            schedule.s_day.strftime(
                '%Y.%m.%d'
            ),

        'places':
            places,

        'pays':
            payments,

        'total_pay':
            total_pay
    })


# ==============================================
# 여행 수정
# ==============================================

def travel_update(
    request,
    travel_id
):

    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )


    login_user = request.session.get(
        'login_ok_user'
    )


    member = None


    if login_user:

        try:

            member = Member.objects.get(
                user_id=login_user
            )

        except Member.DoesNotExist:

            member = None


    # ==========================================
    # 수정 저장
    # ==========================================

    if request.method == 'POST':

        travel.t_title = (
            request.POST.get(
                't_title'
            )
        )


        travel.t_place = (
            request.POST.get(
                't_place'
            )
        )


        travel.t_start = (
            request.POST.get(
                't_start'
            )
        )


        travel.t_end = (
            request.POST.get(
                't_end'
            )
        )


        traffic = ','.join(
            request.POST.getlist(
                'traffic'
            )
        )


        travel.t_way = (
            traffic
        )


        travel.t_day = (
            request.POST.get(
                't_start'
            )
        )


        travel.save()


        return redirect(
            'travel_detail',
            travel_id=travel.t_id
        )


    return render(
        request,
        'sherpaapp/travel_update.html',
        {
            'travel':
                travel,

            'member':
                member
        }
    )


# ==============================================
# 여행 정보·날짜 수정 (일정 상세의 '여행 수정' 팝업, POST → JSON)
# - 날짜를 옮기면 DAY별 일정(Schedule)·숙소(TravelDayPlan)도 같은 만큼 함께 옮김 (DAY 1은 계속 DAY 1)
# - 기간이 늘면 뒤에 빈 날이 생기고, 줄면 잘리는 날의 일정을 지움
#   잘리는 날에 장소·비용이 있으면 confirm=1 없이는 지우지 않고 무엇이 지워지는지 돌려줌
# ==============================================

# ==============================================
# 여행 기간 축제·행사 (여행 상세 왼쪽 목록, JSON)
# ==============================================

def travel_festivals(request, travel_id):
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    travel = Travel.objects.filter(t_id=travel_id).first()
    if not travel:
        return JsonResponse({'success': False, 'message': '여행을 찾을 수 없습니다.'}, status=404)
    if travel.member_id != member.m_id:
        return JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)

    places = Place.objects.filter(travel=travel).only('p_lat', 'p_lon')
    try:
        festivals = festival_service.festivals_for_travel(travel, places)
    except Exception:
        # 축제 목록은 덤이라, 실패해도 화면은 그대로 쓰게 빈 목록
        logger.exception('축제 목록 실패 travel=%s', travel_id)
        festivals = []

    # 축제 진행 시간 (time 원문, open·close 'HH:MM') - 실패해도 목록은 보여준다
    try:
        festivals = hours_service.festival_times(festivals, travel.t_start.month if travel.t_start else None)
    except Exception:
        logger.exception('축제 시간 실패 travel=%s', travel_id)

    # 축제 요금 (fee: 1인 금액 × 비용 관리 인원) - 실패해도 목록은 보여준다
    try:
        festivals = budget_service.festival_fees(festivals, _budget_people(request, travel.t_id))
    except Exception:
        logger.exception('축제 요금 실패 travel=%s', travel_id)

    return JsonResponse({'success': True, 'festivals': festivals})


# 비용 관리: 예산 금액 변경 기록 최근 10줄 (트리거가 budget_log 에 적은 것)
def budget_log(request, travel_id):
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    travel = Travel.objects.filter(t_id=travel_id).first()
    if not travel:
        return JsonResponse({'success': False, 'message': '여행을 찾을 수 없습니다.'}, status=404)
    if travel.member_id != member.m_id:
        return JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)

    rows = BudgetLog.objects.filter(travel_id=travel_id)[:10]     # Meta ordering 이 '-bl_id' 라 최신이 위
    logs = [{
        'name': row.p_name,
        'action': row.action,
        'old': row.old_amount,
        'new': row.new_amount,
        'at': row.changed_at.strftime('%Y-%m-%d %H:%M'),
    } for row in rows]

    return JsonResponse({'success': True, 'logs': logs})


# 여행 상세: 그날 일정 장소들의 운영시간 (관광공사 + 식당·카페는 보통 영업시간 예상)
# 화면이 일정을 그린 뒤 따로 불러서, 운영시간 밖이면 알려 주고 드래그할 때 회색으로 표시
def travel_hours(request, travel_id, day):
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    travel = Travel.objects.filter(t_id=travel_id).first()
    if not travel:
        return JsonResponse({'success': False, 'message': '여행을 찾을 수 없습니다.'}, status=404)
    if travel.member_id != member.m_id:
        return JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)

    schedules = list(Schedule.objects.filter(travel=travel).order_by('s_day'))
    if day < 1 or day > len(schedules):
        return JsonResponse({'success': False, 'message': '존재하지 않는 DAY입니다.'}, status=404)
    schedule = schedules[day - 1]

    sps = SchedulePlace.objects.filter(schedule=schedule).select_related('place')
    try:
        hours = hours_service.schedule_hours(sps, schedule.s_day)
    except Exception:
        logger.exception('운영시간 실패 travel=%s day=%s', travel_id, day)
        hours = {}

    return JsonResponse({
        'success': True,
        'day': day,
        'date': schedule.s_day.isoformat(),
        'places': {str(k): v for k, v in hours.items()},
    })


def _time_minutes(value):
    """TimeField 값 → 분 (없으면 None)"""
    return value.hour * 60 + value.minute if value else None


# 여행 상세 '운영시간에 맞추기' 버튼 (🟦 hours_service.fit_stay, 11/06 결정)
# POST → 그날 장소마다 마감을 넘는 체류를 마감 시각까지로 줄임 (뒤 일정 시각은 그대로)
#   {success, day, changed: [{sp_id, name, before, after, message}],
#    warnings: [{sp_id, name, status, message}]}   (warnings: 마감 직전 도착·휴무처럼 체류로는 못 맞추는 곳)
def travel_fit_hours(request, travel_id, day):
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '허용되지 않는 요청입니다.'}, status=405)

    travel = Travel.objects.filter(t_id=travel_id).first()
    if not travel:
        return JsonResponse({'success': False, 'message': '여행을 찾을 수 없습니다.'}, status=404)
    if travel.member_id != member.m_id:
        return JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)

    schedules = list(Schedule.objects.filter(travel=travel).order_by('s_day'))
    if day < 1 or day > len(schedules):
        return JsonResponse({'success': False, 'message': '존재하지 않는 DAY입니다.'}, status=404)
    schedule = schedules[day - 1]

    def places():
        return list(
            SchedulePlace.objects.filter(schedule=schedule)
            .select_related('place').order_by('visit_order', 'sp_id')
        )

    try:
        hours = hours_service.schedule_hours(places(), schedule.s_day)
    except Exception:
        logger.exception('운영시간 실패 travel=%s day=%s', travel_id, day)
        return JsonResponse({'success': False, 'message': '운영시간을 불러오지 못했어요.'}, status=502)

    # 마감을 넘는 체류만 마감 시각까지 줄이고 그 장소 떠나는 시각만 고친다.
    # 뒤 일정 시각은 그대로 둔다 (다시 계산하면 점심·저녁이 앞으로 당겨짐 → 빈 시간은 자유 시간)
    changed = []
    with transaction.atomic():
        for sp in places():
            fit = hours_service.fit_stay(
                sp.place.p_kind, hours.get(sp.sp_id), _time_minutes(sp.arrive_time), sp.stay_time,
            )
            if fit['status'] != 'shortened' or fit['stay'] == sp.stay_time:
                continue
            changed.append({
                'sp_id': sp.sp_id, 'name': sp.place.p_name,
                'before': sp.stay_time or 60, 'after': fit['stay'], 'message': fit['message'],
            })
            sp.stay_time = fit['stay']
            sp.start_time = (
                datetime.combine(schedule.s_day, sp.arrive_time) + timedelta(minutes=fit['stay'])
            ).time()
            sp.save(update_fields=['stay_time', 'start_time'])

    warnings = []
    for sp in places():
        fit = hours_service.fit_stay(
            sp.place.p_kind, hours.get(sp.sp_id), _time_minutes(sp.arrive_time), sp.stay_time,
        )
        if fit['status'] in ('late', 'closed'):
            warnings.append({
                'sp_id': sp.sp_id, 'name': sp.place.p_name,
                'status': fit['status'], 'message': fit['message'],
            })

    return JsonResponse({
        'success': True,
        'day': day,
        'changed': changed,
        'warnings': warnings,
    })


# 여행 상세: 그날 장소마다 AI 예상 비용 (여행 만들 때와 같은 가격 × 비용 관리에서 계산한 인원) — 🟦 예산 AI
# GET → {success, day, people, places: {sp_id: cost}, planned, by}  (cost 모양은 mock.json places.items[].cost)
def travel_costs(request, travel_id, day):
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    travel = Travel.objects.filter(t_id=travel_id).first()
    if not travel:
        return JsonResponse({'success': False, 'message': '여행을 찾을 수 없습니다.'}, status=404)
    if travel.member_id != member.m_id:
        return JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)

    schedules = list(Schedule.objects.filter(travel=travel).order_by('s_day'))
    if day < 1 or day > len(schedules):
        return JsonResponse({'success': False, 'message': '존재하지 않는 DAY입니다.'}, status=404)

    sps = (
        SchedulePlace.objects.filter(schedule=schedules[day - 1])
        .select_related('place').order_by('visit_order', 'sp_id')
    )
    items = [{
        'sp_id': sp.sp_id,
        'name': sp.place.p_name,
        'kind': sp.place.p_kind or '',
        'lat': _float_or_none(sp.place.p_lat),
        'lon': _float_or_none(sp.place.p_lon),
        'kakao_id': sp.place.p_kakao_id or None,
        'is_stay': '숙' in (sp.place.p_kind or ''),
    } for sp in sps]

    people = _budget_people(request, travel.t_id)
    try:
        estimate = budget_service.plan_budget([{'day': day, 'items': items}], people)
    except Exception:
        logger.exception('예상 비용 실패 travel=%s day=%s', travel_id, day)
        estimate = {'planned': 0, 'by': {}}

    # 비용 관리에서 회원이 고친 금액이 있으면 그 금액으로 (edited: true)
    places = {str(it['sp_id']): it['cost'] for it in items if it.get('cost')}
    for sp_id, amount in TravelBudgetItem.objects.filter(schedule_place_id__in=[it['sp_id'] for it in items]).values_list('schedule_place_id', 'amount'):
        cost = dict(places.get(str(sp_id)) or {'cat': 'etc', 'source': 'user', 'per': None, 'unit': 'person', 'cap': 1})
        cost.update(amount=amount, edited=True)
        places[str(sp_id)] = cost

    return JsonResponse({
        'success': True,
        'day': day,
        'people': people,
        'places': places,
        'planned': sum(c['amount'] for c in places.values()),
        'by': estimate['by'],
    })


TRAVEL_MAX_DAYS = 30


@require_POST
def travel_reschedule(request, travel_id):
    login_user = request.session.get('login_ok_user')
    if not login_user:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    travel = (
        Travel.objects.select_related('member')
        .filter(t_id=travel_id).first()
    )
    if not travel:
        return JsonResponse({'success': False, 'message': '없는 여행이에요.'}, status=404)
    if travel.member.user_id != login_user:
        return JsonResponse({'success': False, 'message': '내 여행만 수정할 수 있어요.'}, status=403)

    title = (request.POST.get('t_title') or '').strip()
    place = (request.POST.get('t_place') or '').strip()
    try:
        new_start = datetime.strptime(request.POST.get('t_start') or '', '%Y-%m-%d').date()
        new_end = datetime.strptime(request.POST.get('t_end') or '', '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': '날짜를 다시 골라 주세요.'}, status=400)

    if not title:
        return JsonResponse({'success': False, 'message': '여행 이름을 적어 주세요.'}, status=400)
    if not place:
        return JsonResponse({'success': False, 'message': '여행 지역을 적어 주세요.'}, status=400)
    if len(title) > 100 or len(place) > 100:
        return JsonResponse({'success': False, 'message': '이름과 지역은 100자까지 쓸 수 있어요.'}, status=400)
    if new_end < new_start:
        return JsonResponse({'success': False, 'message': '끝나는 날이 시작하는 날보다 빠를 수 없어요.'}, status=400)
    if (new_end - new_start).days + 1 > TRAVEL_MAX_DAYS:
        return JsonResponse({'success': False, 'message': '여행 기간은 %d일까지 정할 수 있어요.' % TRAVEL_MAX_DAYS}, status=400)

    shift = timedelta(days=(new_start - travel.t_start).days)
    schedules = list(Schedule.objects.filter(travel=travel))
    day_plans = list(TravelDayPlan.objects.filter(travel=travel))

    # 옮긴 뒤 새 기간 밖으로 나가는 날 = 지워질 날
    dropped = [s for s in schedules if s.s_day + shift > new_end]
    dropped_plans = [p for p in day_plans if p.plan_date + shift > new_end]

    if dropped and request.POST.get('confirm') != '1':
        place_count = SchedulePlace.objects.filter(schedule__in=dropped).count()
        pay_count = Pay.objects.filter(schedule__in=dropped).count()
        if place_count or pay_count:
            old_start = travel.t_start
            day_labels = sorted(
                'DAY %d' % ((s.s_day - old_start).days + 1) for s in dropped
            )
            parts = []
            if place_count:
                parts.append('장소 %d곳' % place_count)
            if pay_count:
                parts.append('비용 %d건' % pay_count)
            return JsonResponse({
                'success': False,
                'needs_confirm': True,
                'message': '기간이 줄어서 %s의 %s이(가) 지워져요. 그래도 바꿀까요?' % (
                    ', '.join(day_labels), ', '.join(parts)
                ),
            }, status=409)

    with transaction.atomic():
        # 지워질 날 먼저 지움 (장소·비용은 CASCADE로 함께 지워짐)
        Schedule.objects.filter(pk__in=[s.pk for s in dropped]).delete()
        TravelDayPlan.objects.filter(pk__in=[p.pk for p in dropped_plans]).delete()

        # 같은 날짜 중복 금지(unique) 때문에, 미는 방향의 끝쪽부터 하나씩 옮김
        if shift.days:
            keep = [s for s in schedules if s not in dropped]
            keep.sort(key=lambda s: s.s_day, reverse=shift.days > 0)
            for s in keep:
                s.s_day = s.s_day + shift
                s.save(update_fields=['s_day'])

            keep_plans = [p for p in day_plans if p not in dropped_plans]
            keep_plans.sort(key=lambda p: p.plan_date, reverse=shift.days > 0)
            for p in keep_plans:
                p.plan_date = p.plan_date + shift
                p.save(update_fields=['plan_date'])

        travel.t_title = title
        travel.t_place = place
        travel.t_start = new_start
        travel.t_end = new_end
        travel.t_day = new_start
        travel.save(update_fields=['t_title', 't_place', 't_start', 't_end', 't_day'])

    return JsonResponse({'success': True, 'message': '여행 정보를 바꿨어요.'})


# ==============================================
# 여행 삭제
# ==============================================

@require_POST
def travel_delete(
    request,
    travel_id
):
    member = _login_member(request)
    if not member:
        return redirect('login')

    travel = get_object_or_404(
        Travel,
        t_id=travel_id
    )

    if travel.member_id != member.m_id:
        return HttpResponseForbidden('내 여행만 지울 수 있어요.')

    travel.delete()

    return redirect(
        'travel_list'
    )


# ==============================================
# 홈페이지
# ==============================================

# ==============================================
# 메인 - 일정 시작 폼 / 최근 일정 미리보기 도우미
# ==============================================

_BUDGET_STYLE_LABELS = {
    'value': '가성비',
    'premium': '비싸도 괜찮음',
}


def _parse_plan_query(request):
    """메인 화면의 입력(q, budget_style)을 여행 만들기 화면의 미리 채울 값으로 바꾼다.

    - q 전체는 여행 제목 후보로 쓴다.
    - '강릉 1박 2일' 처럼 'N박 M일' 앞의 단어가 있으면 여행 지역 후보로 쓴다.
    """
    query = (request.GET.get('q') or '').strip()[:100]
    style = request.GET.get('budget_style') or ''

    place = ''
    match = re.search(r'([가-힣A-Za-z]+)\s*\d+\s*박\s*\d+\s*일', query)
    if match:
        place = match.group(1)

    return {
        'prefill_title': query,
        'prefill_place': place,
        'prefill_budget_style': _BUDGET_STYLE_LABELS.get(style, ''),
        'prefill_budget_code': style if style in _BUDGET_STYLE_LABELS else '',
    }


def _format_stay_time(minutes):
    if not minutes:
        return ''

    hours, mins = divmod(int(minutes), 60)

    if hours and mins:
        return f'{hours}시간 {mins}분'
    if hours:
        return f'{hours}시간'
    return f'{mins}분'


def _home_trip_card(travel, today):
    """홈 화면 '내 여행 일정' 카드 한 장에 필요한 값 (기존 _build_recent_travel 결과를 재사용)."""
    card = _build_recent_travel(travel)
    stops = [item['name'] for day in card['days'] for item in day['items']]

    start, end = travel.t_start, travel.t_end
    if start and end and start <= today <= end:
        dday, state = '여행 중', 'now'
    elif start and start > today:
        left = (start - today).days
        dday, state = ('D-DAY' if left == 0 else 'D-%d' % left), 'soon'
    else:
        dday, state = '다녀옴', 'past'

    card.update({
        'stop_count': len(stops),
        'stops': stops[:3],
        'more': max(len(stops) - 3, 0),
        'nights': (end - start).days if start and end else None,
        'dday': dday,
        'state': state,
    })
    return card


def _build_recent_travel(travel):
    """메인 화면 '최근 만든 일정' 카드용 데이터 (최대 3일, 하루 3곳)."""
    days = []

    if travel.t_start and travel.t_end and travel.t_end >= travel.t_start:
        day_count = (travel.t_end - travel.t_start).days + 1

        for offset in range(min(day_count, 3)):
            day = travel.t_start + timedelta(days=offset)

            schedule_places = (
                SchedulePlace.objects
                .filter(schedule__travel=travel, schedule__s_day=day)
                .select_related('place')
                .order_by('visit_order', 'sp_id')[:3]
            )

            items = []

            for sp in schedule_places:
                visit_time = sp.arrive_time or sp.start_time
                detail = [
                    part for part in (
                        sp.place.p_kind,
                        _format_stay_time(sp.stay_time),
                    ) if part
                ]

                items.append({
                    'time': visit_time.strftime('%H:%M') if visit_time else '',
                    'name': sp.place.p_name,
                    'detail': ' · '.join(detail),
                })

            days.append({
                'number': offset + 1,
                'items': items,
            })

    return {
        'id': travel.t_id,
        'title': travel.t_title or travel.t_place or '내 여행',
        'place': travel.t_place or '',
        'start': travel.t_start,
        'end': travel.t_end,
        'days': days,
    }


def index(request):

    template = loader.get_template(
        'index.html'
    )


    login_user = request.session.get(
        'login_ok_user'
    )


    member = None
    recent_travel = None
    recent_travels = []


    if login_user:

        try:

            member = Member.objects.get(
                user_id=login_user
            )

        except Member.DoesNotExist:

            member = None


    # 로그인한 회원의 가장 최근 여행
    if member:

        latest_travel = (
            Travel.objects
            .filter(member=member)
            .order_by('-t_id')
            .first()
        )

        if latest_travel:
            recent_travel = _build_recent_travel(latest_travel)

        # 홈 '내 여행 일정' 카드 목록 (최근 4개)
        today = date.today()
        recent_travels = [
            _home_trip_card(t, today)
            for t in Travel.objects.filter(member=member).order_by('-t_id')[:4]
        ]


    return HttpResponse(
        template.render(
            {
                'member':
                    member,
                'recent_travel':
                    recent_travel,
                'recent_travels':
                    recent_travels,
                # 홈 오른쪽 카드: 장소 리뷰 대신 공유된 여행 루트 추천
                'route_picks':
                    build_route_picks(),
            },
            request
        )
    )


# ==============================================
# 비용 관리
# ==============================================

# ==============================================
# 비용 관리 화면용 계산 (분류 / 날짜별 묶음 / 그래프)
# ==============================================

# (이름, 키, 색, 아이콘, 키워드)
BUDGET_CATEGORIES = [
    ('관광지', 'sight', '#2d6cdf', 'landmark',
     ('관광', '입장', '체험', '티켓', '문화', '역사', '공원', '박물관', '미술관')),
    ('식비', 'food', '#f0a03c', 'utensils',
     ('음식', '식당', '맛집', '점심', '저녁', '아침', '간식')),
    ('카페', 'cafe', '#a9744f', 'cup',
     ('카페', '커피', '디저트', '베이커리', '빵', '음료')),
    ('교통', 'move', '#7a8cf0', 'bus',
     ('이동', '버스', '택시', '지하철', '기차', 'KTX', '렌트', '주유', '주차', '항공', '톨게이트')),
    ('숙박', 'stay', '#2fb59b', 'bed',
     ('숙소', '호텔', '게스트', '펜션', '리조트', '모텔')),
    ('쇼핑', 'shop', '#e46b9b', 'bag',
     ('기념품', '마트')),
    ('기타', 'etc', '#9aa5b8', 'card', ()),
]

# 키워드로 찾을 때의 우선순위 (넓게 걸리는 '관광지'는 마지막)
_BUDGET_KEYWORD_ORDER = ('stay', 'move', 'cafe', 'food', 'shop', 'sight')


def _budget_category(pay):
    """비용 한 건이 어떤 분류인지 알아낸다. 모르면 '기타'."""
    text = pay.pay_context or ''
    by_key = {c[1]: c for c in BUDGET_CATEGORIES}

    # 1) 비용 추가 화면에서 고른 항목 이름이 그대로 들어 있는 경우
    for cat in BUDGET_CATEGORIES[:-1]:
        if cat[0] in text:
            return cat

    # 2) 내용이나 장소 종류에 단서가 있는 경우
    kind = pay.place.p_kind if pay.place_id and pay.place and pay.place.p_kind else ''

    for source in (text, kind):
        for key in _BUDGET_KEYWORD_ORDER:
            if any(word in source for word in by_key[key][4]):
                return by_key[key]

    return by_key['etc']


# AI 예상 예산을 계산한 인원 (DB 칸이 없어서 로그인 세션에 여행별로 기억)
BUDGET_PEOPLE_DEFAULT = 2


def _budget_people(request, travel_id):
    saved = (request.session.get('budget_people') or {}).get(str(travel_id))
    return saved or BUDGET_PEOPLE_DEFAULT


def _remember_budget_people(request, travel_id, people):
    saved = dict(request.session.get('budget_people') or {})
    saved[str(travel_id)] = people
    request.session['budget_people'] = saved   # 새 dict로 넣어야 세션이 저장됨


# ==============================================
# 이메일 중복 확인
# ==============================================

def check_email(request):

    user_id = request.GET.get(
        'user_id'
    )


    exists = (
        Member.objects
        .filter(
            user_id=user_id
        )
        .exists()
    )


    return JsonResponse({
        'is_exists':
            exists
    })


# 닉네임 규칙: 앞뒤 공백 빼고 2~10자. 문제가 있으면 안내 문장, 없으면 ''
def nickname_problem(nickname):
    nickname = (nickname or '').strip()
    if len(nickname) < 2 or len(nickname) > 10:
        return '닉네임은 2~10자로 정해 주세요.'
    return ''


# 비밀번호 규칙 (가입·비밀번호 재설정). 문제가 있으면 안내 문장, 없으면 ''
def password_problem(pwd, user_id=''):
    pwd = pwd or ''
    if len(pwd) < 8 or len(pwd) > 30:
        return '비밀번호는 8~30자로 정해 주세요.'
    if re.search(r'\s', pwd):
        return '비밀번호에 공백(띄어쓰기)은 넣을 수 없어요.'
    if not re.search(r'[A-Z]', pwd):
        return '비밀번호에 영문 대문자를 하나 이상 넣어 주세요.'
    # 영문 소문자
    if not re.search(r'[a-z]', pwd):
        return '비밀번호에 영문 소문자를 하나 이상 넣어 주세요.'
    # 특수문자 (영문·숫자가 아닌 글자)
    if not re.search(r'[^A-Za-z0-9]', pwd):
        return '비밀번호에 특수문자(!@# 등)를 하나 이상 넣어 주세요.'
    if re.search(r'(.)\1\1', pwd):
        return '같은 글자를 3번 연속으로 쓸 수 없어요.'
    # 아이디가 들어 있으면 안됨 (대소문자 무시)
    if user_id and user_id.lower() in pwd.lower():
        return '비밀번호에 아이디를 넣을 수 없어요.'
    return ''


# ==============================================
# 회원가입 처리
# ==============================================

def join_ok(request):

    user_id = request.POST.get(
        'user_id'
    )

    email = request.POST.get(
        'email'
    )

    pwd = request.POST.get(
        'pwd'
    )

    name = request.POST.get(
        'name'
    )

    nickname = request.POST.get(
        'nickname'
    )

    gender = request.POST.get(
        'gender'
    )

    age_group = request.POST.get(
        'age_group'
    )

    agree_profile = request.POST.get(
        'agree_profile'
    )

    # 프로필 캐릭터: 고른 게 없거나 목록에 없는 값이면 랜덤 배정
    profile_img = request.POST.get('profile_img')
    if profile_img not in AVATAR_KEYS:
        profile_img = random.choice(AVATAR_KEYS)

    # 아이디 중복
    if (
        Member.objects
        .filter(
            user_id=user_id
        )
        .exists()
    ):

        return HttpResponse("""
            <script>
                alert('이미 사용 중인 ID입니다.');
                history.back();
            </script>
        """)

    # 이메일 중복
    if (
        Member.objects
        .filter(
            email=email
        )
        .exists()
    ):

        return HttpResponse("""
            <script>
                alert('이미 사용 중인 이메일입니다.');
                history.back();
            </script>
        """)

    # 비밀번호·닉네임 규칙
    problem = password_problem(pwd, user_id) or nickname_problem(nickname)
    if problem:
        return HttpResponse(f"""
            <script>
                alert('{problem}');
                history.back();
            </script>
        """)

    # 동의 안했으면 두 값을 비우기만 하고, 아래로 계속 진행
    if (
        agree_profile != '1'
    ):
        gender = None
        age_group = None

    # 성별은 M, F만
    if (
        gender not in ('M', 'F')
    ):
        gender = None

    # 나이대는 10~60 숫자만
    try:
        age_group = int(age_group)
        if age_group not in (10, 20, 30, 40, 50, 60):
            age_group = None
    except (ValueError, TypeError):
        age_group = None

    Member.objects.create(
        user_id=user_id,
        email=email,
        pwd=make_password(pwd),
        name=name,
        nickname=nickname,
        gender=gender,
        age_group=age_group,
        profile_img=profile_img,
    )

    return HttpResponse("""
        <script>
            alert('회원가입이 완료되었습니다!');
            location.href = '../login/';
        </script>
    """)


# ==============================================
# 로그인 처리
# ==============================================

def login_ok(request):

    user_id = request.POST.get(
        'user_id'
    )

    pwd = request.POST.get(
        'pwd'
    )


    try:

        member = Member.objects.get(
            user_id=user_id
        )


        if check_password(pwd, member.pwd):

            request.session[
                'login_ok_user'
            ] = member.user_id

            # 팝업 없이 바로 홈으로
            return redirect('index')

        elif not member.pwd.startswith('pbkdf2_') and member.pwd == pwd:
            member.pwd = make_password(pwd)
            member.save()
            request.session[
                'login_ok_user'
            ] = member.user_id

            # 팝업 없이 바로 홈으로
            return redirect('index')
        
        else:

            return HttpResponse("""
                <script>
                    alert('비밀번호가 틀렸습니다.');
                    history.back();
                </script>
            """)


    except Member.DoesNotExist:

        return HttpResponse("""
            <script>
                alert('존재하지 않는 이메일입니다.');
                history.back();
            </script>
        """)


# ==============================================
# 마이페이지
# ==============================================

def mypage(request):

    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    try:

        member = Member.objects.get(
            user_id=login_user
        )

    except Member.DoesNotExist:

        return redirect(
            'login'
        )


    return render(
        request,
        'mypage.html',
        {
            'member':
                member,
            'record':
                build_travel_record(member)
        }
    )


# 내 정보 '여행 기록' 숫자들 (완성한 여행, 지출, 자주 간 지역 등)
def build_travel_record(member):

    today = date.today()
    travels = Travel.objects.filter(member=member)
    travel_count = travels.count()

    # 끝난 여행 = 마지막 날이 오늘보다 전
    done = list(travels.filter(t_end__lt=today).values('t_start', 't_end'))
    travel_days = sum(
        (t['t_end'] - t['t_start']).days + 1
        for t in done
        if t['t_start'] and t['t_end'] and t['t_end'] >= t['t_start']
    )

    total_spend = (
        Pay.objects
        .filter(schedule__travel__member=member)
        .aggregate(total=Sum('pay_pay'))['total']
    ) or 0

    avg_budget = travels.aggregate(avg=Avg('t_budget'))['avg'] or 0

    top_place = (
        travels
        .values('t_place')
        .annotate(n=Count('t_id'))
        .order_by('-n', 't_place')
        .first()
    )

    top_concept = (
        TravelCategory.objects
        .filter(travel__member=member)
        .values('category__c_name')
        .annotate(n=Count('tc_id'))
        .order_by('-n', 'category__c_name')
        .first()
    )

    return {
        'done_count': len(done),
        'travel_days': travel_days,
        'place_count': SchedulePlace.objects.filter(schedule__travel__member=member).count(),
        'upcoming_count': travels.filter(t_start__gt=today).count(),
        'total_spend': '{:,}'.format(total_spend),
        'avg_spend': '{:,}'.format(round(total_spend / travel_count)) if travel_count else '0',
        'avg_budget': '{:,}'.format(round(avg_budget)),
        'top_place': top_place['t_place'] if top_place else '',
        'top_place_count': top_place['n'] if top_place else 0,
        'top_concept': top_concept['category__c_name'] if top_concept else '',
        'top_concept_count': top_concept['n'] if top_concept else 0,
    }


# ==============================================
# 로그아웃
# ==============================================

def logout(request):

    request.session.flush()

    # 팝업 없이 바로 홈으로
    return redirect('index')


# ==============================================
# ID / PW 찾기
# ==============================================

def idpw(request):

    template = loader.get_template(
        'idpw.html'
    )


    return HttpResponse(
        template.render(
            {},
            request
        )
    )


# ==============================================
# 아이디 찾기
# ==============================================

def id_find(request):

    name = request.POST.get(
        'name'
    )

    email = request.POST.get(
        'email'
    )


    members = (
        Member.objects
        .filter(
            name=name,
            email=email
        )
    )


    if members.exists():

        ids = [
            member.user_id
            for member in members
        ]


        return HttpResponse(f"""
            <script>
                alert('회원님의 아이디는 {", ".join(ids)} 입니다.');
                location.href = '../idpw/';
            </script>
        """)


    return HttpResponse("""
        <script>
            alert('일치하는 회원정보가 없습니다.');
            history.back();
        </script>
    """)


# ==============================================
# 비밀번호 찾기
# ==============================================

def pw_find(request):

    user_id = request.POST.get(
        'user_id'
    )

    email = request.POST.get(
        'email'
    )

    name = request.POST.get(
        'name'
    )

    new_pwd = request.POST.get(
        'new_pwd'
    )

    new_pwd_check = request.POST.get(
        'new_pwd_check'
    )

    code = (request.POST.get('code') or '').strip()

    # 인증 코드 확인 (pw_code 에서 세션에 넣어 둔 것)
    saved = request.session.get('pw_reset') or {}
    now = datetime.now().timestamp()

    if saved.get('user_id') != user_id or now > saved.get('until', 0):
        return HttpResponse("""
            <script>
                alert('인증 코드를 먼저 받아 주세요. (10분이 지났으면 다시 받기)');
                history.back();
            </script>
        """)

    if saved.get('tries', 0) >= PW_CODE_TRIES:
        return HttpResponse("""
                <script>
                    alert('5번 틀렸어요. 인증 코드를 다시 받아 주세요.');
                    history.back();
                </script>
            """)

    if not check_password(code, saved['code']):
        saved['tries'] = saved.get('tries', 0) + 1
        request.session['pw_reset'] = saved          # 바꾼 dict 를 세션에 다시 넣기
        return HttpResponse(f"""
        <script>
            alert('인증 코드가 맞지 않아요. ({saved['tries']}/5)');
            history.back();
        </script>
        """)

    try:

        member = Member.objects.get(
            user_id=user_id,
            email=email,
            name=name
        )


        if (
            new_pwd
            !=
            new_pwd_check
        ):

            return HttpResponse("""
                <script>
                    alert('비밀번호가 일치하지 않습니다.');
                    history.back();
                </script>
            """)

        # 비밀번호 규칙
        problem = password_problem(new_pwd, user_id)
        if problem:
            return HttpResponse(f"""
                <script>
                    alert('{problem}');
                    history.back();
                </script>
            """)


        member.pwd = (
            make_password(new_pwd)
        )


        member.save()
        request.session.pop('pw_reset', None)       # 한 번 쓴 코드는 버리기


        return HttpResponse("""
            <script>
                alert('비밀번호가 변경되었습니다.');
                location.href = '../login/';
            </script>
        """)


    except Member.DoesNotExist:

        return HttpResponse("""
            <script>
                alert('일치하는 회원정보가 없습니다.');
                history.back();
            </script>
        """)


PW_CODE_SECONDS = 10 * 60     # 코드 유효 시간 (10분)
PW_CODE_TRIES = 5             # 틀려도 되는 횟수
PW_CODE_RESEND = 5           # 다시 받으려면 기다리는 시간 (5초, 버튼 두번 눌림 막기)


# 비밀번호 찾기 1단계: 아이디·이메일·이름이 맞으면 6자리 코드를 메일로 (TEAM_UPDATES 11/10)
@require_POST
def pw_code(request):
    user_id = (request.POST.get('user_id') or '').strip()
    email = (request.POST.get('email') or '').strip()
    name = (request.POST.get('name') or '').strip()
    now = datetime.now().timestamp()        # time.time() 과 같은 값(1970년부터 흐른 초)

    # 5초 안에 다시 누르면 막기 (버튼 연타)
    saved = request.session.get('pw_reset') or {}
    if now - saved.get('sent', 0) < PW_CODE_RESEND:
        return JsonResponse({'success': False, 'message': '잠시 뒤에 다시 받을 수 있어요.'}, status=429)

    member = Member.objects.filter(user_id=user_id, email=email, name=name).first()
    if member:
        code = '%06d' % secrets.randbelow(1000000)          # 000000 ~ 999999
        request.session['pw_reset'] = {
            'user_id': member.user_id,
            'code': make_password(code),                           # 코드도 비밀번호처럼 그대로 저장하지 않기
            'until': now + PW_CODE_SECONDS,
            'tries': 0,
            'sent': now,
        }
        send_mail(
            '[TRIPA] 비밀번호 찾기 인증 코드',
            f'인증 코드: {code}\n10분 안에 입력해 주세요. 직접 요청하지 않았다면 이 메일은 무시해 주세요.',
            None,                                           # 보내는 사람: settings.DEFAULT_FROM_EMAIL
            [member.email],
        )
    else:
        request.session['pw_reset'] = {'sent': now}         # 없는 회원도 5초 막기는 똑같이

    # 회원이 있든 없든 같은 문구 (가입 여부가 드러나지 않게)
    return JsonResponse({'success': True, 'message': '입력한 정보가 맞으면 인증 코드를 메일로 보냈어요.'})


# 비밀번호 찾기 2단계 (🟦 [확인] 버튼): 코드가 맞는지만 확인 → 맞으면 화면이 새 비밀번호 칸을 열어 줌
# 비밀번호는 안 바꾸고 코드도 안 지움 (실제 변경은 pw_find 가 코드를 한 번 더 확인)
# 틀린 횟수는 pw_find 와 같은 tries 를 씀 → 둘을 합쳐 5번
@require_POST
def pw_code_check(request):
    user_id = (request.POST.get('user_id') or '').strip()
    code = (request.POST.get('code') or '').strip()
    saved = request.session.get('pw_reset') or {}
    now = datetime.now().timestamp()

    if saved.get('user_id') != user_id or now > saved.get('until', 0):
        return JsonResponse({'success': False, 'message': '인증 코드를 먼저 받아 주세요. (10분이 지났으면 다시 받기)'})
    if saved.get('tries', 0) >= PW_CODE_TRIES:
        return JsonResponse({'success': False, 'message': '5번 틀렸어요. 인증 코드를 다시 받아 주세요.'})
    if not check_password(code, saved['code']):
        saved['tries'] = saved.get('tries', 0) + 1
        request.session['pw_reset'] = saved
        return JsonResponse({'success': False, 'message': f"인증 코드가 맞지 않아요. ({saved['tries']}/{PW_CODE_TRIES})"})

    return JsonResponse({'success': True, 'message': '인증됐어요. 새 비밀번호를 입력해 주세요.'})


# ==============================================
# 내정보 수정
# ==============================================

def mypage_edit(request):

    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    try:

        member = Member.objects.get(
            user_id=login_user
        )

    except Member.DoesNotExist:

        return redirect(
            'login'
        )


    if request.method == 'POST':

        name = request.POST.get(
            'name'
        )

        nickname = request.POST.get(
            'nickname'
        )


        member.name = (
            name
        )


        # 닉네임 규칙
        error = nickname_problem(nickname)
        if error:
            return render(request, 'mypage_edit.html', {'member': member, 'error': error, 'avatars': AVATAR_CHOICES, 'age_groups': AGE_GROUP_CHOICES})


        member.nickname = ((nickname or '').strip())

        # 프로필 캐릭터 (목록에 있는 값일 때만 바꿈)
        profile_img = request.POST.get('profile_img')
        if profile_img in AVATAR_KEYS:
            member.profile_img = profile_img

        # 이메일 등록·변경 (비워 두면 기존 값 유지: 아이디 찾기에 필요해서 지우지 않음)
        email = (request.POST.get('email') or '').strip()

        if email and email != (member.email or ''):
            error = None

            try:
                validate_email(email)
            except ValidationError:
                error = '이메일 형식이 올바르지 않아요. (예: example@tripa.com)'

            if not error and Member.objects.filter(email=email).exclude(m_id=member.m_id).exists():
                error = '이미 다른 회원이 쓰고 있는 이메일이에요.'

            if error:
                member.email = email  # 입력한 값을 그대로 다시 보여 주기 (저장은 안 함)
                return render(request, 'mypage_edit.html', {'member': member, 'error': error, 'avatars': AVATAR_CHOICES, 'age_groups': AGE_GROUP_CHOICES})

            member.email = email

        # 성별·나이대 (🟦 11/11, 회의 안건 8: 내 정보에서 넣기·고치기·지우기 · join_ok 와 같은 규칙)
        if request.POST.get('profile_form') == '1':
            gender = request.POST.get('gender')
            age_group = request.POST.get('age_group')
            if request.POST.get('agree_profile') != '1':
                gender, age_group = None, None          # 동의 안 함 = 지우기
            if gender not in ('M', 'F'):
                gender = None
            try:
                age_group = int(age_group)
                if age_group not in (10, 20, 30, 40, 50, 60):
                    age_group = None
            except (ValueError, TypeError):
                age_group = None
            member.gender = gender
            member.age_group = age_group

        member.save()


        return redirect(
            'mypage'
        )


    return render(
        request,
        'mypage_edit.html',
        {
            'member': member,
            'avatars': AVATAR_CHOICES,
            'age_groups': AGE_GROUP_CHOICES,
        }
    )

# ==============================================
# 회원탈퇴
# ==============================================

def member_delete(request):

    # POST 요청만 허용
    if request.method != 'POST':

        return redirect(
            'mypage'
        )


    # 로그인 확인
    login_user = request.session.get(
        'login_ok_user'
    )


    if not login_user:

        return redirect(
            'login'
        )


    # 현재 회원 조회
    try:

        member = Member.objects.get(
            user_id=login_user
        )

    except Member.DoesNotExist:

        request.session.flush()

        return redirect(
            'login'
        )


    # 입력한 비밀번호
    password = request.POST.get(
        'password',
        ''
    )


        # 비밀번호 확인
    if not check_password(password, member.pwd):

        return HttpResponse("""
            <script>
                alert('비밀번호가 일치하지 않습니다.');
                history.back();
            </script>
        """)


    # 회원 삭제
    member.delete()


    # 로그인 세션 삭제
    request.session.flush()


    return HttpResponse("""
        <script>
            alert('회원탈퇴가 완료되었습니다.');
            location.href = '../';
        </script>
    """)

def schedule_place_search(request):
    query = request.GET.get('query', '').strip()

    if not query:
        return JsonResponse({'places': []})

    try:
        places = _search_kakao_places(query)
    except requests.RequestException as e:
        return JsonResponse({
            'places': [],
            'message': f'장소 검색 중 오류가 발생했습니다: {e}',
        }, status=502)

    return JsonResponse({'places': places})


# ==============================================
# 방문시간 기준 일정 순서 재정렬
# ==============================================

def reorder_schedule_places_by_time(schedule):
    """같은 DAY의 장소를 방문시간 오름차순으로 정렬하고 visit_order를 다시 부여한다."""

    schedule_places = list(
        SchedulePlace.objects
        .filter(schedule=schedule)
        .order_by('visit_order', 'sp_id')
    )

    # 방문시간이 있는 장소를 먼저, 빠른 시간부터 정렬한다.
    # 동일한 시간은 기존 visit_order와 sp_id 순서를 유지한다.
    schedule_places.sort(
        key=lambda item: (
            item.arrive_time is None,
            item.arrive_time or time.max,
            item.visit_order if item.visit_order is not None else 999999,
            item.sp_id,
        )
    )

    changed_places = []

    for new_order, item in enumerate(schedule_places, start=1):
        if item.visit_order != new_order:
            item.visit_order = new_order
            changed_places.append(item)

    if changed_places:
        SchedulePlace.objects.bulk_update(
            changed_places,
            ['visit_order']
        )

    return schedule_places


# ==============================================
# 교통수단 값 정규화
# ==============================================

def normalize_schedule_transport(transport):
    """TRAVEL.T_WAY 값을 get_kakao_route()에서 쓰는 형식으로 통일한다."""

    transport = (
        str(transport or 'car')
        .split(',')[0]
        .strip()
        .lower()
    )

    transport_map = {
        'car': 'car',
        '자동차': 'car',
        '차': 'car',
        'walk': 'walk',
        '도보': 'walk',
        'bike': 'bike',
        '자전거': 'bike',
        'public_transport': 'public_transport',
        'public transport': 'public_transport',
        'public': 'public_transport',
        '대중교통': 'public_transport',
    }

    return transport_map.get(
        transport,
        transport
    )


# ==============================================
# 좌표 기준 이동시간 계산
# ==============================================

def get_route_travel_minutes_by_coords(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
    transport,
    fallback_minutes=0,
):
    """
    첫 번째 일정처럼 PLACE 객체가 없는 출발지(S)에서도
    동일한 경로시간 계산을 사용하기 위한 함수.
    """

    try:
        if (
            start_lat is None
            or start_lon is None
            or end_lat is None
            or end_lon is None
        ):
            raise ValueError(
                '경로 좌표가 없습니다.'
            )

        normalized_transport = (
            normalize_schedule_transport(
                transport
            )
        )

        # 대중교통은 화면과 같은 카카오 대중교통 경로(🟦 transit_service)로 시간을 맞춘다.
        # 같은 구간은 캐시 7일, 700m 안은 도보. 못 찾으면 저장된 계획시간.
        if normalized_transport == 'public_transport':
            route = transit_service.transit_route(start_lat, start_lon, end_lat, end_lon)
            if route and route.get('minutes'):
                return int(route['minutes'])
            return max(int(fallback_minutes or 0), 0)

        route_data = get_kakao_route(
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            transport=normalized_transport,
        )

        if not route_data:
            raise ValueError(
                '경로 데이터가 없습니다.'
            )

        duration_seconds = float(
            route_data.get(
                'duration',
                0
            )
            or 0
        )

        if duration_seconds <= 0:
            raise ValueError(
                '이동시간이 없습니다.'
            )

        return max(
            int(
                (duration_seconds + 59)
                // 60
            ),
            1
        )

    except Exception as e:
        print(
            '좌표 기준 일정 이동시간 계산 실패:',
            e
        )

        return max(
            int(fallback_minutes or 0),
            0
        )


# ==============================================
# 두 장소 사이 이동시간 계산
# ==============================================

def get_route_travel_minutes(
    start_place,
    end_place,
    transport,
    fallback_minutes=0,
):
    """
    현재 지도 경로와 동일하게 get_kakao_route()를 사용해
    두 장소 사이 이동시간을 '분' 단위로 반환한다.

    Kakao Mobility Directions의 duration 값은 초 단위이므로
    올림하여 분으로 변환한다.
    """

    if (
        not start_place
        or not end_place
        or start_place.p_lat is None
        or start_place.p_lon is None
        or end_place.p_lat is None
        or end_place.p_lon is None
    ):
        return max(
            int(fallback_minutes or 0),
            0
        )

    return get_route_travel_minutes_by_coords(
        start_place.p_lat,
        start_place.p_lon,
        end_place.p_lat,
        end_place.p_lon,
        transport,
        fallback_minutes,
    )


# ==============================================
# DAY 일정 시간 연쇄 재계산
# ==============================================

def recalculate_schedule_timeline(
    schedule,
    anchor_sp_id=None,
):
    """
    방문시간 또는 체류시간이 수정되었을 때
    영향받는 뒤쪽 일정의 시간을 연쇄적으로 다시 계산한다.

    계산식:
        현재 장소 출발시간
        + 현재 장소 -> 다음 장소 이동시간
        = 다음 장소 방문시간

        다음 장소 방문시간
        + 다음 장소 체류시간
        = 다음 장소 출발시간

    anchor_sp_id가 있으면 사용자가 직접 수정한 장소의
    방문시간은 그대로 유지하고 그 장소 이후 일정만 밀어낸다.
    """

    schedule_places = list(
        SchedulePlace.objects
        .filter(schedule=schedule)
        .select_related('place')
        .order_by('visit_order', 'sp_id')
    )

    if not schedule_places:
        return []

    # ==========================================
    # 연쇄 계산 시작 위치
    # ==========================================
    anchor_index = 0

    if anchor_sp_id is not None:
        for index, item in enumerate(
            schedule_places
        ):
            if item.sp_id == anchor_sp_id:
                anchor_index = index
                break

    anchor = schedule_places[
        anchor_index
    ]

    # ==========================================
    # 사용자가 수정한 기준 장소 자체 정리
    # ==========================================

    # 첫 장소도 DAY 시작점(S) -> 1번 장소의 이동시간을 반영한다.
    if anchor_index == 0:
        start_point = _build_route_start_point(
            schedule.travel,
            schedule,
        )

        anchor.travel_time = (
            get_route_travel_minutes_by_coords(
                (
                    start_point.get('lat')
                    if start_point
                    else None
                ),
                (
                    start_point.get('lon')
                    if start_point
                    else None
                ),
                anchor.place.p_lat,
                anchor.place.p_lon,
                schedule.travel.t_way,
                anchor.travel_time or 0,
            )
        )

        # 삭제/전체 재계산(anchor_sp_id=None)일 때는
        # 시작지 출발시각 + 실제 이동시간으로 첫 일정도 다시 맞춘다.
        if (
            anchor_sp_id is None
            and start_point
            and start_point.get('departure_time')
        ):
            try:
                start_departure = datetime.strptime(
                    start_point['departure_time'],
                    '%H:%M'
                ).time()

                anchor_arrival_dt = (
                    datetime.combine(
                        schedule.s_day,
                        start_departure,
                    )
                    + timedelta(
                        minutes=anchor.travel_time
                    )
                )

                anchor.arrive_time = (
                    anchor_arrival_dt.time()
                )

            except (TypeError, ValueError):
                pass

    else:
        previous = schedule_places[
            anchor_index - 1
        ]

        anchor.travel_time = (
            get_route_travel_minutes(
                previous.place,
                anchor.place,
                schedule.travel.t_way,
                anchor.travel_time or 0,
            )
        )

    # 기준 장소의 방문시간은 사용자가 직접 설정한 값을 유지한다.
    # 대신 체류시간에 맞춰 출발시간은 다시 계산한다.
    if anchor.arrive_time:
        anchor_arrival_dt = datetime.combine(
            schedule.s_day,
            anchor.arrive_time
        )

        anchor.start_time = (
            anchor_arrival_dt
            + timedelta(
                minutes=anchor.stay_time or 0
            )
        ).time()

    anchor.save(
        update_fields=[
            'travel_time',
            'arrive_time',
            'start_time',
        ]
    )

    # ==========================================
    # 기준 장소 다음 일정부터 연쇄 재계산
    # ==========================================
    previous = anchor

    for current in schedule_places[
        anchor_index + 1:
    ]:

        travel_minutes = (
            get_route_travel_minutes(
                previous.place,
                current.place,
                schedule.travel.t_way,
                current.travel_time or 0,
            )
        )

        # 앞 장소의 출발시간이 없으면 이후 계산을 진행할 수 없다.
        if not previous.start_time:
            current.travel_time = travel_minutes
            current.save(
                update_fields=[
                    'travel_time'
                ]
            )
            previous = current
            continue

        previous_start_dt = datetime.combine(
            schedule.s_day,
            previous.start_time
        )

        current_arrival_dt = (
            previous_start_dt
            + timedelta(
                minutes=travel_minutes
            )
        )

        current_start_dt = (
            current_arrival_dt
            + timedelta(
                minutes=current.stay_time or 0
            )
        )

        current.travel_time = travel_minutes
        current.arrive_time = current_arrival_dt.time()
        current.start_time = current_start_dt.time()

        current.save(
            update_fields=[
                'travel_time',
                'arrive_time',
                'start_time',
            ]
        )

        previous = current

    return schedule_places


# ==============================================
# 일정 장소 추가
# ==============================================

def schedule_place_add(request):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': '잘못된 요청입니다.',
        }, status=400)

    schedule_id = request.POST.get('schedule_id')
    travel_id = request.POST.get('travel_id')
    s_day = request.POST.get('s_day')
    place_id = request.POST.get('place_id')
    arrive_time = request.POST.get('arrive_time')
    requested_stay_time = request.POST.get('stay_time')

    # 카카오 검색 결과를 바로 추가하는 경우 넘어오는 값
    place_name = request.POST.get('place_name', '').strip()
    place_addr = request.POST.get('place_addr', '').strip()
    place_kind = request.POST.get('place_kind', '').strip()
    place_lat = request.POST.get('place_lat') or None
    place_lon = request.POST.get('place_lon') or None
    place_image = request.POST.get('place_image') or None
    place_kakao_id = request.POST.get('place_kakao_id') or None  # 리뷰·사진을 붙이는 열쇠, 화면이 안 보내면 None

    # schedule_id가 있으면 기존 일정을 사용한다.
    if schedule_id:
        schedule = get_object_or_404(Schedule, s_id=schedule_id)
        travel = schedule.travel
    else:
        if not travel_id or not s_day:
            return JsonResponse({
                'success': False,
                'message': '일정 정보가 없습니다.',
            }, status=400)

        travel = get_object_or_404(Travel, t_id=travel_id)
        schedule = (
            Schedule.objects
            .filter(travel=travel, s_day=s_day)
            .order_by('s_id')
            .first()
        )

        if not schedule:
            schedule = Schedule.objects.create(
                travel=travel,
                s_day=s_day,
            )

    # place_id가 있으면 기존 PLACE를 사용한다.
    if place_id:
        place = get_object_or_404(Place, p_id=place_id)
    else:
        if not place_name:
            return JsonResponse({
                'success': False,
                'message': '장소 정보가 없습니다.',
            }, status=400)

        place = (
            Place.objects
            .filter(
                travel=travel,
                p_name=place_name,
                p_addr=place_addr,
            )
            .first()
        )

        if not place:
            place = Place.objects.create(
                travel=travel,
                p_name=place_name,
                p_addr=place_addr,
                p_kind=place_kind,
                p_lat=place_lat,
                p_lon=place_lon,
                p_image=place_image,
                p_kakao_id=place_kakao_id,
            )

    # 이미지가 비어 있으면 API를 통해 자동 보완하고 DB에 저장한다.
    if hasattr(place, 'p_image') and not (place.p_image or ''):
        try:
            image_query = f"{place.p_name} {place.p_addr or ''}".strip()
            auto_image = (
                place_image
                or _search_kakao_image(image_query)
                or _search_kakao_image(place.p_name)
            )

            if auto_image:
                place.p_image = auto_image
                place.save(update_fields=['p_image'])
        except requests.RequestException:
            pass

    # 같은 장소가 같은 DAY에 이미 들어가 있으면 중복 추가 방지
    if SchedulePlace.objects.filter(schedule=schedule, place=place).exists():
        return JsonResponse({
            'success': False,
            'message': '이미 일정에 추가된 장소입니다.',
        }, status=400)

    last_place = (
        SchedulePlace.objects
        .filter(schedule=schedule)
        .order_by('-visit_order', '-sp_id')
        .first()
    )

    visit_order = (
        last_place.visit_order + 1
        if last_place
        else 1
    )

    # 방문시간을 따로 넘기지 않아도 추가 가능하게 한다.
    # 기존 일정이 있으면 마지막 장소 출발시간, 없으면 10:00을 기본값으로 사용한다.
    if arrive_time:
        try:
            arrival = datetime.strptime(
                arrive_time,
                '%H:%M'
            ).time()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': '방문시간 형식이 올바르지 않습니다.',
            }, status=400)
    elif last_place and last_place.start_time:
        arrival = last_place.start_time
    else:
        arrival = time(10, 0)

    # 체류시간은 직접 전달된 값이 있으면 사용하고,
    # 없으면 장소 종류별 기본값을 적용한다.
    if requested_stay_time not in (None, ''):
        try:
            stay_time = int(requested_stay_time)
            if stay_time <= 0 or stay_time > 24 * 60:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({
                'success': False,
                'message': '체류시간은 1~1440분 사이로 설정해주세요.',
            }, status=400)
    else:
        kind = place.p_kind or ''

        if '쇼핑' in kind:
            stay_time = 120
        elif '역사' in kind or '문화' in kind:
            stay_time = 90
        elif '랜드마크' in kind:
            stay_time = 60
        elif '공원' in kind:
            stay_time = 90
        elif '카페' in kind:
            stay_time = 60
        elif '음식' in kind or '식당' in kind:
            stay_time = 90
        elif '자연' in kind or '바다' in kind:
            stay_time = 120
        elif '관광' in kind:
            stay_time = 120
        else:
            stay_time = 60

    arrival_datetime = datetime.combine(
        schedule.s_day,
        arrival
    )

    start_time = (
        arrival_datetime
        + timedelta(minutes=stay_time)
    ).time()

    schedule_place = SchedulePlace.objects.create(
        schedule=schedule,
        place=place,
        visit_order=visit_order,
        stay_time=stay_time,
        arrive_time=arrival,
        start_time=start_time,
    )

    # 새 장소도 방문시간 기준으로 전체 DAY 순서를 다시 정렬한다.
    reorder_schedule_places_by_time(schedule)

    # 새 장소를 기준으로 이후 일정의 이동시간 / 방문시간 / 출발시간을
    # 연쇄적으로 다시 계산한다.
    recalculate_schedule_timeline(
        schedule,
        anchor_sp_id=schedule_place.sp_id
    )

    schedule_place.refresh_from_db(
        fields=[
            'visit_order',
            'travel_time',
            'arrive_time',
            'start_time',
        ]
    )

    return JsonResponse({
        'success': True,
        'message': f'{place.p_name} 장소가 일정에 추가되었습니다.',
        'schedule_id': schedule.s_id,
        'sp_id': schedule_place.sp_id,
        'visit_order': schedule_place.visit_order,
        'place_id': place.p_id,
        'place_name': place.p_name,
        'address': place.p_addr,
        'kind': place.p_kind,
        'place_image': getattr(place, 'p_image', '') or '',
        'arrive_time': (
            schedule_place.arrive_time.strftime('%H:%M')
            if schedule_place.arrive_time
            else ''
        ),
        'stay_time': schedule_place.stay_time,
        'travel_time': schedule_place.travel_time,
        'start_time': (
            schedule_place.start_time.strftime('%H:%M')
            if schedule_place.start_time
            else ''
        ),
    })


# ==============================================
# 일정 장소 삭제
# ==============================================

def schedule_place_delete(request):

    if request.method != 'POST':

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '잘못된 요청입니다.'
            },
            status=400
        )


    sp_id = request.POST.get(
        'sp_id'
    )


    if not sp_id:

        return JsonResponse(
            {
                'success':
                    False,

                'message':
                    '삭제할 일정 정보가 없습니다.'
            },
            status=400
        )


    login_user = request.session.get('login_ok_user')
    if not login_user:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    schedule_place = get_object_or_404(
        SchedulePlace.objects.select_related('schedule__travel__member', 'place'), sp_id=sp_id
    )
    if schedule_place.schedule.travel.member.user_id != login_user:
        return JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)

    schedule = (
        schedule_place.schedule
    )
    was_stay = '숙' in (schedule_place.place.p_kind or '')
    stay_place_id = schedule_place.place_id

    schedule_place.delete()

    # 숙소 줄을 지워서 그날 같은 숙소가 한 줄 이하로 남으면 = 체크인 없음 → 하루 계획의 체크인 시각도 비우기
    if was_stay and SchedulePlace.objects.filter(schedule=schedule, place_id=stay_place_id).count() < 2:
        TravelDayPlan.objects.filter(travel=schedule.travel, plan_date=schedule.s_day).update(checkin_time=None)


    # ==========================================
    # 삭제 후 순서 / 이동시간 / 전체 타임라인 재계산
    # ==========================================

    reorder_schedule_places_by_time(
        schedule
    )

    recalculate_schedule_timeline(
        schedule
    )


    return JsonResponse({
        'success':
            True,

        'message':
            '일정이 삭제되었습니다.'
    })


# ==============================================
# 일정 장소 순서 변경 (드래그로 옮겼을 때)
# ==============================================

def schedule_place_reorder(request):
    """sp_ids='12,15,13' 처럼 그날 장소 전체를 새 순서대로 받아 저장하고 시간을 다시 계산한다."""

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '잘못된 요청입니다.'}, status=400)

    login_user = request.session.get('login_ok_user')

    if not login_user:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    try:
        sp_ids = [int(value) for value in request.POST.get('sp_ids', '').split(',') if value.strip()]
    except ValueError:
        sp_ids = []

    if not sp_ids or len(sp_ids) != len(set(sp_ids)):
        return JsonResponse({'success': False, 'message': '순서 정보가 올바르지 않습니다.'}, status=400)

    first = get_object_or_404(
        SchedulePlace.objects.select_related('schedule__travel__member'),
        sp_id=sp_ids[0]
    )
    schedule = first.schedule

    # 내 여행의 일정만 바꿀 수 있다
    if schedule.travel.member.user_id != login_user:
        return JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)

    rows = list(
        SchedulePlace.objects
        .filter(schedule=schedule)
        .order_by('visit_order', 'sp_id')
    )

    # 그날 장소를 빠짐없이 한 번씩 보내야 한다 (다른 날 장소가 섞이면 거절)
    if sorted(sp_ids) != sorted(row.sp_id for row in rows):
        return JsonResponse(
            {'success': False, 'message': '일정이 바뀌었어요. 새로고침 후 다시 시도해 주세요.'},
            status=409
        )

    if sp_ids == [row.sp_id for row in rows]:
        return JsonResponse({'success': True, 'message': '변경 사항이 없습니다.'})

    by_id = {row.sp_id: row for row in rows}
    ordered = [by_id[sp_id] for sp_id in sp_ids]

    # 하루의 시작 시각은 그대로 두고, 첫 장소가 바뀌어도 그 시각부터 이어서 계산한다
    first_arrival = next((row.arrive_time for row in rows if row.arrive_time), None)

    for new_order, row in enumerate(ordered, start=1):
        row.visit_order = new_order

    if first_arrival:
        ordered[0].arrive_time = first_arrival

    SchedulePlace.objects.bulk_update(ordered, ['visit_order', 'arrive_time'])
    recalculate_schedule_timeline(schedule)

    return JsonResponse({'success': True, 'message': '순서를 바꿨습니다.'})


# ==============================================
# 일정 방문시간 수정
# ==============================================

def schedule_place_time_update(request):

    if request.method != 'POST':
        return JsonResponse(
            {
                'success': False,
                'message': '잘못된 요청입니다.'
            },
            status=400
        )

    sp_id = request.POST.get('sp_id')
    arrive_time = request.POST.get('arrive_time')
    stay_time_value = request.POST.get('stay_time')

    if not sp_id:
        return JsonResponse(
            {
                'success': False,
                'message': '일정 정보가 없습니다.'
            },
            status=400
        )

    if arrive_time in (None, '') and stay_time_value in (None, ''):
        return JsonResponse(
            {
                'success': False,
                'message': '수정할 시간 정보가 없습니다.'
            },
            status=400
        )

    schedule_place = get_object_or_404(
        SchedulePlace,
        sp_id=sp_id
    )

    schedule = schedule_place.schedule
    update_fields = []
    arrival_changed = False

    # ==========================================
    # 방문시간 수정
    # ==========================================
    if arrive_time not in (None, ''):
        try:
            arrival = datetime.strptime(
                arrive_time,
                '%H:%M'
            ).time()
        except ValueError:
            return JsonResponse(
                {
                    'success': False,
                    'message': '방문시간 형식이 올바르지 않습니다.'
                },
                status=400
            )

        if schedule_place.arrive_time != arrival:
            arrival_changed = True

        schedule_place.arrive_time = arrival
        update_fields.append('arrive_time')

    # ==========================================
    # 체류시간 수정
    # ==========================================
    if stay_time_value not in (None, ''):
        try:
            stay_time = int(stay_time_value)

            if stay_time <= 0 or stay_time > 24 * 60:
                raise ValueError

        except (TypeError, ValueError):
            return JsonResponse(
                {
                    'success': False,
                    'message': '체류시간은 1~1440분 사이로 설정해주세요.'
                },
                status=400
            )

        schedule_place.stay_time = stay_time
        update_fields.append('stay_time')

    # ==========================================
    # 출발시간 재계산
    # 방문시간 + 체류시간
    # ==========================================
    if schedule_place.arrive_time:
        arrival_datetime = datetime.combine(
            schedule.s_day,
            schedule_place.arrive_time
        )

        start_datetime = (
            arrival_datetime
            + timedelta(
                minutes=(schedule_place.stay_time or 0)
            )
        )

        schedule_place.start_time = start_datetime.time()
        update_fields.append('start_time')

    schedule_place.save(
        update_fields=list(dict.fromkeys(update_fields))
    )

    # ==========================================
    # 방문시간이 변경되면 같은 DAY 전체를 시간순 재정렬
    # ==========================================
    if arrival_changed:
        reorder_schedule_places_by_time(
            schedule
        )

    # ==========================================
    # 수정한 장소를 기준으로 뒤쪽 일정 연쇄 재계산
    #
    # - 현재 장소 출발시간 = 방문시간 + 체류시간
    # - 다음 장소 이동시간 = 새 방문순서 기준 실제 경로시간
    # - 다음 장소 방문시간 = 이전 출발시간 + 이동시간
    # - 다음 장소 출발시간 = 방문시간 + 체류시간
    # ==========================================
    recalculate_schedule_timeline(
        schedule,
        anchor_sp_id=schedule_place.sp_id
    )

    schedule_place.refresh_from_db(
        fields=[
            'visit_order',
            'travel_time',
            'arrive_time',
            'stay_time',
            'start_time',
        ]
    )

    return JsonResponse({
        'success': True,
        'message': '일정 시간이 변경되었습니다.',
        'visit_order': schedule_place.visit_order,
        'arrive_time': (
            schedule_place.arrive_time.strftime('%H:%M')
            if schedule_place.arrive_time
            else ''
        ),
        'stay_time': schedule_place.stay_time,
        'travel_time': schedule_place.travel_time,
        'start_time': (
            schedule_place.start_time.strftime('%H:%M')
            if schedule_place.start_time
            else ''
        )
    })


# ==============================================
# 경로 조회
# ==============================================

def _build_route_start_point(
    travel,
    schedule,
):
    """
    DAY 1은 Travel.start_*,
    DAY 2 이후는 전날의 유효 숙소를 출발점으로 사용한다.
    """

    schedule_date = schedule.s_day

    # DAY 1 여부는 날짜 타입 비교가 아니라 실제 첫 Schedule 기준으로 판단한다.
    # (SQLite/MySQL, 문자열/date 타입 차이 때문에 start_point가 누락되는 문제 방지)
    first_schedule = (
        Schedule.objects
        .filter(travel=travel)
        .order_by('s_day', 's_id')
        .first()
    )

    is_first_day = (
        first_schedule is not None
        and first_schedule.s_id == schedule.s_id
    )

    if is_first_day:

        if (
            travel.start_lat is None
            or travel.start_lon is None
        ):
            return None

        return {
            'name':
                travel.start_place
                or '출발지',

            'address':
                travel.start_addr
                or travel.start_place
                or '',

            'lat':
                float(
                    travel.start_lat
                ),

            'lon':
                float(
                    travel.start_lon
                ),

            'departure_time': (
                travel.start_time.strftime('%H:%M')
                if travel.start_time
                else '09:00'
            ),

            'marker':
                'S',
        }


    # DAY 2 이후
    previous_date = (
        schedule_date
        -
        timedelta(days=1)
    )

    # 기존 Travel 숙소를 fallback으로 둔다.
    current_name = (
        travel.accommodation
        or None
    )

    current_addr = (
        travel.accommodation
        or ''
    )

    current_lat = (
        travel.accommodation_lat
    )

    current_lon = (
        travel.accommodation_lon
    )


    # 이전 날짜까지 TravelDayPlan을 순서대로 읽어서
    # 마지막으로 입력된 숙소를 유효 숙소로 사용한다.
    previous_plans = (
        TravelDayPlan.objects
        .filter(
            travel=travel,
            plan_date__lte=previous_date
        )
        .order_by(
            'plan_date',
            'tdp_id'
        )
    )


    for plan in previous_plans:

        if (
            plan.accommodation_name
            and
            plan.accommodation_lat is not None
            and
            plan.accommodation_lon is not None
        ):

            current_name = (
                plan.accommodation_name
            )

            current_addr = (
                plan.accommodation_addr
                or plan.accommodation_name
            )

            current_lat = (
                plan.accommodation_lat
            )

            current_lon = (
                plan.accommodation_lon
            )


    if (
        not current_name
        or current_lat is None
        or current_lon is None
    ):

        return None


    current_plan = (
        TravelDayPlan.objects
        .filter(
            travel=travel,
            plan_date=schedule_date
        )
        .order_by(
            'tdp_id'
        )
        .first()
    )


    return {
        'name':
            current_name,

        'address':
            current_addr
            or current_name,

        'lat':
            float(
                current_lat
            ),

        'lon':
            float(
                current_lon
            ),

        'departure_time': (
            current_plan.departure_time.strftime('%H:%M')
            if (
                current_plan
                and
                current_plan.departure_time
            )
            else '09:00'
        ),

        'marker':
            'S',
    }


# ==============================================
# 마지막 DAY 출발지 복귀 정보
# 기본 복귀 예정 시간: 22:00
# ==============================================

def _build_return_home_point(
    travel,
    schedule
):
    """
    마지막 DAY에만 최초 출발지를 복귀 지점으로 반환한다.
    실제 장소 일정(SCHEDULE_PLACES)에는 저장하지 않고,
    지도/타임라인용 가상 복귀 지점으로 사용한다.
    """

    last_schedule = (
        Schedule.objects
        .filter(travel=travel)
        .order_by('-s_day', '-s_id')
        .first()
    )

    if (
        last_schedule is None
        or last_schedule.s_id != schedule.s_id
    ):
        return None

    lat = getattr(
        travel,
        'start_lat',
        None
    )

    lon = getattr(
        travel,
        'start_lon',
        None
    )

    if lat is None or lon is None:
        return None

    name = (
        getattr(
            travel,
            'start_place',
            None
        )
        or '출발지'
    )

    address = (
        getattr(
            travel,
            'start_addr',
            None
        )
        or name
    )

    return {
        'name': name,
        'address': address,
        'lat': float(lat),
        'lon': float(lon),
        'arrival_time': '22:00',
        'marker': 'R',
        'travel_time': 0,
    }


# ==============================================
# [보관용 / 현재 미사용] Kakao Mobility 대중교통 통합 길찾기
# - 제휴 API 사용 승인을 받으면 아래 코드를 다시 활성화할 수 있다.
# - 현재는 카카오 대중교통 길찾기를 서버에서 부른다 (🟦 transit_service, /transit_route/).
# ==============================================
# # ==============================================
# # Kakao Mobility 대중교통 통합 길찾기
# # ==============================================
#
# KAKAO_PUBLIC_TRANSIT_URL = (
#     'https://apis-navi.kakaomobility.com/'
#     'affiliate/publictransit/v1/multimodal/directions'
# )
#
#
# def _seconds_from_midnight_to_hhmm(value):
#     """Kakao 대중교통 API의 자정 기준 초 값을 HH:MM으로 변환한다."""
#     try:
#         total = int(value)
#     except (TypeError, ValueError):
#         return None
#
#     if total < 0:
#         return None
#
#     total %= 24 * 60 * 60
#     hour = total // 3600
#     minute = (total % 3600) // 60
#     return f'{hour:02d}:{minute:02d}'
#
#
# def _normalize_transit_departure_hhmmss(value):
#     """09:30 / datetime.time 등을 Kakao hhmmss 정수 형식으로 바꾼다."""
#     if value is None:
#         return -1
#
#     if isinstance(value, time):
#         return (
#             value.hour * 10000
#             + value.minute * 100
#             + value.second
#         )
#
#     value = str(value).strip()
#     if not value:
#         return -1
#
#     for fmt in ('%H:%M:%S', '%H:%M'):
#         try:
#             parsed = datetime.strptime(value, fmt).time()
#             return (
#                 parsed.hour * 10000
#                 + parsed.minute * 100
#                 + parsed.second
#             )
#         except ValueError:
#             pass
#
#     return -1
#
#
# def _kakao_transit_day_type(travel_date):
#     """
#     Kakao 대중교통 API day_type.
#     토요일/일요일은 구분하고, 평일 공휴일은 별도 공휴일 캘린더가
#     없으므로 Weekday로 요청한다.
#     """
#     weekday = travel_date.weekday()
#
#     if weekday == 5:
#         return 'Saturday'
#
#     if weekday == 6:
#         return 'Holiday'
#
#     return 'Weekday'
#
#
# def _kakao_transit_vehicle_label(mode, vehicle_type):
#     vehicle_type = str(vehicle_type or '').strip().upper()
#
#     if mode == 'walk':
#         return '도보'
#
#     if mode == 'subway':
#         return {
#             'GENERAL': '지하철',
#             'EXPRESS': '급행 지하철',
#             'LIMITED_EXPRESS': '특급 지하철',
#             'DIRECT': '직행 지하철',
#         }.get(vehicle_type, '지하철')
#
#     return {
#         'EMPTY': '버스',
#         'BLUE': '간선버스',
#         'GREEN': '지선버스',
#         'RED': '광역버스',
#         'YELLOW': '순환버스',
#         'AIRPORT': '공항버스',
#         'GENERAL': '일반버스',
#         'SEAT': '좌석버스',
#         'EXPRESS': '급행버스',
#         'MAUL': '마을버스',
#         'DIRECT': '직행버스',
#         'OUTER': '외곽버스',
#         'INTERCITY': '시외버스',
#         'RURAL': '농어촌버스',
#     }.get(vehicle_type, '버스')
#
#
# def _append_transit_path_points(target, path):
#     """[x1,y1,x2,y2,...]를 지도용 [{lat,lon}, ...]로 변환한다."""
#     if not isinstance(path, list):
#         return
#
#     for i in range(0, len(path) - 1, 2):
#         try:
#             lon = float(path[i])
#             lat = float(path[i + 1])
#         except (TypeError, ValueError):
#             continue
#
#         point = {
#             'lat': lat,
#             'lon': lon,
#         }
#
#         if target and target[-1] == point:
#             continue
#
#         target.append(point)
#
#
# def _get_kakao_public_transit_route(
#     start_item,
#     end_item,
#     travel_date,
# ):
#     """
#     Kakao Mobility 대중교통 통합 길찾기에서 추천 경로 1개를 조회한다.
#
#     반환값은 travel_route()의 기존 route 구조와 맞춘다.
#     API 사용 권한/네트워크 문제가 있으면 예외를 발생시키고
#     호출부에서 기존 예상 경로로 fallback 한다.
#     """
#
#     departure_hhmmss = _normalize_transit_departure_hhmmss(
#         start_item.get('departure_time')
#     )
#
#     params = {
#         'start': f"{start_item['lon']},{start_item['lat']}",
#         'goal': f"{end_item['lon']},{end_item['lat']}",
#         'date': int(travel_date.strftime('%Y%m%d')),
#         'hhmmss': departure_hhmmss,
#         'day_type': _kakao_transit_day_type(travel_date),
#         'route_type': 'All',
#     }
#
#     headers = {
#         'Authorization': f'KakaoAK {settings.KAKAO_REST_API_KEY}',
#         'accept': 'application/json',
#         'Content-Type': 'application/json',
#     }
#
#     try:
#         response = requests.get(
#             KAKAO_PUBLIC_TRANSIT_URL,
#             headers=headers,
#             params=params,
#             timeout=12,
#         )
#     except requests.RequestException as e:
#         raise RuntimeError(
#             'Kakao 대중교통 API 연결 실패'
#         ) from e
#
#     if not response.ok:
#         message = ''
#         try:
#             error_data = response.json()
#             message = (
#                 error_data.get('msg')
#                 or error_data.get('message')
#                 or error_data.get('result_message')
#                 or ''
#             )
#         except ValueError:
#             pass
#
#         suffix = f': {message}' if message else ''
#         raise RuntimeError(
#             f'Kakao 대중교통 API HTTP {response.status_code}{suffix}'
#         )
#
#     data = response.json()
#
#     result_code = data.get('result_code')
#     if result_code != 0:
#         raise RuntimeError(
#             data.get('result_message')
#             or f'Kakao 대중교통 길찾기 실패 ({result_code})'
#         )
#
#     journeys = data.get('journeys') or []
#     if not journeys:
#         raise RuntimeError(
#             'Kakao 대중교통 추천 경로가 없습니다.'
#         )
#
#     # 문서상 journeys는 추천 순으로 제공되므로 첫 번째 경로 사용
#     journey = journeys[0]
#     summary = journey.get('summary') or {}
#     sections = journey.get('sections') or []
#
#     points = []
#     transit_steps = []
#     major_steps = []
#
#     for section in sections:
#         route = section.get('route') or {}
#         departure_stop = section.get('departure_stop') or {}
#         arrival_stop = section.get('arrival_stop') or {}
#
#         route_short_name = (
#             route.get('route_short_name')
#             or ''
#         )
#
#         vehicle_type = (
#             route.get('vehicle_type_name')
#             or ''
#         )
#
#         is_walk = (
#             str(route_short_name).strip().lower() == 'walk'
#             or str(vehicle_type).strip().lower() == 'walk'
#         )
#
#         is_subway = (
#             not is_walk
#             and (
#                 route.get('branch_id')
#                 or route.get('branch_direction')
#                 or route.get('train_type')
#             )
#         )
#
#         if is_walk:
#             mode = 'walk'
#         elif is_subway:
#             mode = 'subway'
#         else:
#             mode = 'bus'
#
#         vehicle_label = _kakao_transit_vehicle_label(
#             mode,
#             vehicle_type
#         )
#
#         line_name = ''
#         if mode != 'walk':
#             line_name = (
#                 route_short_name
#                 or route.get('route_full_name')
#                 or ''
#             )
#
#         display_name = vehicle_label
#         if line_name:
#             display_name = f'{vehicle_label} {line_name}'
#
#         step = {
#             'mode': mode,
#             'vehicle_type': vehicle_type,
#             'vehicle_label': vehicle_label,
#             'line_name': line_name,
#             'display_name': display_name,
#             'boarding_stop': departure_stop.get('stop_name') or '',
#             'alighting_stop': arrival_stop.get('stop_name') or '',
#             'departure_time': _seconds_from_midnight_to_hhmm(
#                 departure_stop.get('departure_time')
#             ),
#             'arrival_time': _seconds_from_midnight_to_hhmm(
#                 arrival_stop.get('arrival_time')
#             ),
#             'duration_minutes': max(
#                 int((int(section.get('time') or 0) + 59) // 60),
#                 0,
#             ),
#             'waiting_minutes': max(
#                 int((int(section.get('waiting_time') or 0) + 59) // 60),
#                 0,
#             ),
#             'direction': route.get('last_stop_name_of_trip') or '',
#             'first_trip': bool(section.get('first_trip', False)),
#             'last_trip': bool(section.get('last_trip', False)),
#             'platform_number': (
#                 (section.get('transfer') or {}).get('platform_number')
#                 or ''
#             ),
#         }
#
#         transit_steps.append(step)
#
#         if mode != 'walk':
#             major_steps.append(step)
#
#         _append_transit_path_points(
#             points,
#             section.get('path')
#         )
#
#         # path가 없는 구간은 최소한 정류장 좌표로 연결한다.
#         if not section.get('path'):
#             for stop in (departure_stop, arrival_stop):
#                 try:
#                     lon = float(stop.get('x'))
#                     lat = float(stop.get('y'))
#                 except (TypeError, ValueError):
#                     continue
#
#                 point = {
#                     'lat': lat,
#                     'lon': lon,
#                 }
#                 if not points or points[-1] != point:
#                     points.append(point)
#
#     if len(points) < 2:
#         points = [
#             {
#                 'lat': float(start_item['lat']),
#                 'lon': float(start_item['lon']),
#             },
#             {
#                 'lat': float(end_item['lat']),
#                 'lon': float(end_item['lon']),
#             },
#         ]
#
#     transport_names = [
#         step['display_name']
#         for step in major_steps
#         if step.get('display_name')
#     ]
#
#     transport_label = (
#         ' → '.join(transport_names)
#         if transport_names
#         else '대중교통'
#     )
#
#     first_major = major_steps[0] if major_steps else None
#     last_major = major_steps[-1] if major_steps else None
#
#     # 출발지에서 첫 승차지점까지 도보 시간이 있으면 함께 제공한다.
#     first_walk_minutes = 0
#     for step in transit_steps:
#         if step['mode'] != 'walk':
#             break
#         first_walk_minutes += step.get('duration_minutes') or 0
#
#     return {
#         'from_place': start_item['name'],
#         'to_place': end_item['name'],
#         'from_marker': start_item['marker'],
#         'to_marker': end_item['marker'],
#         'to_order': end_item['order'],
#         'success': True,
#         'estimated': False,
#         'api_source': 'kakao_public_transit',
#         'points': points,
#         'distance': int(summary.get('distance') or 0),
#         'duration': int(summary.get('total_time') or 0),
#         'moving_time': int(summary.get('moving_time') or 0),
#         'waiting_time': int(summary.get('waiting_time') or 0),
#         'walking_time': int(summary.get('walking_time') or 0),
#         'transfer_count': int(summary.get('transfer_count') or 0),
#         'transport': 'public_transport',
#         'transport_label': transport_label,
#         # 일정상 해당 구간을 시작하려는 시각
#         'origin_departure_time': start_item.get('departure_time'),
#         # 실제 노선에 승차하는 시각
#         'departure_time': (
#             first_major.get('departure_time')
#             if first_major
#             else start_item.get('departure_time')
#         ),
#         'departure_time_source': 'kakao_timetable',
#         'arrival_time': (
#             last_major.get('arrival_time')
#             if last_major
#             else None
#         ),
#         'transit_type': (
#             first_major.get('vehicle_label')
#             if first_major
#             else '대중교통'
#         ),
#         'line_name': (
#             first_major.get('line_name')
#             if first_major
#             else None
#         ),
#         'boarding_stop': (
#             first_major.get('boarding_stop')
#             if first_major
#             else None
#         ),
#         'alighting_stop': (
#             last_major.get('alighting_stop')
#             if last_major
#             else None
#         ),
#         'first_walk_minutes': first_walk_minutes,
#         'transit_steps': transit_steps,
#         'transit_detail_available': bool(transit_steps),
#     }
#
#

# ==============================================
# 일정별 지도 경로 API
# 출발지 S -> 일정 1 -> 일정 2 -> ...
# ==============================================

def travel_route(
    request,
    schedule_id
):

    schedule = get_object_or_404(
        Schedule,
        s_id=schedule_id
    )

    travel = schedule.travel


    schedule_places = list(
        SchedulePlace.objects
        .filter(
            schedule=schedule
        )
        .select_related(
            'place'
        )
        .order_by(
            'visit_order'
        )
    )


    # ==========================================
    # 교통수단
    # ==========================================

    transport = request.GET.get(
        'transport'
    )

    if not transport:

        transport = (
            travel.t_way
            or 'car'
        )


    transport = (
        str(transport)
        .split(',')[0]
        .strip()
        .lower()
    )


    transport_map = {

        'car':
            'car',

        '자동차':
            'car',

        '차':
            'car',

        'walk':
            'walk',

        '도보':
            'walk',

        'bike':
            'bike',

        '자전거':
            'bike',

        'public_transport':
            'public_transport',

        'public transport':
            'public_transport',

        'public':
            'public_transport',

        '대중교통':
            'public_transport',
    }


    transport = transport_map.get(
        transport,
        transport
    )


    # ==========================================
    # 출발지
    # ==========================================

    start_point = (
        _build_route_start_point(
            travel,
            schedule
        )
    )

    # 마지막 DAY이면 최초 출발지로 돌아가는 복귀 지점을 만든다.
    return_point = (
        _build_return_home_point(
            travel,
            schedule
        )
    )


    # ==========================================
    # 일정 장소
    # ==========================================

    places = []


    for sp in schedule_places:

        place = sp.place

        if (
            place.p_lat is None
            or
            place.p_lon is None
        ):

            continue


        places.append({

            'id':
                place.p_id,

            'name':
                place.p_name,

            'address':
                place.p_addr,

            'lat':
                float(
                    place.p_lat
                ),

            'lon':
                float(
                    place.p_lon
                ),

            'order':
                sp.visit_order,

            'arrival_time': (
                sp.arrive_time.strftime(
                    '%H:%M'
                )
                if sp.arrive_time
                else None
            ),

            'stay_time':
                sp.stay_time,

            'start_time': (
                sp.start_time.strftime('%H:%M')
                if sp.start_time
                else None
            ),

            'travel_time':
                sp.travel_time,

            'kind':
                place.p_kind,
        })


    # ==========================================
    # 경로 계산용 waypoint
    # ==========================================

    waypoints = []


    if start_point:

        waypoints.append({

            'name':
                start_point['name'],

            'lat':
                start_point['lat'],

            'lon':
                start_point['lon'],

            'marker':
                'S',

            'order':
                None,

            'departure_time':
                start_point.get('departure_time'),
        })


    for place in places:

        waypoints.append({

            'name':
                place['name'],

            'lat':
                place['lat'],

            'lon':
                place['lon'],

            'marker':
                str(
                    place['order']
                ),

            'order':
                place['order'],

            'departure_time':
                place.get('start_time'),
        })


    # 마지막 DAY은 마지막 일정 -> 최초 출발지(R) 구간까지 경로에 포함한다.
    if return_point:

        # Kakao Mobility가 아직 차단돼 있어도 타임라인에 이동시간을
        # 보여줄 수 있도록 기존 평균속도 계산값을 함께 내려준다.
        if waypoints:
            previous_point = waypoints[-1]

            try:
                return_point['travel_time'] = (
                    get_travel_time(
                        previous_point['lat'],
                        previous_point['lon'],
                        return_point['lat'],
                        return_point['lon'],
                        transport
                    )
                )
            except Exception as e:
                print(
                    '출발지 복귀 예상시간 계산 실패:',
                    e
                )
                return_point['travel_time'] = 0

        waypoints.append({
            'name': return_point['name'],
            'lat': return_point['lat'],
            'lon': return_point['lon'],
            'marker': 'R',
            'order': None,
            'departure_time': None,
        })


    routes = []
    route_points = []

    total_distance = 0
    total_duration = 0


    def build_estimated_route(
        start_item,
        end_item,
        message=''
    ):
        """
        실제 경로 API를 사용할 수 없을 때 지도에서 구간 자체가
        사라지지 않도록 두 지점을 직선으로 연결하는 예상 구간을 만든다.

        주의: 대중교통 노선/정류장/탑승시각을 의미하는 실제 경로가 아니다.
        """
        try:
            minutes = get_travel_time(
                start_item['lat'],
                start_item['lon'],
                end_item['lat'],
                end_item['lon'],
                transport
            )
        except Exception:
            minutes = 0

        points = [
            {
                'lat': float(start_item['lat']),
                'lon': float(start_item['lon']),
            },
            {
                'lat': float(end_item['lat']),
                'lon': float(end_item['lon']),
            },
        ]

        if transport == 'public_transport':
            transport_label = '대중교통(상세 노선 미연동)'
        elif transport == 'car':
            transport_label = '자동차(예상)'
        elif transport == 'walk':
            transport_label = '도보(예상)'
        elif transport == 'bike':
            transport_label = '자전거(예상)'
        else:
            transport_label = '이동(예상)'

        return {
            'from_place': start_item['name'],
            'to_place': end_item['name'],
            'from_marker': start_item['marker'],
            'to_marker': end_item['marker'],
            'to_order': end_item['order'],
            'success': True,
            'estimated': True,
            'message': message,
            'points': points,
            'distance': 0,
            'duration': max(int(minutes or 0), 0) * 60,
            'transport': transport,
            'transport_label': transport_label,
            # 현재 값은 실제 버스/지하철 시간표가 아니라
            # 우리 일정에서 이 구간을 출발하도록 계획한 시각이다.
            'departure_time': start_item.get('departure_time'),
            'departure_time_source': 'schedule',
            'arrival_time': None,
            'transit_type': None,
            'line_name': None,
            'boarding_stop': None,
            'alighting_stop': None,
            'transit_detail_available': False,
        }


    for index in range(
        len(waypoints) - 1
    ):

        start_item = waypoints[index]
        end_item = waypoints[index + 1]


        # 대중교통은 서버에서 제휴 API를 호출하지 않는다.
        # 먼저 S/장소/R 좌표를 이용해 임시 경로를 만들고,
        # travel_detail.html이 /transit_route/ (카카오 대중교통 길찾기)로 상세 노선을 보강한다.
        if transport == 'public_transport':
            estimated_route = build_estimated_route(
                start_item,
                end_item,
                '대중교통 경로 조회 전 임시 경로'
            )
            estimated_route['api_source'] = 'transit_pending'
            estimated_route['transit_api_error'] = False
            routes.append(estimated_route)
            route_points.extend(
                estimated_route['points']
            )
            total_duration += estimated_route['duration']

            # ------------------------------------------------------
            # [보관용 / 현재 미사용] Kakao Mobility 제휴 대중교통 API
            # ------------------------------------------------------
            # try:
            #     transit_route = _get_kakao_public_transit_route(
            #         start_item,
            #         end_item,
            #         schedule.s_day,
            #     )
            #     routes.append(transit_route)
            #     route_points.extend(transit_route.get('points', []))
            #     total_distance += transit_route.get('distance', 0) or 0
            #     total_duration += transit_route.get('duration', 0) or 0
            # except Exception as e:
            #     estimated_route = build_estimated_route(
            #         start_item,
            #         end_item,
            #         str(e)
            #     )
            #     estimated_route['transit_api_error'] = True
            #     routes.append(estimated_route)
            #     route_points.extend(estimated_route['points'])
            #     total_duration += estimated_route['duration']

            continue

        try:
            route_data = get_kakao_route(
                start_lat=start_item['lat'],
                start_lon=start_item['lon'],
                end_lat=end_item['lat'],
                end_lon=end_item['lon'],
                transport=transport
            )

        except Exception as e:
            estimated_route = build_estimated_route(
                start_item,
                end_item,
                str(e)
            )
            routes.append(estimated_route)
            route_points.extend(
                estimated_route['points']
            )
            total_duration += estimated_route['duration']
            continue

        if not route_data:
            estimated_route = build_estimated_route(
                start_item,
                end_item,
                '경로 데이터가 없어 예상 구간으로 표시'
            )
            routes.append(estimated_route)
            route_points.extend(
                estimated_route['points']
            )
            total_duration += estimated_route['duration']
            continue

        points = route_data.get('points', []) or []
        distance = route_data.get('distance', 0) or 0
        duration = route_data.get('duration', 0) or 0

        # 응답은 왔지만 그릴 좌표가 없으면 예상 직선 구간으로 대체한다.
        if len(points) < 2:
            estimated_route = build_estimated_route(
                start_item,
                end_item,
                '상세 경로 좌표가 없어 예상 구간으로 표시'
            )
            routes.append(estimated_route)
            route_points.extend(
                estimated_route['points']
            )
            total_duration += estimated_route['duration']
            continue

        route_points.extend(points)
        total_distance += distance
        total_duration += duration

        routes.append({
            'from_place': start_item['name'],
            'to_place': end_item['name'],
            'from_marker': start_item['marker'],
            'to_marker': end_item['marker'],
            'to_order': end_item['order'],
            'success': True,
            'estimated': False,
            'points': points,
            'distance': distance,
            'duration': duration,
            'transport': transport,
            'transport_label': (
                '자동차'
                if transport == 'car'
                else transport
            ),
            'departure_time': start_item.get('departure_time'),
            'departure_time_source': 'schedule',
            'arrival_time': None,
            'transit_type': None,
            'line_name': None,
            'boarding_stop': None,
            'alighting_stop': None,
            'transit_detail_available': False,
        })


    return JsonResponse({

        'success':
            True,

        'schedule_id':
            schedule.s_id,

        's_day':
            schedule.s_day.strftime(
                '%Y.%m.%d'
            ),

        'transport':
            transport,

        'start_point':
            start_point,

        'return_point':
            return_point,

        'is_last_day':
            bool(return_point),

        'places':
            places,

        'routes':
            routes,

        'points':
            route_points,

        'route_points':
            route_points,

        'distance':
            total_distance,

        'duration':
            total_duration,

        'total_distance':
            total_distance,

        'total_duration':
            total_duration,
    })



# ==============================================
# AI 대화로 여행 만들기
#
#   travel_chat        : 대화 한 번 처리 (AI 답변 + 갱신된 일정 초안)
#   travel_chat_apply  : 완성된 초안으로 실제 여행 생성
#
# 일정(장소/시간표) 자체는 기존 generate_schedule()이 만든다.
# ==============================================
chat_logger = logging.getLogger(__name__)

CHAT_BODY_LIMIT = 30000


def _chat_member(request):
    login_user = request.session.get('login_ok_user')

    if not login_user:
        return None

    try:
        return Member.objects.get(user_id=login_user)
    except Member.DoesNotExist:
        return None


def _chat_json_body(request):
    """요청 본문을 dict로 읽는다. 잘못되면 None."""
    if len(request.body) > CHAT_BODY_LIMIT:
        return None

    try:
        body = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return None

    return body if isinstance(body, dict) else None


def _chat_error(message, status, **extra):
    return JsonResponse({'ok': False, 'error': message, **extra}, status=status)


def _decimal_or_none(value):
    if value is None:
        return None

    return Decimal(str(value))


def _read_mock():
    mock_path = settings.BASE_DIR.parent/'mock.json'
    with open(mock_path, encoding='utf-8') as f:
        data = json.load(f)
    return data


def chat_page(request):
    """React 채팅 시험 화면. frontend 를 npm run build 한 결과(static/chat/)를 띄운다."""
    if not request.session.get('login_ok_user'):
        return redirect('login')
    return render(request, 'sherpaapp/chat.html')


@require_POST
def api_chat(request):
    member = _chat_member(request)
    if not member:
        return _chat_error('로그인이 필요해요.', 401, login=True)
    data = _read_mock()
    return JsonResponse(data, json_dumps_params={'ensure_ascii': False})


def api_trip(request, trip_id):
    member = _chat_member(request)
    if not member:
        return _chat_error('로그인이 필요해요.', 401, login=True)
    data = _read_mock()
    return JsonResponse(data, json_dumps_params={'ensure_ascii': False})


@require_POST
def travel_chat(request):
    member = _chat_member(request)

    if not member:
        return _chat_error('로그인이 필요해요.', 401, login=True)

    body = _chat_json_body(request)

    if body is None:
        return _chat_error('요청 형식이 올바르지 않아요.', 400)

    if not chat_service.check_rate_limit(request.session):
        return _chat_error('잠시 후 다시 시도해 주세요. (요청이 너무 많아요)', 429)

    category_names = list(
        Category.objects.order_by('c_id').values_list('c_name', flat=True)
    )

    try:
        result = chat_service.run_chat_turn(
            body.get('messages'),
            body.get('draft'),
            category_names,
            today=date.today(),
            profile={'gender':member.gender, 'age_group':member.age_group},
        )
    except chat_service.ChatError as error:
        return _chat_error(str(error), 502)
    except Exception:
        chat_logger.exception('travel_chat 처리 중 오류')
        return _chat_error('대화를 처리하지 못했어요. 잠시 후 다시 시도해 주세요.', 500)

    return JsonResponse(result)


@require_POST
def travel_chat_apply(request):
    member = _chat_member(request)

    if not member:
        return _chat_error('로그인이 필요해요.', 401, login=True)

    body = _chat_json_body(request)

    if body is None:
        return _chat_error('요청 형식이 올바르지 않아요.', 400)

    category_names = list(
        Category.objects.order_by('c_id').values_list('c_name', flat=True)
    )

    # 브라우저가 보낸 초안은 한 번 더 검증한다.
    draft = chat_service.normalize_draft(
        body.get('draft'),
        None,
        category_names,
        date.today(),
        resolve=False,
    )

    missing = chat_service.missing_fields(draft)

    if missing:
        return _chat_error(
            '아직 필요한 정보가 있어요: ' + ', '.join(missing),
            400,
        )

    try:
        travel = _chat_create_travel(member, draft)
    except ValueError as error:
        return _chat_error(str(error), 400)

    detail_url = reverse('travel_detail', kwargs={'travel_id': travel.t_id})
    warning = None

    try:
        generate_schedule(travel)
    except Exception:
        chat_logger.exception('AI 대화 여행 일정 생성 실패 (t_id=%s)', travel.t_id)
        warning = '여행은 만들어졌지만 자동 일정 생성에 실패했어요. 상세 화면에서 다시 확인해 주세요.'

    if warning is None:
        try:
            failed_pins = _chat_finish_schedule(
                travel,
                draft,
                _chat_clean_removed(body.get('removed')),
                _chat_clean_order(body.get('order')),
                with_images=True,
            )

            if failed_pins:
                warning = '일부 장소(%s)는 일정에 넣지 못했어요. 상세 화면에서 직접 추가해 주세요.' % ', '.join(failed_pins[:3])
        except Exception:
            chat_logger.exception('AI 대화 일정에 담은 장소/삭제/순서 반영 실패 (t_id=%s)', travel.t_id)
            warning = '여행은 만들어졌지만 담은 장소나 순서를 일정에 반영하지 못했어요. 상세 화면에서 확인해 주세요.'

    # 만들어진 일정 전체(자동으로 들어간 식당·카페 포함)의 예상 비용을 분류별 예산으로 저장 (🟦 budget_service)
    try:
        estimate = budget_service.plan_budget(_chat_preview_days(travel, draft), draft.get('people'))
        if not estimate['items']:
            estimate = budget_service.draft_budget(draft)   # 일정 생성이 실패했으면 담은 장소·숙소만
        budget_service.save_limits(travel, estimate['by'])
        _remember_budget_people(request, travel.t_id, estimate['people'])   # 비용 관리 인원 칸에 같은 인원

        # 대화에서 총예산을 따로 말하지 않았으면 AI 예상 합계를 총 예산으로 (비용 관리 화면에 그대로 보임)
        if not draft.get('budget_total') and estimate['planned'] > 0:
            travel.t_budget = estimate['planned']
            travel.save(update_fields=['t_budget'])
    except Exception:
        chat_logger.exception('AI 대화 분류별 예산 저장 실패 (t_id=%s)', travel.t_id)

    return JsonResponse({
        'ok': True,
        'url': detail_url,
        'warning': warning,
        'travel_id': travel.t_id,
        'start': draft['start'],
        'pins': [],  # 담은 장소는 이제 서버가 직접 일정에 넣는다
    })


# ==============================================
# AI 대화 여행 만들기 - 일정 미리보기
# ==============================================

PREVIEW_RATE_COUNT = 30        # 10분에 30번까지 (일정 생성은 무거운 작업이라 따로 센다)
PREVIEW_PHOTO_NEW = 8          # 미리보기에서 사진을 새로 찾는 장소 수 (나머지는 다음 미리보기 때)
PREVIEW_CACHE_SECONDS = 600    # 같은 초안/삭제 조건이면 10분 동안 저장해 둔 결과를 다시 쓴다
PREVIEW_TRANSPORT_LABEL = {
    'car': '자동차',
    'walk': '도보',
    'bike': '자전거',
    'public_transport': '대중교통',
}
WEEKDAY_KO = ['월', '화', '수', '목', '금', '토', '일']


def _chat_create_travel(member, draft):
    """검증된 초안으로 Travel / 컨셉 / 숙소 행을 만든다. (적용과 미리보기가 같이 쓴다)"""
    start = datetime.strptime(draft['start'], '%Y-%m-%d').date()
    end = datetime.strptime(draft['end'], '%Y-%m-%d').date()

    categories = list(
        Category.objects.filter(c_name__in=draft['categories']).order_by('c_id')
    )

    if not categories:
        raise ValueError('여행 컨셉을 다시 선택해 주세요.')

    start_place = draft.get('start_place') or {}
    start_time = draft.get('start_time') or None

    with transaction.atomic():
        travel = Travel.objects.create(
            member=member,
            t_title=draft['title'],
            t_place=draft['place'],
            t_start=start,
            t_end=end,
            t_day=start,
            t_way=draft.get('transport') or '',
            t_budget=draft.get('budget_total') or 100000,
            start_place=start_place.get('name') or start_place.get('query'),
            start_addr=start_place.get('addr'),
            start_lat=_decimal_or_none(start_place.get('lat')),
            start_lon=_decimal_or_none(start_place.get('lon')),
            start_time=start_time,
        )

        # generate_schedule()이 읽으므로 먼저 저장
        for category in categories:
            TravelCategory.objects.get_or_create(
                travel=travel,
                category=category,
            )

        for stay in draft.get('stays') or []:
            TravelDayPlan.objects.create(
                travel=travel,
                plan_date=datetime.strptime(stay['date'], '%Y-%m-%d').date(),
                accommodation_name=stay.get('name') or stay.get('query'),
                accommodation_addr=stay.get('addr'),
                accommodation_lat=_decimal_or_none(stay.get('lat')),
                accommodation_lon=_decimal_or_none(stay.get('lon')),
                arrival_time=stay.get('arrival_time') or None,
                departure_time=stay.get('departure_time') or None,
                checkin_time=stay.get('checkin_time') or None,   # 🟩 체크인하고 다시 나가기
            )

            # 숙소 장소를 kakao_id와 함께 먼저 만들어 둔다.
            # TravelDayPlan에는 kakao_id 칸이 없지만, 일정 생성은 같은 이름의 Place를 다시 쓰므로
            # 숙소에도 사진·리뷰 별점이 붙는다.
            if stay.get('kakao_id'):
                candidate = build_accommodation_candidate(
                    stay.get('name') or stay.get('query'),
                    stay.get('addr'),
                    stay.get('lat'),
                    stay.get('lon'),
                )

                if candidate:
                    candidate['kakao_id'] = stay['kakao_id']
                    get_or_create_place(travel, candidate)

    return travel


def _chat_clean_removed(raw):
    """브라우저가 보낸 '미리보기에서 지운 장소' 목록을 정리한다. [{day, name}]"""
    result = []

    if not isinstance(raw, list):
        return result

    for item in raw[:60]:
        if not isinstance(item, dict):
            continue

        day = item.get('day')
        name = item.get('name')

        if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 31:
            continue

        if not isinstance(name, str) or not name.strip():
            continue

        result.append({'day': day, 'name': name.strip()[:100]})

    return result


def _chat_apply_removed(travel, removed):
    """만들어진 일정에서 사용자가 지운 장소를 빼고, 시간을 다시 계산한다."""
    touched = {}

    for item in removed:
        day_date = travel.t_start + timedelta(days=item['day'] - 1)
        schedule = Schedule.objects.filter(travel=travel, s_day=day_date).first()

        if not schedule:
            continue

        deleted, _ = SchedulePlace.objects.filter(
            schedule=schedule,
            place__p_name=item['name'],
        ).delete()

        if deleted:
            touched[schedule.s_id] = schedule

    for schedule in touched.values():
        reorder_schedule_places_by_time(schedule)
        recalculate_schedule_timeline(schedule)


def _default_stay_minutes(kind):
    """장소 종류별 기본 체류시간(분). 장소 직접 추가(schedule_place_add)와 같은 기준."""
    kind = kind or ''

    if '쇼핑' in kind:
        return 120
    if '역사' in kind or '문화' in kind:
        return 90
    if '랜드마크' in kind:
        return 60
    if '공원' in kind:
        return 90
    if '카페' in kind:
        return 60
    if '음식' in kind or '식당' in kind:
        return 90
    if '자연' in kind or '바다' in kind:
        return 120
    if '관광' in kind:
        return 120

    return 60


def _chat_add_pins(travel, pins, with_images=False):
    """대화에서 담아 둔 장소를 만들어진 일정에 넣는다. 넣지 못한 장소 이름 목록을 돌려준다."""
    failed = []

    for pin in pins or []:
        name = (pin.get('name') or '').strip()

        try:
            with transaction.atomic():
                day = int(pin.get('day'))
                day_date = travel.t_start + timedelta(days=day - 1)

                if not name or day_date > travel.t_end:
                    raise ValueError('날짜가 여행 기간 밖이에요.')

                addr = (pin.get('addr') or '').strip()
                kind = (pin.get('kind') or '').strip()
                kakao_id = str(pin.get('kakao_id') or '').strip() or None  # 리뷰·사진을 붙이는 열쇠, 화면이 안 보내면 None

                schedule = (
                    Schedule.objects.filter(travel=travel, s_day=day_date).order_by('s_id').first()
                    or Schedule.objects.create(travel=travel, s_day=day_date)
                )

                place = Place.objects.filter(travel=travel, p_name=name, p_addr=addr).first()

                if not place:
                    place = Place.objects.create(
                        travel=travel,
                        p_name=name,
                        p_addr=addr,
                        p_kind=kind,
                        p_kakao_id=kakao_id,
                        p_lat=pin.get('lat'),
                        p_lon=pin.get('lon'),
                    )

                if with_images and not (place.p_image or ''):
                    try:
                        if place.p_kakao_id:
                            image = place_photo_url(place)
                        else:
                            image = _search_kakao_image(f'{name} {addr}'.strip()) or _search_kakao_image(name)

                        if image:
                            place.p_image = image
                            place.save(update_fields=['p_image'])
                    except requests.RequestException:
                        pass

                if SchedulePlace.objects.filter(schedule=schedule, place=place).exists():
                    continue

                prev = (
                    SchedulePlace.objects.filter(schedule=schedule)
                    .order_by('-visit_order', '-sp_id')
                    .exclude(place__p_kind__contains='숙')
                    .first()
                )

                arrival = None

                if pin.get('time'):
                    try:
                        arrival = datetime.strptime(pin['time'], '%H:%M').time()
                    except ValueError:
                        arrival = None

                # 시각 없이 담은 곳: 그날 일정 중 운영시간에 맞는 첫 자리 (못 찾으면 아래 기존 방식)
                if arrival is None:
                    stay = _default_stay_minutes(place.p_kind)
                    hours = hours_service.place_hours(
                        place.p_name, place.p_kind, schedule.s_day,
                        place.p_lat, place.p_lon, place.p_kakao_id,
                    )
                    rows = (SchedulePlace.objects.filter(schedule=schedule)
                            .exclude(place__p_kind__contains='숙').order_by('visit_order'))
                    for row in rows:
                        if not row.start_time:
                            continue
                        at = row.start_time.hour * 60 + row.start_time.minute
                        fit = hours_service.fit_stay(place.p_kind, hours, at, stay)
                        if fit['status'] in ('ok', 'shortened'):
                            arrival = row.start_time
                            break

                if arrival is None:
                    arrival = (prev.start_time if prev and prev.start_time else None) or time(10, 0)

                stay_time = _default_stay_minutes(place.p_kind)
                start_time = (datetime.combine(schedule.s_day, arrival) + timedelta(minutes=stay_time)).time()

                schedule_place = SchedulePlace.objects.create(
                    schedule=schedule,
                    place=place,
                    visit_order=(prev.visit_order + 1) if prev else 1,
                    stay_time=stay_time,
                    arrive_time=arrival,
                    start_time=start_time,
                )

                reorder_schedule_places_by_time(schedule)
                recalculate_schedule_timeline(schedule, anchor_sp_id=schedule_place.sp_id)
                # 1) 이 여행에서, 오늘(schedule)이 아닌 날의 일정 줄들
                dup = SchedulePlace.objects.filter(schedule__travel=travel).exclude(schedule=schedule)
                # 2) 그중 같은 장소만
                if kakao_id:
                    dup = dup.filter(place__p_kakao_id=kakao_id)
                else:
                    dup = dup.filter(place=place)
                # 3) 지울 날들 기억해 두고 지우기
                days = set()
                for row in dup:
                    days.add(row.schedule)
                dup.delete()
                # 4) 지운 날들 시간 다시 계산
                for day in days:
                    reorder_schedule_places_by_time(day)
                    recalculate_schedule_timeline(day)
        except Exception:
            chat_logger.exception('AI 대화 담은 장소를 일정에 넣지 못함: %s', name)
            failed.append(name or '(이름 없음)')

    return failed


def _chat_clean_order(raw):
    """브라우저가 보낸 '사용자가 바꾼 순서' 목록을 정리한다. [{day, names:[...]}]"""
    result = []

    if not isinstance(raw, list):
        return result

    for item in raw[:31]:
        if not isinstance(item, dict):
            continue

        day = item.get('day')
        names = item.get('names')

        if isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 31:
            continue

        if not isinstance(names, list):
            continue

        clean = []

        for name in names[:40]:
            if isinstance(name, str) and name.strip() and name.strip()[:100] not in clean:
                clean.append(name.strip()[:100])

        if clean:
            result.append({'day': day, 'names': clean})

    return result


def _chat_apply_order(travel, order):
    """사용자가 정한 장소 순서대로 바꾸고, 이동시간과 방문시간을 다시 계산한다."""
    for item in order:
        day_date = travel.t_start + timedelta(days=item['day'] - 1)
        schedule = Schedule.objects.filter(travel=travel, s_day=day_date).first()

        if not schedule:
            continue

        rows = list(
            SchedulePlace.objects
            .filter(schedule=schedule)
            .select_related('place')
            .order_by('visit_order', 'sp_id')
        )

        if len(rows) < 2:
            continue

        by_name = {}

        for row in rows:
            by_name.setdefault(row.place.p_name, []).append(row)

        ordered = []

        for name in item['names']:
            if by_name.get(name):
                ordered.append(by_name[name].pop(0))

        picked = {row.sp_id for row in ordered}
        ordered += [row for row in rows if row.sp_id not in picked]

        if [row.sp_id for row in ordered] == [row.sp_id for row in rows]:
            continue

        # 하루의 시작 시각은 그대로 두고, 첫 장소가 바뀌어도 그 시각부터 이어서 계산한다
        first_arrival = next((row.arrive_time for row in rows if row.arrive_time), None)

        for new_order, row in enumerate(ordered, start=1):
            row.visit_order = new_order

        if first_arrival:
            ordered[0].arrive_time = first_arrival

        SchedulePlace.objects.bulk_update(ordered, ['visit_order', 'arrive_time'])
        recalculate_schedule_timeline(schedule)


def _fit_meal_windows(schedule, fixed_times=None):
    """채팅 적용 때만: 점심 12~13시·저녁 18~19시 도착에 맞춰 식사 앞 장소들 체류를 범위 안에서 늘리고 줄인다
    fixed_times: {장소 이름: 'HH:MM'} 시각을 정해 담은 곳 (그 시각 그대로)"""
    fixed_times = fixed_times or {}
    anchor = None                         # 이 줄 뒤만 다시 계산 (점심 차례는 하루 처음부터)
    for window in (stay_rules.LUNCH, stay_rules.DINNER):
        meal_row = None
        for _ in range(3):                # 이동 시간이 다시 계산되며 조금씩 달라져서 최대 3번
            rows = list(SchedulePlace.objects.filter(schedule=schedule)
                        .select_related('place').order_by('visit_order', 'sp_id'))
            ids = [r.sp_id for r in rows]
            begin = ids.index(anchor) + 1 if anchor in ids else 0

            meal = next((i for i in range(begin, len(rows))
                         if hours_service.is_food(rows[i].place.p_kind)), None)
            if meal is None or not rows[meal].arrive_time:
                return
            meal_row = rows[meal]

            # 식사 앞에 시각 정한 장소가 있으면 → 그 시각으로 되돌리고 기준점으로, 그 뒤만 움직임
            for i in range(begin, meal):
                pinned = fixed_times.get(rows[i].place.p_name)
                if pinned:
                    rows[i].arrive_time = datetime.strptime(pinned, '%H:%M').time()
                    rows[i].save(update_fields=['arrive_time'])
                    anchor, begin = rows[i].sp_id, i + 1

            need = stay_rules.meal_shift(_time_minutes(meal_row.arrive_time), window)
            movable = [r for r in rows[begin:meal]
                       if '숙' not in (r.place.p_kind or '') and not hours_service.is_food(r.place.p_kind)]
            if not need or not movable:
                break
            limits = []
            for r in movable:
                low, normal, high = stay_rules.stay_range(r.place.p_kind, r.place.p_name)
                limits.append((low, high))
            old = [r.stay_time or 60 for r in movable]
            new = stay_rules.spread(old, limits, need)
            if new == old:                # 더 늘리거나 줄일 여유가 없음
                break
            for r, stay in zip(movable, new):
                r.stay_time = stay
            SchedulePlace.objects.bulk_update(movable, ['stay_time'])
            recalculate_schedule_timeline(schedule, anchor_sp_id=anchor)

        # 그래도 이르면: 식사를 시간대 시작에 고정하고 기다리기
        if meal_row and _time_minutes(meal_row.arrive_time) < window[0]:
            meal_row.arrive_time = time(window[0] // 60, window[0] % 60)
            meal_row.save(update_fields=['arrive_time'])
            recalculate_schedule_timeline(schedule, anchor_sp_id=meal_row.sp_id)

        anchor = meal_row.sp_id if meal_row else anchor     # 저녁 차례는 점심 뒤부터


def _chat_finish_schedule(travel, draft, removed, order, with_images=False):
    """자동으로 만든 일정 위에 사용자가 고른 것(담은 장소, 삭제, 순서)을 얹는다."""
    # 🟩 담은 장소가 그날 쉬면 여는 날로 옮김 (안내는 미리보기 days[].moved·excluded)
    pins, travel.hours_notes = move_closed_pins(travel, draft.get('pins') or [])
    failed = _chat_add_pins(travel, pins, with_images)
    _chat_apply_removed(travel, removed)
    _chat_apply_order(travel, order)

    # 식사 시간대 맞추기 (채팅 적용 때만, 여행 상세에서 고칠 때는 안부름)
    fixed = {pin.get('name'): pin.get('time') for pin in pins if pin.get('time')}
    for schedule in Schedule.objects.filter(travel=travel):
        _fit_meal_windows(schedule, fixed)

    return failed


def _hhmm(value):
    return value.strftime('%H:%M') if value else None


def _float_or_none(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _chat_preview_days(travel, draft):
    """방금 만든 일정을 날짜별 타임라인(출발 → 장소 순서)으로 정리한다."""
    day_plan_map = get_travel_day_plans(travel)
    schedules = list(Schedule.objects.filter(travel=travel).order_by('s_day'))
    dates = [schedule.s_day for schedule in schedules]
    stays = resolve_effective_accommodations(travel, dates, day_plan_map)
    pin_keys = {(pin.get('day'), pin.get('name')) for pin in draft.get('pins') or []}
    days = []

    for index, schedule in enumerate(schedules):
        rows = list(
            SchedulePlace.objects
            .filter(schedule=schedule)
            .select_related('place')
            .order_by('visit_order', 'sp_id')
        )

        if index == 0:
            start_name = travel.start_place or '출발지'
        else:
            previous_stay = stays.get(dates[index - 1])
            start_name = previous_stay['name'] if previous_stay else '전날 숙소'

        items = []
        for row in rows:
            place = row.place
            kind = place.p_kind or ''

            items.append({
                'sp_id': row.sp_id,   # 예산 대안 '바꾸기'가 어느 자리인지 알려고 (추가 키)
                'name': place.p_name,
                'kind': kind,
                'addr': place.p_addr or '',
                'lat': _float_or_none(place.p_lat),
                'lon': _float_or_none(place.p_lon),
                'arrive': _hhmm(row.arrive_time),
                'leave': _hhmm(row.start_time),
                'stay': row.stay_time,
                'move': row.travel_time,
                'is_stay': '숙' in kind,
                'pin': (index + 1, place.p_name) in pin_keys,
                'kakao_id': place.p_kakao_id or None,
            })

        # 같은 숙소가 하루에 두 줄이면 앞 줄 = 체크인, 뒤 줄 = 귀가 (🟧 11/10 규칙, mock.json stay_role)
        stay_rows = [item for item in items if item['is_stay']]

        for item in items:
            item['stay_role'] = None

        if len(stay_rows) >= 2 and stay_rows[0]['name'] == stay_rows[-1]['name']:
            stay_rows[0]['stay_role'] = 'checkin'
            stay_rows[-1]['stay_role'] = 'return'

        days.append({
            'day': index + 1,
            'date': schedule.s_day.isoformat(),
            'label': schedule.s_day.strftime('%m.%d'),
            'weekday': WEEKDAY_KO[schedule.s_day.weekday()],
            'start_time': _hhmm(get_day_start_time(travel, schedule.s_day, index, day_plan_map)),
            'start_name': start_name,
            'items': items,
        })

    return days


def _chat_attach_hours(travel, days):
    """미리보기 날마다 운영시간 안내를 붙인다 — items[].hours, excluded, moved (🟩 schedule_service, mock.json)

    롤백(transaction) 밖에서 불러야 한다. 안에서 여러 스레드가 캐시 표를 읽으면 잠금을 기다리느라 50초씩 멈춘다.
    """
    notes = getattr(travel, 'hours_notes', None) or {}
    jobs = [(day, item) for day in days for item in day['items'] if not item['is_stay']]

    def one(job):
        day, item = job
        try:
            return hours_service.place_hours(
                item['name'], item['kind'], date.fromisoformat(day['date']),
                item['lat'], item['lon'], item['kakao_id'],
            )
        except Exception:  # 한 곳이 실패해도 나머지는 보여준다
            chat_logger.warning('AI 대화 미리보기 운영시간 실패: %s', item['name'], exc_info=True)
            return None

    with ThreadPoolExecutor(max_workers=hours_service.WORKERS) as pool:
        found = {id(item): hours for (_, item), hours in zip(jobs, pool.map(one, jobs))}

    def minutes(text):
        return int(text[:2]) * 60 + int(text[3:5]) if text else None

    for day in days:
        day['excluded'] = (notes.get(day['day']) or {}).get('excluded', [])
        day['moved'] = (notes.get(day['day']) or {}).get('moved', [])
        previous_leave = minutes(day['start_time'])

        for item in day['items']:
            arrive = minutes(item['arrive'])
            hours = found.get(id(item))
            wait = 0

            # 앞 장소에서 떠나 이동해도 여는 시각보다 일찍 닿아서 기다린 시간
            if hours and arrive is not None and previous_leave is not None and arrive == hours.get('open_min'):
                wait = max(arrive - (previous_leave + (item['move'] or 0)), 0)

            item['hours'] = (
                schedule_hours_badge(item['kind'], hours, arrive, item['stay'], wait)
                if arrive is not None else None
            )
            previous_leave = minutes(item['leave']) or previous_leave


@require_POST
def travel_chat_preview(request):
    member = _chat_member(request)

    if not member:
        return _chat_error('로그인이 필요해요.', 401, login=True)

    body = _chat_json_body(request)

    if body is None:
        return _chat_error('요청 형식이 올바르지 않아요.', 400)

    category_names = list(
        Category.objects.order_by('c_id').values_list('c_name', flat=True)
    )

    draft = chat_service.normalize_draft(
        body.get('draft'),
        None,
        category_names,
        date.today(),
        resolve=False,
    )

    missing = chat_service.missing_fields(draft)

    if missing:
        return _chat_error('아직 필요한 정보가 있어요: ' + ', '.join(missing), 400)

    removed = _chat_clean_removed(body.get('removed'))
    order = _chat_clean_order(body.get('order'))

    # 같은 초안 + 같은 삭제 조건이면 다시 계산하지 않고 저장해 둔 결과를 돌려준다.
    # (저장된 결과를 쓰는 건 요청 횟수로 세지 않는다)
    cache_key = 'chat_preview:%s:%s' % (
        member.pk,
        hashlib.sha1(
            json.dumps([draft, removed, order], ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')
        ).hexdigest(),
    )
    cached = cache.get(cache_key)

    if cached:
        return JsonResponse(cached)

    if not chat_service.check_rate_limit(
        request.session,
        key='ai_preview_calls',
        count=PREVIEW_RATE_COUNT,
    ):
        recent = request.session.get('ai_preview_calls') or []
        wait = 30

        if recent:
            wait = max(5, int(chat_service.RATE_LIMIT_SECONDS - (datetime.now().timestamp() - min(recent))) + 1)

        return _chat_error(
            '미리보기 요청이 많아요. %d초 뒤에 다시 시도해 주세요.' % wait,
            429,
            retry_after=wait,
        )

    days = []

    try:
        # 진짜 일정 생성 로직을 한 번 돌려 결과만 읽고, 저장은 전부 취소(롤백)한다.
        with transaction.atomic():
            travel = _chat_create_travel(member, draft)
            generate_schedule(travel)
            _chat_finish_schedule(travel, draft, removed, order)
            days = _chat_preview_days(travel, draft)
            transaction.set_rollback(True)
    except ValueError as error:
        return _chat_error(str(error), 400)
    except Exception:
        chat_logger.exception('AI 대화 일정 미리보기 실패')
        return _chat_error('일정 미리보기를 만들지 못했어요. 잠시 후 다시 시도해 주세요.', 500)

    # 장소마다 운영시간 안내 + 담은 장소를 옮겼거나 못 넣은 안내 (🟩, mock.json plan.days[])
    try:
        _chat_attach_hours(travel, days)
    except Exception:
        chat_logger.exception('AI 대화 미리보기 운영시간 안내 실패')

    # 장소마다 사진 1장 (mock.json 의 stops[].photo). 롤백 밖에서 해야 찾은 사진이 저장된다.
    # 새로 찾는 건 한 번에 PREVIEW_PHOTO_NEW곳까지 (응답이 늦어지지 않게)
    attach_photos([item for day in days for item in day['items']], max_new=PREVIEW_PHOTO_NEW)

    # 날짜별 날씨(days[].weather, mock.json) + 장소마다 실내/실외(items[].indoor) — 🟦 rain_service
    try:
        weather = rain_service.trip_days_weather(draft['place'], draft['start'], draft['end'], draft.get('center'))
        for day in days:
            day['weather'] = weather.get(day['date'])
        rain_service.attach_indoor([item for day in days for item in day['items']])
    except Exception:
        chat_logger.exception('AI 대화 미리보기 날씨·실내 판단 실패')

    # 장소마다 예상 비용(cost) + 일정 전체 예상 예산(budget) — 자동으로 들어간 식당·카페도 포함 (🟦 budget_service)
    try:
        plan_budget = budget_service.plan_budget(days, draft.get('people'))
    except Exception:
        chat_logger.exception('AI 대화 미리보기 예상 비용 실패')
        plan_budget = None

    transport = (draft.get('transport') or '').strip()

    result = {
        'ok': True,
        'days': days,
        'transport': PREVIEW_TRANSPORT_LABEL.get(transport, ''),
        'budget': plan_budget,
    }
    cache.set(cache_key, result, PREVIEW_CACHE_SECONDS)

    return JsonResponse(result)


# ==========================================
# 장소별 리뷰 목록
# ==========================================
def review_list(request):
    """kakao_id 장소의 리뷰를 최신순·도움돼요 순으로 돌려준다. 평균 별점·개수, 내 리뷰·내가 누른 도움돼요 표시 포함"""
    kakao_id = request.GET.get('kakao_id')
    sort = request.GET.get('sort')
    if not kakao_id:
        return JsonResponse(
            {'success': False, 'message': 'kakao_id가 필요합니다.'}, status=400
            )
    reviews = Review.objects.filter(kakao_id=kakao_id).select_related('member').annotate(helpful_count=Count('helpfuls'))
    if sort == 'helpful':
        reviews = reviews.order_by('-helpful_count', '-created_at')
    else:
        reviews = reviews.order_by('-created_at')
    stats = reviews.aggregate(avg_rating=Avg('rating'), count=Count('rv_id'))
    me = None
    my_ids = set()
    login_user = request.session.get('login_ok_user')
    if login_user:
        me = Member.objects.filter(user_id=login_user).first()
        if me:
            my_ids = set(ReviewHelpful.objects.filter(member=me, review__kakao_id=kakao_id).values_list('review_id', flat=True))
    result = []
    for r in reviews:
        result.append({
            'rv_id': r.rv_id,
            'member_name': r.member.nickname,
            'rating': r.rating,
            'content': r.content,
            'tags': r.tags or [],
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'helpful_count': r.helpful_count,
            'is_mine': bool(me and r.member_id == me.m_id),
            'is_helpful': bool(r.rv_id in my_ids),
        })
    return JsonResponse({
        'success': True,
        'kakao_id': kakao_id,
        'avg': round(stats['avg_rating'] or 0, 1),
        'count': stats['count'],
        'reviews': result
    })


# ==========================================
# 여러 장소 리뷰 평균
# ==========================================

def review_summary(request):
    """kakao_ids(쉼표, 최대 50개) 장소들의 평균 별점·리뷰 수를 한 번에 돌려준다. 리뷰 없는 장소는 빠진다"""
    kakao_ids = request.GET.get('kakao_ids', '')
    id_list = [k.strip() for k in kakao_ids.split(',') if k.strip()][:50]
    
    if not id_list:
        return JsonResponse(
            {'success': False, 'message': 'kakao_ids가 필요합니다.'}, status=400
        )
    stats = (
        Review.objects.filter(kakao_id__in=id_list)
        .values('kakao_id')
        .annotate(rating=Avg('rating'),
        count=Count('rv_id'))
        )
    result = {}
    for s in stats:
        result[s['kakao_id']] = {'rating': round(s['rating'], 1), 'count': s['count']}
    return JsonResponse({
        'success': True,
        'reviews': result
    })


# ==========================================
# 리뷰 키워드 요약(AI)
# ==========================================

def review_keywords(request):
    """kakao_id 장소 리뷰의 키워드(최대 5개)와 한 줄 요약을 돌려준다. 실제 요약은 review_service.summarize_review"""
    kakao_id = request.GET.get('kakao_id')
    if not kakao_id:
        return JsonResponse(
            {'success': False, 'message': 'kakao_id가 필요합니다.'}, status=400
        )
    result = summarize_review(kakao_id)
    if result is None:
        return JsonResponse({
            'success': True,
            'kakao_id': kakao_id,
            'keywords': [],
            'summary': '',
            'count': 0
        })
    else:
        return JsonResponse({
            'success': True,
            'kakao_id': kakao_id,
            'keywords': result['keywords'],
            'summary': result['summary'],
            'count': result['count']
        })


# 이 장소와 리뷰가 비슷한 장소 (🟧 RAG). ?kakao_id=…&top_k=5
def similar_places(request):
    kakao_id = request.GET.get('kakao_id')
    if not kakao_id:
        return JsonResponse({'success': False, 'message': 'kakao_id가 필요합니다.'}, status=400)
    try:
        top_k = min(int(request.GET.get('top_k', 5)), 10)
    except ValueError:
        top_k = 5
    places = embed_service.similar_places(kakao_id, top_k=top_k)
    return JsonResponse({'success': True, 'kakao_id': kakao_id, 'places': places})


# =========================================================
# 예산 AI (🟦): 초안 예상 비용 / 카테고리 예산 저장
# =========================================================

@require_POST
def budget_estimate(request):
    """AI 대화 초안의 담은 장소·숙소 → 인원 기준 예상 비용
    POST JSON {draft} → {success, people, planned, by: {분류: 금액}, items: [...], unknown: [이름]}
    """
    if not _chat_member(request):
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    body = _chat_json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'message': '요청 형식이 올바르지 않아요.'}, status=400)

    category_names = list(Category.objects.order_by('c_id').values_list('c_name', flat=True))
    draft = chat_service.normalize_draft(body.get('draft'), None, category_names, date.today(), resolve=False)

    try:
        estimate = budget_service.draft_budget(draft)
    except Exception:
        logger.exception('예상 비용 계산 실패')
        return JsonResponse({'success': False, 'message': '예상 비용을 계산하지 못했어요.'}, status=500)

    return JsonResponse({'success': True, **estimate})


def budget_category(request, travel_id):
    """여행의 카테고리(분류별) 예산
    GET  → {success, budget: {total, limit: {분류: 예산}, by: {분류: 쓴 돈}}}
    GET ?plan=1 → 위 + plan·counts·people·items (장소별 금액, 비용 관리 화면)
    POST JSON {limit: {sight: 30000, food: 150000, ...}, items: {sp_id: 금액 또는 null}, total: 총예산(선택)} → 같은 모양
         limit 은 보낸 분류만 저장, items 는 장소별로 고친 금액 (null 이면 AI 금액으로 되돌림)
    분류 키: sight·food·cafe·move·stay·shop·etc (mock.json budget 키)
    """
    member = _login_member(request)
    if not member:
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    travel = Travel.objects.filter(t_id=travel_id).first()
    if not travel:
        return JsonResponse({'success': False, 'message': '여행을 찾을 수 없습니다.'}, status=404)
    if travel.member_id != member.m_id:
        return JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)

    if request.method == 'POST':
        body = _chat_json_body(request)
        if body is None or not isinstance(body.get('limit'), dict):
            return JsonResponse({'success': False, 'message': 'limit 값이 필요해요.'}, status=400)
        total = budget_service.clean_limits({'etc': body.get('total')}).get('etc') if 'total' in body else None
        if not budget_service.clean_limits(body['limit']) and not isinstance(body.get('items'), dict) and total is None:
            return JsonResponse({'success': False, 'message': '저장할 분류 금액이 없어요.'}, status=400)
        if isinstance(body.get('items'), dict):
            _save_budget_items(travel, body['items'])
        limits = budget_service.save_limits(travel, body['limit'])
        if total is not None:
            travel.t_budget = total   # 비용 관리에서 총예산을 직접 고침
        else:
            # total 을 안 보내면: 여행 만들 때 정한 금액을 지키고, 분류 합계가 더 크면 그만큼 늘린다
            travel.t_budget = max(travel.t_budget or 0, sum(limits.values()))
        travel.save(update_fields=['t_budget'])
    elif request.method == 'GET':
        limits = budget_service.load_limits(travel)
    else:
        return JsonResponse({'success': False, 'message': '허용되지 않는 요청입니다.'}, status=405)

    used = {c: 0 for c in budget_service.CATEGORIES}
    for pay in Pay.objects.filter(schedule__travel=travel).select_related('place'):
        cat = _budget_category(pay)[1]
        if cat in used:
            used[cat] += pay.pay_pay or 0

    result = {
        'success': True,
        'budget': {'total': travel.t_budget or 0, 'limit': limits, 'by': used},
    }

    # ?plan=1 → 지금 일정의 분류별 예상 비용·장소 수도 (카테고리 예산 화면, 추가 키)
    #   plan: {분류: 예상 금액}, counts: {분류: 장소 수}, people: 계산 인원
    if request.method == 'GET' and request.GET.get('plan'):
        people = _budget_people(request, travel.t_id)
        try:
            days = _chat_preview_days(travel, {})
            estimate = budget_service.plan_budget(days, people)
            items = _budget_items(travel, days)
            counts = {c: 0 for c in budget_service.CATEGORIES}
            for item in items:
                counts[item['cat']] = counts.get(item['cat'], 0) + 1
            # 차트용: 여행 날짜 목록과 날짜별 쓴 돈 (Pay)
            daily_used = {}
            for pay in Pay.objects.filter(schedule__travel=travel).select_related('schedule'):
                if pay.schedule_id and pay.schedule and pay.schedule.s_day:
                    key = pay.schedule.s_day.isoformat()
                    daily_used[key] = daily_used.get(key, 0) + (pay.pay_pay or 0)
            result['budget'].update({
                'plan': estimate['by'],
                'counts': counts,
                'people': estimate['people'],
                'items': items,
                'days': [d.get('date') for d in days],
                'daily_used': daily_used,
            })
        except Exception:
            logger.exception('카테고리 예산 일정 예상 실패 travel=%s', travel_id)

    return JsonResponse(result)


def _budget_items(travel, days):
    """비용 관리: 일정 장소마다 AI 금액(ai)과 회원이 고친 금액(amount) — 가격을 모르는 장소도 넣어서 직접 적을 수 있게
    days: plan_budget 을 거친 _chat_preview_days (장소마다 cost)
    → [{sp_id, day, date, name, kind, cat, ai, amount, edited, per, unit, source}]
    """
    saved = dict(TravelBudgetItem.objects.filter(travel=travel).values_list('schedule_place_id', 'amount'))
    items = []
    for day in days:
        for it in day.get('items') or []:
            cost = it.get('cost') or None
            kind = '숙박' if it.get('is_stay') else (it.get('kind') or '')
            ai = cost['amount'] if cost else None
            items.append({
                'sp_id': it.get('sp_id'),
                'day': day.get('day'),
                'date': day.get('date'),
                'name': it.get('name'),
                'kind': it.get('kind') or '',
                'cat': cost['cat'] if cost else budget_service.category_of(kind, it.get('name')),
                'ai': ai,
                'amount': saved.get(it.get('sp_id'), ai),
                'edited': it.get('sp_id') in saved,
                'per': cost['per'] if cost else None,
                'unit': cost['unit'] if cost else None,
                'source': cost['source'] if cost else None,
            })
    return items


def _save_budget_items(travel, items):
    """{sp_id: 금액 | null} 저장 (내 여행의 장소만, null 은 AI 금액으로 되돌림)"""
    ids = []
    for key in items:
        try:
            ids.append(int(key))
        except (TypeError, ValueError):
            continue
    places = {sp.sp_id: sp for sp in SchedulePlace.objects.filter(schedule__travel=travel, sp_id__in=ids)}
    for key, value in items.items():
        try:
            sp = places.get(int(key))
        except (TypeError, ValueError):
            continue
        if not sp:
            continue
        if value is None:
            TravelBudgetItem.objects.filter(schedule_place=sp).delete()
            continue
        try:
            amount = int(str(value).replace(',', ''))
        except (TypeError, ValueError):
            continue
        if 0 <= amount <= 100000000:
            TravelBudgetItem.objects.update_or_create(schedule_place=sp, defaults={'travel': travel, 'amount': amount})


# ==============================================
# 예산 AI (🟦): 예상 비용이 총예산을 넘으면 같은 분류의 더 싼 대안 / 바꾸기
# ==============================================

def _my_travel_json(request, travel_id):
    """(member, travel, 오류 응답) — 로그인 401, 없는 여행 404, 남의 여행 403"""
    member = _login_member(request)
    if not member:
        return None, None, JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)
    travel = Travel.objects.filter(t_id=travel_id).first()
    if not travel:
        return member, None, JsonResponse({'success': False, 'message': '여행을 찾을 수 없습니다.'}, status=404)
    if travel.member_id != member.m_id:
        return member, None, JsonResponse({'success': False, 'message': '권한이 없습니다.'}, status=403)
    return member, travel, None


# GET → {success, people, planned, budget, over, suggestions: [{sp_id, day, name, cat, amount, options: [...]}]}
def budget_alternatives(request, travel_id):
    _, travel, error = _my_travel_json(request, travel_id)
    if error:
        return error

    try:
        # ?cat=food → 그 분류만 (카테고리 예산 화면에서 분류가 넘쳤을 때, 총예산과 상관없이)
        only_cat = request.GET.get('cat')
        result = budget_service.over_budget_options(
            _chat_preview_days(travel, {}),
            _budget_people(request, travel.t_id),
            travel.t_budget,
            only_cat=only_cat if only_cat in budget_service.CATEGORIES else None,
        )
    except Exception:
        logger.exception('예산 대안 실패 travel=%s', travel_id)
        return JsonResponse({'success': False, 'message': '대안을 찾지 못했어요. 잠시 뒤 다시 시도해 주세요.'}, status=500)

    # 대안 정보 칸에 쓸 사진 (저장된 건 바로, 새로 찾는 건 8곳까지 — 나머지는 다음에)
    options = [o for sg in result['suggestions'] for o in sg['options']]
    try:
        attach_photos(options, max_new=8)
    except Exception:
        logger.warning('예산 대안 사진 실패 travel=%s', travel_id, exc_info=True)

    return JsonResponse(dict(result, success=True))


# POST {sp_id, name, addr, kind, lat, lon, kakao_id} → 그 자리의 장소만 대안으로 바꾸고 그날 시간을 다시 계산
@require_POST
def budget_swap(request, travel_id):
    _, travel, error = _my_travel_json(request, travel_id)
    if error:
        return error

    sp = (
        SchedulePlace.objects.select_related('place', 'schedule')
        .filter(sp_id=request.POST.get('sp_id') or 0, schedule__travel=travel)
        .first()
    )
    name = (request.POST.get('name') or '').strip()
    if not sp or not name:
        return JsonResponse({'success': False, 'message': '바꿀 장소 정보가 없습니다.'}, status=400)

    lat = _decimal_or_none(request.POST.get('lat'))
    lon = _decimal_or_none(request.POST.get('lon'))
    addr = (request.POST.get('addr') or '').strip()
    kakao_id = (request.POST.get('kakao_id') or '').strip() or None
    old = sp.place

    if SchedulePlace.objects.filter(schedule=sp.schedule, place__p_name=name).exclude(sp_id=sp.sp_id).exists():
        return JsonResponse({'success': False, 'message': '이미 그날 일정에 있는 장소예요.'}, status=400)

    place = Place.objects.filter(travel=travel, p_name=name, p_addr=addr).first()
    if not place:
        place = Place.objects.create(
            travel=travel, p_name=name, p_addr=addr,
            p_kind=(request.POST.get('kind') or old.p_kind or '').strip(),
            p_lat=lat, p_lon=lon, p_kakao_id=kakao_id,
        )

    with transaction.atomic():
        sp.place = place
        sp.save(update_fields=['place'])
        TravelBudgetItem.objects.filter(schedule_place=sp).delete()   # 다른 장소라 고친 금액은 지움

        # 숙소를 바꾸면 그날 밤 숙소 정보도 같이 (다음 날 출발점이 됨)
        if '숙' in (old.p_kind or ''):
            TravelDayPlan.objects.filter(travel=travel, plan_date=sp.schedule.s_day).update(
                accommodation_name=name, accommodation_addr=addr,
                accommodation_lat=lat, accommodation_lon=lon,
            )
            if travel.accommodation == old.p_name:
                travel.accommodation = name
                travel.accommodation_lat = lat
                travel.accommodation_lon = lon
                travel.save(update_fields=['accommodation', 'accommodation_lat', 'accommodation_lon'])

    recalculate_schedule_timeline(sp.schedule)

    return JsonResponse({
        'success': True,
        'message': "'%s' 대신 '%s'(으)로 바꿨어요." % (old.p_name, name),
        'sp_id': sp.sp_id,
    })


# ==============================================
# 비 오는 날 실내 / 실외 (🟦 rain_service)
# ==============================================

# GET ?name=&lat=&lon=&people=&skip=이름|이름 → {success, options: [실내 대안 …]} (미리보기·일정 관리 같이 씀)
def rain_options(request):
    if not _login_member(request):
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    lat = _float_or_none(request.GET.get('lat'))
    lon = _float_or_none(request.GET.get('lon'))
    if lat is None or lon is None:
        return JsonResponse({'success': False, 'message': '장소 위치가 없어요.'}, status=400)

    skip = [s for s in (request.GET.get('skip') or '').split('|') if s][:50]
    try:
        options = rain_service.indoor_options(
            (request.GET.get('name') or '').strip(), lat, lon,
            budget_service.clean_people(request.GET.get('people') or 2), skip,
        )
    except Exception:
        logger.exception('실내 대안 실패')
        return JsonResponse({'success': False, 'message': '실내 대안을 찾지 못했어요.'}, status=500)

    return JsonResponse({'success': True, 'options': options})


# 장소 사이 대중교통 경로 (🟦 transit_service, 카카오 대중교통 길찾기 · ODsay 대신)
# GET ?from=위도,경도&to=위도,경도 → {success, route: transit_route 결과}
def transit_route(request):
    if not _login_member(request):
        return JsonResponse({'success': False, 'message': '로그인이 필요합니다.'}, status=401)

    def point(text):
        parts = (text or '').split(',')
        if len(parts) != 2:
            return None
        lat, lon = _float_or_none(parts[0]), _float_or_none(parts[1])
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return lat, lon

    start, end = point(request.GET.get('from')), point(request.GET.get('to'))
    if not start or not end:
        return JsonResponse({'success': False, 'message': '출발·도착 위치가 필요해요.'}, status=400)

    route = transit_service.transit_route(start[0], start[1], end[0], end[1])
    if route is None:
        return JsonResponse({'success': False, 'message': '대중교통 경로를 찾지 못했어요.'}, status=502)
    return JsonResponse({'success': True, 'route': route})


# 여행 상세 '체크인하고 다시 나가기' (🟦, 11/09 결정 · 11/10 숙소 두 줄 규칙)
# POST time=HH:MM → 그날 숙소(마지막 숙소 줄)와 같은 Place 로 체크인 줄을 그 시각에 하나 더 넣는다
#   같은 날 같은 숙소 두 줄 = 앞 줄 체크인(짐 두기), 뒤 줄 귀가. 체크인 줄 뒤 일정 시간은 다시 계산
#   → {success, sp_id, message}. 빼기·시각 바꾸기는 기존 일정 삭제·방문시간 수정을 그대로 씀
CHECKIN_STAY_MIN = 30   # 짐 두는 시간 (분)


@require_POST
def travel_checkin(request, travel_id, day):
    _, travel, error = _my_travel_json(request, travel_id)
    if error:
        return error

    schedules = list(Schedule.objects.filter(travel=travel).order_by('s_day'))
    if day < 1 or day > len(schedules):
        return JsonResponse({'success': False, 'message': '존재하지 않는 DAY입니다.'}, status=404)
    schedule = schedules[day - 1]

    rows = list(
        SchedulePlace.objects.filter(schedule=schedule)
        .select_related('place').order_by('visit_order', 'sp_id')
    )
    stays = [row for row in rows if '숙' in (row.place.p_kind or '')]
    if not stays:
        return JsonResponse({'success': False, 'message': '이 날은 숙소가 없어요. 숙소를 먼저 넣어 주세요.'}, status=400)
    stay = stays[-1]
    if sum(1 for row in rows if row.place_id == stay.place_id) >= 2:
        return JsonResponse({'success': False, 'message': '이미 체크인 줄이 있어요. 시각은 체크인 줄 시간을 눌러 바꿔 주세요.'}, status=400)

    try:
        checkin = datetime.strptime((request.POST.get('time') or '').strip(), '%H:%M').time()
    except ValueError:
        return JsonResponse({'success': False, 'message': '체크인 시각을 골라 주세요.'}, status=400)
    if stay.arrive_time and checkin >= stay.arrive_time:
        return JsonResponse({
            'success': False,
            'message': f"체크인은 숙소로 돌아오는 시각({stay.arrive_time.strftime('%H:%M')})보다 빨라야 해요.",
        }, status=400)

    leave = (datetime.combine(schedule.s_day, checkin) + timedelta(minutes=CHECKIN_STAY_MIN)).time()
    with transaction.atomic():
        row = SchedulePlace.objects.create(
            schedule=schedule, place=stay.place, visit_order=stay.visit_order,
            stay_time=CHECKIN_STAY_MIN, arrive_time=checkin, start_time=leave,
        )

        # 하루 계획에도 저장 → 날짜 옮기기·일정 다시 만들기 때도 체크인이 남게 (🟩 generate_schedule 이 읽는 칸)
        TravelDayPlan.objects.filter(travel=travel, plan_date=schedule.s_day).update(checkin_time=checkin)
        reorder_schedule_places_by_time(schedule)                         # 체크인 시각 자리로
        recalculate_schedule_timeline(schedule, anchor_sp_id=row.sp_id)   # 그 뒤 일정 시간 다시

    message = f"{checkin.strftime('%H:%M')}에 {stay.place.p_name} 체크인 줄을 넣었어요."

    # 바로 앞 일정이 체크인 시각보다 늦게 끝나면 겹친다고 알려 줌 (막지는 않음)
    row.refresh_from_db()
    before = (
        SchedulePlace.objects.filter(schedule=schedule, visit_order__lt=row.visit_order)
        .select_related('place').order_by('-visit_order').first()
    )
    if before and before.start_time and before.start_time > checkin:
        message += (f" 앞 일정({before.place.p_name})이 {before.start_time.strftime('%H:%M')}에 끝나서 겹쳐요."
                    " 체크인 시각을 늦추거나 앞 일정 체류를 줄여 주세요.")

    return JsonResponse({'success': True, 'sp_id': row.sp_id, 'message': message})


# 여행 상세 이동 구간: 대중교통·택시·자가용 금액 비교 (🟦 fare_service.move_fares)
# GET ?from=위도,경도&to=위도,경도 → {success, fares: {people, distance, options[], cheapest, walk}}
# 인원은 비용 관리에서 쓰는 인원(_budget_people)
def travel_move_fares(request, travel_id):
    _, travel, error = _my_travel_json(request, travel_id)
    if error:
        return error

    def point(text):
        parts = (text or '').split(',')
        if len(parts) != 2:
            return None
        lat, lon = _float_or_none(parts[0]), _float_or_none(parts[1])
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return lat, lon

    start, end = point(request.GET.get('from')), point(request.GET.get('to'))
    if not start or not end:
        return JsonResponse({'success': False, 'message': '출발·도착 위치가 필요해요.'}, status=400)

    fares = fare_service.move_fares(start[0], start[1], end[0], end[1], _budget_people(request, travel.t_id))
    return JsonResponse({'success': True, 'fares': fares})


# GET → {success, people, days: [{day, date, weather}], places: {sp_id: indoor}}  (places 는 그날만)
def travel_weather(request, travel_id, day):
    _, travel, error = _my_travel_json(request, travel_id)
    if error:
        return error

    schedules = list(Schedule.objects.filter(travel=travel).order_by('s_day'))
    if day < 1 or day > len(schedules):
        return JsonResponse({'success': False, 'message': '존재하지 않는 DAY입니다.'}, status=404)

    weather = {}
    if travel.t_start and travel.t_end:
        center = None
        first = (
            SchedulePlace.objects.filter(schedule__travel=travel, place__p_lat__isnull=False)
            .select_related('place').order_by('schedule__s_day', 'visit_order').first()
        )
        if first:
            center = {'lat': float(first.place.p_lat), 'lon': float(first.place.p_lon)}
        weather = rain_service.trip_days_weather(
            travel.t_place, travel.t_start.isoformat(), travel.t_end.isoformat(), center)

    sps = (
        SchedulePlace.objects.filter(schedule=schedules[day - 1])
        .select_related('place').order_by('visit_order', 'sp_id')
    )
    items = [{
        'sp_id': sp.sp_id, 'name': sp.place.p_name, 'kind': sp.place.p_kind or '',
        'lat': _float_or_none(sp.place.p_lat), 'lon': _float_or_none(sp.place.p_lon),
        'kakao_id': sp.place.p_kakao_id or None, 'is_stay': '숙' in (sp.place.p_kind or ''),
    } for sp in sps]
    rain_service.attach_indoor(items)

    return JsonResponse({
        'success': True,
        'people': _budget_people(request, travel.t_id),
        'days': [
            {'day': i, 'date': s.s_day.isoformat(), 'weather': weather.get(s.s_day.isoformat())}
            for i, s in enumerate(schedules, start=1)
        ],
        'places': {str(it['sp_id']): it['indoor'] for it in items},
    })


# ==============================================
# 카테고리 예산 화면 (React, 🟦) — frontend 빌드 결과(static/budget/)를 띄움
# 데이터는 화면이 budget_category·budget_alternatives·budget_swap 주소로 직접 불러옴
# ==============================================

def category_budget_page(request, travel_id=None):
    member = _login_member(request)
    if not member:
        return redirect('login')

    travels = Travel.objects.filter(member=member).order_by('-t_start', '-t_id')
    if travel_id:
        travel = get_object_or_404(Travel, t_id=travel_id, member=member)
    else:
        travel = travels.first()

    return render(request, 'sherpaapp/category_budget.html', {
        'member': member,
        'travels': travels,
        'travel': travel,
    })
