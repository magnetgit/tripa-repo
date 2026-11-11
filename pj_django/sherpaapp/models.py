from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

# ==============================================
# 회원
# ==============================================

GENDER_CHOICES = [
    ('M', '남성'),
    ('F', '여성')
]
AGE_GROUP_CHOICES = [
    (10, '10대'),
    (20, '20대'),
    (30, '30대'),
    (40, '40대'),
    (50, '50대'),
    (60, '60대 이상')
]

# 프로필 캐릭터 (그림: static/sherpaapp/avatars/<키>.svg)
AVATAR_CHOICES = [
    ('bear', '배낭 곰'),
    ('cat', '선글라스 고양이'),
    ('fox', '밀짚모자 여우'),
    ('penguin', '고글 펭귄'),
    ('rabbit', '베레모 토끼'),
    ('dog', '모자 강아지'),
    ('panda', '비니 판다'),
    ('frog', '안경 개구리'),
    ('lion', '선글라스 사자'),
    ('koala', '꽃핀 코알라'),
    ('hamster', '헤드폰 햄스터'),
    ('duck', '캡모자 오리'),
    ('raccoon', '나비넥타이 너구리'),
    ('pig', '고깔모자 돼지'),
    ('monkey', '두건 원숭이'),
    ('owl', '학사모 부엉이'),
    ('tiger', '하트안경 호랑이'),
    ('sheep', '리본 양'),
]
AVATAR_KEYS = [key for key, _ in AVATAR_CHOICES]

class Member(models.Model):

    m_id = models.AutoField(
        primary_key=True,
        db_column='M_ID'
    )

    user_id = models.CharField(
        max_length=100,
        db_column='ID',
        unique=True
    )

    email = models.EmailField(
        max_length=100,
        db_column='EMAIL',
        null=True,
        blank=True,
        unique=True
    )

    pwd = models.CharField(
        max_length=255,
        db_column='PWD'
    )

    nickname = models.CharField(
        max_length=30,
        db_column='NICKNAME'
    )

    name = models.CharField(
        max_length=30,
        db_column='NAME'
    )

    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        null=True,
        blank=True,
        db_column='GENDER'
    )

    age_group = models.PositiveSmallIntegerField(
        choices=AGE_GROUP_CHOICES,
        null=True,
        blank=True,
        db_column='AGE_GROUP'
    )

    # 프로필 캐릭터 키 (AVATAR_CHOICES 중 하나, 가입 때 안 고르면 랜덤)
    profile_img = models.CharField(
        max_length=30,
        choices=AVATAR_CHOICES,
        null=True,
        blank=True,
        db_column='PROFILE_IMG'
    )

    # 가입 시각 (운영 대시보드 월별·연도별 증감). 칸을 만들기 전 회원은 마이그레이션 시각으로 채워짐
    joined_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        db_column='JOINED_AT'
    )

    class Meta:
        db_table = 'member'

    def __str__(self):
        return self.nickname

    @property
    def avatar_key(self):
        # 값이 없는 예전 회원은 회원번호로 정해서 항상 같은 캐릭터가 나오게 함
        if self.profile_img in AVATAR_KEYS:
            return self.profile_img
        return AVATAR_KEYS[(self.m_id or 0) % len(AVATAR_KEYS)]


# ==============================================
# 여행
# ==============================================

