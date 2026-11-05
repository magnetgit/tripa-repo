from django.urls import path
from . import views


urlpatterns = [

    # ==========================================
    # 메인
    # ==========================================

    path(
        '',
        views.index,
        name='index'
    ),


    # ==========================================
    # 회원
    # ==========================================

    path(
        'join/',
        views.join,
        name='join'
    ),

    path(
        'login/',
        views.login,
        name='login'
    ),

    path(
        'check_email/',
        views.check_email,
        name='check_email'
    ),

    path(
        'join_ok/',
        views.join_ok,
        name='join_ok'
    ),

    path(
        'login_ok/',
        views.login_ok,
        name='login_ok'
    ),

    path(
        'logout/',
        views.logout,
        name='logout'
    ),

    path(
        'idpw/',
        views.idpw,
        name='idpw'
    ),

    path(
        'id_find/',
        views.id_find,
        name='id_find'
    ),

    path(
        'pw_find/',
        views.pw_find,
        name='pw_find'
    ),


    # ==========================================
    # 마이페이지
    # ==========================================

    path(
        'mypage/',
        views.mypage,
        name='mypage'
    ),

    path(
        'mypage_edit/',
        views.mypage_edit,
        name='mypage_edit'
    ),


    # ==========================================
    # 장소 검색
    # ==========================================

    path(
        'place_search/',
        views.place_search,
        name='place_search'
    ),

    path(
        'place_search_search',
        views.place_search_search,
        name='place_search_search'
    ),


    # ==========================================
    # 여행
    # ==========================================

    path(
        'travel_create/',
        views.travel_create,
        name='travel_create'
    ),

    path(
        'travel_chat/',
        views.travel_chat,
        name='travel_chat'
    ),

    path(
        'travel_chat_apply/',
        views.travel_chat_apply,
        name='travel_chat_apply'
    ),

    path(
        'travel_chat_preview/',
        views.travel_chat_preview,
        name='travel_chat_preview'
    ),
    # API (mock.json 모양)
    path(
        'api/chat/',
        views.api_chat,
        name='api_chat'
    ),
    # API (mock.json 모양)
    path(
        'api/trips/<int:trip_id>/',
        views.api_trip,
        name='api_trip'
    ),
    # React 채팅 시험 화면 (frontend 빌드 결과를 띄움)
    path(
        'chat/',
        views.chat_page,
        name='chat_page'
    ),

    path(
        'travel_list/',
        views.travel_list,
        name='travel_list'
    ),

    path(
        'schedule_manage/',
        views.schedule_manage,
        name='schedule_manage'
    ),

    path(
        'travel_detail/<int:travel_id>/',
        views.travel_detail,
        name='travel_detail'
    ),

    path(
        'travel_detail_day/<int:travel_id>/<int:day>/',
        views.travel_detail_day,
        name='travel_detail_day'
    ),

    path(
        'travel_update/<int:travel_id>/',
        views.travel_update,
        name='travel_update'
    ),

    path(
        'travel_reschedule/<int:travel_id>/',
        views.travel_reschedule,
        name='travel_reschedule'
    ),

    path(
        'route/<int:sr_id>/',
        views.route_detail,
        name='route_detail'
    ),

    path(
        'route/<int:sr_id>/rate/',
        views.route_rate,
        name='route_rate'
    ),

    path(
        'route/<int:sr_id>/comment/',
        views.route_comment,
        name='route_comment'
    ),

    path(
        'route/comment/<int:rc_id>/delete/',
        views.route_comment_delete,
        name='route_comment_delete'
    ),

    path(
        'route_share/<int:travel_id>/',
        views.route_share,
        name='route_share'
    ),

    path(
        'travel_costs/<int:travel_id>/<int:day>/',
        views.travel_costs,
        name='travel_costs'
    ),

    path(
        'travel_hours/<int:travel_id>/<int:day>/',
        views.travel_hours,
        name='travel_hours'
    ),

    # 예산 AI (🟦): 초안 예상 비용, 여행별 카테고리 예산 (GET 읽기 / POST 저장)
    path(
        'budget_estimate/',
        views.budget_estimate,
        name='budget_estimate'
    ),

    path(
        'budget/<int:travel_id>/category/',
        views.budget_category,
        name='budget_category'
    ),

    path(
        'travel_festivals/<int:travel_id>/',
        views.travel_festivals,
        name='travel_festivals'
    ),

    path(
        'travel_delete/<int:travel_id>/',
        views.travel_delete,
        name='travel_delete'
    ),


    # ==========================================
    # 일정 장소
    # ==========================================

    path(
        'schedule_place_search/',
        views.schedule_place_search,
        name='schedule_place_search'
    ),

    path(
        'schedule_place_add/',
        views.schedule_place_add,
        name='schedule_place_add'
    ),

    path(
        'schedule_place_delete/',
        views.schedule_place_delete,
        name='schedule_place_delete'
    ),

    path(
        'schedule_place_reorder/',
        views.schedule_place_reorder,
        name='schedule_place_reorder'
    ),

    # ==========================================
    # 리뷰 API (목록·평균·키워드 요약)
    # ==========================================

    path(
        'review_list/',
        views.review_list,
        name='review_list'
    ),

    path(
        'review_summary/',
        views.review_summary,
        name='review_summary'
    ),

    path(
        'review_keywords/',
        views.review_keywords,
        name='review_keywords'
    ),

    path(
        'schedule_place_time_update/',
        views.schedule_place_time_update,
        name='schedule_place_time_update'
    ),


    # ==========================================
    # 경로 계산
    # ==========================================

    path(
        'api/route/<int:schedule_id>/',
        views.travel_route,
        name='travel_route'
    ),


    # ==========================================
    # 비용 관리
    # ==========================================

    path(
        'budget/',
        views.budget,
        name='budget'
    ),

    path(
        'budget/<int:travel_id>/',
        views.budget,
        name='budget_travel'
    ),

    path(
        'budget/<int:travel_id>/update-total/',
        views.budget_update_total,
        name='budget_update_total'
    ),

    # AI 예상 예산 다시 계산 (저장된 일정 × 인원)
    path(
        'budget/<int:travel_id>/ai-fill/',
        views.budget_ai_fill,
        name='budget_ai_fill'
    ),

    path(
        'budget/<int:travel_id>/add/',
        views.budget_add,
        name='budget_add'
    ),

    path(
        'budget/<int:travel_id>/delete/<int:pay_id>/',
        views.budget_delete,
        name='budget_delete'
    ),

    path(
        'budget/<int:travel_id>/update/<int:pay_id>/',
        views.budget_update_pay,
        name='budget_update_pay'
    ),

    path(
        'member_delete/',
        views.member_delete,
        name='member_delete'
    ),


    # ==========================================
    # 리뷰 게시판
    # ==========================================

    path(
        'review/',
        views.review_board,
        name='review_board'
    ),

    path(
        'review/write/',
        views.review_write,
        name='review_write'
    ),

    path(
        'review/<int:rv_id>/edit/',
        views.review_update,
        name='review_update'
    ),

    path(
        'review/<int:rv_id>/delete/',
        views.review_delete,
        name='review_delete'
    ),

    path(
        'review/<int:rv_id>/helpful/',
        views.review_helpful,
        name='review_helpful'
    ),
]
