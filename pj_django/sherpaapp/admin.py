from django.contrib import admin
from django.shortcuts import render
from django.urls import path

from .models import (
    AGE_GROUP_CHOICES,
    GENDER_CHOICES,
    BudgetLog,
    Category,
    EmbedChunk,
    Member,
    Pay,
    Place,
    PlacePhoto,
    Schedule,
    SchedulePlace,
    SharedRoute,
    RouteComment,
    RouteRating,
    Travel,
    TravelBudgetItem,
    TravelCategory,
    TravelDayPlan,
    TravelBudget,
    Review,
    ReviewHelpful,
    ReviewSummary,
)
from .services import stats_service


# =========================================================
# Admin 사이트 제목
# =========================================================

admin.site.site_header = "TRIPA 관리자"
admin.site.site_title = "TRIPA Admin"
admin.site.index_title = "TRIPA 서비스 관리"

# 첫 화면 위에 '회원 통계' 바로가기 (🟩 11/11)
admin.site.index_template = "admin/sherpa_index.html"

# 관리자 첫 화면·왼쪽 메뉴의 표 이름을 한국어로 (모델 Meta를 바꾸면 마이그레이션이 생겨서 화면에서만 바꿈)
KOREAN_MODEL_NAMES = {
    "Member": "회원",
    "Travel": "여행",
    "TravelDayPlan": "날짜별 여행 계획",
    "TravelBudget": "카테고리 예산",
    "TravelBudgetItem": "장소별 예산 금액",
    "BudgetLog": "예산 변경 기록",
    "Category": "취향 카테고리",
    "TravelCategory": "여행별 카테고리",
    "Place": "장소",
    "PlacePhoto": "장소 사진",
    "Schedule": "일정(날짜)",
    "SchedulePlace": "일정 장소",
    "Pay": "지출 (예전)",
    "Review": "리뷰",
    "ReviewHelpful": "리뷰 도움돼요",
    "ReviewSummary": "리뷰 키워드 요약",
    "EmbedChunk": "AI 검색 조각 (RAG)",
    "SharedRoute": "공유 루트",
    "RouteComment": "공유 루트 댓글",
}

_original_get_app_list = admin.site.get_app_list


def _korean_app_list(request, app_label=None):
    app_list = _original_get_app_list(request, app_label)
    for app in app_list:
        if app["app_label"] == "sherpaapp":
            app["name"] = "TRIPA 서비스"
        for model in app["models"]:
            model["name"] = KOREAN_MODEL_NAMES.get(model["object_name"], model["name"])
        app["models"].sort(key=lambda model: model["name"])   # 한국어 이름 가나다순
    return app_list


admin.site.get_app_list = _korean_app_list


# =========================================================
# Inline
# =========================================================

class TravelDayPlanInline(admin.TabularInline):
    model = TravelDayPlan
    extra = 0
    fields = (
        "plan_date",
        "accommodation_name",
        "arrival_time",
        "departure_time",
    )
    ordering = ("plan_date",)


class TravelCategoryInline(admin.TabularInline):
    model = TravelCategory
    extra = 0
    autocomplete_fields = ("category",)


class TravelBudgetInline(admin.TabularInline):
    model = TravelBudget
    extra = 0
    fields = ("category", "amount")


class PlaceInline(admin.TabularInline):
    model = Place
    extra = 0
    fields = (
        "p_name",
        "p_addr",
        "p_kind",
    )
    show_change_link = True


class ScheduleInline(admin.TabularInline):
    model = Schedule
    extra = 0
    fields = ("s_day",)
    ordering = ("s_day",)
    show_change_link = True


class SchedulePlaceInline(admin.TabularInline):
    model = SchedulePlace
    extra = 0
    autocomplete_fields = ("place",)
    fields = (
        "visit_order",
        "place",
        "arrive_time",
        "stay_time",
        "start_time",
        "travel_time",
    )
    ordering = ("visit_order",)


class PayInline(admin.TabularInline):
    model = Pay
    extra = 0
    autocomplete_fields = ("place",)
    fields = (
        "pay_context",
        "pay_pay",
        "place",
    )


# =========================================================
# 회원
# =========================================================

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "m_id",
        "user_id",
        "email",
        "nickname",
        "name",
        "travel_count",
        "review_count",
        "gender",
        "age_group",
    )
    list_filter = (
        "gender",
        "age_group",
    )
    search_fields = (
        "user_id",
        "email",
        "nickname",
        "name",
    )
    ordering = ("m_id",)
    exclude = ("pwd",)   # 비밀번호(암호화된 값)는 관리자 화면에도 안 보이게
    list_per_page = 50

    @admin.display(description="여행 수")
    def travel_count(self, obj):
        return obj.travels.count()

    @admin.display(description="리뷰 수")
    def review_count(self, obj):
        return obj.reviews.count()


