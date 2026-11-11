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

    path(
        'pw_code/',
        views.pw_code,
        name='pw_code'
    ),

    # 비밀번호 찾기: 인증 코드만 확인 (🟦 [확인] 버튼)
    path(
        'pw_code_check/',
        views.pw_code_check,
        name='pw_code_check'
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
    # 장소 정보 한 번에 (🟩 11/11, mock.json place_info)
    path(
        'api/place_info/',
        views.api_place_info,
        name='api_place_info'
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

    # 비 오는 날 실내 / 실외 (🟦): 실내 대안, 여행 날짜별 날씨·장소 실내 여부
    path(
        'rain_options/',
        views.rain_options,
        name='rain_options'
    ),

    path(
        'travel_weather/<int:travel_id>/<int:day>/',
        views.travel_weather,
        name='travel_weather'
    ),

    # 장소 사이 대중교통 경로 (🟦 카카오 대중교통 길찾기, ODsay 대신)
    path(
        'transit_route/',
        views.transit_route,
        name='transit_route'
    ),

    # 여행 상세 '체크인하고 다시 나가기': 그날 숙소 체크인 줄 넣기 (🟦)
    path(
        'travel_checkin/<int:travel_id>/<int:day>/',
        views.travel_checkin,
        name='travel_checkin'
    ),

    # 여행 상세 이동 구간 금액 비교: 대중교통·택시·자가용 (🟦)
    path(
        'travel_move_fares/<int:travel_id>/',
        views.travel_move_fares,
        name='travel_move_fares'
    ),
    path(
        'travel_access/<int:travel_id>/',
        views.travel_access,
        name='travel_access'
    ),
    path(
        'travel_access/<int:travel_id>/choose/',
        views.travel_access_choose,
        name='travel_access_choose'
    ),

    # 예산을 넘으면 같은 분류의 더 싼 대안 (🟦 예산 AI)
    path(
        'budget_alternatives/<int:travel_id>/',
        views.budget_alternatives,
        name='budget_alternatives'
    ),

    path(
        'budget_swap/<int:travel_id>/',
        views.budget_swap,
        name='budget_swap'
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

    # 여행 상세 '운영시간에 맞추기' 버튼 (🟦 마감 넘는 체류 줄이기)
    path(
        'travel_fit_hours/<int:travel_id>/<int:day>/',
        views.travel_fit_hours,
        name='travel_fit_hours'
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
        'budget_log/<int:travel_id>/',
        views.budget_log,
        name='budget_log'
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
        'similar_places/',
        views.similar_places,
        name='similar_places'
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
    # 비용 관리 = React 카테고리 예산 화면 (🟦, 11/09)
    # AI가 매긴 분류별 금액을 회원이 고치는 화면. 예전 지출 기록 화면(budget.html)은 없앰
    # ==========================================

    path(
        'budget/',
        views.category_budget_page,
        name='budget'
    ),

    path(
        'budget/<int:travel_id>/',
        views.category_budget_page,
        name='budget_travel'
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
