"""관리자 '회원 화면 보기' /manage/ (🟩 11/12) — 읽기 전용은 middleware.ManageReadOnlyMiddleware

/manage/              회원 목록 (검색) → [이 회원 화면 보기]
/manage/view/<m_id>/  POST: 그 회원으로 로그인한 것처럼 (원래 로그인은 기억해 둠) → 내 여행 화면
/manage/stop/         POST: 끝내기 → 원래대로 → /manage/
장고 관리자(is_staff)만. 회원 표에 칸을 더하지 않아서 마이그레이션 없음
"""
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .middleware import MANAGE_KEY, end_manage_view
from .models import AGE_GROUP_CHOICES, GENDER_CHOICES, Member

PER_PAGE = 50


@staff_member_required
def manage_home(request):
    q = (request.GET.get('q') or '').strip()
    members = (
        Member.objects.annotate(travel_count=Count('travels', distinct=True))
        .order_by('-m_id')
    )
    if q:
        members = members.filter(
            Q(user_id__icontains=q) | Q(name__icontains=q) | Q(nickname__icontains=q) | Q(email__icontains=q)
        )

    page = Paginator(members, PER_PAGE).get_page(request.GET.get('page'))
    genders, ages = dict(GENDER_CHOICES), dict(AGE_GROUP_CHOICES)
    rows = [{
        'm_id': m.m_id,
        'user_id': m.user_id,
        'name': m.name or m.nickname or '',
        'gender': genders.get(m.gender, '-'),
        'age': ages.get(m.age_group, '-'),
        'travels': m.travel_count,
        'joined': m.joined_at,
    } for m in page]

    return render(request, 'admin/sherpa_manage.html', {
        **admin.site.each_context(request),
        'title': '회원 화면 보기 (읽기 전용)',
        'rows': rows,
        'page': page,
        'q': q,
        'viewing': request.session.get(MANAGE_KEY),
    })


@staff_member_required
@require_POST
def manage_start(request, m_id):
    member = get_object_or_404(Member, m_id=m_id)
    view = request.session.get(MANAGE_KEY)
    # 이미 다른 회원을 보고 있었으면 그때 기억한 '원래 로그인'을 그대로
    prev = view['prev_user'] if view else request.session.get('login_ok_user')
    request.session[MANAGE_KEY] = {
        'user_id': member.user_id,
        'name': member.name or member.nickname or member.user_id,
        'prev_user': prev,
    }
    request.session['login_ok_user'] = member.user_id
    return redirect('travel_list')


@require_POST
def manage_stop(request):
    end_manage_view(request.session)
    if getattr(request.user, 'is_staff', False):
        return redirect('manage_home')
    return redirect('index')