class Travel(models.Model):

    t_id = models.AutoField(
        primary_key=True,
        db_column='T_ID'
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column='M_ID',
        related_name='travels'
    )

    # 기존 필드
    t_day = models.DateField(
        db_column='T_DAY',
        null=True,
        blank=True
    )

    # 여행을 만든 시각 (T_DAY 는 출발일이라 따로, 운영 대시보드 월별·연도별 증감)
    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        db_column='CREATED_AT'
    )

    t_place = models.CharField(
        max_length=100,
        db_column='T_PLACE',
    )

    t_title = models.CharField(
        max_length=100,
        db_column='T_TITLE',
    )

    t_way = models.CharField(
        max_length=30,
        db_column='T_WAY',
        null=True,
        blank=True
    )

    t_start = models.DateField(
        db_column='T_START',
    )

    t_end = models.DateField(
        db_column='T_END',
    )

    # ==========================================
    # 총 예산
    # ==========================================

    t_budget = models.IntegerField(
        db_column='T_BUDGET',
        default=100000
    )

    # ==========================================
    # 자동 일정 추천에 필요한 추가 정보
    # ==========================================

    # 사용자의 출발 장소
    start_place = models.CharField(
        max_length=200,
        db_column='START_PLACE',
        null=True,
        blank=True
    )

    start_addr = models.CharField(
        max_length=255,
        db_column='START_ADDR',
        null=True,
        blank=True
    )

    start_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='START_LAT',
        null=True,
        blank=True
    )

    start_lon = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='START_LON',
        null=True,
        blank=True
    )

    start_time = models.TimeField(
        db_column='START_TIME',
        null=True,
        blank=True
    )

    # 숙소
    accommodation = models.CharField(
        max_length=200,
        db_column='ACCOMMODATION',
        null=True,
        blank=True
    )

    accommodation_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='ACCOMMODATION_LAT',
        null=True,
        blank=True
    )

    accommodation_lon = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='ACCOMMODATION_LON',
        null=True,
        blank=True
    )

    # 체크인 시간
    checkin_time = models.TimeField(
        db_column='CHECKIN_TIME',
        null=True,
        blank=True
    )

    # 마지막 DAY 최초 출발지 복귀 예정 시간
    # 값이 없으면 화면/경로 API에서 22:00을 기본값으로 사용한다.
    return_time = models.TimeField(
        db_column='RETURN_TIME',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'travel'

    def __str__(self):
        return self.t_title or ''

# ==============================================
# 카테고리 예산
# ==============================================

BUDGET_CATEGORY_CHOICES = [
    ('sight', '관광지'),
    ('food', '식비'),
    ('cafe', '카페'),
    ('move', '교통'),
    ('stay', '숙박'),
    ('shop', '쇼핑'),
    ('etc', '기타')
]

class TravelBudget(models.Model):

    tb_id = models.AutoField(
        primary_key=True,
        db_column='TB_ID'
    )

    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='budgets'
    )

    category = models.CharField(
        max_length=10,
        choices=BUDGET_CATEGORY_CHOICES,
        db_column='CATEGORY'
    )

    amount = models.PositiveIntegerField(
        db_column='AMOUNT',
        default=0
    )

    class Meta:
        db_table = 'travel_budget'

        constraints = [
            models.UniqueConstraint(
                fields=['travel', 'category'],
                name='unique_travel_budget'
            )
        ]            

# ==============================================
# 여행 날짜별 계획
# ==============================================

class TravelDayPlan(models.Model):

    tdp_id = models.AutoField(
        primary_key=True,
        db_column='TDP_ID'
    )

    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='day_plans'
    )

    plan_date = models.DateField(
        db_column='PLAN_DATE'
    )

    accommodation_name = models.CharField(
        max_length=200,
        db_column='ACCOMMODATION_NAME',
        null=True,
        blank=True
    )

    accommodation_addr = models.CharField(
        max_length=255,
        db_column='ACCOMMODATION_ADDR',
        null=True,
        blank=True
    )

    accommodation_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='ACCOMMODATION_LAT',
        null=True,
        blank=True
    )

    accommodation_lon = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        db_column='ACCOMMODATION_LON',
        null=True,
        blank=True
    )

    arrival_time = models.TimeField(
        db_column='ARRIVAL_TIME',
        null=True,
        blank=True
    )

    departure_time = models.TimeField(
        db_column='DEPARTURE_TIME',
        null=True,
        blank=True
    )

    # 숙소에 들렀다(체크인·짐 두기) 다시 나갈 시각 (🟩 11/11). 비면 숙소 도착(arrival_time)이 그날 끝
    checkin_time = models.TimeField(
        db_column='CHECKIN_TIME',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'travel_day_plan'
        ordering = ['plan_date']

        constraints = [
            models.UniqueConstraint(
                fields=['travel', 'plan_date'],
                name='unique_travel_day_plan'
            )
        ]

    def __str__(self):
        return f'{self.travel} - {self.plan_date}'


# ==============================================
# 카테고리
# ==============================================

class Category(models.Model):

    c_id = models.AutoField(
        primary_key=True,
        db_column='C_ID'
    )

    c_name = models.CharField(
        max_length=100,
        db_column='C_NAME',
        unique=True
    )

    class Meta:
        db_table = 'categories'

    def __str__(self):
        return self.c_name


# ==============================================
# 여행 - 카테고리 연결
# ==============================================

class TravelCategory(models.Model):

    tc_id = models.AutoField(
        primary_key=True,
        db_column='TC_ID'
    )

    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='travel_categories'
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column='C_ID',
        related_name='travel_categories'
    )

    class Meta:
        db_table = 'travel_category'

        constraints = [
            models.UniqueConstraint(
                fields=['travel', 'category'],
                name='unique_travel_category'
            )
        ]

    def __str__(self):
        return f'{self.travel} - {self.category}'