# =========================================================
# 여행
# =========================================================

@admin.register(Travel)
class TravelAdmin(admin.ModelAdmin):
    list_display = (
        "t_id",
        "t_title",
        "member",
        "t_place",
        "t_way",
        "t_start",
        "t_end",
        "t_budget",
    )
    list_filter = (
        "t_way",
        "t_start",
        "t_end",
    )
    search_fields = (
        "t_title",
        "t_place",
        "member__user_id",
        "member__nickname",
    )
    autocomplete_fields = ("member",)
    ordering = ("-t_id",)
    date_hierarchy = "t_start"

    fieldsets = (
        (
            "기본 여행 정보",
            {
                "fields": (
                    "member",
                    "t_title",
                    "t_place",
                    "t_way",
                    "t_start",
                    "t_end",
                    "t_day",
                    "t_budget",
                )
            },
        ),
        (
            "출발 정보",
            {
                "fields": (
                    "start_place",
                    "start_addr",
                    "start_lat",
                    "start_lon",
                    "start_time",
                )
            },
        ),
        (
            "숙소 / 복귀 정보",
            {
                "fields": (
                    "accommodation",
                    "accommodation_lat",
                    "accommodation_lon",
                    "checkin_time",
                    "return_time",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = (
        TravelDayPlanInline,
        TravelCategoryInline,
        TravelBudgetInline,
        PlaceInline,
        ScheduleInline,
    )


# =========================================================
# 날짜별 여행 계획
# =========================================================

@admin.register(TravelDayPlan)
class TravelDayPlanAdmin(admin.ModelAdmin):
    list_display = (
        "tdp_id",
        "travel",
        "plan_date",
        "accommodation_name",
        "arrival_time",
        "departure_time",
    )
    list_filter = ("plan_date",)
    search_fields = (
        "travel__t_title",
        "accommodation_name",
        "accommodation_addr",
    )
    autocomplete_fields = ("travel",)
    ordering = ("-plan_date",)


# =========================================================
# 카테고리
# =========================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "c_id",
        "c_name",
    )
    search_fields = ("c_name",)
    ordering = ("c_id",)


@admin.register(TravelCategory)
class TravelCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "tc_id",
        "travel",
        "category",
    )
    list_filter = ("category",)
    search_fields = (
        "travel__t_title",
        "category__c_name",
    )
    autocomplete_fields = (
        "travel",
        "category",
    )


# =========================================================
# 장소
# =========================================================

@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        "p_id",
        "p_name",
        "travel",
        "p_kind",
        "p_addr",
        "p_kakao_id",
    )
    list_filter = ("p_kind",)
    search_fields = (
        "p_name",
        "p_addr",
        "p_kind",
        "travel__t_title",
        "p_kakao_id",
    )
    autocomplete_fields = ("travel",)
    ordering = ("-p_id",)


# =========================================================
# 일정
# =========================================================

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "s_id",
        "travel",
        "s_day",
        "place_count",
        "pay_total",
    )
    list_filter = ("s_day",)
    search_fields = (
        "travel__t_title",
        "travel__member__user_id",
    )
    autocomplete_fields = ("travel",)
    ordering = ("-s_day",)
    date_hierarchy = "s_day"

    inlines = (
        SchedulePlaceInline,
        PayInline,
    )

    @admin.display(description="장소 수")
    def place_count(self, obj):
        return obj.schedule_places.count()

    @admin.display(description="DAY 비용")
    def pay_total(self, obj):
        total = sum(
            pay.pay_pay or 0
            for pay in obj.payments.all()
        )
        return f"{total:,}원"


# =========================================================
# 일정 장소
# =========================================================

@admin.register(SchedulePlace)
class SchedulePlaceAdmin(admin.ModelAdmin):
    list_display = (
        "sp_id",
        "schedule",
        "visit_order",
        "place",
        "arrive_time",
        "stay_time_display_admin",
        "start_time",
        "travel_time_display",
    )
    list_filter = (
        "schedule__s_day",
        "place__p_kind",
    )
    search_fields = (
        "place__p_name",
        "place__p_addr",
        "schedule__travel__t_title",
    )
    autocomplete_fields = (
        "schedule",
        "place",
    )
    ordering = (
        "schedule__s_day",
        "visit_order",
    )

    @admin.display(description="체류시간")
    def stay_time_display_admin(self, obj):
        return obj.stay_time_display

    @admin.display(description="이동시간")
    def travel_time_display(self, obj):
        if obj.travel_time is None:
            return "-"

        hours, minutes = divmod(
            obj.travel_time,
            60,
        )

        if hours and minutes:
            return f"{hours}시간 {minutes}분"

        if hours:
            return f"{hours}시간"

        return f"{minutes}분"


