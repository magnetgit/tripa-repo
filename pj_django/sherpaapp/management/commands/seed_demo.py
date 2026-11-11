"""데모 데이터 만들기 (발표 시연 · 추천 점수 · 리뷰 게시판 시험용)

    python manage.py seed_demo              # 데모 회원 80명 + 여행·일정·리뷰·도움돼요·공유 루트·예산·고친 비용
    python manage.py seed_demo --reset      # 데모 데이터만 지우고 다시 만들기
    python manage.py seed_demo --clear      # 데모 데이터만 지우기 (만들지 않음)
    python manage.py seed_demo --members 30 --seed 7
    python manage.py seed_demo --summaries  # 리뷰 3개 이상 장소는 AI 키워드 요약까지 (LLM 호출, 시간·비용 듦)

- 데모 회원은 아이디가 demo_ 로 시작해요 (demo_01 ~ demo_80). 비밀번호는 모두 아래 DEMO_PASSWORD (시험용).
  demo_01 은 20대 여성, demo_02 는 40대 남성 — 같은 장소라도 추천 카드 순서가 다르게 보여요.
  10대~60대·성별 안 넣은 회원까지 섞여 있어요.
- 여행마다 동행(혼자·연인·친구·가족·아이·부모님)과 인원이 정해지고, 리뷰는 그 동행·나이대·장소·계절에 맞는
  문장을 조합해요 (장소별 문장 PLACE_LINES, 동행 문장 WITH_LINES, 나이대 말투 AGE_LINES). 리뷰 태그도 동행에 맞춰요.
- 장소는 docs/data/busan_spots_draft.csv (팀이 고른 부산 장소, 실제 카카오 장소 번호).
  그래서 채팅 추천 카드에도 데모 리뷰 별점이 붙고, 같은 성별·나이대 가중이 보여요.
- 같은 --seed 값이면 언제나 같은 데이터가 나와요 (발표 화면을 미리 맞춰 둘 수 있게).
- 다녀온 여행의 일부는 회원이 비용 관리에서 장소 금액을 고친 것처럼 travel_budget_item 을 넣어요.
  DB 트리거가 budget_log 를 남기고, 기록 시각은 그 여행 날짜 근처로 옮겨요 (대시보드 '장소별 비용' · 날짜별 추이).
- 데모 회원이 아닌 데이터는 건드리지 않아요. 지울 때도 demo_ 회원과 그 회원의 여행·리뷰·비용 기록만 지워요.

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
    AVATAR_CHOICES, BudgetLog, Category, Member, Place, Review, ReviewHelpful, RouteComment, RouteRating,
    Schedule, SchedulePlace, SharedRoute, Travel, TravelBudget, TravelBudgetItem, TravelCategory,
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
    ('F', 10): {'카페': 1.0, '랜드마크': 0.9, '쇼핑': 0.6, '역사': -0.8, '공원': -0.4},
    ('M', 10): {'랜드마크': 1.0, '음식': 0.8, '쇼핑': 0.4, '역사': -0.6, '전통문화': -0.4},
    ('F', 20): {'카페': 1.2, '랜드마크': 0.7, '바다': 0.5, '역사': -1.2, '전통문화': -0.6},
    ('M', 20): {'음식': 1.1, '쇼핑': 0.6, '바다': 0.4, '전통문화': -0.4},
    ('F', 30): {'카페': 0.8, '음식': 0.6, '자연': 0.4},
    ('M', 30): {'음식': 0.7, '자연': 0.6, '바다': 0.3},
    ('F', 40): {'자연': 0.8, '공원': 0.6, '전통문화': 0.4},
    ('M', 40): {'역사': 1.2, '전통문화': 0.8, '자연': 0.5, '카페': -1.2, '랜드마크': -0.4},
    ('F', 50): {'공원': 0.8, '전통문화': 0.7, '자연': 0.6},
    ('M', 50): {'역사': 0.9, '전통문화': 0.9, '음식': 0.4},
    ('F', 60): {'전통문화': 1.0, '공원': 0.8, '자연': 0.6, '카페': -0.5, '쇼핑': -0.3},
    ('M', 60): {'역사': 1.0, '전통문화': 0.9, '자연': 0.7, '쇼핑': -0.5, '랜드마크': -0.3},
}
# 회원 구성: (성별, 나이대) 순서대로 돌려 씀. None 은 성별·나이대를 안 넣은 회원 (맞춤 가중 없음)
# 시연에 쓰는 두 그룹(20대 여성 · 40대 남성)을 많이 둬서, 한 장소에 같은 그룹 리뷰가 여러 개 쌓이게 함
MEMBER_GROUPS = [('F', 20), ('M', 40), ('F', 20), ('M', 40), ('M', 20), ('F', 30), ('F', 20), ('M', 40),
                 ('M', 30), ('F', 40), ('F', 20), ('M', 40), (None, None), ('M', 50), ('F', 50), ('M', 20),
                 ('F', 20), ('M', 40), (None, None), ('F', 30), ('F', 10), ('M', 10), ('F', 60), ('M', 60)]

# 동행: (리뷰 태그, 인원, 여행 제목에 붙는 말). 나이대마다 자주 가는 동행을 다르게
COMPANIONS = {
    '혼자': ('혼자', 1, '혼자'), '연인': ('연인과', 2, '커플'), '친구': ('친구와', 3, '친구와'),
    '가족': ('가족과', 4, '가족'), '아이': ('아이와', 3, '아이와'), '부모님': ('가족과', 3, '부모님과'),
}
COMPANION_BY_AGE = {
    10: ['친구', '친구', '가족'], 20: ['친구', '연인', '연인', '혼자'], 30: ['연인', '아이', '친구', '혼자'],
    40: ['아이', '아이', '가족', '친구'], 50: ['가족', '친구', '연인', '부모님'], 60: ['가족', '친구', '연인'],
    None: ['혼자', '연인', '친구', '가족'],
}

GOOD = {
    '바다': ['바다 전망이 정말 좋아요', '파도 소리 들으며 산책하기 좋아요', '노을 질 때 꼭 가 보세요', '모래사장이 넓고 깨끗해요',
           '물이 맑아서 사진이 잘 나와요', '해변 따라 걷는 길이 시원해요'],
    '카페': ['커피가 맛있고 분위기가 좋아요', '디저트가 예쁘고 맛있어요', '창가 자리 전망이 최고예요', '원두 향이 진하고 산미가 좋아요',
           '자리 간격이 넓어서 편하게 쉬었어요', '빵이 금방 나와서 따뜻했어요'],
    '음식': ['양이 많고 맛있어요', '현지인 맛집 느낌이에요', '줄 서도 먹을 만해요', '국물이 진하고 깔끔해요',
           '반찬이 넉넉하게 나와요', '회전이 빨라서 생각보다 금방 먹었어요'],
    '역사': ['설명이 잘 되어 있어 공부가 돼요', '천천히 둘러보기 좋아요', '전시가 알차고 동선이 편해요', '부산 역사를 한눈에 볼 수 있어요',
           '해설을 들으니 훨씬 재미있었어요'],
    '전통문화': ['분위기가 멋져요', '구경하는 재미가 있어요', '사진 찍기 좋은 골목이 많아요', '먹거리 구경이 재미있어요',
              '부산다운 모습을 볼 수 있어요'],
    '자연': ['숲길 산책이 정말 좋아요', '풍경이 시원하게 트여 있어요', '공기가 맑고 조용해요', '바다와 절벽이 한눈에 보여요',
           '걷는 내내 경치가 바뀌어서 지루하지 않아요'],
    '공원': ['산책하기 좋은 공원이에요', '벤치가 많아서 쉬어 가기 좋아요', '야경이 예뻐요', '길이 잘 정돈되어 있어요',
           '조용히 바람 쐬기 좋아요'],
    '쇼핑': ['구경할 게 많아요', '기념품 사기 좋아요', '브랜드가 다양해요', '할인 매장이 많아서 득템했어요', '푸드코트도 괜찮아요'],
    '랜드마크': ['야경이 정말 멋져요', '전망대에서 본 풍경이 최고예요', '포토 스팟이 많아요', '부산 오면 한 번은 꼭 와 볼 곳이에요',
             '생각보다 훨씬 볼거리가 많아요'],
}
BAD = {
    '바다': ['바람이 너무 세서 오래 있기 힘들었어요', '사람이 많아서 자리 잡기 어려웠어요'],
    '카페': ['자리가 좁고 시끄러웠어요', '음료 가격이 조금 비싸요'],
    '음식': ['웨이팅이 너무 길었어요', '기대보다는 평범했어요', '가격이 예전보다 올랐어요'],
    '역사': ['생각보다 볼거리가 적었어요', '안내판 글씨가 작아서 읽기 힘들었어요'],
    '전통문화': ['사람이 너무 많아 정신없었어요', '오르막과 계단이 많아요'],
    '자연': ['오르막이 꽤 있어서 힘들었어요', '그늘이 적어서 더웠어요'],
    '공원': ['편의시설이 조금 부족해요', '생각보다 규모가 작아요'],
    '쇼핑': ['주말엔 주차 기다리는 줄이 길어요', '가격이 생각보다 비싸요'],
    '랜드마크': ['대기 줄이 길었어요', '입장료에 비해 조금 짧았어요'],
}
BAD_ANY = ['사람이 너무 많았어요', '주차가 불편했어요', '기대보다는 평범했어요', '가격이 조금 비싸요']

# 장소마다 그곳다운 한 줄 (리뷰에 섞어 넣음, 없으면 컨셉 문장만)
PLACE_LINES = {
    '해운대해수욕장': ['해변열차랑 같이 보면 하루 코스로 좋아요', '아침 일찍 가면 한산해서 걷기 좋아요'],
    '광안리해수욕장': ['밤에 광안대교 불빛이 정말 예뻐요', '해변 앞 카페거리 구경도 재미있어요'],
    '송정해수욕장': ['서핑하는 사람들 구경하는 재미가 있어요', '해운대보다 조용해서 좋았어요'],
    '다대포해수욕장': ['해 질 녘 노을이 정말 유명할 만해요', '갯벌이랑 산책로가 넓어요'],
    '송도해수욕장': ['구름다리랑 케이블카까지 같이 즐겼어요', '바다 위 다리 걷는 게 재미있어요'],
    '일광해수욕장': ['동네 바다 느낌이라 아늑해요', '물이 얕아서 놀기 좋아요'],
    '임랑해수욕장': ['사람이 적어서 조용히 바다 보기 좋아요', '물빛이 정말 맑아요'],
    '영진돼지국밥 본점': ['수육 백반 꼭 드셔 보세요', '아침 일찍부터 열어서 해장하기 좋아요'],
    '국제밀면 본점': ['물밀면 육수가 시원해요', '비빔밀면 양념이 달지 않아서 좋았어요'],
    '대영횟집': ['회가 두툼하고 신선해요', '매운탕까지 먹으니 배불러요'],
    '고래사어묵 해운대점': ['어묵 종류가 정말 다양해요', '선물용 포장이 깔끔해요'],
    '본전돼지국밥': ['국물이 맑은 편이라 부담 없어요', '역 근처라 도착하자마자 먹기 좋아요'],
    '초량밀면': ['면이 쫄깃하고 육수가 깔끔해요', '만두도 같이 시키는 걸 추천해요'],
    '자갈치횟집': ['시장에서 고른 회를 바로 먹을 수 있어요', '바다 보면서 먹는 맛이 있어요'],
    '비비비당': ['전통차랑 바다 전망이 잘 어울려요', '좌식 자리라 편하게 쉬었어요'],
    '미피카페 부산점': ['캐릭터 디저트가 너무 귀여워요', '굿즈 구경하는 재미가 있어요'],
    '블랙업커피 서면본점': ['서면 쇼핑하다 쉬어 가기 좋아요', '시그니처 라떼가 진해요'],
    '모모스 영도 로스터리&커피바': ['바다 보이는 로스터리라 분위기가 좋아요', '원두 종류가 많아서 고르는 재미가 있어요'],
    '카페만디': ['주택을 고친 카페라 아늑해요', '정원 자리가 특히 좋아요'],
    '카페윤': ['영도 바다가 한눈에 보여요', '빵 종류가 많아요'],
    '카페385': ['조용하게 책 읽기 좋은 곳이에요', '핸드드립이 맛있어요'],
    '해운대블루라인파크 미포정거장': ['해변열차 바다 쪽 자리 꼭 앉으세요', '스카이캡슐은 미리 예약하는 게 좋아요'],
    '해운대블루라인파크 청사포정거장': ['청사포 등대까지 걸어가기 좋아요', '열차 타고 미포까지 가는 길이 예뻐요'],
    '오륙도스카이워크': ['유리 바닥이라 짜릿해요', '바람 부는 날엔 꽤 무서워요'],
    '감천문화마을': ['골목마다 그림이 있어서 걷는 재미가 있어요', '어린왕자 포토존 줄이 길어요'],
    '롯데월드 어드벤처 부산': ['놀이기구가 생각보다 다양해요', '오전 일찍 가야 덜 기다려요'],
    '동백섬': ['누리마루까지 한 바퀴 돌기 딱 좋아요', '해운대 야경이 잘 보여요'],
    '태종대유원지': ['다누비열차 타면 편하게 둘러봐요', '절벽 전망이 시원해요'],
    '이기대해안산책로': ['광안대교 보이는 길이 정말 멋져요', '구름다리 구간이 재미있어요'],
    '흰여울문화마을': ['바다 옆 골목이 영화 같아요', '해안 터널 사진이 예쁘게 나와요'],
    '허심청 호텔농심': ['온천물이 좋아서 피로가 풀려요', '여행 마지막 날 쉬어 가기 좋아요'],
    '오륙도': ['섬들이 겹쳐 보이는 풍경이 신기해요', '스카이워크랑 같이 보면 좋아요'],
    '황령산': ['부산 시내 야경이 한눈에 보여요', '드라이브 코스로 최고예요'],
    '용두산공원': ['부산타워 전망이 좋아요', '광복동이랑 같이 둘러보기 좋아요'],
    '암남공원 해안산책로': ['송도 바다 보면서 걷기 좋아요', '바위 해안이 멋져요'],
    '금정산국립공원': ['등산로가 잘 되어 있어요', '산성 길 따라 걷는 맛이 있어요'],
    '용소웰빙공원 전망대': ['호수 산책로가 한적해요', '전망대에서 보는 풍경이 시원해요'],
    '동백공원 해안산책로': ['해운대 끝에서 걷기 좋은 짧은 코스예요', '파도 소리가 가까이 들려요'],
    '부산박물관': ['부산 역사가 시대별로 잘 정리되어 있어요', '무료라 부담 없이 보기 좋아요'],
    '임시수도기념관': ['피란 시절 이야기가 인상 깊어요', '옛 건물 분위기가 그대로예요'],
    '부산장난감박물관': ['어른도 추억에 빠지게 돼요', '체험 공간이 있어서 지루하지 않아요'],
    '부산박물관 동래관': ['동래 역사를 알기 좋아요', '규모는 작아도 알차요'],
    '부산박물관 부산관': ['전시 설명이 쉬워요', '가볍게 둘러보기 좋아요'],
    '동래읍성지': ['성곽 따라 걷는 길이 좋아요', '동래 시내가 내려다보여요'],
    '부산근현대역사관 별관': ['옛 건물 안에서 보는 전시가 색달라요', '근대 부산 이야기가 흥미로워요'],
    '자갈치시장': ['활기찬 시장 분위기가 부산답네요', '꼼장어 구이 꼭 드셔 보세요'],
    '국제시장': ['구경거리랑 먹거리가 정말 많아요', '비빔당면이랑 어묵 먹으면서 다녔어요'],
    '해동용궁사': ['바닷가 절이라 풍경이 특별해요', '계단이 많으니 편한 신발 신으세요'],
    '부전시장': ['물건이 싸고 인심이 좋아요', '현지 시장 분위기를 느낄 수 있어요'],
    '범어사': ['산사가 고요하고 공기가 좋아요', '단풍철에 특히 예뻐요'],
    '신세계백화점 센텀시티점': ['하루 종일 있어도 될 만큼 넓어요', '스파랑 같이 즐기기 좋아요'],
    '롯데백화점 광복점': ['옥상 전망이 의외로 멋져요', '음악분수 시간 맞춰 가 보세요'],
    '롯데백화점 센텀시티점': ['센텀 쪽 쇼핑하기 편해요', '식당가가 다양해요'],
    '롯데프리미엄아울렛 동부산점': ['아울렛 건물 자체가 예뻐요', '할인 폭이 커서 득템했어요'],
    '신세계사이먼 부산프리미엄아울렛': ['명품 매장이 많아요', '걸어 다니기 넓어서 편한 신발 추천해요'],
}

# 동행에 맞는 한 줄 (컨셉별로 있으면 그것 먼저, '' 는 어디서나)
WITH_LINES = {
    '아이': {'바다': ['아이가 모래놀이하며 한참 놀았어요'], '역사': ['아이 체험학습으로도 좋아요'],
             '카페': ['아이 의자가 있어서 편했어요'], '랜드마크': ['아이가 제일 신나 했어요'],
             '': ['아이가 정말 좋아했어요', '유모차 끌고 다니기 괜찮았어요']},
    '연인': {'바다': ['둘이 손잡고 걷기 좋았어요'], '카페': ['데이트하기 좋은 분위기예요'],
             '랜드마크': ['야경 보면서 걷기 좋은 데이트 코스예요'], '': ['데이트 코스로 딱이에요', '둘이 사진 정말 많이 찍었어요']},
    '친구': {'음식': ['여럿이 가서 이것저것 나눠 먹기 좋았어요'], '쇼핑': ['친구들이랑 구경하다 시간 가는 줄 몰랐어요'],
             '': ['친구들이랑 수다 떨기 좋았어요', '여럿이 가도 자리 잡기 괜찮았어요']},
    '혼자': {'음식': ['혼밥하기 편한 분위기예요'], '카페': ['혼자 조용히 쉬기 좋았어요'],
             '': ['혼자 와도 눈치 안 보여요', '혼자 천천히 둘러보기 좋았어요']},
    '가족': {'음식': ['가족 모두 입맛에 맞았어요'], '': ['가족 모두 만족했어요', '가족끼리 오기 편한 곳이에요']},
    '부모님': {'': ['부모님이 특히 좋아하셨어요', '부모님 모시고 가기 좋은 곳이에요']},
}
# 나이대 말투 (좋을 때 한 줄들, 아쉬울 때 한 줄들)
AGE_LINES = {
    10: (['친구들이랑 사진 엄청 찍었어요', '학교 친구들한테 추천했어요'], ['학생한테는 가격이 조금 부담돼요']),
    20: (['인생샷 건졌어요', '분위기가 감성 있어요'], ['사진 찍으려는 줄이 길었어요']),
    30: (['동선이 편해서 좋았어요', '쉬어 가기 좋은 곳이에요'], ['주말엔 너무 붐벼요']),
    40: (['일정 사이에 들르기 편했어요', '오랜만에 여유롭게 둘러봤어요'], ['안내가 조금 부족해서 헤맸어요']),
    50: (['걷기 편해서 좋았어요', '옛날 생각이 나서 좋았어요'], ['계단이 많아서 조금 힘들었어요']),
    60: (['천천히 걷기 좋았어요', '쉬어 갈 곳이 많아서 편했어요'], ['계단이 많아서 무릎이 힘들었어요']),
}
OUTDOOR = {'바다', '자연', '공원', '랜드마크', '전통문화'}   # 계절 한 줄을 붙이는 컨셉
REVIEW_MAX = 100    # Review.content max_length
INTROS = ['처음 부산 가는 분께 추천하는 코스예요', '걷기 편하게 동선을 짰어요', '맛집 위주로 다닌 여행이에요',
          '아이와 함께 다녀온 코스예요', '바다를 실컷 본 여행이에요', '사진 찍기 좋은 곳만 모았어요']
COMMENTS = ['동선 참고할게요!', '저도 다음 주에 가요', '여기 카페 저도 좋았어요', '일정 짜는 데 도움 됐어요', '좋은 코스네요']


class Command(BaseCommand):
    help = '데모 회원·여행·리뷰·도움돼요·공유 루트·예산을 만든다 (아이디 demo_ 로 시작하는 회원만)'

    def add_arguments(self, parser):
        parser.add_argument('--members', type=int, default=80, help='데모 회원 수 (기본 80)')
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
            edited = make_budget_items(rnd, travels)

        summaries = make_summaries(reviews) if opts['summaries'] else 0
        self.stdout.write(self.style.SUCCESS(
            f'데모 데이터: 회원 {len(members)} · 여행 {len(travels)} · 리뷰 {len(reviews)} · 도움돼요 {helpfuls} · '
            f'공유 루트 {routes} · 예산 {budgets} · 고친 비용 {edited}' + (f' · AI 요약 {summaries}' if opts['summaries'] else '')))
        self.stdout.write(f'로그인: {DEMO_PREFIX}01 (20대 여성), {DEMO_PREFIX}02 (40대 남성) / 비밀번호는 이 파일의 DEMO_PASSWORD')


# ---------------------------------------------------------------------------
# 지우기
# ---------------------------------------------------------------------------
def clear_demo():
    """demo_ 회원을 지우면 그 회원의 여행·일정·장소·리뷰·도움돼요·공유 루트·예산이 같이 지워진다 (CASCADE)."""
    qs = Member.objects.filter(user_id__startswith=DEMO_PREFIX)
    n = qs.count()
    travel_ids = list(Travel.objects.filter(member__in=qs).values_list('t_id', flat=True))
    qs.delete()
    # budget_log 는 여행과 연결(FK)이 없어서 따로 지움 (지울 때 트리거가 남긴 'delete' 줄까지)
    BudgetLog.objects.filter(travel_id__in=travel_ids).delete()
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
# 여행 · 일정 · 장소 (지난 여행 3개 + 다가오는 여행 1개, 여행마다 동행·인원)
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
        # 지난 여행 3개(계절이 다르게) + 다가오는 여행 1개
        starts = [today - timedelta(days=rnd.randint(150, 240)), today - timedelta(days=rnd.randint(40, 120)),
                  today - timedelta(days=rnd.randint(5, 30)), today + timedelta(days=rnd.randint(7, 40))]
        for start in starts:
            days = rnd.choice([2, 2, 3])
            main = rnd.choice(favorite[:2]) if rnd.random() < .4 else rnd.choice(concepts)
            picks = [main, rnd.choice(concepts)]
            who = rnd.choice(COMPANION_BY_AGE.get(m.age_group, COMPANION_BY_AGE[None]))
            people = COMPANIONS[who][1]
            car = .7 if who in ('아이', '가족', '부모님') else .3     # 아이·가족 여행은 차가 많게
            t = Travel.objects.create(
                member=m, t_day=start - timedelta(days=rnd.randint(3, 20)), t_place='부산',
                t_title=f'부산 {days - 1}박 {days}일 {COMPANIONS[who][2]} {main} 여행',
                t_way='CAR' if rnd.random() < car else 'public_transport',
                t_start=start, t_end=start + timedelta(days=days - 1),
                t_budget=rnd.randrange(150000, 300001, 10000) * people, start_time=time(9, 0),
            )
            t.demo_with = who    # 리뷰 문장·태그에 씀 (DB 칸 아님, 이번 실행 동안만)
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


def _with_line(rnd, who, concept):
    lines = WITH_LINES.get(who, {})
    return rnd.choice(lines.get(concept) or lines.get('') or [''])


def _season_line(rnd, month, concept):
    """계절에 맞는 한 줄 (실외 장소만, 가끔)"""
    if concept not in OUTDOOR or rnd.random() > .35:
        return ''
    if month in (12, 1, 2):
        return rnd.choice(['겨울이라 바람이 차요, 따뜻하게 입고 가세요', '추웠지만 하늘이 맑아서 좋았어요'])
    if month in (6, 7, 8):
        return rnd.choice(['한낮엔 더워서 아침이나 저녁에 가는 걸 추천해요', '여름이라 햇볕이 강해요, 모자 꼭 챙기세요'])
    if month in (3, 4, 5):
        return rnd.choice(['봄이라 걷기 딱 좋은 날씨였어요', '꽃 필 때라 더 예뻤어요'])
    return rnd.choice(['가을 날씨라 걷기 좋았어요', '선선해서 오래 있어도 좋았어요'])


def review_text(rnd, member, place, rating, who, month):
    """별점·장소·동행·나이대·계절에 맞는 리뷰 1~3문장"""
    concept = place.p_kind
    good_age, bad_age = AGE_LINES.get(member.age_group, ([], []))
    place_line = rnd.choice(PLACE_LINES.get(place.p_name, [''])) if rnd.random() < .7 else ''
    if rating <= 2:
        parts = [rnd.choice(BAD.get(concept, BAD_ANY)), rnd.choice(BAD_ANY + bad_age)]
    elif rating == 3:
        parts = [rnd.choice(GOOD.get(concept, ['좋았어요'])),
                 '다만 ' + rnd.choice(BAD.get(concept, BAD_ANY) + bad_age)]
        if place_line:
            parts.insert(1, place_line)
    else:
        parts = [rnd.choice(GOOD.get(concept, ['좋았어요']))]
        extras = [place_line, _with_line(rnd, who, concept), rnd.choice(good_age) if good_age else '']
        rnd.shuffle(extras)
        parts += [e for e in extras if e][:rnd.choice([1, 2, 2])]
        if rating == 5 and rnd.random() < .4:
            parts.append(rnd.choice(['다음에 또 올 거예요', '강력 추천해요', '부산 오면 꼭 들르세요']))
    season = _season_line(rnd, month, concept)
    if season and rnd.random() < .6:
        parts.append(season)
    # 리뷰 칸은 100자까지: 문장을 하나씩 붙이다가 넘으면 멈춤 (문장 중간에서 자르지 않게)
    text = ''
    for part in (p.rstrip('.') for p in parts if p):
        if part in text:       # 같은 문장 두 번 안 쓰기
            continue
        joined = f'{text}. {part}' if text else part
        if len(joined) > REVIEW_MAX:
            break
        text = joined
    return text


def review_tags(rnd, place, rating, who):
    """동행 태그 + 별점·장소에 맞는 태그"""
    tags = [COMPANIONS[who][0]]
    if who == '아이' and rnd.random() < .5:
        tags.append('가족과')
    if rating == 5 and rnd.random() < .6:
        tags.append('다시 가고 싶어요')
    if place.p_kind in ('카페', '랜드마크', '바다', '전통문화') and rating >= 4 and rnd.random() < .5:
        tags.append('사진 맛집')
    if place.p_kind in ('음식', '쇼핑') and rating >= 4 and rnd.random() < .4:
        tags.append('가성비')
    return [t for t in TAGS if t in tags]     # 순서는 TAGS 기준


def make_reviews(rnd, travels):
    today = date.today()
    reviews = []
    seen = set()
    for t in travels:
        if t.t_end >= today:
            continue
        who = getattr(t, 'demo_with', '혼자')
        for p in Place.objects.filter(travel=t):
            key = (t.member_id, p.p_kakao_id)
            if key in seen or rnd.random() > .95:
                continue
            seen.add(key)
            r = _rating(rnd, t.member, p.p_kind)
            text = review_text(rnd, t.member, p, r, who, t.t_start.month)
            tags = review_tags(rnd, p, r, who)
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
# 고친 비용 — 회원이 비용 관리에서 장소 금액을 직접 고친 것처럼 (대시보드 '장소별 비용')
# ---------------------------------------------------------------------------
# 컨셉별 1인 금액 범위(원). 바다·자연·공원·역사는 대개 무료라 거의 안 고침
PAY_PER_PERSON = {
    '음식': (12000, 28000), '카페': (6000, 11000), '쇼핑': (10000, 40000),
    '전통문화': (5000, 20000), '랜드마크': (3000, 27000), '역사': (0, 5000),
}


def make_budget_items(rnd, travels):
    """다녀온 여행의 60%에서 장소 2~4곳 금액을 넣고, 그중 일부는 한 번 더 고친다.
    INSERT·UPDATE 때 DB 트리거(0018)가 budget_log 를 남기고, 그 기록 시각을 여행 날짜 근처로 옮긴다."""
    today = date.today()
    count = 0
    for t in travels:
        if t.t_end >= today or rnd.random() > .6:
            continue
        people = COMPANIONS[t.demo_with][1]
        sps = [sp for sp in SchedulePlace.objects.filter(schedule__travel=t).select_related('place')
               if sp.place.p_kind in PAY_PER_PERSON]
        for sp in rnd.sample(sps, min(len(sps), rnd.randint(2, 4))):
            low, high = PAY_PER_PERSON[sp.place.p_kind]
            amount = rnd.randint(low, high) * people // 1000 * 1000
            item = TravelBudgetItem.objects.create(travel=t, schedule_place=sp, amount=amount)
            if rnd.random() < .35:                       # 다녀와서 실제 쓴 돈으로 한 번 더 고침
                item.amount = max(0, int(amount * rnd.uniform(.7, 1.3)) // 1000 * 1000)
                item.save(update_fields=['amount', 'updated_at'])
            count += 1
        # 트리거는 NOW() 로 남기니, 여행 준비(출발 전)·다녀온 뒤 날짜로 옮김
        for log in BudgetLog.objects.filter(travel_id=t.t_id):
            day = (t.t_start - timedelta(days=rnd.randint(1, 5)) if log.action == 'insert'
                   else t.t_end + timedelta(days=rnd.randint(0, 3)))
            log.changed_at = datetime.combine(day, time(rnd.randint(9, 22), rnd.randint(0, 59)))
            log.save(update_fields=['changed_at'])
    return count


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