# ==============================================
# 장소
# ==============================================

class Place(models.Model):

    p_id = models.AutoField(
        primary_key=True,
        db_column='P_ID'
    )

    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='places'
    )

    p_name = models.CharField(
        max_length=100,
        db_column='P_NAME'
    )

    p_addr = models.CharField(
        max_length=255,
        db_column='P_ADDR',
        null=True,
        blank=True
    )

    p_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        db_column='P_LAT'
    )

    p_lon = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        db_column='P_LON'
    )

    # 실제 장소 종류
    # 예: 역사 / 카페 / 음식 / 공원
    p_kind = models.CharField(
        max_length=100,
        db_column='P_KIND',
        null=True,
        blank=True
    )

    p_image = models.TextField(
        db_column='P_IMAGE',
        null=True,
        blank=True
    )

    p_kakao_id = models.CharField(
        max_length=20,
        db_column='P_KAKAO_ID',
        null=True,
        blank=True,
        db_index=True
    )

    class Meta:
        db_table = 'place'

    def __str__(self):
        return self.p_name

# ==============================================
# 리뷰
# ==============================================

class Review(models.Model):

    rv_id = models.AutoField(
        primary_key=True,
        db_column='RV_ID'
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column='M_ID',
        related_name='reviews'
    )

    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='P_ID',
        related_name='reviews'
    )

    kakao_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_column='KAKAO_ID',
        db_index=True
    )

    place_name = models.CharField(
        max_length=100,
        db_column='PLACE_NAME'
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_column='RATING'
    )

    content = models.CharField(
        max_length=100,
        db_column='CONTENT'
    )

    tags = models.JSONField(
        default=list,
        blank=True,
        db_column='TAGS'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='CREATED_AT'
    )

    class Meta:
        db_table = 'review'

        constraints = [
            models.UniqueConstraint(
                fields=['member', 'kakao_id'],
                name='unique_review_member_kakao_id'
            )
        ]

# ==============================================
# 도움돼요
# ==============================================

class ReviewHelpful(models.Model):

    rh_id = models.AutoField(
        primary_key=True,
        db_column='RH_ID'
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column='M_ID'
    )

    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='helpfuls',
        db_column='RV_ID'
    )

    class Meta:
        db_table = 'review_helpful'

        constraints = [
            models.UniqueConstraint(
                fields=['member', 'review'],
                name='unique_review_helpful'
            )
        ]

# ==============================================
# 일정
# ==============================================

class Schedule(models.Model):

    s_id = models.AutoField(
        primary_key=True,
        db_column='S_ID'
    )

    s_day = models.DateField(
        db_column='S_DAY'
    )

    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='schedules'
    )

    class Meta:
        db_table = 'schedule'
        ordering = ['s_day']
        constraints = [models.UniqueConstraint(
            fields=['travel', 's_day'],
            name='unique_schedule'
            )]

    def __str__(self):
        return str(self.s_day)


# ==============================================
# 일정 장소
# ==============================================

class SchedulePlace(models.Model):

    sp_id = models.AutoField(
        primary_key=True,
        db_column='SP_ID'
    )

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        db_column='S_ID',
        related_name='schedule_places'
    )

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        db_column='P_ID',
        related_name='schedule_places'
    )

    # 몇 번째 방문 장소인지
    visit_order = models.IntegerField(
        db_column='VISIT_ORDER'
    )

    # 체류 시간 (분)
    stay_time = models.IntegerField(
        db_column='STAY_TIME',
        null=True,
        blank=True,
        help_text='체류 시간(분)'
    )

    # 도착 시간
    arrive_time = models.TimeField(
        db_column='ARRIVAL_TIME',
        null=True,
        blank=True
    )

    # 출발 시간
    start_time = models.TimeField(
        db_column='START_TIME',
        null=True,
        blank=True
    )

    # 이전 장소 → 현재 장소 이동 시간
    travel_time = models.IntegerField(
        db_column='TRAVEL_TIME',
        null=True,
        blank=True,
        help_text='이동 시간(분)'
    )

    class Meta:
        db_table = 'schedule_places'
        ordering = ['visit_order']

    def __str__(self):
        return (
            f'{self.schedule.s_day}'
            f' - {self.visit_order}. '
            f'{self.place.p_name}'
        )

    @property
    def stay_time_display(self):

        if self.stay_time is None:
            return ''

        hours, minutes = divmod(
            self.stay_time,
            60
        )

        if hours and minutes:
            return f'{hours}시간 {minutes}분'

        elif hours:
            return f'{hours}시간'

        return f'{minutes}분'