# =========================================================
# 비용
# =========================================================

@admin.register(Pay)
class PayAdmin(admin.ModelAdmin):
    list_display = (
        "pay_id",
        "pay_context",
        "formatted_pay",
        "schedule",
        "place",
    )
    list_filter = (
        "schedule__s_day",
    )
    search_fields = (
        "pay_context",
        "place__p_name",
        "schedule__travel__t_title",
    )
    autocomplete_fields = (
        "schedule",
        "place",
    )
    ordering = ("-pay_id",)

    @admin.display(description="금액")
    def formatted_pay(self, obj):
        return f"{obj.pay_pay or 0:,}원"


# =========================================================
# 리뷰
# =========================================================

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "rv_id",
        "place_name",
        "member",
        "rating",
        "content",
        "created_at",
    )
    list_filter = (
        "rating",
        "created_at",
    )
    search_fields = (
        "place_name",
        "content",
        "kakao_id",
        "member__user_id",
    )
    autocomplete_fields = (
        "member",
        "place",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


# =========================================================
# 리뷰 도움돼요 · 키워드 요약 (🟩 11/11 추가)
# =========================================================

@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ("rh_id", "review", "member")
    search_fields = ("review__place_name", "member__user_id")
    autocomplete_fields = ("review", "member")
    ordering = ("-rh_id",)


@admin.register(ReviewSummary)
class ReviewSummaryAdmin(admin.ModelAdmin):
    list_display = ("rs_id", "kakao_id", "summary", "review_count", "updated_at")
    search_fields = ("kakao_id", "summary")
    list_filter = ("updated_at",)
    ordering = ("-updated_at",)


# =========================================================
# 예산 (카테고리 예산 · 장소별 금액 · 바뀐 기록)
# =========================================================

@admin.register(TravelBudget)
class TravelBudgetAdmin(admin.ModelAdmin):
    list_display = ("tb_id", "travel", "category", "formatted_amount")
    list_filter = ("category",)
    search_fields = ("travel__t_title", "travel__member__user_id")
    autocomplete_fields = ("travel",)
    ordering = ("-tb_id",)

    @admin.display(description="금액")
    def formatted_amount(self, obj):
        return f"{obj.amount or 0:,}원"


@admin.register(TravelBudgetItem)
class TravelBudgetItemAdmin(admin.ModelAdmin):
    list_display = ("tbi_id", "travel", "place_name", "formatted_amount", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("schedule_place__place__p_name", "travel__t_title")
    autocomplete_fields = ("travel", "schedule_place")
    ordering = ("-updated_at",)

    @admin.display(description="장소")
    def place_name(self, obj):
        return obj.schedule_place.place.p_name

    @admin.display(description="금액")
    def formatted_amount(self, obj):
        return f"{obj.amount or 0:,}원"


@admin.register(BudgetLog)
class BudgetLogAdmin(admin.ModelAdmin):
    """DB 트리거(🟧)가 쓰는 기록이라 보기만 (넣기·고치기·지우기 없음)"""
    list_display = ("bl_id", "travel_id", "p_name", "action", "old_amount", "new_amount", "changed_at")
    list_filter = ("action", "changed_at")
    search_fields = ("p_name",)
    ordering = ("-changed_at",)
    date_hierarchy = "changed_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =========================================================
# 장소 사진 · AI 검색 조각
# =========================================================

@admin.register(PlacePhoto)
class PlacePhotoAdmin(admin.ModelAdmin):
    list_display = ("ph_id", "kakao_id", "source", "url", "checked_at")
    list_filter = ("source", "checked_at")
    search_fields = ("kakao_id", "url")
    ordering = ("-checked_at",)


@admin.register(EmbedChunk)
class EmbedChunkAdmin(admin.ModelAdmin):
    list_display = ("ec_id", "kind", "ref_id", "seq", "short_text", "model", "updated_at")
    list_filter = ("kind", "model")
    search_fields = ("ref_id", "text")
    exclude = ("vector",)   # 숫자 수백 개라 화면에 안 띄움
    ordering = ("kind", "ref_id", "seq")

    @admin.display(description="내용")
    def short_text(self, obj):
        return (obj.text or "")[:60]


# =========================================================
# 공유 루트 · 별점 · 댓글
# =========================================================

class RouteRatingInline(admin.TabularInline):
    model = RouteRating
    extra = 0
    autocomplete_fields = ("member",)


class RouteCommentInline(admin.TabularInline):
    model = RouteComment
    extra = 0
    autocomplete_fields = ("member",)


@admin.register(SharedRoute)
class SharedRouteAdmin(admin.ModelAdmin):
    list_display = ("sr_id", "travel", "member", "intro", "rating_count", "comment_count", "created_at")
    list_filter = ("created_at",)
    search_fields = ("travel__t_title", "member__user_id", "intro")
    autocomplete_fields = ("travel", "member")
    ordering = ("-created_at",)
    inlines = (RouteRatingInline, RouteCommentInline)

    @admin.display(description="별점 수")
    def rating_count(self, obj):
        return obj.ratings.count()

    @admin.display(description="댓글 수")
    def comment_count(self, obj):
        return obj.comments.count()


@admin.register(RouteComment)
class RouteCommentAdmin(admin.ModelAdmin):
    list_display = ("rc_id", "route", "member", "content", "created_at")
    list_filter = ("created_at",)
    search_fields = ("content", "member__user_id")
    autocomplete_fields = ("route", "member")
    ordering = ("-created_at",)


# =========================================================
# 회원 통계 화면 /admin/stats/ (🟩 11/11, 숫자는 stats_service — 🟧 Streamlit과 같은 함수)
# =========================================================

def _choice(value, allowed):
    """주소 ?gender=F&age_group=20 값 확인 (모르는 값은 전체)"""
    if value == stats_service.NONE:
        return value
    for code in allowed:
        if str(code) == value:
            return code
    return None


def member_stats_view(request):
    gender = _choice(request.GET.get("gender"), [c for c, _ in GENDER_CHOICES])
    age_group = _choice(request.GET.get("age_group"), [c for c, _ in AGE_GROUP_CHOICES])
    order = request.GET.get("order")
    if order not in ("visits", "reviews", "rating"):
        order = "visits"
    names = stats_service.labels()

    # 성별·나이대 줄 × 장소 종류 칸 = 그 그룹 방문 중 몇 %
    cells = stats_service.group_preferences()
    kinds = sorted(
        {c["kind"] for c in cells if c["kind"]},
        key=lambda k: -sum(c["visits"] for c in cells if c["kind"] == k),
    )
    groups = {}
    for c in cells:
        row = groups.setdefault((c["gender"], c["age_group"]), {"visits": 0, "by_kind": {}})
        row["visits"] += c["visits"]
        row["by_kind"][c["kind"]] = c

    pivot = []
    for (g, a), row in groups.items():
        shares = []
        for kind in kinds:
            cell = row["by_kind"].get(kind)
            pct = round(100 * cell["visits"] / row["visits"]) if cell and row["visits"] else 0
            shares.append({"pct": pct, "rating": cell["rating"] if cell else None})
        pivot.append({
            "label": "%s · %s" % (names["gender"].get(g, g), names["age"].get(a, a)),
            "visits": row["visits"],
            "shares": shares,
        })

    summary = stats_service.member_summary()

    context = {
        **admin.site.each_context(request),
        "title": "회원 통계",
        "summary": summary,
        "gender_cards": [(names["gender"][k], n) for k, n in summary["by_gender"].items()],
        "age_cards": [(names["age"][k], n) for k, n in summary["by_age"].items()],
        "names": names,
        "gender": "" if gender is None else str(gender),
        "age_group": "" if age_group is None else str(age_group),
        "order": order,
        "gender_options": [(str(k), v) for k, v in names["gender"].items()],
        "age_options": [(str(k), v) for k, v in names["age"].items()],
        "places": stats_service.favorite_places(gender, age_group, limit=10, order=order),
        "kinds": kinds,
        "pivot": pivot,
        "spending": stats_service.place_spending(limit=10),
    }
    return render(request, "admin/sherpa_member_stats.html", context)


_original_get_urls = admin.site.get_urls


def _urls_with_stats():
    # admin_view: 관리자(is_staff)로 로그인해야만 열림, 아니면 로그인 화면으로
    return [
        path("stats/", admin.site.admin_view(member_stats_view), name="member_stats"),
    ] + _original_get_urls()


admin.site.get_urls = _urls_with_stats