# ==============================================
# 비용 관리: 장소별 예산 (🟦 11/09)
# AI가 일정 장소마다 매긴 금액(가격 × 인원)을 회원이 고친 값만 저장한다.
# 저장한 값이 없는 장소는 AI 금액을 그대로 쓴다. 분류 합계는 travel_budget 에 저장.
# 일정에서 장소를 빼면(SchedulePlace 삭제) 같이 지워진다.
# ==============================================

class TravelBudgetItem(models.Model):

    tbi_id = models.AutoField(
        primary_key=True,
        db_column='TBI_ID'
    )

    travel = models.ForeignKey(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='budget_items'
    )

    # 일정의 그 자리 (장소 하나에 금액 하나)
    schedule_place = models.OneToOneField(
        SchedulePlace,
        on_delete=models.CASCADE,
        db_column='SP_ID',
        related_name='budget_item'
    )

    amount = models.PositiveIntegerField(
        db_column='AMOUNT',
        default=0
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        db_column='UPDATED_AT'
    )

    class Meta:
        db_table = 'travel_budget_item'


class BudgetLog(models.Model):

    bl_id = models.AutoField(
        primary_key=True,
        db_column='BL_ID'
    )

    travel_id = models.IntegerField(
        db_column='T_ID'
    )

    sp_id = models.IntegerField(
        db_column='SP_ID'
    )

    p_name = models.CharField(
        max_length=100,
        db_column='P_NAME'
    )

    action = models.CharField(
        max_length=10,
        db_column='ACTION'
    )

    old_amount = models.IntegerField(
        db_column='OLD_AMOUNT',
        null=True,
        blank=True
    )

    new_amount = models.IntegerField(
        db_column='NEW_AMOUNT',
        null=True,
        blank=True
    )

    changed_at = models.DateTimeField(
        db_column='CHANGED_AT'
    )

    class Meta:
        db_table = 'budget_log'
        ordering = ['-bl_id']


# ==============================================
# 비용
# ==============================================

class Pay(models.Model):

    pay_id = models.AutoField(
        primary_key=True,
        db_column='PAY_ID'
    )

    pay_context = models.CharField(
        max_length=255,
        db_column='PAY_CONTENT',
        null=True,
        blank=True
    )

    pay_pay = models.IntegerField(
        db_column='PAY_PAY',
    )

    # 어느 날짜의 비용인지
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        db_column='S_ID',
        related_name='payments'
    )

    # 어느 장소에서 발생한 비용인지
    # 장소와 관계없는 비용은 NULL 가능
    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        db_column='P_ID',
        null=True,
        blank=True,
        related_name='payments'
    )

    class Meta:
        db_table = 'pay'

    def __str__(self):

        if self.pay_context:
            return f'{self.pay_context} - {self.pay_pay or 0}원'

        return f'{self.pay_pay or 0}원'

# ==============================================
# 장소 사진 (카카오 장소 ID당 한 장)
# ==============================================

PHOTO_SOURCE_CHOICES = [
    ('tour', '한국관광공사'),
    ('kakao', '카카오 이미지 검색'),
    ('none', '사진 없음'),
]


class PlacePhoto(models.Model):

    ph_id = models.AutoField(
        primary_key=True,
        db_column='PH_ID'
    )

    kakao_id = models.CharField(
        max_length=20,
        unique=True,
        db_column='KAKAO_ID'
    )

    # 사진 없음(none)이면 NULL
    url = models.TextField(
        null=True,
        blank=True,
        db_column='URL'
    )

    source = models.CharField(
        max_length=10,
        choices=PHOTO_SOURCE_CHOICES,
        db_column='SOURCE'
    )

    # 사진 없음은 이 날짜로부터 일정 기간 뒤 다시 찾는다
    checked_at = models.DateTimeField(
        auto_now=True,
        db_column='CHECKED_AT'
    )

    class Meta:
        db_table = 'place_photo'

    def __str__(self):
        return f'{self.kakao_id} ({self.source})'


# 장소별 리뷰 AI 요약 저장 (카카오 ID당 한 줄). review_count가 바뀌면 다시 요약
class ReviewSummary(models.Model):

    rs_id = models.AutoField(
        primary_key=True,
        db_column='RS_ID'
    )

    kakao_id = models.CharField(
        max_length=20,
        unique=True,
        db_column='KAKAO_ID'
    )

    keywords = models.JSONField(
        default=list,
        blank=True,
        db_column='KEYWORDS'
    )

    summary = models.CharField(
        max_length=100,
        blank=True,
        db_column='SUMMARY'
    )

    review_count = models.IntegerField(
        db_column='REVIEW_COUNT',
        default=0
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        db_column='UPDATED_AT'
    )

    class Meta:
        db_table = 'review_summary'

    def __str__(self):
        return f'{self.kakao_id} - {len(self.keywords)} ({self.review_count})'


# ==============================================
# 리뷰·관광공사 소개글 임베딩 조각
# ==============================================
# 글 조각과 그 벡터(숫자 목록)를 저장하는 표 (embed_chunk)
# 🟧 리뷰 RAG(kind='review')와 🟩 여행지 정보 RAG(kind='tour')가 같이 쓴다 (TEAM_UPDATES 11/09 공유 정의)
# 저장·검색은 직접 하지 말고 services/embed_service.py의 save_chunks·search를 쓴다
class EmbedChunk(models.Model):

    ec_id = models.AutoField(
        primary_key=True,
        db_column='EC_ID'
    )

    kind = models.CharField(
        max_length=20,
        db_column='KIND'
    )

    ref_id = models.CharField(
        max_length=64,
        db_column='REF_ID'
    )

    seq = models.PositiveSmallIntegerField(
        default=0,
        db_column='SEQ'
    )

    text = models.TextField(
        db_column='TEXT'
    )

    vector = models.JSONField(
        db_column='VECTOR'
    )

    model = models.CharField(
        max_length=100,
        db_column='MODEL'
    )

    meta = models.JSONField(
        default=dict,
        blank=True,
        db_column='META'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        db_column='UPDATED_AT'
    )

    # 표 이름과 인덱스: (kind, ref_id)는 옛 조각 지울 때, model은 지금 모델 것만 찾을 때 빠르게
    class Meta:
        db_table = 'embed_chunk'
        indexes = [models.Index(fields=['kind', 'ref_id']), models.Index(fields=['model'])]


# ==============================================
# 여행 루트 공유 (리뷰 게시판 '여행 루트' 탭)
# - 주인이 '게시판에 공유'를 누른 여행만 남에게 보임
# - 다른 회원은 별점(한 사람 1개, 바꿀 수 있음)과 댓글을 남김
# ==============================================

class SharedRoute(models.Model):

    sr_id = models.AutoField(
        primary_key=True,
        db_column='SR_ID'
    )

    # 여행 하나당 공유 하나 (여행을 지우면 같이 지워짐)
    travel = models.OneToOneField(
        Travel,
        on_delete=models.CASCADE,
        db_column='T_ID',
        related_name='shared_route'
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column='M_ID',
        related_name='shared_routes'
    )

    # 한 줄 소개 (선택)
    intro = models.CharField(
        max_length=200,
        blank=True,
        default='',
        db_column='INTRO'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='CREATED_AT'
    )

    class Meta:
        db_table = 'shared_route'

    def __str__(self):
        return f'{self.travel.t_title} ({self.member.nickname})'


class RouteRating(models.Model):

    rr_id = models.AutoField(
        primary_key=True,
        db_column='RR_ID'
    )

    route = models.ForeignKey(
        SharedRoute,
        on_delete=models.CASCADE,
        db_column='SR_ID',
        related_name='ratings'
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column='M_ID',
        related_name='route_ratings'
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_column='RATING'
    )

    created_at = models.DateTimeField(
        auto_now=True,
        db_column='CREATED_AT'
    )

    class Meta:
        db_table = 'route_rating'

        constraints = [
            models.UniqueConstraint(
                fields=['route', 'member'],
                name='unique_route_rating_member'
            )
        ]


class RouteComment(models.Model):

    rc_id = models.AutoField(
        primary_key=True,
        db_column='RC_ID'
    )

    route = models.ForeignKey(
        SharedRoute,
        on_delete=models.CASCADE,
        db_column='SR_ID',
        related_name='comments'
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column='M_ID',
        related_name='route_comments'
    )

    content = models.CharField(
        max_length=300,
        db_column='CONTENT'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='CREATED_AT'
    )

    class Meta:
        db_table = 'route_comment'
        ordering = ['created_at']
