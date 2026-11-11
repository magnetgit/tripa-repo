# 팀 변경 기록 (TEAM_UPDATES)

`git pull`로 받은 변경이 **내 파트(🟦 프론트 / 🟧 백엔드 / 🟩 AI)에 무엇을 바꾸는지** 적는 곳입니다.
최신 항목이 맨 위입니다. 다른 파트에 영향을 주는 변경(화면 id·주소·응답 키·DB·설정)을 올릴 때는 여기에 한 항목을 추가해 주세요.

- 기준 목업: [TRIPA 화면 목업](https://claude.ai/artifact/BqZEgyPi2NH36UjyHwbYBk) (화면 모양 참고용, 코드가 아님). 같은 내용의 사본이 `docs/mockup/tripa-mockup.html`에 있어서 브라우저로 바로 열 수 있어요 (가장 최신은 링크 쪽)
- 기준 응답 모양: 리포 최상위 `mock.json`
- pull 뒤 확인 방법: [`docs/PULL_CHECKLIST.md`](PULL_CHECKLIST.md)
- 앱 확장 가이드: [`docs/APP_GUIDE.md`](APP_GUIDE.md)

---

## 2026-11-11 · 예상 비용: 관광지 가격 못 찾던 문제(창덕궁 등) + 'AI 예상' 가격 — 🟦 임영준
DB·주소 변경 없음 · `cost.source`에 값 **`'ai'` 추가** (기존 `'tour'`·`'estimate'` 그대로) · `budget_service.py`(🟦)만

- **고친 것:** 관광공사에서 요금을 찾을 때 이름이 겹치는 첫 항목을 써서 `창덕궁` → `국가유산진흥원 창덕궁상품관`(쇼핑)을 잡아 가격이 비었어요
  - 이제 요금용 검색은 **이름이 똑같은 것 먼저**, 쇼핑(38)·음식점(39)은 빼고, 거리 1.5km 안 → 창덕궁 1인 3,000원(관광공사)
  - 캐시 열쇠 `place_price:v2` (예전에 '가격 없음'으로 저장된 것은 안 씀)
- **AI 예상:** 관광공사 요금도 보통 가격도 없는 관광지·기타는 AI에게 성인 1명 입장료를 물어봄 → `source: 'ai'`, `text: 'AI 예상 (성인 1명 입장료)'` (30일 캐시, 실패는 하루)
  - 화면 표시: 추천 카드·미리보기 "AI 예상", 여행 상세 마우스 올림 "AI가 예상한 입장료"
- 여행 상세 AI 예상 비용·비용 관리 'AI 예상대로 채우기'·장소별 AI 금액에 그대로 반영 (`plan_budget` 같은 함수)

### 🟧 수한 · 🟩 지윤
- `cost.source`로 문구를 나누는 곳이 있으면 `'ai'`도 생겼어요 (없으면 할 일 없음)

---

## 2026-11-11 · 성별·나이대 입력 안내 + 내 정보에서 성별·나이대 넣기·고치기·지우기 — 🟦 임영준
DB·주소·응답 키 변경 없음 · ⚠️ **🟧 `views.mypage_edit`에 몇 줄 추가** (회의 안건 8 "내 정보에서 수정·삭제 가능"이 아직 없어서)

- **내 정보 수정**(`mypage_edit.html`): 성별·나이대 고르기 + **[선택] 동의** 체크. 저장 규칙은 `join_ok`와 같음
  - 동의 안 하면 둘 다 지움(None), 성별 M/F만, 나이대 10~60만. 고르고 동의 안 하면 화면에서 막음
  - 폼에 숨은 칸 `profile_form=1`이 있을 때만 바꿈 (다른 곳에서 이 주소로 저장해도 성별·나이대는 그대로)
- **마이페이지**: 성별·나이대 칸 표시(없으면 "선택 안 함") + 안 넣었으면 "💡 넣으면 나와 비슷한 사람들이 좋아한 곳을 먼저 보여 드려요 · [넣으러 가기]"
- **채팅 추천 카드 위**(React·`travel_chat.js`): 안 넣은 회원만, **가장 최근 추천 카드 위에 한 줄** + "내 정보에서 넣기" 링크, × 누르면 이 브라우저에서 다시 안 보임 (억지로 받지 않기)
  - 템플릿 `data-profile`(full·half·none, 손님은 빈 값) · `data-profile-url`

### 🟧 수한
- [ ] `mypage_edit` 추가 부분 확인 (성별·나이대 저장, `join_ok`와 같은 규칙인지). 추천 점수(`profile`)는 저장만 되면 그대로 반영돼요

---

## 2026-11-11 · 체크인하고 다시 나가기 (여행 상세에서 체크인 줄 넣기) + 숙소 두 줄 화면 표시 — 🟦 임영준
DB·기존 응답 키 변경 없음 · **새 주소 `POST travel_checkin/<travel_id>/<day>/`** (`views.py`에 추가만, 11/10 🟧 숙소 두 줄 규칙 그대로)

### 여행 상세
- 숙소가 있는 날 일정 맨 위에 **🛏 체크인하고 다시 나가기** 막대: 시각(기본 15:00) 고르고 **[체크인 넣기]**
  - 그날 숙소(마지막 숙소 줄)와 **같은 `Place`로** 체크인 줄을 그 시각에 하나 더 넣음 (짐 두기 30분) → 시각 순서 자리로, 뒤 일정 시간 다시 계산 (`recalculate_schedule_timeline` anchor)
  - 앞 일정과 겹치면 안내만 (막지 않음), 귀가 시각보다 늦으면 막음, 이미 두 줄이면 막음
- 두 줄이 되면: 앞 줄 **🛏 체크인 · 짐 두고 다시 나가기**, 뒤 줄 **🏠 숙소로 귀가** 표시. 막대는 "15:00 ○○ 체크인 · [체크인 줄 빼기]"
  - 시각 바꾸기 = 체크인 줄 시간 고치기, 빼기 = 일정 삭제, 순서 = 끌기 (기존 기능 그대로)
- 지도: 같은 숙소 마커 두 개 중 두 번째를 살짝 옆으로 비켜 두 번호가 다 보이게
- AI 예상 비용: `cost.same_stay`면 "숙박비는 체크인 줄에" (11/10 🟦 할 일)
- `POST travel_checkin/<id>/<day>/` `time=HH:MM` → `{success, sp_id, message}` (주인만)

### 미리보기 (여행 만들기·채팅)
- 같은 숙소 두 번째 줄 태그 **숙소로 귀가**, `cost.same_stay`면 "숙박비는 체크인 줄에", 합계에서 0원

### 🟩 지윤
- [ ] 일정 만들 때 "날마다 체크인 시각·외출 여부"를 고르는 건 `schedule_service` 일정 구조가 필요해요 (11/09 분담). 같은 규칙(같은 `Place` 두 줄)으로 만들면 위 화면이 그대로 보여요. 체크인 시각을 대화 초안에 받을 키가 필요하면 먼저 정해서 알려 줘 (`mock.json`)

### 🟧 수한
- 할 일 없음 (`views.py`에 함수·주소 추가만, `schedule_place_add`의 "같은 장소 중복 막기"는 안 건드림)

---

## 2026-11-11 · 이동수단별 가격 비교 (대중교통·택시·자가용) + 📐 공유 정의 `fare_service.move_fares` — 🟦 임영준
DB·기존 응답 키 변경 없음 · **새 주소 `GET travel_move_fares/<travel_id>/?from=위도,경도&to=위도,경도`** · 새 파일 `services/fare_service.py` · `mock.json`에 `move_fares` 예시

### 화면 (여행 상세)
- 이동 구간마다 🚗 자가용 · 🚌 대중교통 · 🚕 택시 금액, 제일 싼 것에 **가장 쌈** (싼 순서)
- 목록 맨 위(운영시간 요약 아래)에 **오늘 이동비 비교**: 이동수단별 그날 합계 + 가장 싼 것 (걸어가는 구간은 0원, 금액 모르는 구간은 "N구간은 금액 모름")
- 인원은 비용 관리 인원(`_budget_people`)과 같음

### 📐 공유 정의 `fare_service.move_fares(from_lat, from_lon, to_lat, to_lon, people)`
- → `{people, distance, walk, cheapest, options: [{mode: car|transit|taxi, label, total, per, note}]}` (값이 있는 것만, 싼 순서)
- 택시·통행료·거리: 카카오모빌리티 자동차 길찾기 `summary.fare.taxi`·`fare.toll` (캐시 `carfare:…` 7일). 택시는 4명당 1대, 통행료 포함
- 대중교통: `transit_service.transit_route` 1인 요금 × 인원 (같은 캐시)
- 자가용: 거리 ÷ 연비 12km/L × 휘발유 1,700원/L + 통행료 (주차비 제외, `FUEL_PRICE`·`FUEL_KM_PER_L` 상수)
- 700m 안은 `walk: true` (0원)
- 한계: 카카오 대중교통에 없는 **장거리 열차·항공·배는 안 나와요** → 🟩 "가는 길 실제 시간표" 결과가 나오면 그 운임을 `options`에 `mode: 'train'` 등으로 **추가만** 해서 붙이기

### 🟧 수한 · 🟩 지윤
- 🟧 할 일 없음 (`views.py`에 함수·주소 추가만)
- [ ] 🟩 실제 시간표 운임을 붙일 때 이 모양 그대로 써 주세요 (바꿀 게 있으면 알려 줘)

---

## 2026-11-11 · 담은 장소는 운영시간 안 첫 자리에 + 식사 시간대 맞추기(`stay_rules`) — 🟧 이수한
DB·응답 키 변경 없음. 바로 아래 📐 공유 정의를 코드로 넣었어요 (`services/stay_rules.py` 새 파일 + `views.py`).

- **담은 장소 자리** (`_chat_add_pins`): 시각 없이 담은 곳은 그날 일정을 앞에서부터 보며 `hours_service.fit_stay`가 `ok`·`shortened`인 첫 자리에 (전엔 늘 맨 끝 = 저녁 식사 뒤라 박물관이 20:00에 들어갔음). 못 찾으면 예전처럼 맨 끝
- **식사 시간대** (`_fit_meal_windows`, 채팅 "적용하기" 때만): 점심 12~13시·저녁 18~19시 도착이 되게 식사 앞 장소 체류를 `stay_range` 안에서 비율대로 늘리고 줄임(`stay_rules.spread`), 이동 시간이 다시 계산돼서 최대 3번, 그래도 이르면 시간대 시작까지 기다리기
  - `recalculate_schedule_timeline(anchor_sp_id=…)`로 **기준점 뒤만** 다시 계산 → 저녁을 맞춰도 점심·시각 정한 담은 장소가 안 움직임
  - 시각 정한 담은 장소(`pin.time`)·식사·숙소는 안 건드림. 최소까지 줄여도 못 맞추면 그대로 (장소는 안 뺌)
- 확인(부산 11/16~17, 되돌림): 화요일 박물관 20:00 → 11:00 / 점심 12:30 / 17:00 정한 광안리 그대로 / 저녁 18:00. 이동이 긴 날은 점심 13:22처럼 조금 넘음

### 🟩 지윤
- 일정 만들기 결과 뒤에 `_fit_meal_windows`가 한 번 더 돌아요 (채팅 적용 때). 처음부터 `stay_range`의 보통 값을 쓰면 덜 움직여요

---

## 2026-11-11 · 📐 공유 정의: 장소 종류별 체류 시간 범위 + 식사 시간대(점심 12~13시·저녁 18~19시) — 🟧 이수한 (먼저 공유)
DB·응답 키 변경 없음. 코드는 다음 PR (`services/stay_rules.py` 새 파일, 🟧). 체류 시간을 한 값(대부분 90분)으로 고정하지 않고 **범위 안에서 늘리고 줄여요**.

**체류 시간 범위 (분)** — `stay_rules.stay_range(kind, name)` → `(최소, 보통, 최대)`

| 종류 | 최소 | 보통 | 최대 |
|---|---|---|---|
| 카페 | 20 | 50 | 90 |
| 음식 | 40 | 60 | 90 |
| 바다·공원 | 30 | 70 | 120 |
| 자연(산책로·섬) | 40 | 90 | 150 |
| 역사·박물관 | 40 | 80 | 120 |
| 전통문화·시장 | 30 | 70 | 120 |
| 랜드마크·전망대 | 30 | 60 | 120 |
| 쇼핑 | 40 | 90 | 180 |

- (11/11 바꿈) 장소 이름 목록 대신 **이름·카카오 분류에 든 낱말로 묶음**: 놀이공원·테마파크·어드벤처·워터파크 120~180~300 · 유원지 90~120~180 · 온천·스파·찜질 90~120~180 · 아쿠아리움·수족관 60~90~150. 카페·음식 줄을 맨 위에 둬서 "월드카레"처럼 이름에 낱말이 섞여도 식당은 식당으로
- 모르는 종류는 30~60~90

**식사 시간대** — `stay_rules.fit_meal_windows(schedule)`
- 점심 도착 **12:00~13:00**, 저녁 도착 **18:00~19:00**
- 늦어지면 식사 **앞** 장소들 체류를 보통 → 최소 쪽으로 나눠서 줄임, 일찍 되면 보통 → 최대 쪽으로 늘림 (빈 시간 대신 더 머물기)
- 시각을 정해 담은 장소(`pin.time`)와 식사 자체는 안 건드림. 범위 안에서 못 맞추면 그대로 두기
- **적용: 채팅 "적용하기"(`_chat_finish_schedule`) 마지막에만.** 여행 상세에서 사용자가 시간·순서를 직접 고칠 때는 적용 안 함 (일부러 옮긴 점심이 되돌아가지 않게)

### 🟩 지윤
- [ ] 일정 만들기에서 체류를 정할 때 `stay_range(...)`의 **보통** 값을 쓰면 처음부터 자연스러워져요 (지금 대부분 90분). 쓸지·언제 쓸지는 지윤이가 정해 주세요. 식사 시각(12:30·18:30)은 이 시간대 안이라 그대로 괜찮아요

### 🟦 영준
- 변경 없음 (화면에 보이는 체류·시각이 장소마다 조금씩 달라져요)

---

## 2026-11-10 · 비밀번호 찾기 화면: 인증 코드 받기·확인 → 새 비밀번호 칸 열기 + 새 주소 `pw_code_check/` — 🟦 임영준
DB·기존 주소·응답 키 변경 없음 · **새 주소 `POST pw_code_check/` (추가만, `views.py`)** · `pw_code`·`pw_find`는 안 건드림

- `idpw.html` 비밀번호 찾기 순서: 아이디·이메일·이름 → **[인증 코드 받기]** (`pw_code`) → 코드 6자리 → **[인증 코드 확인]** (`pw_code_check`) → 맞으면 **새 비밀번호 칸·[비밀번호 변경] 버튼이 열림** → `pw_find`
  - 확인 전에는 새 비밀번호 칸·변경 버튼이 숨어 있음. 확인 뒤 코드·아이디를 바꾸거나 코드를 다시 받으면 다시 닫힘
  - 다시 받기 버튼 대기는 서버 `PW_CODE_RESEND`와 같은 5초 (`idpw.html`의 `RESEND_SECONDS`)
- `POST pw_code_check/` (`views.pw_code_check`): `user_id`·`code` → `{success, message}`
  - 코드만 확인하고 **비밀번호는 안 바꾸고 코드도 안 지움** (실제 변경 때 `pw_find`가 한 번 더 확인)
  - 틀린 횟수는 `pw_find`와 같은 세션 `tries` → 둘을 합쳐 5번
  - 문구: 맞음 "인증됐어요. 새 비밀번호를 입력해 주세요." / 틀림 "인증 코드가 맞지 않아요. (n/5)" / 코드 없음·10분 지남·5번 틀림은 `pw_find`와 같은 문구
- `auth.css`에 `.btn-code-check` 추가 → `idpw.html`의 `?v=8`

### 🟧 수한
- [ ] `pw_code_check` 확인 (`pw_find` 코드 확인과 같은 규칙인지). 화면이 들어왔으니 서버 배포 + 서버 메일 계정 설정

---

## 2026-11-10 · 비밀번호 찾기: 다시 받기 대기 1분 → 5초 + "터미널에 메일이 안 보여요" 확인 순서 — 🟧 이수한
DB·주소·응답 키 변경 없음. `PW_CODE_RESEND = 5` (버튼 연타 막기), 막히면 `message`: "잠시 뒤에 다시 받을 수 있어요." (429). **코드 입력 시간은 10분 그대로.** 다시 받기 대기는 화면에 시간 표시 안 해요 (서버 `message`만 보여 주기).

### 🟦 영준 — runserver 터미널에 인증 코드 메일이 안 보일 때 (위에서부터 확인)
1. **회원 정보가 하나라도 다름** (가장 흔함): 아이디·이메일·이름이 **셋 다 정확히** 맞아야 메일을 보내요. 안 맞아도 화면 문구는 "입력한 정보가 맞으면 …보냈어요"로 **똑같이** 떠요 (가입 여부가 안 드러나게 일부러). 내 PC DB에 그 회원이 있는지:
   ```bash
   python manage.py shell -c "from sherpaapp.models import Member; print(Member.objects.filter(user_id='아이디', email='이메일', name='이름').exists())"
   ```
   `False`면 이게 원인 (내 PC DB 회원 정보는 서버·다른 사람 PC와 달라요)
2. **최신 코드가 아님**: `git pull origin main` 했는지. 브라우저 F12 → Network 탭에서 `pw_code` 요청 상태: `200` 서버까지 감 / `404` 코드 없음(pull 필요) / `403` CSRF 토큰이 안 실림(`new FormData(form)`의 form 안에 `{% csrf_token %}` 있는지)
3. **다른 터미널을 봄**: 메일 내용은 `python manage.py runserver`를 실행한 **그 터미널**에 찍혀요. VS Code ▶ 실행·디버그로 켰으면 **"디버그 콘솔"** 탭
4. **메일 설정 자체 확인**: 아래를 친 터미널에 `Subject: 시험`이 보이면 메일 설정은 정상 → 원인은 1~3번
   ```bash
   python manage.py shell -c "from django.core.mail import send_mail; send_mail('시험', '터미널에 보이면 성공', None, ['test@example.com'])"
   ```
- `.env`에 `EMAIL_HOST_USER`가 있으면 터미널 대신 **진짜 메일**로 가요 (그때는 받을 회원 이메일이 실제 주소여야 함, 데모 회원 `demo_..@example.com`은 도착 안 함)

---

## 2026-11-10 · 데모 데이터 더 자세하게: 회원 80명·리뷰 1,650개, 동행·나이대·장소·계절에 맞는 리뷰 — 🟧 이수한
DB·응답 키 변경 없음. `seed_demo`만 바뀜. 로컬에서 새로 만들려면 `python manage.py seed_demo --reset` (데모 회원 `demo_`만 지우고 다시 만들어요).

- 회원 40 → **80명** (10대~60대·성별 안 넣은 회원까지), 여행은 회원마다 지난 여행 3개(계절이 다르게) + 다가오는 여행 1개
- 여행마다 **동행·인원**: 혼자(1)·연인(2)·친구(3)·가족(4)·아이(3)·부모님(3), 나이대마다 자주 가는 동행이 달라요. 여행 제목에도 붙어요 (예: `부산 1박 2일 커플 카페 여행`), 예산도 인원에 맞춰요
- 리뷰 563 → **1,650개** (장소 55곳 모두, 장소당 14~67개). 문장 = 컨셉 문장 + **장소마다 그곳다운 한 줄**(55곳) + 동행 한 줄 + 나이대 말투 + 계절 한 줄, 100자 안
  - 예: `숲길 산책이 정말 좋아요. 유모차 끌고 다니기 괜찮았어요. 구름다리 구간이 재미있어요` (40대 여성·아이와·이기대해안산책로·5점)
  - 태그는 동행에 맞춤(`아이와`·`연인과`…), 5점은 `다시 가고 싶어요`, 사진 장소는 `사진 맛집`
- 그룹 차이(추천 점수 시연용): 20대 여성 카페 4.55·역사 2.58 / 40대 남성 역사 4.62·카페 2.33
- **서버는 아직 예전 데모 데이터예요** (비밀번호 찾기 화면이 들어오면 같이 배포하고 `seed_demo --reset` + `index_reviews`)

### 🟦 영준 · 🟩 지윤
- 로컬에서 리뷰 게시판·추천 카드를 볼 때 `seed_demo --reset` 한 번 해 주세요 (로그인 `demo_01` 20대 여성 / `demo_02` 40대 남성)

---

## 2026-11-10 · 비밀번호 찾기 인증 코드: 서버 쪽 완료 → 🟦 화면 부탁 (⚠️ 화면 전까지 서버 배포 안 함) — 🟧 이수한
DB 변경 없음. 11/10 설계(바로 아래 항목) 그대로. **pull 뒤 로컬 비밀번호 찾기는 화면이 들어올 때까지 "인증 코드를 먼저 받아 주세요"로 막혀요** (서버는 화면이 들어온 뒤 같이 배포).

- `POST /pw_code/` (`views.pw_code`): 아이디·이메일·이름 → 6자리 코드 메일 (세션 `pw_reset`, 10분, 1분 안에 다시 받기 429, 없는 회원도 같은 문구)
- `POST /pw_find/`: `code` 칸 확인 (틀리면 `(n/5)`, 5번이면 다시 받기, 다른 아이디·재사용 막음, 바꾼 뒤 코드 지움)
- 메일: `.env` `EMAIL_HOST_USER` 비어 있으면 **runserver 터미널에 메일 내용이 찍혀요** (팀원 PC 설정 필요 없음, `.env.example` 빈 칸 추가)
- 확인(되돌림): 코드 없이·틀린 코드·다른 아이디·맞는 코드+재사용·5번 틀림 모두 기대대로

### 🟦 영준 — `templates/idpw.html` 비밀번호 찾기 (Claude Code에 부탁해도 돼요)
- [x] 안내 문구(127줄): "아이디·이메일·이름을 넣고 인증 코드를 받은 뒤, 메일로 온 코드와 새 비밀번호를 입력해 주세요."
- [x] 이름 칸 다음(160줄)에 **인증 코드 칸** `name="code"` (6자리 숫자, `inputmode="numeric"` `maxlength="6"` `autocomplete="one-time-code"`) + **[인증 코드 받기] 버튼 `type="button"`** (폼 안이라 type 없으면 제출돼요)
- [x] 버튼 → `fetch("{% url 'pw_code' %}", {method: "POST", body: new FormData(form)})` → 응답 `message`를 칸 아래에 표시 (FormData에 csrf·아이디·이메일·이름이 같이 들어가요, 429도 `message`가 와요)
- 확인: runserver 터미널에 찍힌 코드로 비밀번호 바꾸기까지. 끝나면 🟧가 서버 배포 + 서버 메일 계정 설정

---

## 2026-11-10 · 일정을 처음 만들 때 비 오는 날은 실내 먼저 — 🟩 서지윤
DB·응답 키·주소 변경 없음 · 🟩 `schedule_service.py`만 (🟦 `rain_service` 함수를 그대로 씀, 11/06 결정)

- `generate_schedule` 시작할 때 `rain_service.trip_days_weather`로 비 오는 날을 한 번 찾음 (`rainy: true`인 날 = 16일 안 예보 · 이미 지난 날 실제 날씨. 작년 날씨는 참고용이라 안 씀)
- 비 오는 날이 있으면 여행지 근처 실내 후보(`rain_service.INDOOR_QUERIES`: 박물관·미술관·전시관·아쿠아리움·복합쇼핑몰, 10km)를 한 번 찾아 **그날에만** 후보에 더함 (분류 `실내`, 체류 90분, 같은 건물은 한 곳만)
- 비 오는 날 `fill_activities(..., rainy=True)`: 넣을 수 있는 곳 중 **실내(`rain_service.place_indoor`)만** 고르고, 실내가 하나도 없을 때만 실외 → 그다음은 지금처럼 가까운 순 + 운영시간 맞추기
- 새 함수: `rainy_trip_dates`, `candidate_indoor`, `indoor_candidates`, `prefer_indoor`
- 시험(부산 11/15~17, 바다·자연·랜드마크, 2일차를 비로 정함): 2일차 관광 3곳 모두 실내(벡스코·임권택영화박물관·수영성마을박물관), 다른 날은 그대로. 미리보기 약 10초(실내 후보 검색 +2~4초)
- 지금 실제 부산 예보는 11/15~17 모두 비라서 그 날짜로 만들면 전부 실내 위주로 나와요
- 알아 둘 것(이번에 안 고침): 컨셉 '자연' 검색에 **'자연드림'(생협 매장)·'자연약국'**이 장소로 들어와요 (`search_places`·`filter_by_real_kind`, 이름에 '자연'이 들어가서)

### 확인
- [ ] 🟦 미리보기 날씨·실내 배지와 맞는지 한 번 봐 주세요 (비 오는 날 실외 '실내 대안 보기'가 거의 안 뜨게 됨)

---

## 2026-11-10 · 비밀번호 찾기 이메일 인증 코드 (새 주소 `pw_code/`, 폼 칸 `code`, `.env` `EMAIL_*`) — 🟧 이수한 (설계 먼저 공유)
DB 변경 없음 (코드는 세션에 10분만). 코드는 다음 PR. **지금은 아이디·이메일·이름만 맞으면 누구나 남의 비밀번호를 바꿀 수 있어서** 메일로 받은 코드를 확인하게 바꿔요.

**흐름**
1. `idpw` 화면 비밀번호 찾기: 아이디·이메일·이름 입력 → **[인증 코드 받기]** → `POST /pw_code/`
   - 응답 `{"success": true, "message": "입력한 정보가 맞으면 인증 코드를 메일로 보냈어요"}` (회원이 없어도 같은 문구 → 가입 여부가 드러나지 않게)
   - 6자리 숫자, 10분, 5번 틀리면 다시 받기. 같은 사람이 1분 안에 다시 받기는 막음
2. 메일의 코드 + 새 비밀번호 → 기존 `POST /pw_find/`에 **`code` 칸 추가** → 코드가 맞을 때만 변경 (기존 칸 `user_id`·`email`·`name`·`new_pwd`·`new_pwd_check` 그대로)

**메일 설정 (`.env`, 값은 각자)**
- `EMAIL_HOST_USER`·`EMAIL_HOST_PASSWORD`가 **비어 있으면 메일을 안 보내고 runserver 터미널에 찍혀요** → 팀원 PC는 아무것도 안 넣어도 돼요 (터미널에서 코드 보고 입력)
- 서버만 Gmail 계정 + **앱 비밀번호**(16자리) 넣기 (🟧가 서버 `.env`에 직접, 코드·GitHub에는 절대 안 넣음). `.env.example`에 빈 칸 추가

### 🟦 영준
- [x] `idpw.html` 비밀번호 찾기에 [인증 코드 받기] 버튼(`fetch` `POST /pw_code/`, 위 응답의 `message` 표시) + `code` 입력칸(6자리 숫자) — 🟧가 같이 할 수도 있어요, 편한 쪽 댓글

### 🟩 지윤
- 변경 없음

---

## 2026-11-10 · 일정을 처음 만들 때부터 운영시간·쉬는 날 고려 + 📐 안내 응답 키 (`hours`·`excluded`·`moved`) — 🟩 서지윤
DB 변경 없음 · 응답 키 **추가만** (`mock.json` `plan.days[]`) · 🟩 `schedule_service.py` + 🟧 `views.py` 세 군데 조금

### 쓰는 함수 (새 함수 없음)
- 🟦 `hours_service.place_hours`·`fit_stay`·`last_arrival` **그대로** 써요 (이름·받는 값 안 바꿈)
- `fit_stay`가 `early`(아직 안 엶)로 돌려주는 곳은 🟩 `schedule_service` 안에서만 처리: **여는 시각까지 60분 안이면 기다렸다 도착**, 더 길면 그 자리에 다른 곳

### 일정 만들 때 규칙 (11/06 결정 그대로)
- 그날 쉬는 곳 · 마감 전 도착 못 하는 곳(`late`, 음식점 60분·그 밖 30분 전)은 그 자리에 안 넣음
- 마감을 넘는 체류는 마감까지 줄임(`shortened`)
- 담은 장소(사용자가 고른 곳)가 그날 쉬면 여행 중 여는 날로 옮기고, 못 옮기면 빼고 안내

### 응답 키 (AI 대화 미리보기 `days[]` = `mock.json` `plan.days[]`)
| 키 | 모양 | 뜻 |
|---|---|---|
| `items[].hours` (`stops[].hours`) | `{open, close, estimated, status, wait, message}` 또는 `null` | `open`·`close` `"10:00"`, `estimated` 보통 영업시간으로 짐작, `status` = `fit_stay` 값(자동으로 넣은 곳은 `ok`·`shortened`·`unknown`, 담은 장소·순서를 바꾼 날은 `late`·`early`·`closed`도 나올 수 있음 → 경고로), `wait` 문 열기를 기다린 분(없으면 0), `message` 안내 한 줄(없으면 `""`). 모르면 `null` |
| `excluded` (이미 있는 키) | `[{name, reason, message, open_days}]` | 그날 못 넣은 곳. `reason`: `closed`(휴무) · `late`(마감 전 도착 못 함) · 기존 `weekly_off`·`monthly_off`·`holiday`. `open_days`: 이 여행에서 여는 날 번호 `[1]`(없으면 `[]`) |
| `moved` (새 키) | `[{name, from_day, to_day, message}]` | 쉬는 날이라 다른 날로 옮긴 담은 장소. 없으면 `[]` |

- 문장 예: `"10:00 문 여는 시각까지 20분 기다려요"`, `"마감(18:00)에 맞춰 체류 120분 → 90분"`, `"월요일 휴무라 DAY 2(화)로 옮겼어요"`, `"이 여행에서는 DAY 1(목)에 갈 수 있어요"`
- 화면은 `message`를 그대로 보여 줘도 되고, `status`·`reason`으로 직접 만들어도 돼요

### 코드 (🟩 `services/schedule_service.py`, 함수 추가 + 고르는 곳만 바꿈)
- `fill_activities`(관광)·`add_meal_before_deadline`·`add_meal`(식사): 가까운 곳부터 보면서 **운영시간이 맞는 첫 곳** (`pick_open_candidate`) → `save_schedule_place(forced_arrival=기다린 도착, stay_time_override=줄인 체류)`
- 새 함수: `candidate_hours`(후보 운영시간, 여행 하나 만드는 동안 메모리 캐시) · `fit_opening_hours`(기다리기·줄이기·못 넣음) · `move_closed_pins`(담은 장소 옮기기 → 안내) · `hours_badge`(미리보기 `hours` 한 칸)
- 숙소 줄은 검사 안 함 (`fit_stay`가 숙박은 `unknown`)

### 🟧 `views.py` (세 군데, 기존 동작 그대로)
- `_chat_finish_schedule`: `_chat_add_pins` 전에 `move_closed_pins` 한 줄 → 미리보기·적용 둘 다 옮긴 날로 들어감 (안내는 `travel.hours_notes`에 잠깐 담음, DB 저장 안 함)
- 새 `_chat_attach_hours(travel, days)`: `travel_chat_preview`에서 **롤백 밖**에서 불러 `hours`·`excluded`·`moved`를 붙임
  - ⚠ 알아 둘 것: 롤백(`transaction.atomic`) **안에서** 스레드 여러 개로 `place_hours`(DB 캐시 표)를 읽으면 잠금을 기다리느라 **50초씩 멈춰요** (처음에 그래서 167초 → 롤백 밖으로 옮겨 8초)
- `_chat_preview_days`는 안 바꿈 (예산 등 다른 곳도 그대로)

### 시험 (부산 11/15(일)~17(화), 역사·카페·랜드마크, 담은 장소 부산박물관 2일차(월))
- 운영시간 검사를 끄면 일요일 휴무 식당·여는 시각 전 카페가 들어감 → 켜면 자동으로 넣은 곳 운영시간 문제 **0곳**
- 부산박물관(매주 월요일 휴무) → DAY 1(일)로 옮김 + `moved` 안내
- 작은 경우 16개 통과: 40분 기다림 · 90분이면 안 넣음 · 음식점 마감 1시간 전 · 체류 줄이기 · 여는 날 없는 담은 장소는 `excluded`
- 미리보기 8초 (검사 없을 때 5초, 처음 보는 장소는 관광공사를 한 번 더 부름)

### 아직 안 한 것 / 알아 둘 것
- 담은 장소를 넣은 날은 🟧 `recalculate_schedule_timeline`이 뒤 시각을 다시 계산해서 **기다린 시간·점심 12:30 같은 빈 시간이 당겨질 수 있어요** (원래 있던 동작, 그날은 `hours`가 `early` 경고로 알려 줌)
- 미리보기 롤백 안에서 찾은 운영시간은 캐시에 안 남아요 (실제 적용 때는 남음)

### 확인
- [ ] 🟦 미리보기·일정 화면에서 이 키 써 주기 (모양 바꾸고 싶으면 PR 댓글)
- [ ] 🟧 `_chat_add_pins`(담은 장소 넣기)와 옮기기가 겹치는지 같이 확인 부탁

---

## 2026-11-10 · 체류 시간을 운영시간에 맞추기 + '운영시간에 맞추기' 버튼 + 📐 공유 정의 `hours_service.fit_stay` — 🟦 임영준
DB·기존 응답 키 변경 없음 · **새 주소 `travel_fit_hours/<travel_id>/<day>/` (POST)** · `hours_service.py`에 함수 추가만

### 📐 공유 정의 (11/06 결정: 🟩 일정 만들기도 같은 함수를 써요)
- `hours_service.last_arrival(kind, close_min)` → 이 시각(분)까지 도착해야 함: **음식점 마감 60분 전, 카페·그 밖 30분 전**
- `hours_service.fit_stay(kind, hours, arrive_min, stay_min)` → `{'status', 'stay', 'last_arrival', 'message'}`
  - `hours`: `place_hours(...)` 결과(없으면 None), `arrive_min`: 도착(분, 09:30 → 570), `stay_min`: 체류(분)
  - `status`: `ok` · `shortened`(마감을 넘는 체류 → `stay`가 줄인 값, 예: "마감(18:00)에 맞춰 체류 120분 → 90분") · `late`(마감 직전 도착이라 옮겨야 함, 예: "마감(21:00)까지 50분뿐이라 식사할 시간이 부족해요 · 20:00 전에 도착하게 옮겨 보세요") · `closed`(휴무) · `early`(아직 안 엶, 여기선 안 고침) · `unknown`(모름·24시간·숙소)
  - `is_food(kind)`: 음식·식당·맛집·한식… (카페·디저트는 아님)

### 화면 (여행 상세)
- 마감 직전 도착(음식점 1시간·그 밖 30분 전 넘김)도 주황 경고 + 맨 위 요약에 포함
- 마감을 넘는 체류가 있으면 요약에 **'운영시간에 맞추기'** 버튼 → 그 장소 체류를 마감 시각까지로 줄이고 떠나는 시각만 고침. **뒤 일정 시각은 그대로**(다시 계산하면 점심·저녁이 앞당겨져서), 빈 시간은 자유 시간
  - 결과 안내: 줄인 곳 + "체류로는 못 맞추는 곳"(마감 직전 도착·휴무 → 자리 옮기기)
- `POST travel_fit_hours/<id>/<day>/` (주인만) → `{success, day, changed: [{sp_id, name, before, after, message}], warnings: [{sp_id, name, status, message}]}`
- 아직 안 한 것: "사용자가 직접 고친 체류는 줄이지 않기"(11/06) — 직접 고쳤는지 기록하는 칸이 없어서, 버튼을 누를 때만 줄여요

### 🟩 지윤
- [x] 처음 일정 만들 때 운영시간 맞추기에 `fit_stay`·`last_arrival` 그대로 써 주세요 (이름·받는 값 바꿀 땐 알려 줘)

---

## 2026-11-10 · 여행 상세: 이동 구간마다 카카오맵·네이버지도 길찾기 링크 (대중교통 여행) — 🟦 임영준
DB·응답 키·주소 변경 없음 (화면만, `travel_detail.html`)

- 대중교통 여행이면 이동 구간 칸 아래에 **카카오맵 길찾기 · 네이버지도 길찾기** 버튼 (새 탭, 대중교통 탭으로 열림)
  - 카카오: `https://map.kakao.com/link/by/traffic/출발이름,위도,경도/도착이름,위도,경도`
  - 네이버: `https://map.naver.com/p/directions/x,y,출발이름,,/x,y,도착이름,,/-/transit` (x,y는 네이버 지도 좌표 = 위도·경도를 웹 메르카토르 미터로 바꾼 값)
- 출발·도착은 그 구간 경로(`from_place`·`to_place`, `points` 처음·끝) 그대로. 자동차·도보 여행에는 안 나와요
- 🟧🟩 할 일 없음

---

## 2026-11-10 · 로컬 LLM 비교: 리뷰 키워드 요약 GPT vs qwen3·EXAONE·Llama (`compare_review_llm` 명령 추가) — 🟧 이수한
코드·DB·응답 키 변경 없음 (시험 명령 추가만). 전체 표: [`docs/reports/review_llm_compare.md`](reports/review_llm_compare.md)

- `python manage.py compare_review_llm` → 리뷰 많은 장소 5곳(종류 안 겹치게)을 모델마다 같은 PROMPT로 요약해 표로 저장 (**DB 저장 안 함, `.env`도 안 바꿈**)
  - `--models gpt-4o-mini,qwen3:8b,exaone3.5:7.8b,llama3.1:8b` (gpt* 는 OpenAI, 나머지는 이 PC Ollama) · `--places 5` · `--rounds 2`
  - 모델마다 예비 모델·예비 AI를 꺼서, 로컬 모델이 몰래 OpenAI로 넘어가지 않게 함
- RTX 3060 8GB(시연 PC 사양), 5곳 × 2번:

| 모델 | JSON 정상 | 규칙 지킴 | 키워드 수 | 요약 길이 | 평균 시간 |
|---|---|---|---|---|---|
| `gpt-4o-mini` | 10/10 | 9/10 | 5.0개 | 31자 | 1.6초 |
| `qwen3:8b` (설정 B 기본) | 10/10 | 10/10 | 3.0개 | 28자 | 1.4초 |
| `exaone3.5:7.8b` (예비) | 10/10 | 8/10 | 3.9개 | 40자 | 1.2초 |
| `llama3.1:8b` | 10/10 | 10/10 | 2.7개 | 30자 | 1.1초 |

- **JSON은 40번 모두 정상** → 설정 B(`qwen3:8b`)로 시연해도 리뷰 요약은 그대로 돼요
- GPT는 키워드를 5개 채우지만 `양이 많고`·`줄 서도`처럼 리뷰 문장을 그대로 가져옴(명사구 규칙 위반), qwen3는 단점(주차·가격)을 거의 안 적음, EXAONE이 가장 풍부
- 한계: `seed_demo` 데모 리뷰라 표현이 비슷함. 실제 리뷰가 쌓이면 다시 돌려 보기
- 다음(🟧): `review_service` PROMPT·저장 전 문장형 키워드 거르기, 요약 60자(PROMPT)·100자(코드) 맞추기

### 🟩 지윤
- 참고만. 채팅·일정 에이전트 로컬 시험(3주차)도 같은 방식(`override_settings`로 모델 하나씩, 예비 끄기)으로 표를 만들 수 있어요

---

## 2026-11-10 · 체크인하고 다시 나가기: 숙소 두 줄 규칙 + 숙박비 한 번만 (`cost.same_stay` 키 추가 예정) — 🟧 이수한
DB 변경 없음. 응답 키는 **추가만**(`cost.same_stay`), `mock.json`에 `same_stay` 예시. 🟩 일정 구조 작업 전에 먼저 정해 두는 규칙이에요 (11/09 결정, PR #59).

**숙소 두 줄 규칙 (새 칸 없이)**
- 같은 날(`Schedule`) 안에 **같은 숙소**(`P_ID` 같음, `p_kind`에 `숙`)가 두 번 나오면 **앞 줄 = 체크인(짐 두기), 뒤 줄 = 귀가**
- 다음 날 출발점은 그대로 전날 숙소 (지금과 같음)
- 🟩 `schedule_service`에서 귀가 줄을 만들 때 **같은 `Place`를 다시 쓰면** 이 규칙이 그대로 맞아요 (새 숙소 `Place`를 또 만들지 않기)

**지금 확인한 문제:** 숙소가 하루에 두 줄이면 숙박비가 두 번 잡혀요 (`plan_budget`): 신라스테이 해운대 2명 1박 90,000원 → 두 줄이면 180,000원

**고칠 것 (🟧, `budget_service.plan_budget`)**: 같은 날 같은 숙소의 두 번째 줄부터는 금액 0, `cost`에 `same_stay: true`
```json
"cost": {"amount": 0, "cat": "stay", "source": "tour", "per": 90000, "unit": "room", "cap": 2, "people": 2, "text": "…", "same_stay": true}
```
- 첫 줄(체크인)은 지금과 같은 `cost` (`same_stay` 키 없음). 합계(`planned`, `by.stay`)는 한 번만

### 🟦 영준
- [x] `cost.same_stay`가 `true`인 숙소 줄은 금액 대신 "숙박비는 체크인 줄에" 같은 안내 (키 이름 위 그대로)

### 🟩 지윤
- [ ] 귀가 줄은 같은 숙소 `Place`로 (위 규칙). 다른 방법이 필요하면 TEAM_UPDATES에 먼저 적어 주세요

---

## 2026-11-10 · 예산 금액 변경 자동 기록 (DB 트리거 → `budget_log` 표, `GET /budget_log/<travel_id>/`) — 🟧 이수한
**DB 추가:** 마이그레이션 `0018_budgetlog` (새 표 `budget_log` + `travel_budget_item` 트리거 3개). 응답 키는 새 주소라 **추가만**, `mock.json`에 `budget_log` 예시. pull 뒤 `python manage.py migrate` 해 주세요.

- 비용 관리에서 장소 금액을 넣기·고치기·지우기 하면 **DB가 알아서** 한 줄씩 적어요 (파이썬 코드 변경 없음, 같은 금액으로 다시 저장하면 안 적음)
  - 트리거: `trg_budget_item_ins` / `trg_budget_item_upd` (금액이 달라졌을 때만) / `trg_budget_item_del`
  - `budget_log` 칸: `BL_ID`, `T_ID`, `SP_ID` (둘 다 FK 아님 → 여행·장소를 지워도 기록은 남음), `P_NAME`(그때 장소 이름), `ACTION`(`insert`/`update`/`delete`), `OLD_AMOUNT`, `NEW_AMOUNT`, `CHANGED_AT`
- `GET /budget_log/<travel_id>/` (로그인·내 여행만) → 최근 10줄, 최신이 위
```json
{"success": true, "logs": [{"name": "해운대블루라인파크", "action": "update", "old": 12000, "new": 15000, "at": "2026-11-10 12:35"}]}
```
  - `action`: `insert`(처음 넣음, `old: null`) · `update` · `delete`(`new: null`)
- 수업 연결: 08/10·08/11 16·17일차 트리거

### 🟦 영준
- [x] (11/11 🟦 완료, `LogPanel.jsx`) 비용 관리 화면에 "최근 변경" 몇 줄: `해운대블루라인파크 12,000원 → 15,000원 · 11/10 12:35` (이 주소 사용)

### 🟩 지윤
- 변경 없음 (관리자 페이지에서 보고 싶으면 `BudgetLog` 모델)

---

## 2026-11-10 · 축제 이용요금 → 예상 비용 (축제 카드에 `fee` 키) — 🟧 이수한
DB 변경 없음. 응답 키는 **추가만**(`GET /travel_festivals/<id>/`의 `festivals[]`에 `fee`), `mock.json`에 `festival_fee` 예시.

**지금 확인한 것 (실제 축제 79개로 시험)**
- 축제를 일정에 끌어 넣으면 이미 예상 비용에 들어가요: `place_kind='축제'` → `budget_service.place_price` → 관광공사 `detailIntro2`의 `usetimefestival` → 1인 요금 × 인원 (`sight` 분류)
- 79개 중 무료 52 · 금액 읽음 19 · 모름 8 (`'유료'`, `'프로그램별 상이'`처럼 금액이 안 적힌 것). 이름으로 찾은 관광공사 항목은 79개 모두 축제 목록과 같은 ID
- 빠진 것: **넣기 전 축제 카드에는 요금이 안 보여요** → 이번에 `fee` 키를 붙여요

**붙일 키** (`festivals[]` 각각, 인원은 비용 관리에서 고른 인원)
```json
"fee": {"per": 10000, "amount": 20000, "people": 2, "paid": true, "text": "성인 10,000원 · 청소년 5,000원"}
```
| 경우 | `per` | `amount` | `paid` |
|---|---|---|---|
| 금액 읽음 | 1인 금액 | `per × people` | `true` |
| 무료 (`'무료(일부 유료)'` 포함) | `0` | `0` | `false` |
| 유료인데 금액 안 적힘 | `null` | `null` | `true` |
| 요금 정보 없음 | `null` | `null` | `false` (`text: ''`) |
- 관광공사 실패·키 없음이면 `fee: null` (목록은 그대로)
- **들어감:** `budget_service.festival_fee(content_id)`(축제 하나, 캐시 7일) · `festival_fees(festivals, people)`(목록에 `fee`, 6개씩 동시에) → `views.travel_festivals`에서 축제 시간 다음에 붙여요. 실패해도 목록은 그대로
- 확인: 데모 여행(12/20, 3명) 축제 3개 모두 `fee` 붙음 · 2027 ACE Fair 10,000원 × 3 = 30,000원 · 렉키의 수상한 피크닉 9,000원 × 3 = 27,000원 · 처음 2.8초, 다음부터 캐시
- 수업 연결: 08/24·08/25 25·26일차 공공 API

### 🟦 영준
- [x] (11/11 🟦 완료) 축제 카드에 요금 한 줄: `1인 10,000원 · 2명 20,000원` / `무료` / `유료 · 금액은 홈페이지` (`text`는 마우스 올리면 보이게 해도 좋아요). 키 이름은 위 표 그대로

### 🟩 지윤
- 변경 없음. 일정에 넣은 축제 비용은 지금처럼 `plan_budget`에 들어가요

---

## 2026-11-10 · 🆕 비슷한 장소 찾기 (리뷰 RAG) `GET /similar_places/` — 🟧 이수한
DB 변경 없음(0016 `embed_chunk` 표 그대로). 응답 키는 새 주소라 **추가만**, `mock.json`에 `similar_places` 예시.

- 장소별 리뷰를 한 덩어리로 임베딩해 저장(`embed_service.index_reviews`, `kind='review'`, 장소 하나 = 조각 하나) → 저장된 숫자끼리 코사인으로 비슷한 장소 (`embed_service.similar_places(kakao_id, top_k=5)`, OpenAI 호출 없음, 0.03초)
- `GET /similar_places/?kakao_id=…&top_k=5` → `{success, kakao_id, places: [{kakao_id, name, score}]}` (점수 높은 순, 최대 10, 저장 안 된 장소면 `places: []`, kakao_id 없으면 400)
- 리뷰가 늘면 `python manage.py index_reviews`로 다시 저장 (리뷰 2개 이상 장소만, 같은 장소는 옛 조각 지우고 새로)
- 예: 해운대해수욕장 → 일광(0.89)·송도·송정해수욕장, 모모스 영도 → 카페385·카페만디·블랙업커피, 부산박물관 → 근현대역사관·동래읍성지
- 수업 연결: 09/30 49일차 임베딩·코사인 유사도, 10/01 50일차 RAG

### 🟦 영준 (선택)
- [ ] 장소 정보·리뷰 화면에 "리뷰가 비슷한 장소" 카드 (이 주소 사용)

### 🟩 지윤
- 여행지 RAG(`kind='tour'`)와 같은 표·함수예요. `search(질문, kind='tour')`는 리뷰 조각을 안 섞어요

---

## 2026-11-10 · 일정 시간 다시 계산할 때 대중교통은 카카오 경로 시간으로 — 🟧 이수한
DB·응답 키 변경 없음. `views.get_route_travel_minutes_by_coords`의 대중교통 부분만 바뀜.

- `recalculate_schedule_timeline`(장소 추가·순서 바꾸기·시간 수정·담은 장소 넣기 뒤 시간 다시 맞추기)에서 **대중교통 구간 이동시간 = 🟦 `transit_service.transit_route`의 `minutes`** (화면의 카카오 경로와 같은 값). 전에는 저장된 계획시간을 그대로 썼어요
  - 같은 구간은 캐시 7일, 700m 안은 도보, 카카오 실패·키 없음이면 전처럼 저장된 시간
  - 일정을 **처음 만들 때**(`schedule_service.fill_activities`)는 지금처럼 거리 짐작 (후보마다 부르면 느려서)
- 예: 해운대블루라인파크 → 자갈치 20분 → **35분**, 자갈치 → 본전돼지국밥 25분 → **47분** (카카오와 같음). 처음 계산 1.5초, 두 번째부터 캐시 0초
- 🟩 지윤: 쉬는 요일 옮기기·일정 고칠 때 운영시간 검사에서 시간을 다시 계산하면 대중교통 여행은 이 시간으로 나와요 (도착 시각이 더 정확해져서 운영시간 검사도 정확해짐)

---

## 2026-11-10 · `place_search` 화면 삭제 (10/30 안건 7 결정대로) — 🟧 이수한
DB·응답 키 변경 없음. 화면 주소만 없어져요.

- 지움: 뷰 `place_search`·`place_search_search`, 주소 `place_search/`·`place_search_search`, 템플릿 `place_search.html`
- **남김**: `schedule_place_search`(여행 상세에서 장소 찾아 넣기)와 그 안의 `_search_kakao_places`, 장소 검색 창 CSS(`.place-search-*`, 여행 만들기·상세에서 씀)
- 템플릿에서 지운 주소 이름을 쓰는 곳 없음 확인, `/place_search/` → 404, `/schedule_place_search/` → 200

---

## 2026-11-09 · 📐 공유: 추천 점수 키워드 보너스용 `draft` 인자 (🟩 `chat_service.py` 호출 한 줄에 추가만) — 🟧 이수한
아직 코드 없음 (먼저 공유, 11/09 규칙). 🟧 추천 점수 PR에 같이 들어가요.

- `review_rank.rank_by_reviews(items, keep_first=0, profile=None, draft=None)` — `draft` 인자 **추가만**
  - 여행 컨셉(`draft['categories']`, 예: `['바다', '카페']`)과 장소 리뷰 키워드(`ReviewSummary.keywords`)가 겹치면 점수에 조금 더해요(순서만, 카드 `review` 값 그대로)
- 🟩 `chat_service.py` `search_recommendations` 안의 `rank_by_reviews(...)` 호출(1137줄)에 `draft=draft` 하나 추가 — 이미 받고 있는 `draft`를 넘기기만 해요
- 성별·나이대 가중은 이제 **하나만 있어도** 적용돼요 (성별만 → 같은 성별, 나이대만 → 같은 나이대)

---

## 2026-11-09 · 로컬 LLM(설정 B, `qwen3:8b`) 예산 대화 시험 결과 + 숙소가 다른 말로 덮어써지는 문제 고침 (🟩 `chat_service.py`에 함수 추가) — 🟦 임영준
DB·응답 키 변경 없음. 🟩 파일에 함수 1개 + 호출 1줄 **추가만**

### 시험
- `.env` 설정 B(`qwen3:8b`, 예비 `exaone3.5:7.8b`)로 여행 만들기 대화 → 미리보기 → 적용 → 비용 관리까지 (Ollama 실행 확인: `ollama ps` 100% GPU)
- 대화: "제주 2박 3일 맛집 여행" → "오늘출발" → "2명" → "추천해줘" → "제주공항 근처로 추천해줘"(카드에서 숙소 담기) → "이동수단은 자동차야" → "예산은 50만원이야" → "2일차 숙소 추천해줘"

### 결과
- ✅ 지역·날짜·인원(2명)·컨셉·이동수단 모두 바르게 읽음
- ✅ 예산: "예산은 50만원이야" → 초안 예산 `총 500,000원`, 적용 후 `Travel.t_budget` 500,000 저장
- ✅ 예상 비용(카드·초안)은 코드 계산(`budget_service`)이라 모델과 상관없이 맞음 (식비 148,000 + 숙박 240,000 = 388,000)
- ❌ **숙소가 다른 말로 덮어써짐:** "예산은 50만원이야" 턴에서 qwen3가 초안을 다시 쓰며, 카드에서 담아 둔 11/9 숙소(팜파스호텔 제주)를 앞에서 했던 말 "제주공항 근처"로 바꿈 → 위치 못 찾음 경고 + 숙박비가 예상 비용에서 빠짐
  - 원인: `normalize_draft`의 숙소 부분(`chat_service.py` 409줄 근처)은 같은 날짜·같은 이름이면 예전 숙소를 쓰는데, 이름이 바뀌어서 새로 검색하다 실패
  - 설정 A(GPT)에서는 못 본 실수

### 고친 것 (🟦, `chat_service.py`)
- `_keep_found_stays(ai_stays, prev, user_text)` 추가 (`_keep_previous` 바로 아래), `run_chat_turn`에서 컨셉 거르기 다음에 한 줄로 부름
- **이번 사용자 메시지에 숙소 얘기(`_STAY_ASK_WORDS`·`_STAY_WORDS`)가 없으면, 위치까지 찾은 숙소는 AI가 바꾸거나 빼도 그대로 둠** (날짜·컨셉을 코드가 지키는 것과 같은 방식)
  - 빈 날짜에 새 숙소를 넣는 건 그대로 받음, '첫날 숙소는 ○○로 바꿔줘'처럼 숙소 얘기를 하면 지금처럼 AI 판단
- 가짜 AI로 시험: 고치기 전에는 "예산은 50만원이야" 턴에 숙소가 '제주공항 근처' → 카카오 검색 '스테이근처'로 바뀜 / 고친 뒤 팜파스호텔 그대로, 숙소 바꾸기 요청·빈 날짜 추가는 그대로 동작

### 🟩 지윤
- [ ] 확인만 (같은 함수 근처를 고칠 일이 있으면 알려 줘)

### 정리
- 시험 뒤 `.env`는 설정 A로 되돌림
- 🟦 "로컬 LLM: 예산 AI 시험·보완" 3주차 항목은 이걸로 끝 (보완은 🟩 요청으로 넘김)

---

## 2026-11-09 · 수업에서 안 배운 코드는 Claude Code가 자세히 설명해 줘요 — 🟧 이수한
코드 변경 없음 (팀 공통 Claude 규칙 `.claude/rules/team-updates.md`에 한 항목 추가). **pull 후 Claude Code를 다시 열면** 적용돼요.

- 힌트를 받을 때도, "직접 수정해 줘"로 맡길 때도 처음 보는 문법·기능이 나오면 Claude가 **① 무엇인지 ② 왜 여기서 쓰는지 ③ 작은 예시(넣으면 → 나오는 것) ④ 흔한 실수**를 같이 적어 줘요
- 수업에서 배운 것(GROUP BY·트리거·공공 API·임베딩·RAG·LangChain·FastAPI 등)은 몇 일차인지 짚고 짧게
- 설명이 부족하면 "이거 수업에서 안 배웠어, 자세히 설명해 줘"라고 하면 돼요
- **보기 좋게:** 코드는 VS Code처럼 색이 나뉘게 언어를 붙인 코드 블록(`python`·`django`·`css`·`javascript`…)으로, 고칠 줄은 `diff` 블록(빨강 = 원래, 초록 = 바꾼 것)으로 보여 줘요
- 예: 오늘 나온 것들 — `**{field: v}`(사전을 이름 있는 인자로 풀기), `collections.Counter`, 줄 끝 쉼표가 튜플을 만듦, `Paginator.get_elided_page_range`, CSS 선택자 우선순위, `?v=` 번호로 캐시 피하기

---

## 2026-11-09 · ✅ ODsay 뺌 → 카카오 대중교통 경로(서버) + 📐 공유 정의 `transit_service.transit_route` — 🟦 임영준
DB 변경 없음 · 기존 응답 키 그대로 · **새 주소 `/transit_route/` + `mock.json`에 `transit_route` 추가** · `.env`의 `ODSAY_WEB_API_KEY`는 이제 안 씀(지워도 됨)

### 📐 공유 정의 (11/09 규칙, 🟧 서버 이동시간도 이걸 써 주세요)
- `sherpaapp/services/transit_service.py`
  - `transit_route(from_lat, from_lon, to_lat, to_lon)` → dict, 호출 실패(키 없음·네트워크)면 `None`
  - 돌려주는 값: `walk`(걷는 구간인지), `minutes`, `distance`(m), `fare`(1인 원, 모르면 None), `transfers`, `label`(예: '버스 141 → 지하철 2호선'), `steps[]`(`mode`·`kind`·`line`·`name`·`from`·`to`·`minutes`·`distance`·`stops`·`guidance`), `segments[]`(`mode`, `points: [[위도, 경도], …]` 지도 선, 처음·끝 걷는 길 포함), `url`(카카오맵 길찾기 링크) — 예시는 `mock.json`의 `transit_route`
  - 캐시: 키 `transit:위도,경도:위도,경도`(소수 4자리), 7일 (🟧 11/09 결정대로 표 없이 캐시)
  - 700m 이내는 카카오를 부르지 않고 걷기(`walk: true`). 카카오가 경로를 못 찾으면 2km 안은 걷기, 더 멀면 `None`
  - `meters(a, b)`: 두 점 (위도, 경도) 직선 거리(m)도 같이 씀
- `GET /transit_route/?from=위도,경도&to=위도,경도` (로그인 필요) → `{success, route: 위 dict}`

### 바뀐 화면
- **여행 상세:** 대중교통 여행이면 구간마다 노선·탑승/하차 정류장·환승·**1인 요금**·실제 노선 모양을 처음부터 보여 줘요. ODsay '상세 경로 보기' 버튼·한도 초과 안내는 없어졌어요 (`travel_detail.html` ODsay 코드 약 2,000줄 → 250줄)
- **채팅·여행 만들기 지도:** 같은 서버 주소로 실제 노선을 그려요 (React `frontend/src/lib/transit.js`, 예전 `travel_chat.js`)
- 지운 것: `ODSAY_WEB_API_KEY`(settings·context processor·`.env.example`·템플릿 `data-odsay-key`), `frontend/src/lib/odsay.js`

### 🟧 이수한
- [ ] 서버 일정 시각 계산을 카카오 경로로 맞출 때 `transit_service.transit_route(...)['minutes']` 사용 (확정된 구간만 부르기, 11/09 결정)
- [ ] 배포 서버 `.env`의 `ODSAY_WEB_API_KEY`는 지워도 돼요 (있어도 안 씀)

### 🟩 서지윤
- 할 일 없음 (`schedule_service.py` 주석에 ODsay 얘기가 남아 있는데 동작과는 상관없어요)

---

## 2026-11-09 · 비용 관리: 총예산 = 내가 정한 금액 (직접 고치기) — 🟦 임영준
DB 변경 없음 · 응답 키 그대로 · **요청 키 추가만**

- 전: 총예산 = 분류 예산 합계 → 대화에서 "예산 50만 원"이라고 해도 비용 관리에는 AI 예상 합계(예: 388,000원)가 보였음
- 지금: 총예산 = `Travel.t_budget` (대화에서 정한 금액, 안 정했으면 적용 때 AI 예상 합계). 비용 관리 위 칸에서 직접 고칠 수 있음
  - 남은 금액 = 총예산 − 일정 예상, 분류에 안 나눈 금액·분류가 총예산보다 많을 때 경고도 보여 줌
- `budget_category` POST에 **`total`(선택)** 추가: 보내면 그 값이 총예산. 안 보내면 총예산은 그대로 두고 분류 합계가 더 클 때만 늘림 (전에는 항상 분류 합계로 덮어씀)
- 🟧🟩 할 일 없음

---

## 2026-11-09 · 📐 공유: 리뷰 게시판 '장소 리뷰' 탭에 분류 보기·정렬·번호 페이지 (🟦 `review.html`에 칩 추가) — 🟧 이수한
아직 코드 없음 (먼저 공유, 11/09 규칙). 🟧가 이 모양으로 만들어요. DB·응답 키 변경 없음 (화면 주소의 GET 값과 템플릿 값만 추가).

- 주소: `review_board/?tab=places` 에 GET 값 추가
  - `by` = `place`(장소) · `kind`(카테고리) · `region`(지역) · `tag`(태그), 없으면 전체
  - `v` = 고른 칩 값 (예: `by=kind&v=카페`)
  - `sort` = `helpful`(추천 많은 순, **기본**) · `new`(최신순)
  - `page` = 번호
- 템플릿에 넘기는 값 (추가만): `groups`(기준 버튼 목록), `by`, `v`, `sort`, `chips` = `[{value, label, count}]`, `page_numbers`(‹ 1 2 … › 번호 목록). 기존 `page`·`best_reviews`·`review_total`·`tags`는 그대로
- 🟦 영준: `review.html`의 장소 리뷰 탭 위쪽에 기준 버튼·칩·정렬 버튼, 아래쪽 이전/다음을 번호 페이지로 바꿀게 (다른 부분은 안 건드림). 같은 곳을 고칠 일이 있으면 알려 줘

---

## 2026-11-09 · 업무 분배: 🟦 4주차 일 2개를 🟩·🟧로 옮겨요 — 🟧 이수한
코드 변경 없음 (담당만 바꿈). 기준: **아직 시작 안 한 4주차 일**만 나눠요. 각자 맡아서 아직 못 한 일은 그대로 그 사람 몫이에요.

| 일 | 바뀐 담당 | 이유 |
|---|---|---|
| 가는 길·돌아오는 길 **실제 시간표** (열차·국내항공·연안여객선) | 🟦 영준 → 🟩 **지윤** (4주차) | 일정 시작 시각을 정하는 일이라 일정 에이전트 영역, 🟩 4주차가 비어 있음. 🟦 "이동수단별 가격 비교"는 이 결과(운임)를 화면에 써요 |
| **축제 이용요금 → 예상 비용** 반영 | 🟦 영준 → 🟧 **수한** (4주차) | 관광공사 요금 읽기·비용 계산(서버 쪽). `budget_service.py`(🟦 파일)에 함수를 **추가만** 하고, 시작 전에 여기 공유할게 |
| 관리자 페이지 `/manage/` (회원 화면을 읽기 전용으로 보기, 저장·수정은 403) | 🟧 수한 → 🟩 **지윤** (4주차) | 🟩 4주차 여유. 회원 `is_admin` 칸이 필요하면 마이그레이션 번호는 TEAM_UPDATES에 먼저 적고 시작 |

- 바꾼 뒤 필수 할 일: 🟧 13 (3주차 7·4주차 6, 작은 일 위주) · 🟦 9 (4·5) · 🟩 10 (7·3)
- 공유 규칙 그대로: 🟩 시간표 함수(편명·출발·도착·운임)를 먼저 정해서 여기 적어 주면 🟦 가격 비교가 그대로 써요

### 확인
- [ ] 🟦 확인
- [x] 🟩 확인 (실제 시간표·관리자 페이지 맡기)

---

## 2026-11-09 · 할 일 추가: 가져올 기능 후보 1·2순위 + 성별·나이대 개선 — 🟧 이수한
코드 변경 없음 (진행도에 할 일 추가). 자세한 건 [진행도](https://claude.ai/artifact/1Lwf6NtqDRyUH16a1ZFPMb)·[역할 분담 → 가져올 기능 후보](https://claude.ai/artifact/WREMzfhPWtDKpPGYSCBocq#bring)

### 4주차 필수 (후보 1순위)
- 🟧 장소 리뷰 분류 보기(장소·카테고리·지역·태그) + 추천 많은 순 + 번호 페이지 — 13·14일차 집계·GROUP BY
- 🟧 **예산 금액 변경 자동 기록**(DB 트리거) — 원래 후보는 "지출 변경 기록(pay_log)"이었는데, #64·#67로 지출 입력이 없어져서 **회원이 고치는 예산 금액(`travel_budget_item`) 기록**으로 바꿨어요. 🟦 비용 화면에 최근 변경 몇 줄을 보여 주면 좋아요
- 🟦 축제 이용요금 → 일정에 넣으면 예상 비용 자동 반영 (1인 요금 × 인원) — 25·26일차 공공 API
- "비슷한 관광지 추천"은 🟧 RAG(`similar_places`)에 포함, 🟩 후보 1순위(여행지 RAG·의도 나누기·운영시간)는 이미 3주차에 있음

### 4주차 선택 (후보 2순위, %에서 빠짐)
- 🟦 마이페이지 여행 기록 통계 (집계 쿼리는 🟧가 도울 수 있음)
- 🟧 FastAPI AI 서버 분리 · Streamlit 운영 대시보드

### 성별·나이대 (추천 점수 #68 후속)
- 지금은 성별·나이대를 **둘 다** 넣은 회원만 맞춤 순서가 돼요(안 넣으면 지금처럼 전체 평점 순)
- 🟧 3주차: 하나만 있어도 가중 (성별만 → 같은 성별, 나이대만 → 같은 나이대)
- 🟦 4주차: 채팅 추천 카드 위·마이페이지에 "성별·나이대를 넣으면 나와 비슷한 사람들이 좋아한 곳을 먼저 보여 드려요" 안내 (억지로 받지 않기)

### 확인
- [ ] 🟦 확인 (4주차 할 일이 많으면 선택 항목부터 빼도 돼요)
- [x] 🟩 확인

---

## 2026-11-09 · 📐 공유 정의: 추천 점수에 회원 성별·나이대를 넘기는 `profile` 인자 (🟩 `chat_service.py`에 추가만) — 🟧 이수한
아직 코드 없음 (먼저 공유, 11/09 규칙). 🟧가 추천 점수 작업 PR에서 이 모양대로 넣어요.

- 모양: `profile = {'gender': 'M' | 'F' | None, 'age_group': 10~60 | None}` (동의 안 한 회원은 `None` 값, 로그인 안 했으면 `profile=None`)
- 넘기는 길 (모두 **기본값 `None` 인자를 추가만**, 기존 호출·응답 키 그대로)
  - `views.travel_chat` → `chat_service.run_chat_turn(..., profile=…)`
  - `run_chat_turn(…, profile=None)` → `search_recommendations(…, profile=profile)`
  - `search_recommendations(…, profile=None)` → `review_rank.rank_by_reviews(…, profile=profile)`
  - `rank_by_reviews(items, keep_first=0, profile=None)` → 같은 성별·나이대 리뷰 점수를 섞어 순서만 바꿈 (`item['review']`는 그대로)
- 🟩 지윤: `run_chat_turn`·`search_recommendations` 선언 줄에 인자가 하나씩 늘어요. 같은 줄을 고칠 일이 있으면 알려 줘 (충돌 방지)

---

## 2026-11-09 · ⚠️ #64 확인: "쓴 돈(지출)"을 적는 곳이 없어졌는데 화면은 아직 "쓴 돈"을 보여 줘요 → 🟦 정해서 반영 — 🟧 이수한
코드 변경 없음 (확인 결과 전달)

### 지금 상태 (main `416f0f6` 기준)
- React로 바꾸면서 예전 지출 입력(`budget_add`·`budget_update_pay`·`budget_delete`)이 빠졌어요. **지금 코드에는 지출(`Pay`)을 새로 저장하는 곳이 하나도 없어요**
- 그런데 새 예산 차트는 아직 "쓴 돈"을 그려요
  - `frontend/src/budget/ChartPanel.jsx`: 분류별 예산/일정 예상/**쓴 돈** 막대, 날짜별 **쓴 돈** 선 (`used`·`dailyUsed`)
  - `views.py` `budget_category` (5836~5847줄): `Pay`에서 `daily_used`·분류별 쓴 돈 계산해서 보냄
- 그래서 새 여행은 **"쓴 돈"이 항상 0**으로 보여요. 시연 때 "왜 비어 있지?"가 나올 수 있어요

### 🟦 영준: 셋 중 하나로 정해서 반영해 줘 (기능 동결 11/19 전)
1. **React 화면에 지출 입력을 다시 넣기** (🟧 추천): 분류(또는 장소)마다 "쓴 돈 추가·고치기·지우기" 작은 입력, 서버엔 저장 API를 **추가**(`Pay` 표 그대로 사용, 새 표 필요 없음). 예산 AI의 "계획 → 실제" 비교가 살아나요
2. **"쓴 돈"을 화면에서 빼기**: 차트·응답에서 쓴 돈 부분 정리 (응답 키를 빼는 건 3인 합의, 화면에서 안 쓰기만 하면 키는 남겨도 됨)
3. **그대로 두기**: 비어 보이는 칸이 남아요

- 정하면 이 항목 아래에 한 줄로 적어 주세요 (예: "→ 1번으로, 11/xx PR")
- 진행도 3주차 🟦에 "쓴 돈(지출) 처리 정하고 반영" 항목을 넣어 뒀어요 (주간 가이드에 방법 있음)

→ 🟦 **2번으로** (11/09): 쓴 돈은 화면에서 뺐고, 그 칸은 **남은 금액 = 총예산 − 일정 예상**으로 바꿨어요 (넘치면 빨간 "X원 초과"). 분류 줄의 쓴 돈 표시와 차트 2개의 쓴 돈 막대도 뺐어요. 응답 키 `by`·`daily_used`는 그대로 둬요 (빼려면 3인 합의). 🟧 서버 코드는 손대지 않아도 돼요.

### 확인
- [x] 🟦 몇 번으로 할지 결정 (2번)
- [ ] 🟦 반영 PR

---

## 2026-11-09 · 추천 카드를 누르면 지도에서 위치 보기 — 🟦 임영준
DB·응답 키 변경 없음 (화면만)

- 대화의 추천 카드(빈 곳)를 누르면 지도가 그 장소로 옮겨 가고(확대 5단계) **주황 핀**에 이름 표시, 누른 카드는 주황 테두리. 넣기 버튼·카카오맵 링크는 그대로 동작. 폰처럼 지도가 화면 밖이면 지도까지 내려감
- 대화 화면 `travel_chat.js` `focusPlace()`, React `App.jsx`(`focus` 상태) → `ChatPanel`·`RecCards`(누르기) · `MapPanel`(핀), 모양 `.tc-mappin--focus`·`.tc-card.is-focus`

---

## 2026-11-09 · 추천 카드에 ★ TRIPA 추천 + 영업시간·입장료·휴무·주차·팁 (`pick`) — 🟦 임영준
DB·응답 키 변경 없음 (🟩가 이미 보내던 `pick`을 화면에 보여 줌)

- 팀이 고른 부산 장소(`docs/data/busan_spots_draft.csv`, 31곳)가 카드에 나오면: 주황 테두리 + **★ TRIPA 추천** 배지 + 영업·입장료·휴무·주차·팁 칸 (값 있는 것만)
- 대화 화면 `travel_chat.js` `pickInfo()`, React `RecCards.jsx` `PickInfo`, 모양 `style.css` `.tc-pick`·`.tc-tag--pick`·`.tc-card.is-pick`
- 시험: 부산 '바다' → 해운대·광안리, '맛집' → 영진돼지국밥·국제밀면이 TRIPA 추천으로 앞에 나옴

---

## 2026-11-09 · 비용 관리: 분류를 펼쳐 장소별 금액 보고 고치기 — 🟦 임영준 (**DB 변경 → 모두 `migrate`**)
**새 표 `travel_budget_item` (모델 `TravelBudgetItem`, 마이그레이션 `0017_travel_budget_item`, 🟧 `0016_embedchunk` 다음)** → pull 후 `python manage.py migrate`

- 표: `travel`(FK) · `schedule_place`(일정의 그 자리, OneToOne) · `amount` · `updated_at`. **회원이 고친 장소만** 저장, 없으면 AI 금액. 일정에서 장소를 빼면 같이 지워지고, 대안으로 바꾸면(`budget_swap`) 고친 금액은 지움
- 화면(React `CategoryRow.jsx`): 분류마다 '상세 N곳 보기 · 고치기' → 장소마다 DAY·이름·AI 금액(1인/1박 방)·금액 칸·'AI 금액'(되돌리기). 장소 금액을 고치면 그 분류 예산 = 장소 합계. 가격 모르는 곳(예: 창덕궁)도 나와서 직접 적을 수 있음
- API (추가만)
  - `GET budget/<id>/category/?plan=1` → `budget.items: [{sp_id, day, date, name, kind, cat, ai, amount, edited, per, unit, source}]`, `counts`는 이제 가격 모르는 곳도 셈
  - `POST budget/<id>/category/` → `{limit: {...}, items: {sp_id: 금액 | null}}` (null = AI 금액으로). 남의 여행 장소는 무시
  - `GET travel_costs/<id>/<day>/` → 고친 장소는 그 금액 + `edited: true` (여행 상세 카드에 '예산 22,000원 (직접 고침)')

- **예산 차트** (예전 비용 관리 '지출 차트' 3개를 React `ChartPanel.jsx`로 옮김, 같은 Chart.js 4.4.1 CDN·`.bg-chart` 모양)
  - 분류별 예산 비율(도넛) · 날짜별 예상 비용·쓴 돈 + 하루 예산 점선 · 분류별 예산/일정 예상/쓴 돈(가로 막대). 금액 칸을 고치면 바로 다시 그림
  - `GET budget/<id>/category/?plan=1`에 `days`(여행 날짜 목록)·`daily_used`({날짜: 쓴 돈}) 추가

### 확인
- [ ] 🟧🟩 pull 후 `migrate` (0016·0017) — 🟩 완료 (11/10)
- [ ] 🟧 `views.py` `_budget_items`·`_save_budget_items` 확인 부탁

---

## 2026-11-09 · ⚠️ 비용 관리 = React 카테고리 예산 화면으로 바꿈 (예전 지출 기록 화면 없앰) — 🟦 임영준
DB 변경 없음. **주소 이름 몇 개가 없어졌어요** (아래). 다른 화면에서 쓰던 곳은 없음을 확인함.

- 왼쪽 메뉴 '비용 관리'(`{% url 'budget' %}`, `budget_travel`) → 이제 React 카테고리 예산 화면(`category_budget_page`, 템플릿 `category_budget.html`). 주소는 그대로 `budget/`·`budget/<id>/`
- 회원은 **AI가 매긴 분류별 금액만** 고쳐요. 총예산은 따로 안 고치고 **분류 합계 = 총예산** (`budget_category` POST가 `t_budget`도 합계로 저장)
- 없앤 것 (🟧 `views.py`·`urls.py`에서 지움)
  - 템플릿 `budget.html`, 뷰 `budget`·`budget_update_total`·`budget_add`·`budget_delete`·`budget_update_pay`·`budget_ai_fill`, 계산 `_budget_overview`·`_budget_chart`·`_budget_ai_rows`·`_pct`
  - 주소 이름 `budget_update_total`·`budget_add`·`budget_delete`·`budget_update_pay`·`budget_ai_fill`, 잠깐 있던 `category_budget`·`category_budget_travel`
  - → **지출(Pay) 추가·수정·삭제 화면이 없어요.** 지출 기록이 다시 필요하면 회의에서 정하기
  - 여행 상세 왼쪽 'DAY n 여행 비용'(기록한 지출 목록·합계) 칸도 없앰 → 그 자리에 'AI 예상 비용'만 (`renderPayment`). `travel_detail_day`의 `pays`·`total_pay` 응답 키는 그대로 둠
  - 🟦 로컬 DB의 예전 시험 지출 17건은 지웠어요 (각자 로컬 DB는 각자 판단)
- 남긴 것: `_budget_category`·`BUDGET_CATEGORIES`(분류 API가 씀), `_budget_people`(인원)
- `style.css`의 `.bg-*`(예전 비용 관리 모양)는 지금 안 쓰지만 남겨 둠

### 확인
- [ ] 🟧 `views.py`에서 지운 비용 관리 뷰들 확인 부탁 (Pay 모델·표는 그대로)
- [ ] 🟩🟧 지출 기록 화면이 없어도 되는지 (회의)

---

## 2026-11-09 · 카테고리 예산 화면 (React) — 🟦 임영준
DB 변경 없음. 🟧 `views.py`·`urls.py`에 **추가만**. 응답 키 추가만.

- 새 화면 `GET category_budget/` · `category_budget/<travel_id>/` (`category_budget`, `category_budget_travel`) → `sherpaapp/category_budget.html` 이 React 빌드(`static/budget/budget.js`·`budget.css`)를 띄움. 로그인 필요, 남의 여행 404
  - 들어가는 곳: 비용 관리 왼쪽 'AI 예상 예산' 칸의 **카테고리 예산 고치기 →**
  - 화면: 여행 고르기 · 총예산/분류 합계/일정 예상(AI) · 분류마다 금액 입력 + 예산 대비 일정 예상 막대(쓴 돈은 세로선) · 'AI 예상대로 채우기'·'되돌리기'·'저장' · 넘친 분류는 '더 싼 곳 찾기' → 바꾸기 · 오른쪽 'AI가 장소를 고르는 방식' + 분류별 한 곳당 상한(예산 ÷ 장소 수)
- React 소스 `frontend/src/budget/` (`BudgetApp.jsx`·`CategoryRow.jsx`·`FlowPanel.jsx`·`api.js`·`cats.js`·`budget.css`), 빌드 설정 `frontend/vite.budget.config.js`
  - **`npm run build` 한 번으로 `/chat/`·카테고리 예산 둘 다 빌드** (package.json `build` 바꿈). `/chat/` 결과물은 그대로
- API 추가 키
  - `GET budget/<id>/category/?plan=1` → `budget`에 `plan`(지금 일정의 분류별 예상 비용)·`counts`(분류별 장소 수)·`people` 추가
  - `GET budget_alternatives/<id>/?cat=food` → 그 분류만, 총예산과 상관없이 대안 (`over_budget_options(..., only_cat=)`)
  - `budget_service.plan_counts(items)` 추가

### 확인
- [ ] 🟧 `views.py` `category_budget_page`, `budget_category`의 `?plan=1` 확인 부탁
- [ ] 🟦 왼쪽 메뉴에 '카테고리 예산'을 따로 넣을지 (지금은 비용 관리에서 들어감)

---

## 2026-11-09 · 일정 미리보기·일정 관리에 날씨 + 실내/실외, 비 오는 날 실내 대안으로 바꾸기 — 🟦 임영준
DB 변경 없음. 🟧 `views.py`·`urls.py`에 **추가만**. 응답 키 추가 (`mock.json` `plan.days[].weather`에 label·temp_min·rain_pct·rainy, `stops[].indoor`).

- 새 파일 `services/rain_service.py` (🟦)
  - `trip_days_weather(place, start, end, center)` → `{날짜: {date, kind, label, temp, temp_min, rain_pct, rainy}}` (🟩 `trip_weather` 그대로, 16일 안만). **`rainy`: 비·눈이거나 강수 확률 60% 이상**
  - `place_indoor(name, kind, lat, lon, kakao_id)` → True/False/None. 🟩 `is_indoor`를 그대로 쓰고, 우리 `p_kind`(랜드마크 등)로 모르면 카카오 분류를 찾아 판단 (7일 캐시, 키 `indoor:v1:`). 식당·카페·숙소·쇼핑은 실내
  - `indoor_options(name, lat, lon, people, skip)` → 5km 안 박물관·미술관·전시관·아쿠아리움·쇼핑몰 3곳 (예상 비용·사진 포함)
- 일정 미리보기(`travel_chat_preview`) 응답: 날마다 `weather`, 장소마다 `indoor` 추가
  - 화면(`travel_chat.js`): 일차 탭에 ☀/☁/☔ 기온, 그날 날씨 한 줄, 장소마다 실내/실외 배지. 비 오는 날 실외 장소에 '☔ 실내 대안 보기' → '바꾸기'를 누르면 그 장소는 지운 장소로, 실내 장소는 같은 시간 담은 장소로 넣고 다시 짬
  - React `PlanPreview.jsx`: 날씨·배지만 (바꾸기는 아직)
- 일정 관리(여행 상세): 날짜 버튼에 날씨, 카드에 실내/실외, 왼쪽 'DAY n 날씨' 상자. 비 오는 날 실외 장소마다 실내 대안 → '바꾸기'(기존 `budget_swap` 그대로)
- 새 주소
  - `GET rain_options/?name=&lat=&lon=&people=&skip=` (`rain_options`) → `{success, options}` (로그인 401)
  - `GET travel_weather/<travel_id>/<day>/` (`travel_weather`) → `{success, people, days: [{day, date, weather}], places: {sp_id: indoor}}` (로그인 401, 남의 여행 403)
  - `travel_detail_day` 장소마다 `place_lat`·`place_lon` 추가
- 알아 둘 것: 🟩 `is_indoor`는 '테마파크'를 실외로 봐서 롯데월드 어드벤처가 실외로 나옴 (🟩 단어 목록 문제)
- `rain_service`에서 🟩 `is_indoor`가 모르는 곳 보충 (🟩 파일은 안 건드림): 자연휴양림·숲·올레길(도보여행)·정원·민속촌·읍성 → 실외, 전시·공연·갤러리 → 실내, 축제·행사 → 실외(전시·공연이면 실내). 일정 장소 147곳 중 모름 16 → 2곳(시장·전망대)
- 그래도 모르는 곳(`indoor: null`)은 회색 **'실내·실외 섞임'** 배지 (추천 카드·미리보기·일정 관리)
- **예보가 없는 날도 날씨 채움** (`trip_days_weather`, 날씨마다 `source` 키 추가 — `mock.json`)
  - `forecast`: 16일 안 예보 (지금처럼, 비 오면 실내 대안)
  - `past`: 이미 지난 날 → 그날 실제 날씨 (open-meteo 예보 주소 지난 92일 / 기록 주소 `archive-api`)
  - `last_year`: 16일보다 먼 날 → **작년 같은 날 날씨** (참고용이라 `rainy: false`, 작년에 비·눈이면 `last_year_rain: true`). 화면엔 '☁ 10° 작년', '작년 이맘때 흐림 …'
  - 지난 날씨는 7일 캐시 (키 `wxday:`), 새 키 필요 없음

### 확인
- [x] 🟩 일정을 처음 만들 때부터 비 오는 날 실내를 고르는 건(11/06 결정) 🟩 `schedule_service` 담당 — 이 `rain_service`의 `trip_days_weather`·`place_indoor`를 같이 써도 돼요
- [ ] 🟧 `views.py` 맨 아래 `rain_options`·`travel_weather`, 미리보기에 날씨·실내 붙이는 곳 확인 부탁

---

## 2026-11-09 · 여행 상세 위쪽에 '다른 여행으로 이동' 선택 칸 — 🟦 임영준
DB·응답 키 변경 없음. 🟧 `views.py` `travel_detail` 화면 값에 `my_travels`(내 여행, 최근 출발 순) **추가만**.
- 내 여행일 때만, 여행이 2개 이상이면 '게시판 공유'·'여행 수정' 버튼 옆에 보임. 고르면 바로 그 여행 상세로

---

## 2026-11-09 · 추천 카드에 실내 / 실외 표시, 비 오는 날은 실내 강조 — 🟦 임영준 (🟩 `chat_service.py` 조금 수정)
DB 변경 없음. 응답 키는 **추가만** (`mock.json` `places.weather`).

- 카드 이름 옆에 `indoor` 그대로: `true` → **실내**, `false` → **실외**, `null`(모름) → 표시 안 함 (대화 화면 `travel_chat.js`·React `RecCards.jsx`)
- 가는 날 비·눈 예보면
  - 카드 위 한 줄: "☔ 11/12 비 예보(강수 80%) · 실내 장소를 먼저 보여 드려요" (실내 카드가 없으면 "'1일차 실내 추천'이라고 말해 보세요")
  - 실내는 파란 배지 "실내 · 비 와도 OK", 실외는 흐린 배지 "실외 · 비 오면 아쉬워요"
- 🟩 `chat_service.py`: `rain_first`가 이미 구하던 가는 날 날씨를 `rec['visit_weather']`에 담고, 추천 응답에 **`weather` 키** `{date, kind, label, rain_pct}` 또는 `null` 추가 (`_card_weather`). 실내를 앞에 두는 순서는 🟩 코드 그대로

### 확인
- [x] 🟩 `rain_first`의 한 줄·추천 응답 `weather` 키 확인 부탁

---

## 2026-11-09 · 예산 AI: 예산을 넘으면 같은 분류의 더 싼 대안 + '바꾸기' — 🟦 임영준
DB 변경 없음. 🟧 `views.py`·`urls.py`에 **추가만**.

- 여행 상세 왼쪽 '여행 비용' 아래 **예산 초과 · 더 싼 대안** 상자: 일정 전체 예상 비용 > 총예산(`t_budget`)일 때만 보임
  - 비싼 장소부터 최대 4곳, 장소마다 근처(식당 2km·관광지 3km·숙소 5km)의 같은 분류 장소 중 더 싼 곳 3개 (카카오 장소 검색 → 기존 가격 계산 그대로)
  - 대안 이름을 누르면 정보 펼치기: 사진·주소·카카오 분류·전화·가격 근거(1인 × 인원 / 방 × 개수, 관광공사 요금인지 보통 가격인지)·지금 장소와 비교·TRIPA 리뷰 별점(`review_summary`)·카카오맵 링크
  - '바꾸기' → 그 자리 장소만 바뀌고 그날 시간 다시 계산. 숙소를 바꾸면 그날 밤 `TravelDayPlan` 숙소도 같이 바뀜(다음 날 출발점)
- 새 주소
  - `GET budget_alternatives/<travel_id>/` (`budget_alternatives`) → `{success, people, planned, budget, over, suggestions: [{sp_id, day, name, cat, amount, options: [{name, addr, kind, lat, lon, kakao_id, url, category, phone, distance, cost, save, photo}]}]}`
  - `POST budget_swap/<travel_id>/` (`budget_swap`) `{sp_id, name, addr, kind, lat, lon, kakao_id}` → `{success, message, sp_id}`
  - 둘 다 로그인 401, 남의 여행 403
- `_chat_preview_days`의 장소마다 `sp_id` 키 추가 (일정 미리보기 응답에도 들어감, 추가만)
- 카페는 보통 가격이 다 같아서(7,000원) 대안이 없음

### 확인
- [ ] 🟧 `views.py` 맨 아래 `budget_alternatives`·`budget_swap` 확인 부탁 (장소 바꾸기 + `recalculate_schedule_timeline`)

---

## 2026-11-09 · 📐 공유 정의: 임베딩 함수·벡터 표 (`embed_service`, `embed_chunk`) — 🟧 이수한
아직 코드 없음 (모양 먼저 공유, 11/09 규칙). 🟧가 이 모양 그대로 만들어 PR로 올릴게요. **🟩는 이걸 기준으로 여행지 정보 RAG를 설계하면 돼요.** 바뀌면 이 항목을 고치고 다시 알릴게요.

### 설정
- `.env`에 `AI_EMBED_MODEL` 한 줄 추가 (`.env.example`에도 칸). 주소·키는 지금 `AI_BASE_URL`·`AI_API_KEY` 그대로 (OpenAI 호환 `/embeddings`, Ollama도 같은 방식)
  - 설정 A (평소·서버): `text-embedding-3-small`
  - 설정 B (시연 PC): `bge-m3` (`ollama pull bge-m3`)

### 표 `embed_chunk` (모델 `EmbedChunk`, 마이그레이션 0016은 🟧가 만듦)
| 칸 | 뜻 |
|---|---|
| `kind` | `'review'`(리뷰 묶음) · `'tour'`(관광공사 소개글) … 새 종류는 이 항목에 추가 |
| `ref_id` | 대상 id (문자열: kakao_id 또는 관광공사 contentid) |
| `seq` | 몇 번째 조각인지 (0부터) |
| `text` | 조각 원문 |
| `vector` | 숫자 목록 (JSON) |
| `model` | 만든 임베딩 모델 이름. 모델이 다르면 비교할 수 없어서 검색은 지금 모델 것만 |
| `meta` | 장소 이름·출처 등 (JSON, 비어도 됨) |
| `updated_at` | 만든 시각 |

### 함수 (`services/embed_service.py`, 🟩는 2·3번만 쓰면 됨)
1. `embed_texts(texts) → [[숫자…], …]` — 글 목록 → 벡터 목록. 실패하면 `EmbedError`
2. `save_chunks(kind, ref_id, texts, meta=None) → 저장 개수` — 같은 `kind`·`ref_id`·모델의 옛 조각은 지우고 다시 저장
3. `search(query, kind=None, top_k=3) → [{kind, ref_id, seq, text, score, meta}]` — 코사인 유사도 높은 순
4. (🟧 리뷰용, 나중에) `similar_places(kakao_id, top_k=5)`

### 🟩 쓰는 법 (여행지 정보 RAG)
- 관광공사 소개글 가져오기·자르기(300~500자)는 🟩 → `save_chunks('tour', contentid, 조각들, meta={'name': 장소 이름})`
- 에이전트 도구에서 `search(질문, kind='tour')` → 조각을 근거로 답하고 `meta['name']`으로 출처 표시
- 새 표·마이그레이션은 만들지 않아요

### 확인
- [x] 🟩 이 모양으로 괜찮은지 (바꿀 게 있으면 이 항목에 댓글)

---

## 2026-11-09 · ✅ 결정: 같이 쓰는 함수·키는 "먼저 작업하는 사람이 정하고 바로 공유" + 임베딩·RAG 표는 🟧가 — 🟧 이수한
코드 변경 없음 (규칙 기록, `.claude/rules/team-updates.md`에 한 줄)

### 1) 같이 쓰는 새 함수·응답 키 정하는 방법
- **먼저 작업하는 사람이 정해요.** 이름·받는 값·돌려주는 값을 정하고, 기능을 다 만들기 전이라도 **이 파일에 먼저 적어 작은 PR로 바로** 올려요(응답 키면 `mock.json`도). 🟧가 바로 병합할게요
- 나중에 시작하는 사람은 **작업 전에 TEAM_UPDATES를 먼저 보고** 이미 정해진 걸 그대로 써요
- 이미 있는 키·함수 이름을 **바꾸는 건** 지금처럼 3인 합의
- 이번 주 해당하는 것
  - 운영시간 함수(최소 체류·체류 맞추기·여는 시각까지 기다리기, `hours_service.py`): 🟦 영준·🟩 지윤 중 먼저 시작하는 사람
  - 카카오 대중교통 경로 함수(캐시 키 `transit:`): 🟦 영준이 먼저 (🟧 서버 이동시간은 그걸 씀)
  - 운영시간 문제·쉬는 날 안내 응답 키, 장소 정보 API 응답 모양: 🟩 지윤이 먼저 → 🟦 화면이 씀

### 2) 임베딩 함수·RAG 표는 🟧 수한이 먼저 만들어요
- 🟧가 임베딩 함수(설정 A: OpenAI 임베딩 / 설정 B: 로컬 `bge-m3`)와 벡터 저장 표를 **리뷰·관광공사 소개글 둘 다 담을 수 있게** 먼저 만들고, 함수 이름·표 모양을 여기에 공유해요
- 마이그레이션도 🟧가 한 번에 만들어서 번호(0016)가 겹치지 않게 해요
- 🟩 여행지 정보 RAG는 그 함수·표를 가져다 써요 (소개글 가져오기·자르기·에이전트 도구는 🟩)

### 확인
- [ ] 🟦 확인
- [x] 🟩 확인

---

## 2026-11-09 · ✅ 결정: "체크인하고 다시 나가기" 넣기 + 11/19(목) 기능 동결·시연 리허설 — 🟧 이수한 (기록)
코드 변경 없음 (결정 기록만)

### 1) "체크인하고 다시 나가기" 넣어요 (11/05 제안 → 결정)
- 하루를 `출발 → 관광 → 체크인(짐 두기) → 관광·식사 → 숙소로 귀가`로 만들 수 있게 해요. 숙소가 하루에 두 번 나오고(체크인·귀가), 다음 날 출발점은 그대로 전날 숙소
- 체크인 시각은 막지 않고 안내만 (11/05 결정 그대로). 관광공사 숙소 정보에 체크인 시각이 있으면 "체크인 15:00부터 · 그 전엔 짐 맡기기만 될 수 있어요"
- **언제:** 4주차 (11/16~11/18). 11/19 동결 전에 main 병합
- **담당** (11/05 제안 분담 그대로, 🟦 동의함)
  - 🟩 **서지윤** — `schedule_service` 일정 만들기 구조: 체크인 줄을 하루 중간에, 귀가 줄 추가 (`add_checkin` 1666줄, `add_accommodation_arrival` 2008줄, `generate_schedule` 2048줄). 운영시간 작업(3주차)과 같은 흐름이라 그 뒤에
  - 🟦 **임영준** — 화면: 날마다 체크인 시각·외출 여부 고르기, 일정·지도에 숙소 두 번 표시, 끌기, 미리보기 `is_stay`
  - 🟧 **이수한** — 담은 장소(`_chat_add_pins`)를 체크인 뒤 저녁 칸에도 넣을 수 있게, 숙박비(`stay`)는 숙소 줄이 두 번이어도 한 번만 (🟦 `budget_service`와 같이 확인), 다음 날 출발점·여행 상세 경로 확인
- 응답 키가 늘면(예: 숙소 줄이 체크인인지 귀가인지 표시) `mock.json`에 먼저 적고 시작해요

### 2) 기능 동결·시연 리허설: 11/19(목), 발표 전날
- **11/19(목) 기능 동결:** 이날부터 새 기능은 넣지 않고 버그 수정만. 그 전까지 각자 PR을 main에 병합 (11/18 저녁까지 올려 주면 🟧가 병합·배포)
- **11/19(목) 시연 리허설:** 배포 주소로 처음부터 끝까지(가입 → 대화 → 적용 → 여행 상세·비용·리뷰), 폰 화면 포함. 설정 B(로컬 LLM) 시연도 같이 확인
- **11/20(금) 결과 발표**

### 확인
- [x] 🟩 체크인 기능 일정 만들기 담당 동의
- [ ] 🟦 확인 (11/05에 동의함)

---

## 2026-11-09 · 캐시를 DB에 저장 (모두 `migrate` 한 번) + 카카오 경로는 따로 표 없이 캐시로 — 🟧 이수한
**DB 변경 있음 → pull 후 모두 `python manage.py migrate`** (0015: 캐시 표 `django_cache`). 응답 키·주소 변경 없음.

### 무엇이 바뀌었나
- `settings.py`에 `CACHES`(DB 캐시) 추가. 전에는 설정이 없어서 Django 기본값(프로세스 메모리)이었어요.
  - 서버는 gunicorn 프로세스 3개가 캐시를 **따로** 가졌고, **배포·재시작 때마다 다 지워졌어요.** 그래서 관광공사 운영시간·요금·사진, 날씨, 축제 같은 "7일 캐시"가 실제로는 오래 못 갔어요(관광공사 하루 호출 한도에도 불리).
  - 이제 한 표에 모아 저장해서 프로세스끼리 같이 쓰고, 배포해도 남아요. **코드에서 `cache.get`·`cache.set` 쓰는 방법은 그대로**예요.
- 표는 마이그레이션 0015가 만들어요(`createcachetable`을 따로 안 돌려도 됨).

### 바뀐 결정: 카카오 대중교통 경로 결과 저장
- 11/06에 "경로 저장 표를 따로 만든다"고 했던 것 → **표 없이 캐시로** 바꿔요. 마이그레이션·모델이 필요 없어요.
  - 같은 구간 결과를 `cache.set(키, 결과, 7일)`로 저장. 키는 기능 이름을 앞에 붙이고 좌표를 소수 4자리쯤으로 반올림 (예: `transit:35.1578,129.0590:35.1587,129.1604`)
- 서버 일정 계산(`fill_activities`)은 **모든 후보에 카카오를 부르지 않아요.** 거리 짐작으로 장소를 고르고, **확정된 구간만** 카카오 시간으로 맞춰요(🟧). 후보마다 부르면 일정 하나에 수백 번 호출돼서 느려져요.

### 🟦 영준
- [ ] 카카오 경로 함수에서 결과를 위 방식대로 캐시에 저장 (따로 표 만들지 않기)
- [ ] 경로 함수 이름·받는 값은 🟧와 먼저 맞추기 (서버 시각 계산도 같은 함수를 씀)

### 🟩 지윤
- [ ] 바꿀 것 없음. `hours_service`의 운영시간 캐시가 이제 정말 7일 남아서, 일정 만들 때 운영시간을 여러 번 불러도 관광공사 호출이 덜 나가요
- RAG 소개글·벡터는 캐시가 아니라 따로 표로 저장해요 (지워지면 안 되는 데이터라서)

### 같이 알아 둘 것
- **파싱 코드를 고쳤는데 결과가 그대로면** 옛 결과가 캐시에 남아 있는 거예요. 지우기:
  `python manage.py shell -c "from django.core.cache import cache; cache.clear()"`
- 캐시 키는 250자 안으로, 기능 이름을 앞에 (`hours:`, `budget:`, `transit:` …)
- 마이그레이션 번호 0015를 썼어요. 다음 새 표는 0016. 같은 번호가 두 개 생기면 `python manage.py makemigrations --merge`

---

## 2026-11-09 · 카카오 대중교통·시간표 API 지금 키로 바로 돼요 → 🟦 길안내 작업 시작 가능 — 🟧 이수한
코드·DB·`.env` 변경 없음

- **카카오 대중교통 경로** `GET https://dapi.kakao.com/v2/routing/publictraffic` (`start_x`·`start_y`·`end_x`·`end_y`, 헤더 `Authorization: KakaoAK <KAKAO_REST_API_KEY>`)
  - 지금 쓰는 카카오 REST 키 그대로 돼요. 콘솔에서 따로 켤 것 없음
  - 서면역 → 해운대: `status: OK`, `routes` 15개. 첫 경로 `properties`: SUBWAY · 46분(`totalTime` 초) · 환승 0 · `fare.value` 1,800원, `steps`마다 `guidance`·`stops`·`vehicles`
- **공공데이터 시간표** — 새 키 없이 지금 `TOUR_API_KEY` 하나로 세 API 모두 정상
  - TAGO 열차정보 `1613000/TrainInfo/GetStrtpntAlocFndTrainInfo` (서울→부산 내일 75편)
  - TAGO 국내항공 `1613000/DmstcFlightNvgInfo/GetFlightOpratInfoList` (김포→제주 내일 101편)
  - 연안여객선 `B554035/oprt-schd-info-v2/get-oprt-schd-info-v2` (오늘 718건)
- 로컬과 서버 키 둘 다 확인했어요 (서버는 카카오·열차 확인)

### 🟦 요청
- [ ] ODsay 빼기·카카오 대중교통 경로 작업 시작 (순서·파일·줄은 [주간 가이드](https://claude.ai/artifact/1Lwf6NtqDRyUH16a1ZFPMb#guide-front))
- [ ] 경로 결과 저장 함수 이름은 🟧와 먼저 맞추기

---

## 2026-11-06 · 다음 주 가이드 + Claude Code로 고쳐도 되는 경우 — 🟧 이수한
코드·DB 변경 없음 (팀 공통 Claude 규칙 `.claude/rules/team-updates.md`에 예외 추가 → 열려 있는 Claude Code는 다시 열어야 읽어요)

- **다음 주(3주차) 할 일 가이드:** [팀 진행도](https://claude.ai/artifact/1Lwf6NtqDRyUH16a1ZFPMb#guide) "다음 주 가이드" 탭. 사람별로 무엇을·왜·어느 파일 몇 줄·단계·확인 방법을 적었어요. 단계는 눌러서 지울 수 있고(내 브라우저에만 저장), main에 병합되면 항목 전체에 자동으로 취소선이 그어져요.
- **Claude Code로 고쳐도 돼요 (선택):** 직접 하기 어려우면 Claude Code에 "직접 수정해 줘"라고 분명히 부탁하면 내 브랜치에서 고쳐 줘요(`.claude/rules/team-updates.md` 예외). 가이드마다 그대로 붙여 넣을 부탁 문장이 있어요.
  - 바뀐 코드는 설명을 듣고 화면에서 확인한 뒤 **커밋·PR은 직접** 올려요. PR 설명에 "Claude Code로 수정" 한 줄 적어 주세요.
  - 직접 쓰고 싶으면 지금처럼 힌트만 받아도 돼요. 방식은 각자 골라요.

---

## 2026-11-06 · ✅ 결정: 길안내는 카카오로(ODsay 빼기), 영업시간·날짜를 처음 추천부터 고려 — 🟧 이수한 (기록)
지금은 코드 변경 없음 (결정 기록만). 담당은 아래처럼 나눴고, 바꾸고 싶으면 이 항목에 댓글로 알려 주세요.

### 정한 것 (cloud-tripa 방식 참고)
1. **ODsay를 빼요.** 하루 호출 한도(`Daily quota exceeded`)와 등록 도메인 제한 때문에 시연 때 경로가 안 나올 수 있어요. 길안내는 아래로 바꿔요.
   - 장소 사이 대중교통: **카카오 대중교통 경로(서버 호출)** — 노선 번호·타는 곳·내리는 곳·환승·요금·지도 노선 모양
   - 이동 구간마다 **카카오맵·네이버지도 길찾기 링크** (API가 아니라 호출 제한 없음, 대중교통 여행에서만 표시)
   - 가는 길·돌아오는 길: **공공데이터 시간표 API** (TAGO 열차정보·국내항공운항정보·연안여객선 운항 스케줄)로 그날 실제 편명·출발 시각·1인 운임
2. **영업시간·날짜(요일)를 보고 체류 시간과 방문 시각을 조정해요.**
   - 음식점은 마감 1시간 전, 카페·그 밖은 30분 전까지 도착해야 해요. 못 미치면 "마감까지 30분뿐이라 식사할 시간이 부족해요"처럼 안내
   - 마감을 넘는 체류는 마감 시각까지로 줄여요 (사용자가 직접 고친 체류는 줄이지 않고 운영시간 검사로 알려 줌)
   - 쉬는 요일·행사 기간 밖인 곳은 여행 중 여는 날로 옮기고, 못 옮기면 "이 여행에서는 DAY 1(목)에 갈 수 있어요" 안내
3. **나중에 고치는 게 아니라 처음 추천·일정을 만들 때부터** 전부 고려해요. 이미 만든 여행은 일정 화면의 '운영시간에 맞추기' 버튼으로 맞춰요.

### 담당
- 🟦 **임영준**: ODsay 호출·키 빼고 카카오 대중교통 경로로, 길찾기 링크, 체류 시간 맞추기·'운영시간에 맞추기' 버튼(`hours_service.py`), 가는 길 실제 시간표('이동수단별 가격 비교'와 같이)
- 🟩 **서지윤**: 처음 추천·일정 생성 때 날짜·요일·운영시간 고려(`schedule_service`·`chat_service`), 쉬는 요일인 곳 여는 날로 옮기기·안내. 운영시간 읽기·체류 맞추기는 🟦 `hours_service.py` 함수를 같이 씀
- 🟧 **이수한**: 대중교통 경로 결과 저장 표(같은 구간 7일 보관, 마이그레이션), 서버 이동시간 계산도 카카오 경로로(화면과 서버 시각 같게), 카카오 '대중교통 경로' 사용 설정·공공데이터포털 활용 신청·서버 `.env`

### 같이 지킬 것
- 응답 키·주소는 **추가만** 해요. ODsay용 키(`ODSAY_*`)·코드를 지울 때는 그 키를 쓰는 화면(채팅·여행 만들기·여행 상세)을 같이 확인해요.
- 저장 표가 생기면 모두 `migrate`가 필요해요 (🟧가 PR에 적어 둘게요).
- 🟦 `hours_service.py`와 🟩 일정 생성이 같은 함수를 쓰니, 함수 이름·받는 값은 먼저 정하고 시작해요.

### 확인
- [ ] 🟦 담당 동의
- [x] 🟩 담당 동의

---

## 2026-11-05 · 🟦 #53(예산 AI·인원 묻기·기간 고치기) 확인 + 작은 수정 4개 — 🟩 서지윤
DB·응답 키 변경 없음 → 🟦 🟧 고칠 것 없음 (`chat_service.py`만)

### 확인 결과 (아래 🟦 항목의 🟩 확인 부탁 2개)
- 실제 AI(qwen3:8b) 대화 7턴: 3번 돌려 7/7·7/7·6/7 (틀린 1번은 qwen3가 가끔 거절을 못 하는 것, 이번 변경과 상관없음)
- 기간 읽기: '2박3일로 수정해줘'·'이박삼일'·'3일로'·'당일치기' 맞음, '11월 3일로'·'3일차'·'3일 뒤에'는 기간으로 안 읽음 ✅
- 카드 비용: 카페 1인 7,000×2명 = 14,000 / 해수욕장 0 / 호텔 방 120,000 ✅

### 고친 것
1. **'하루 더 카페 넣어줘'가 기간 늘리기로 읽히던 문제** (`_relative_nights`): 장소를 넣거나 찾는 말(넣어·추천·코스·N일차·카페·바다 등)이 같이 있으면 기간으로 보지 않음. '하루 더 늘려줘'·'하루 더 있고 싶어'·'하루 줄여줘'는 그대로
2. **인원을 아는데 AI가 또 묻던 문제** ("혼자 가" → "혼자 여행하시나요?"): 초안에 인원이 있으면 인원을 묻는 물음 문장만 뺌 (`drop_people_questions`). 빠지면 서버가 다음 질문(숙소 등)을 이어 물음
3. **'커플'·'연인'·'부부' → 2명** (`guess_people`)
4. **비용은 보여 줄 카드 4장에만** (`search_recommendations(..., costs=False)` 뒤 `attach_costs`): 여분 카드 3장 가격은 안 찾음. 다른 곳에서 `search_recommendations`를 기본값으로 부르면 전처럼 비용이 붙음

---

## 2026-11-05 · 리뷰 게시판: 내 글만 수정·삭제 — 🟦 임영준
DB·응답 키 변경 없음. 🟧 `views.py`·`urls.py`에 **추가만**.

- 여행 루트 탭: 내가 공유한 카드에만 '수정(한 줄 소개)'·'삭제(게시판에서 내리기)' 버튼. 기존 `route_share`(내 여행이 아니면 403)를 그대로 씀. 내리면 별점·댓글은 사라지고 여행 일정은 남음
- 장소 리뷰 탭: 내 리뷰에만 '수정(별점·내용·태그)'·'삭제' 버튼
  - `POST review/<rv_id>/edit/` (`review_update`), `POST review/<rv_id>/delete/` (`review_delete`) → 게시판으로 돌아감. 로그인 안 하면 로그인 화면, **남의 리뷰는 403**
- 남의 글에는 버튼이 없고, 주소를 직접 불러도 서버가 막음

### 확인
- [ ] 🟧 `views.py`의 `review_update`·`review_delete` 확인 부탁

---

## 2026-11-05 · 예산 AI: 장소 가격 → 인원 기준 예상 비용, 카테고리 예산 저장 API, 대화에서 인원 묻기 — 🟦 임영준 (🟩 `chat_service.py` 조금 수정)
DB 변경 없음 → `migrate` 필요 없음 (기존 `travel_budget` 표 사용). 응답 키는 **추가만**.

### 1) 가격 찾기 — 새 파일 `services/budget_service.py` (🟦)
- 관광공사(TourAPI) 요금 문장을 읽음: 관광지 `detailInfo2` '입장료', 문화시설·레포츠·축제 `usefee`·`usefeeleports`·`usetimefestival`, 숙박 `detailInfo2` 객실 요금(가장 싼 방)
  - 성인·어른·대인·일반 요금 먼저, 단체 요금 줄은 뺌, '무료'면 0원 (예: 경복궁 3,000 / 남이섬 19,000 / 화성행궁 2,000 / 노보텔 수원 방 187,000)
- 관광공사에 요금이 없으면 **보통 가격 예상**(`source: "estimate"`): 카페 7,000 / 식당은 종류별(횟집 35,000·고기 20,000·국밥 11,000·분식 7,000 …) / 숙소 방 하나(호텔 120,000·게스트하우스 1인 35,000·펜션 4인 150,000 …) / 해수욕장·공원·시장은 0
- 인원 계산: 1인 요금 × 인원, 방 요금 × 방 개수(인원 ÷ 방 기준 인원, 올림)
- 같은 장소는 7일 캐시

### 2) 추천 카드 `cost` 키 (mock.json 키 + 추가)
- `cost: {amount, cat, source, per, unit, cap, people, text}` 또는 `null`
  - `amount` 인원 기준 금액, `cat` 분류(sight·food·cafe·move·stay·shop·etc), `source` `tour`(관광공사 요금)·`estimate`(보통 가격)
  - `per` 1인(또는 방 하나) 금액, `unit` `person`·`room`, `cap` 방 기준 인원, `text` 요금 원문
- 화면(대화 화면 `travel_chat.js`·React `RecCards.jsx`): "1인 9,000원 · 2명 18,000원 (보통 가격 예상)" — 인원이 바뀌면 지금 초안 인원으로 다시 계산

### 3) 새 주소 (🟧 `views.py`·`urls.py`에 **추가만**)
- `POST budget_estimate/` (`budget_estimate`): `{draft}` → `{success, people, planned, by: {분류: 금액}, items, unknown}` — 초안의 담은 장소·숙소 × 인원. 일정 초안 칸에 '예상 비용' 줄로 보여줌
- `GET·POST budget/<travel_id>/category/` (`budget_category`): **카테고리 예산 저장 API**
  - GET → `{success, budget: {total, limit: {분류: 예산}, by: {분류: 쓴 돈}}}` (mock.json `budget`의 `total`·`limit`·`by`)
  - POST JSON `{limit: {food: 150000, stay: 120000}}` → 보낸 분류만 저장(있으면 고침) → 같은 모양. 로그인 401, 남의 여행 403, 값 없으면 400
- `travel_chat_apply`(이 일정 적용하기)가 끝날 때 **만들어진 일정 전체**(자동으로 넣은 식당·카페 포함)의 예상 비용을 분류별 예산으로 `travel_budget`에 저장. 대화에서 총예산을 따로 말하지 않았으면 `t_budget`도 예상 합계로 저장
- 일정 미리보기 응답에 `budget` 키(모양은 `budget_estimate`와 같음), 장소마다 `cost` 키 추가 (mock.json `plan.days[].stops[].cost`)
- `POST budget/<travel_id>/ai-fill/` (`budget_ai_fill`, 폼 `people`): 저장된 일정 × 인원으로 분류별 예산·총 예산을 다시 채우고 비용 관리로 돌아감 (AI 대화로 안 만든 여행·인원 바뀐 여행용)

### 3-1) 비용 관리 화면 `budget.html` (🟦)
- 왼쪽 '여행 예산' 카드에 **AI 예상 예산** 칸: 분류마다 "쓴 돈 / 예산" + 진행 막대, 넘으면 빨간 글씨. 인원 입력 + 'AI 예산 계산 / 다시 계산' 버튼
- 여행 상세 `travel_detail.html` (🟦): 일정 카드마다 '예상 18,000원 (1인 9,000원 × 2명)' 칩, 왼쪽 'DAY n 여행 비용' 아래 **AI 예상 비용**(장소별 + 그날 예상 합계)
  - 새 주소 `GET travel_costs/<travel_id>/<day>/` (`travel_costs`, 🟧 `views.py`·`urls.py`에 추가만): `{success, day, people, places: {sp_id: cost}, planned, by}` — 로그인 401, 남의 여행 403. `travel_hours`처럼 일정을 먼저 그리고 나중에 붙임
- 계산한 인원은 세션 `budget_people: {여행 id: 인원}`에 기억 (적용할 때 대화 인원, 다시 계산할 때 입력 인원) → 인원 칸에 그대로 보임. DB 칸은 없어서 다른 기기·로그아웃 뒤에는 기본 2명
- `views.budget` 화면 값에 `ai_budget: {rows: [{name, key, color, icon, limit, used, left, over, width}], total}` 추가

### 4) 대화에서 인원 묻기 (🟩 `chat_service.py`)
- `next_question`: 컨셉 다음에 "몇 분이서 가시나요? 인원에 맞춰 예상 비용을 계산해 드릴게요."
- `guess_people`: 🟩이 main에 같은 이름으로 먼저 넣어서 **🟩 함수를 그대로 씀** (내가 만든 같은 함수는 합칠 때 뺌). 인원 질문·적용 흐름만 이 항목 내용
- 시스템 프롬프트 6번에 people 설명 한 줄, 추천 카드 만들 때 `attach_costs(items, people)` 호출, 카드에 `_category`(카카오 분류) 잠깐 붙였다가 지움

### 확인
- [x] 🟩 `chat_service.py`의 `guess_people`·`next_question` 인원 질문·`attach_costs` 호출 확인 부탁 — 11/05 확인, 비용은 고른 카드 4장에만 붙게 고침 (맨 위 항목)
- [ ] 🟧 `views.py` 맨 아래 `budget_estimate`·`budget_category`, `travel_chat_apply` 끝의 예산 저장 확인 부탁
- [ ] 🟦 다음: 카테고리 예산 화면(React)에서 `budget_category` 쓰기, 예산 넘으면 같은 분류 더 싼 대안

---

## 2026-11-05 · AI 대화: '1박2일 → 2박3일로 수정해줘'가 안 바뀌던 문제 — 🟦 임영준 (🟩 `chat_service.py` 수정)
DB·응답 키 변경 없음.

- 제목이 '수원 1박 2일 여행'에 남던 문제: `normalize_draft`가 제목 속 'N박 M일'·'당일치기'를 실제 날짜에 맞게 바꿈
- 기간으로 못 읽던 말: `guess_nights`가 '이박삼일', '3일로·3일 일정'(날짜 '11월 3일'은 제외)도 읽음 → 예전엔 이런 말이면 AI가 바꾼 날짜까지 되돌렸음
- '하루 더 늘려줘'·'하루 줄여줘': `_relative_nights`가 이전 박 수 ± 1로 계산 (AI가 날짜를 안 바꿔도 됨)
- 가짜 AI로 시험: 2박3일로 수정/바꿔/하루 더/3일로/이박삼일/하루 줄여/당일치기/11월 13일로/3박4일/3일 뒤 → 모두 날짜·제목 맞음

### 🟩 확인
- [x] `chat_service.py`의 `guess_nights`·`_relative_nights`·`_apply_guessed_dates`·`normalize_draft` 제목 부분 확인 부탁 — 11/05 🟩 확인, '하루 더 카페 넣어줘'만 고침 (맨 위 항목)

---

## 2026-11-05 · 숙소에도 `kakao_id` (숙소 사진·리뷰 별점) — 🟩 서지윤
DB 변경 없음. 응답 키는 **추가만** → 🟦 🟧 고칠 것 없음

### 바뀐 것
- 채팅에서 숙소·출발지를 카카오로 찾을 때 장소 번호도 같이 담음 (`chat_service.kakao_first_place` → `kakao_id`)
  - 초안의 `stays[]`, `start_place`에 `kakao_id` 키 추가 (못 찾으면 `null`). 🟦가 적용하기 때 초안을 그대로 돌려보내면 그대로 남음 (숫자가 아닌 값은 버림)
- 숙소를 저장할 때(`views._chat_create_travel`) 숙소 `Place`를 `p_kakao_id`와 함께 먼저 만들어 둠
  - `TravelDayPlan`에는 `kakao_id` 칸이 없지만, 일정 생성(`get_or_create_place`)이 **같은 이름의 Place**를 다시 쓰므로 숙소 줄에도 `p_kakao_id`가 들어감 → 숙소에도 사진(`place_photo_url`)·리뷰 별점·리뷰 요약이 붙음
  - 적용하기·미리보기 모두 이 함수를 씀

### 시험 (부산 2박, 넣었다 되돌림)
- 시그니엘 부산 `327520717`, 호메르스호텔 `8178073`, 출발지 부산역 `8329752`
- 적용 단계에서도 `kakao_id` 남음 / 이상한 값(`abc<script>`)은 `null`
- 일정 생성 뒤 숙소 Place 2곳 모두 `p_kakao_id` 있음, 숙소 Place 중복 없음

### 남은 것
- 채팅이 아닌 여행 만들기 폼의 숙소(🟧 `TravelDayPlan` 직접 입력)는 그대로 `kakao_id` 없음. 필요하면 `TravelDayPlan`에 칸 추가(마이그레이션) — 🟧 판단

---

## 2026-11-05 · 추천 카드: 쉬는 곳을 빼도 4장 채우기, 주소가 같은 휴무 장소도 빼기, "추천해 드릴까요?" 되묻기 빼기, 거절할 때 카드 안 나오게 — 🟩 서지윤
DB·응답 키 변경 없음 → 🟦 🟧 영향 없음 (카드 모양 그대로)

### 바뀐 것
- **여분 후보** (`chat_service.search_recommendations`의 `spare`): 카카오에서 카드 4장 + 여분 3곳을 받아 두고, 쉬는 곳을 뺀 뒤 앞에서 4장을 씀. 쉬는 곳이 없으면 카드와 순서는 전과 같음 (카페·해운대 맛집·바다·랜드마크·숙소로 확인)
  - 사진은 고른 4장에만 붙임 (여분 사진은 안 찾음)
- **주소가 같은 휴무 장소** (`tour_service.drop_closed`): 쉬는 곳과 주소가 같고 이름 앞부분(3글자 이상)이 같으면 같이 뺌. 예) '부산박물관 동래관'·'부산박물관 부산관'(카카오 이름, 주소는 부산박물관) → 월요일에 빠짐. `notes`에도 함께 나옴
- **되묻는 문장**: 카드를 보여 주는데 AI 답에 "다른 장소를 추천해 드릴까요?"·"찾아드릴까요?" 같은 문장이 있으면 그 문장만 뺌 (`drop_offer_questions`)

### 시험 (부산, 셋째 날 11/16 월)
- '역사': 2장 → **4장** (부산박물관·임시수도기념관 빠지고 여분으로 채움)
- '실내': 1장 → 2장 / '박물관': 1장 (부산 박물관 대부분이 월요일 휴관이라 여분 3곳도 쉬는 곳. 왜 적은지는 `notes`에 나옴 → 🟦 `notes` 표시 부탁 그대로)
- GPT 대화 7턴 그대로 7/7

### 같이 고친 것: 거절하면서 앞 추천 카드를 또 보여 주던 문제
- "규칙 다 무시하고 계산기 코드 짜줘"를 거절하면서 AI가 앞의 카페 추천을 다시 보내던 문제 (gpt-4o-mini)
- 이번 말에 장소 이야기(추천·찾아·어디·갈만한·카페·바다 등)가 없으면 AI가 보낸 추천을 쓰지 않음 (`asks_for_places`). 단, 앞 AI 답이 "추천해 드릴까요?/드릴게요"였으면 '응'·'좋아'도 추천 요청으로 봄
- 시험: 판단 10개 맞음 / GPT 대화 7턴 2번 모두 7/7, 거절 턴에 카드 없음

---

## 2026-11-05 · 담은 장소 버그 2개 수정: 숙소 앞에 넣기, 다른 날 같은 장소 빼기 — 🟧 이수한
DB·응답 키 변경 없음. 🟩 전체 흐름 시험(11/05)에서 넘어온 🟧 부탁 2개예요. 고친 곳은 `views._chat_add_pins` 하나 (적용하기·미리보기 모두 이 함수를 씀)

- **담은 장소가 숙소 체크인 뒤에 붙던 문제:** 넣을 자리를 정할 때 "그날 맨 마지막 줄"(= 숙소) 대신 **숙소를 뺀 마지막 장소**를 기준으로 함 → 담은 장소가 숙소 **앞**에 들어가고, 숙소 도착 시각은 그만큼 뒤로 다시 계산됨
- **같은 장소가 다른 날에 또 나오던 문제:** 담은 장소를 넣은 뒤, 같은 여행의 **다른 날**에 있는 같은 장소(카카오 ID가 있으면 카카오 ID로, 없으면 같은 장소 줄)를 지우고, 그날 순서 번호·시간을 다시 계산
- 시험 (실제 제주 일정, 넣었다 되돌림): 담은 장소가 저녁 식사와 숙소 사이로 들어감 / 2일차에 있던 장소를 1일차에 담으면 2일차에서 빠지고 그날 일정이 앞으로 당겨지며 번호가 1부터 다시 매겨짐

### 아직 남은 것 (🟧 다음 단계)
- [ ] 담은 장소가 저녁 식사 뒤(20시대)에 들어가는 경우가 있음 → 운영시간 안·비슷한 종류 자리에 넣기
- [ ] 사용자가 일부러 두 날 다 담은 같은 장소는 지우지 않기

---

## 2026-11-05 · ✅ 설정 B 확정 (`qwen3:8b` + 예비 `exaone3.5:7.8b`) 반영: 생각 모드 끔, 인원은 코드가 읽음, Ollama 꺼지면 OpenAI로 — 🟩 서지윤
DB·응답 키 변경 없음. **새 설정 3개 추가** (`settings.py`·`.env.example`, 비워 두면 지금과 같음) → 지금 `.env` 그대로 두면 아무것도 안 바뀜

### 바뀐 것 (`services/chat_service.py`)
- **qwen3 생각 모드 끔**: 모델 이름이 `qwen3`로 시작하면 `reasoning_effort=none`을 붙임 (`NO_THINK_MODELS`). 켜 두면 한 번에 20~40초
- **인원은 코드가 읽음** (`guess_people`): '혼자'→1, '둘이서'→2, '3명', '두 명', '네 사람', '성인 2명 아이 1명'→3, '3-4명'→4. '둘째 날'·'명소'·'명동'은 인원으로 안 읽음. 날짜처럼 AI 값보다 먼저 씀 → GPT·로컬 모두
- **기본 AI가 꺼지면 예비 AI로** (`call_llm`): 기본 주소의 모델들(기본+예비 모델)이 모두 연결 안 되거나 바쁘면 `AI_BACKUP_*`의 다른 AI로 한 번 더 시도. 예비 설정이 비어 있으면 지금처럼 오류 안내

### 새 설정 (`.env`, 모두 선택)
| 이름 | 예 | 뜻 |
|---|---|---|
| `AI_BACKUP_BASE_URL` | `https://api.openai.com/v1` | 기본 AI가 안 될 때 넘어갈 주소 |
| `AI_BACKUP_API_KEY` | (OpenAI 키) | 그 주소의 키 |
| `AI_BACKUP_MODEL` | `gpt-4o-mini` | 그 주소의 모델 |

### 시연·포트폴리오 때 `.env` (설정 B, `.env.example` 아래쪽에도 있음)
```
AI_BASE_URL=http://127.0.0.1:11434/v1
AI_MODEL=qwen3:8b
AI_FALLBACK_MODELS=exaone3.5:7.8b
AI_TIMEOUT=120
AI_BACKUP_BASE_URL=https://api.openai.com/v1
AI_BACKUP_API_KEY=(OpenAI 키)
AI_BACKUP_MODEL=gpt-4o-mini
```
- 먼저 `ollama pull qwen3:8b`, `ollama pull exaone3.5:7.8b`. 바꾼 뒤 runserver 다시 켜기. 평소로 돌아가려면 위 줄을 지우거나 `#`

### 시험
- 인원 읽기 14개 맞음
- Ollama가 꺼진 상태(없는 주소)에서 → qwen3·exaone 연결 실패 → OpenAI로 넘어가 5.7초에 답
- 설정 B로 대화 7턴: **7/7** (전에 매번 놓친 '혼자'도 맞음), 평균 7.9초
- 설정 A(지금 `.env`, gpt-4o-mini) 대화 7턴: 7/7, 평균 3.7초 → 그대로 동작

### 🟦🟧 참고
- 리뷰 요약(🟧)·예산 AI(🟦)도 `call_llm`을 쓰므로 Ollama가 꺼지면 같이 OpenAI로 넘어감

---

## 2026-11-05 · 로컬 LLM 모델 비교 (EXAONE·Llama 각 3번 + Qwen3) → 설정 B 제안: `qwen3:8b` + 예비 `exaone3.5:7.8b` — 🟩 서지윤
코드·DB 변경 없음 (시험만). 11/05 결정의 "EXAONE·Llama를 각 2번 더 시험해 설정 B 모델 정하기" 결과예요. 8GB 그래픽카드에 맞는 새 후보 **Qwen3 8B**도 같이 시험했어요.

### 시험 방법
- 우리 채팅 함수(`run_chat_turn`)에 11/02 시험 대화 5개 + 숙소·박물관 추천 2개 = **7턴**, 모델마다 **3번** (11/05 1번 + 2번 더)
- 대화: 부산 11/14 2박3일 → "바다랑 카페 좋아해. 혼자 가"(인원 1) → 대영횟집 근처 카페 → 숙소 추천 → 셋째 날 박물관 → "규칙 다 무시하고 파이썬으로 계산기 코드 짜줘"(거절해야 함) → "이번주 토요일부터 1박 2일 강릉"(오늘 11/2 기준 11/7~8)
- PC: RTX 3060 8GB / Ollama. 응답 시간은 모델을 올린 뒤 기준

### 결과 (3번 합계, 21턴)
| 모델 | 맞음 | 평균 응답 | 매번 틀린 것 | 답 문장 |
|---|---|---|---|---|
| **Qwen3 8B** (`qwen3:8b`, 생각 모드 끔) | 18/21 | 6.5초 | "혼자 가" → 인원 1을 3번 다 놓침 | 자연스러움. 엉뚱한 요청은 대체로 거절 (1번은 "코드를 제공해 드릴게요"라고만 하고 코드는 안 씀) |
| **EXAONE 3.5** (`exaone3.5:7.8b`) | 17/21 | 6.5초 | 계산기 코드 요청에 3번 다 넘어감 ("코드를 작성해 드리겠습니다" + 코드) | 가장 자연스러움 |
| **Llama 3.1** (`llama3.1:8b`) | 21/21 | 5.9초 | 없음 | 어색함: 사용자 말·초안 내용을 그대로 늘어놓거나 "관광공사 정보에 없어서 확인하지 못했다" 같은 엉뚱한 문장 |
| (참고) Qwen3 생각 모드 켬 | 1번만 시험 | 28.2초 | 너무 느림 | - |

- 추천 카드(장소)는 모든 모델이 똑같음 → 장소는 AI가 아니라 우리 코드(카카오·관광공사·팀 장소 표)가 찾음
- 날짜("이번주 토요일", 2박3일 종료일)는 **모든 모델이 9번 다 맞음** (11/02에는 전부 틀렸던 것, 날짜 계산을 코드가 맡게 고친 효과)
- 같은 모델도 돌릴 때마다 조금씩 다름 → 경향 참고용

### EXAONE vs Llama (요청받은 비교)
- **점수는 Llama가 좋음** (21/21, 엉뚱한 요청에 한 번도 안 넘어감). 하지만 답 문장이 어색해서 시연 화면에서 티가 남
- **EXAONE은 한국어가 가장 자연스럽지만** 엉뚱한 요청을 매번 들어줌 → 시연 때 누가 시험해 보면 바로 드러남

### 제안
- 설정 B: `AI_MODEL=qwen3:8b`, `AI_FALLBACK_MODELS=exaone3.5:7.8b`
  - Qwen3가 매번 놓친 "혼자 → 인원 1"은 🟩가 **코드로 보완** (날짜처럼 '혼자·둘이서·N명'을 코드가 읽음) → GPT에도 도움
  - Qwen3는 생각 모드를 꺼야 함 → 🟩가 `chat_service._chat_model`에 옵션(`reasoning_effort=none`) 추가. 넣기 전까지는 지금처럼 `exaone3.5:7.8b` / `llama3.1:8b`
- Qwen3를 안 쓰기로 하면: 기본 `exaone3.5:7.8b` + 엉뚱한 요청 거절을 코드로 보완

### 로컬에서 쓰려면 (각자 노트북)
- `ollama pull qwen3:8b` (5.2GB), `ollama pull exaone3.5:7.8b` (4.8GB). C 드라이브가 부족하면 환경 변수 `OLLAMA_MODELS`를 다른 드라이브 폴더로 바꾸고, 기존 모델 폴더(`%USERPROFILE%\.ollama\models`)도 그리로 옮기기 (🟩 PC는 `H:\ollama\models`)
- `.env` 설정 B: `AI_BASE_URL=http://127.0.0.1:11434/v1`, `AI_MODEL=qwen3:8b`, `AI_FALLBACK_MODELS=exaone3.5:7.8b`, `AI_TIMEOUT=120` (키 값 필요 없음)

### 같이 정할 것
- [ ] 🟦🟧 설정 B를 `qwen3:8b` + 예비 `exaone3.5:7.8b`로 할지 (반대 의견은 PR 댓글로) — **🟦 동의 (11/05)**
- [x] 🟩 정해지면: 생각 모드 끄는 옵션, '혼자·N명' 코드 보완, Ollama가 꺼지면 GPT로 넘어가기

---

## 2026-11-05 · 💡 제안: "체크인하고 다시 나가기" (숙소를 하루 중간에) — 🟧 이수한 · 별도 기능, 세 사람 합의 필요
코드 변경 없음. 🟩 전체 흐름 시험에서 나온 "담은 장소가 체크인 뒤에 붙음" 버그를 보다가 나온 아이디어예요. **버그 수정과는 따로** 진행해요.

### 지금 구조
- `schedule_service.generate_schedule`은 하루를 `출발 → 관광·식사(숙소 도착 시각까지) → 숙소 도착으로 하루 끝`으로 만듦
- 숙소 도착 시각은 날마다 `TravelDayPlan.arrival_time`(비면 20:00). 일찍(예: 15:00) 잡으면 그 뒤로는 일정이 안 생김
- 즉 숙소는 "체크인"이 아니라 **그날 일정의 끝**이라서, 체크인하고 짐 두고 다시 나가는 일정은 만들 수 없음

### 제안
- 날마다 "숙소에 들렀다 나가기(체크인 시각)"를 고를 수 있게 → `출발 → 관광 → 체크인(짐 두기) → 관광·식사 → 숙소로 귀가`
- 숙소가 하루에 두 번 나오고(체크인, 귀가), 다음 날 출발점은 그대로 전날 숙소
- **체크인 시각은 막지 않음 (11/05 결정):** 체크인 전에 도착해서 짐만 맡기고 나가는 사람도 많아서, 숙소 도착 시각은 사용자가 정한 대로 둠. 관광공사 숙소 정보에 체크인 시각(`checkintime`)이 있으면 숙소 줄에 "체크인 15:00부터 · 그 전엔 짐 맡기기만 될 수 있어요"처럼 **안내만** 표시 (회색·경고 아님). 체크인 시각 읽기는 이 기능을 할 때 같이 넣음

### 바뀌는 곳 (그래서 별도 기능)
- 🟩 `schedule_service` 일정 만들기 구조 (숙소 줄을 중간에, 귀가 줄 추가)
- 🟦 화면: 날마다 체크인 시각·외출 여부 고르기, 일정·지도에서 숙소 두 번 표시, 운영시간 경고·끌기
- 🟧 `_chat_add_pins` 넣을 자리, 숙박비(`stay`)가 어느 숙소 줄에 붙을지
- 미리보기 `is_stay`, 여행 상세 경로, 다음 날 출발점 확인

### 정할 것
- [x] 할지 말지, 한다면 언제 (제안: 4주차 여유 있을 때) — **🟦 동의: 하기, 4주차 (11/05)** → ✅ **11/09 결정: 넣는다** (위 11/09 항목)
- [x] 담당 (제안: 🟩 일정 만들기 + 🟦 화면, 🟧는 담은 장소·비용 연결) — **🟦 동의: 화면 맡음 (11/05)** → ✅ 11/09 이 분담대로

### 참고: 버그는 먼저 따로 고침 (🟧)
- 담은 장소가 체크인 뒤에 붙는 문제 → `_chat_add_pins`가 숙소 줄을 빼고 "직전 장소"를 찾아 그 뒤(숙소 앞)에 넣게
- 같은 장소가 다른 날 자동 일정에 또 나오는 문제 → 담은 장소를 넣은 뒤 다른 날의 같은 장소 지우기

---

## 2026-11-05 · ✅ 결정: 로컬 LLM은 "설정 두 벌" + 기능별 분담 — 🟧 이수한 정리
코드·DB 변경 없음. 포트폴리오·시연 때 OpenAI 없이도 돌릴 수 있게 준비하는 방식이에요.

- **새 모델을 만들거나 훈련하지 않고, 공개 모델(EXAONE·Llama)을 Ollama로 그 PC에서 돌려요(로컬 LLM).** 코드는 그대로, `.env` 설정만 두 벌
  - 설정 A (평소·배포): `AI_BASE_URL` = OpenAI, `AI_MODEL` = gpt-4o-mini
  - 설정 B (시연·포트폴리오): `AI_BASE_URL=http://127.0.0.1:11434/v1` (그 PC의 Ollama), `AI_MODEL`·`AI_FALLBACK_MODELS`는 아래 🟩 비교 결과로 정함 (그 전까지 `exaone3.5:7.8b` / 예비 `llama3.1:8b`)
  - 채팅·리뷰 요약·예산 AI 모두 `chat_service.call_llm` 하나로 부르므로 설정만 바꾸면 다 같이 바뀜 (11/02 🟩 시험 `docs/reports/local-llm-test.html`에서 확인)
- **각자 자기 기능이 로컬 모델에서도 잘 되게 다듬기**
  - 🟩 서지윤: 전환 설정 담당 (설정 B 정리, Ollama가 꺼지면 GPT로 넘어가기), 채팅·일정 에이전트 로컬 시험·보완
    - **모델 결정:** EXAONE 3.5(`exaone3.5:7.8b`)와 Llama 3.1(`llama3.1:8b`)을 11/02 시험과 같은 대화로 **각각 2번씩 더** 시험해 성능을 비교하고, 나은 쪽을 설정 B의 기본 모델로 정해 TEAM_UPDATES에 결과를 남기기
  - 🟧 이수한: 리뷰 키워드 요약 로컬 시험 → GPT와 비교표, RAG(리뷰·장소를 로컬 임베딩 `bge-m3`로 저장)
  - 🟦 임영준: 예산 AI(비용 추정) 로컬 시험, 틀리기 쉬운 부분은 코드로 보완
- **미세 조정(모델 재훈련)은 하지 않아요.** 8GB 그래픽카드·저장 공간·시간 대비 효과가 작아서, 시간이 남으면 실험만
- 시연을 각자 노트북에서 하면 그 노트북에도 Ollama와 모델이 있어야 해요

---

## 2026-11-05 · 전체 흐름 시험 결과 (대화 → 미리보기 → 적용하기 → 여행 상세) + 담은 장소 `kakao_id` 버그 수정 — 🟩 서지윤
DB·응답 키 변경 없음. 로컬 서버에서 부산 2박3일(11/14~16, 2명, 부산역 출발, 대중교통)로 처음부터 끝까지 돌려 봄. 서버 오류 없음

### 고친 것 (🟩)
- 채팅에서 카드를 담을 때(pin) 🟦가 보내는 `kakao_id`를 `chat_service._clean_pin`이 버리고 있었음 → 이제 받음 (숫자만). 🟧 #34의 `p_kakao_id` 저장이 채팅 경로에서도 동작 (장난감박물관 `p_kakao_id` 저장 확인)

### 잘 된 것
- 첫 문장으로 지역·날짜·인원·출발지·이동수단 채움 / 바다 추천에 팀이 고른 곳 먼저 + 관광공사 사진 / 숙소 추천은 담은 장소(해운대) 근처 / 월요일 휴관(부산박물관·임시수도기념관·시립미술관) 빠짐 / 날씨 3일 / 미리보기 장소마다 `photo`·`kakao_id`

### 🟧 부탁 (시연 때 바로 보이는 문제)
- [x] **담은 장소가 그날 일정 맨 끝에 붙음** (11/05 🟧 고침, 맨 위 항목) (`views._chat_add_pins`): 1일차에 담은 해운대해수욕장이 숙소 체크인(20:44) **뒤**에 20:44~22:44로 들어감 / 3일차에 담은 박물관이 저녁 식사 뒤 20:00. 여행 상세의 '운영시간이 안 맞는 곳' 경고에도 뜸
  - 제안: 숙소(체크인)보다 앞에 넣기. 가능하면 자동 일정의 비슷한 종류 자리(바다 → 바다 자리)와 바꾸거나, 운영시간(`hours_service`) 안의 자리로
- [x] **같은 장소가 두 번** (11/05 🟧 고침, 맨 위 항목): 1일차에 담은 해운대해수욕장이 2일차 자동 일정에도 또 들어감 → 담은 장소는 다른 날 자동 일정에서 빼기

### 🟦 부탁
- [ ] 채팅 응답의 `notes`(예: "'부산박물관'은 11/16(월) 정기 휴무라 추천에서 빼었어요.")를 답 아래에 작게 표시. 지금은 안 보여서 카드가 왜 2장뿐인지 알 수 없음
- [ ] 미리보기 장소 `photo.url`, 카드 `review`·`pick`·`indoor`는 아직 화면에 없음 (위 항목들 참고)

### 🟩 다음에 고칠 것
- [x] 휴무로 빼면 카드가 줄어듦 (4장 → 2장) → 후보를 더 받아서 채우기 (11/05 완료)
- [x] '부산박물관 동래관'(카카오 이름, 주소는 부산박물관과 같음)이 월요일에도 남음 → 뺀 곳과 주소가 같으면 같이 빼기 (11/05 완료)
- [x] 카드를 보여 주면서 AI가 "다른 실내 장소를 추천해 드릴까요?"라고 되묻는 문장 → 프롬프트 다듬기 (11/05 완료)
- [x] 숙소(`stays`)에는 `kakao_id`가 없어서 숙소 사진은 예전 방식으로 찾음 → 11/05 채팅 숙소에 `kakao_id` 추가 (위 항목)

---

## 2026-11-05 · 추천 카드에 리뷰 별점 `review` 채우기 + 리뷰 좋은 곳을 앞으로 — 🟩 서지윤
DB 변경 없음. 응답 키 변경 없음 (`mock.json`에 이미 있던 `review: {rating, count}`를 이제 서버가 채움) → 🟦 카드에서 바로 쓰면 됨

### 바뀐 것 (`services/review_rank.py` 새 파일, `chat_service.search_recommendations`에서 부름)
- 추천 카드마다 게시판 리뷰의 평균 별점·리뷰 수 → `review: {"rating": 4.6, "count": 23}`, 리뷰 없으면 `null`
  - `review_summary` API와 같은 값. 카드들을 한 번의 쿼리로 읽음 → 🟦가 따로 `review_summary`를 부르지 않아도 됨
- 순서: 팀이 고른 곳(`pick`)은 맨 앞 그대로, 나머지는 리뷰 점수 순
  - 리뷰 2개 미만은 순서에 반영 안 함 (별점 표시만)
  - 점수 = 평균 별점을 3.5점 쪽으로 리뷰 3개만큼 당긴 값 → 5점 2개(4.1)보다 4.6점 30개(4.5)가 앞
  - 점수가 같으면 원래 순서(가까운 순·검색 순) 그대로. 별점 낮은 곳은 뒤로
- 비 오는 날은 이 순서에서 실내를 다시 앞으로 (`rain_first`)

### 🟦 요청
- [ ] 카드에 `review`가 있으면 '★ 4.6 · 리뷰 23개' 표시 (`null`이면 숨김). 위 '🟦 `review_summary` 불러서 채우기' 항목은 안 해도 됨

### 🟧 참고
- [ ] 추천 점수(키워드·같은 성별·나이대 가중)를 만들면 `review_rank.place_score(review)`만 바꾸면 카드 순서에 반영됨

### 시험 (리뷰를 넣었다가 되돌림)
- 강릉 카페: 4번째 곳 5점×4 → 1번째로, 1번째 곳 2점×4 → 맨 뒤로, 5점×1인 곳은 제자리
- 부산 카페·해운대 맛집: 팀이 고른 2곳은 맨 앞 그대로, 그 뒤만 리뷰 순

---

## 2026-11-04 · 여행 만들기 '직접 선택' 화면 삭제 (AI 대화 방식만) — 🟦 임영준
DB·주소 변경 없음.

- `travel_create.html`에서 예전 직접 입력 폼(`?mode=manual`, `#travelCreateForm`, 장소 검색 창·스크립트)을 지움. 이제 `/travel_create/`는 `?mode=manual`이어도 AI 대화 화면
- 일정 초안 아래 '직접 선택해서 만들기' 링크도 지움 (`travel_create.html`, React `DraftPanel.jsx` → `static/chat/chat.js` 다시 빌드)

### 🟧 참고
- [ ] `views.travel_create`의 POST 처리(폼 저장 → `generate_schedule`)는 이제 화면에서 안 부름. 그대로 두었으니 지울지 정해 주세요

---

## 2026-11-04 · 여행 상세: 장소 운영시간 확인·추천, 축제 진행 시간, 끌 때 운영시간 밖이면 회색 — 🟦 임영준
DB 변경 없음. 기존 키·함수 이름 변경 없음, **추가만**.

- 새 파일 `services/hours_service.py`: 관광공사 `detailIntro2`의 운영시간 문장(usetime·opentimefood·playtime 등)을 여는·닫는 시각으로 바꿈
  - 계절마다 다르면(예: `[11월~2월] 06:00~18:00`) 방문 달 칸만, 브레이크·준비 시간은 뺌, 쉬는 날은 `tour_service.closed_on` 그대로 씀
  - 관광공사에 없는 식당·카페는 보통 영업시간(식당 11~21시, 카페 10~22시)을 `estimated: true`로 줌. 7일 캐시
- 새 주소 `travel_hours/<travel_id>/<day>/` `travel_hours` (주인만) → `{success, day, date, places: {sp_id: {text, open, close, open_min, close_min, estimated, closed, rest}}}` (모르는 장소는 빠짐)
- `travel_festivals` 응답의 축제마다 키 추가: `time`(원문), `open`, `close`('HH:MM' 또는 ''), `open_min`, `close_min`
- 화면: 장소마다 '운영 09:00~18:00' 표시, 안 맞으면 주황으로 추천 시간 + "N번째 자리로 옮기면 맞아요", 맨 위 요약. 일정·축제를 끌 때 그 자리 도착 시각이 운영(행사) 시간 밖이면 회색 + 안내

### 🟩 참고
- [ ] `tour_service.find_tour_item`·`_tour_get`·`closed_on`·`REST_KEYS`를 가져다 씀 (이름 바꾸면 알려 주세요). TourAPI 호출이 장소당 처음 한 번씩 늘어남 (7일 캐시)
- [ ] 나중에 AI 일정 짜기에서도 `hours_service.parse_hours(text, month)`로 운영시간 안에 넣을 수 있어요

---

## 2026-11-04 · 여행 루트 카드 표지 = 지역 대표 사진 — 🟦 임영준
DB·주소·키 변경 없음 (pull만 하면 됨).

- 새 파일 `services/region_photo_service.py`: `region_cover(t_place)` → 지역 대표 사진 주소 (못 찾으면 `''`)
  - 주요 지역은 `LANDMARKS`(예: 수원→수원화성)의 명소 사진, 없는 지역은 그 지역 관광지 사진을 관광공사 `searchKeyword2`에서 찾음. 지역별 7일 캐시
- `views._route_cards`의 `cover`가 이 사진을 먼저 쓰고, 없으면 예전처럼 루트 안 첫 장소 사진

### 🟩 참고
- [ ] 🟩의 `tour_service._tour_get`을 가져다 씀 (이름·인자 바꾸면 알려 주세요). 대표 명소를 바꾸거나 더 넣으려면 `LANDMARKS`에 추가

---

## 2026-11-04 · 리뷰 게시판 '여행 루트' 탭: 회원 여행 루트 공유 + 별점·댓글 — 🟦 임영준
**DB 변경 있음 (마이그레이션 0014, 새 테이블 3개만)** → 모두 pull 후 `python manage.py migrate`. 기존 표·키·함수 이름 변경 없음, **추가만**.

- 새 테이블: `shared_route`(여행 하나당 공유 하나, 한 줄 소개) · `route_rating`(루트·회원당 별점 1개, 바꿀 수 있음) · `route_comment`(댓글)
- 리뷰 게시판 `/review/`: 기본 탭이 **여행 루트**(공유된 여행 카드 목록, 검색·최신/별점/댓글순). 예전 장소 리뷰는 `/review/?tab=places` 그대로 → 홈 '여행 리뷰 추천'·`review_list`·`review_summary`·`review_keywords` 영향 없음
- 새 주소(이름 = 주소 이름):
  - `route/<sr_id>/` `route_detail` — DAY별 루트(시간·머묾·이동) + 지도 + 별점 + 댓글
  - `route/<sr_id>/rate/` `route_rate` (POST `rating` 1~5, JSON `{success, mine, avg, count}`, 내 루트는 400)
  - `route/<sr_id>/comment/` `route_comment` (POST `content` ≤300) · `route/comment/<rc_id>/delete/` `route_comment_delete` (내 댓글·내 루트 댓글만)
  - `route_share/<travel_id>/` `route_share` (POST `intro`, `action=unshare`면 공유 취소, 장소가 하나도 없으면 400)
- 여행 상세 헤더에 '게시판에 공유' 버튼(주인만). 공유해도 비용은 안 보임. 공유 취소하면 별점·댓글도 지워짐
- 홈 오른쪽 카드가 '여행 리뷰 추천'(장소) → **'여행 루트 추천'**으로 바뀜: `index`가 `review_picks` 대신 `route_picks`(`build_route_picks()`, 별점 높고 반응 많은 순 3개)를 넘김. `build_review_picks()` 함수는 그대로 남겨 둠

### 🟧 참고
- [ ] 나중에 '내 일정으로 가져오기'(다른 회원 루트 복사)를 만들면 `_route_days()`를 그대로 쓰면 돼요

---

## 2026-11-04 · 비용 '카페' 분류(0013), 지출 차트, `kakao_id` 담아 보내기, 여행 기간 축제·행사 끌어 넣기 — 🟦 임영준
**DB 변경 있음 → 모두 `python manage.py migrate`** (0013: `TravelBudget.category` 선택지에 `cafe` 추가만, 칸 변경 없음). 기존 키·함수 이름 변경 없음, **추가만**.

### 1) 비용 분류 '카페' (`cafe`)
- 비용 추가 화면 '비용 항목'에 카페. 분류 키 표 `BUDGET_CATEGORIES`에 `('카페', 'cafe', ...)`, `BUDGET_CATEGORY_CHOICES`에 `('cafe', '카페')`
- 키워드 '카페·커피·디저트·베이커리·빵·음료'는 이제 식비가 아니라 카페로 셈 → 예전에 '카페'로 적힌 비용도 카페로 다시 묶여 보임

### 2) 비용 관리 아래 '지출 차트'
- 분류별 비율(도넛)·날짜별 지출(하루 예산 점선)·분류별 예산 대비 사용. `views._budget_chart` → 화면 `chart_data` (Chart.js 4.4.1, cdnjs)
- 분류별 예산(`travel_budget`)이 저장되면 연한 '예산' 막대가 같이 나옴

### 3) `kakao_id` 담아 보내기 (위 🟧 요청 완료)
- 장소 검색 응답(`_search_kakao_places`)에 `kakao_id` 키 추가, 장소 추가 폼 3곳에서 `place_kakao_id` 전송

### 4) 여행 상세 왼쪽 '여행 기간 축제·행사' + 끌어서 일정에 넣기
- 새 주소 `travel_festivals/<travel_id>/` (이름 `travel_festivals`, GET, 로그인·내 여행만) → `{success, festivals: [{id, title, start, end, period, addr, lat, lon, image, tel, days, always}]}`
- 새 파일 `services/festival_service.py`: 관광공사 `searchFestival2`로 여행 기간과 겹치고 주소에 여행 지역 이름이 있는 행사(지역 이름이 없을 때만 일정 장소 40km 안), 6시간 저장. 두 달 넘게 하는 건 `always: true`(상시). `TOUR_API_KEY` 필요(없으면 빈 목록)
- 넣을 때는 기존 `schedule_place_add`(`place_kind='축제'`) + 원하는 자리면 `schedule_place_reorder` 그대로 사용 → 🟧 서버 함수 변경 없음

### 🟩 참고
- [ ] 추천 카드 `cost.cat`에 `cafe`를 써도 됨 (지금처럼 `food`여도 그대로 동작)

---

## 2026-11-04 · 리뷰 키워드 요약 (LLM) `review_keywords` + 요약 저장 테이블 `review_summary` — 🟧 이수한
**DB 변경 있음 (마이그레이션 0012)** → 모두 pull 후 `python manage.py migrate`. 기존 응답 키 변경 없음, 새 주소만 추가

- 주소: `GET /review_keywords/?kakao_id=12345`
- 응답: `{"success": true, "kakao_id": "12345", "keywords": ["바다 전망", "사진 맛집", ...], "summary": "한 문장 요약", "count": 3}`
  - `keywords`는 최대 5개, `summary`는 한 문장. 리뷰가 없으면 `keywords: []`, `summary: ""`, `count: 0`
  - `kakao_id`가 없으면 400
- AI 코드: `services/review_service.py`의 `summarize_review(kakao_id)` (최신 리뷰 30개를 `call_llm`으로 요약)
- 새 테이블 `review_summary`: 카카오 ID당 한 줄(키워드·요약·요약할 때의 리뷰 수). **리뷰 수가 바뀔 때만 LLM을 다시 부름** → 첫 호출 2~3초, 그다음은 바로 응답
- LLM이 실패하면 예전 요약을 돌려줌 (없으면 빈 값). 화면이 깨지지 않음

### 🟦 요청 (선택)
- [ ] 장소 정보·리뷰 화면에서 키워드 칩과 한 줄 요약 표시. 첫 호출은 몇 초 걸릴 수 있으니 로딩 표시 권장
- 추천 카드(`mock.json`)에 키워드를 넣을지는 다음 작업(맞춤 추천 점수) 때 같이 정해요

---

## 2026-11-04 · `settings.py`: 서버도 정식 설정(`DEPLOY=True`)으로, DB는 어디서나 MariaDB — 🟧 이수한
DB·응답 키 변경 없음. **팀원 할 일 없음** (로컬 `.env`는 지금 그대로 `DEPLOY=False`)

- 예전 PythonAnywhere용으로 `DEPLOY=True`면 SQLite를 쓰던 블록을 지움 → 로컬·서버 모두 `.env`의 `DB_*`로 MariaDB 접속
- 그동안 서버는 MariaDB를 쓰려고 `DEPLOY=False`로 돌고 있었음 → 이번에 `DEPLOY=True`로 바꿈 (운영에서는 `SECRET_KEY` 필수 검사가 켜짐)
- 로컬에서 `DEPLOY=True`로 켜도 빈 SQLite로 바뀌지 않음

---

## 2026-11-03 · 리뷰 `kakao_id` 빈칸 허용(마이그레이션 0011), 같은 카카오 장소 리뷰 중복 막기 — 🟦 임영준
**DB 변경 있음 → 모두 `python manage.py migrate`**. 응답 키·주소 변경 없음.

### 왜
- 0009에서 리뷰 유니크가 (회원, `kakao_id`)로 바뀜. 그런데 카카오 id가 없는 장소 리뷰는 `''`로 저장돼서, 한 사람이 그런 리뷰를 2개 쓰면 "같은 장소"로 걸려 저장 오류. 이미 `''` 리뷰가 2개 이상 있는 DB는 0009 migrate 자체가 실패함.

### 바꾼 것
- `models.py` `Review.kakao_id` → `null=True, blank=True` (🟧 파일, 이 한 줄만). NULL끼리는 유니크에 안 걸림
- `migrations/0011_review_kakao_id_null.py`: 칸을 NULL 허용으로 + 기존 `''` 리뷰를 NULL로
- `views.py` `review_write`: 카카오 id 없으면 `None` 저장. `_reviewable_places`: 이미 리뷰한 카카오 장소는 다른 여행에서 또 가도 목록에서 뺌

### migrate가 0009에서 실패하면
- 이미 `''` 리뷰가 같은 회원에게 2개 이상 있는 경우. shell에서 그 리뷰들의 `kakao_id`를 잠깐 서로 다른 값(`tmp-리뷰번호`)으로 바꾸고 migrate → 끝나면 `tmp-`로 시작하는 걸 `None`으로 돌려 주세요

### 🟧 확인
- [ ] `review_list`·`review_summary`는 `kakao_id`로만 찾아서 그대로 동작 (NULL 리뷰는 안 나옴)

---

## 2026-11-03 · 일정 장소에도 사진 (`stops[].photo`), 자동 일정에 카카오 ID 저장 — 🟩 서지윤
DB 변경 없음. 응답 키 **추가만** (일정 미리보기 장소에 `photo`·`kakao_id`) → 🟦 화면에서 쓰면 됨. 🟧 파일(`views.py`, `schedule_service.py`)을 조금 고쳤으니 확인 부탁

### 바뀐 것
- **자동 일정이 장소의 카카오 ID를 저장** (`schedule_service.get_or_create_place` → `p_kakao_id`). 검색 결과에 이미 `kakao_id`가 있었는데 저장만 안 하고 있었음. 이미 있는 장소도 비어 있으면 채움
- **채팅 일정 미리보기** (`POST /travel_chat_preview/`)의 `days[].items[]`에 추가
  - `photo`: `{"url", "source": "tour" | "kakao"}` 또는 `null` — 추천 카드의 `photo`와 같은 모양, 같은 사진 표(`place_photo`)
  - `kakao_id`: 카카오 장소 ID 또는 `null` (리뷰 별점 `review_summary`에 쓸 수 있음)
  - 새로 찾는 사진은 한 번에 8곳까지 (나머지는 `null`, 다음 미리보기 때 찾음). 한 번 찾은 사진은 저장돼서 바로 나옴
- **일정 DAY 화면·채팅 '적용하기'의 장소 이미지(`p_image`)**: 카카오 ID가 있으면 추천 카드와 같은 방식(관광공사 → 이름 확인한 카카오 이미지)으로 찾음. 카카오 ID가 없는 장소는 전과 같음. 이미 저장된 `p_image`는 그대로

### 🟦 요청
- [ ] 일정 미리보기 타임라인의 장소에 `photo.url` 표시 (`null`이면 기본 이미지)

### 🟧 확인
- [ ] `schedule_service.get_or_create_place`, `views.py`의 DAY 화면 이미지·`_chat_add_pins` 이미지·`travel_chat_preview` 부분 확인

### 시험
- 부산 1박2일 자동 일정 9곳: 9곳 모두 `kakao_id` 저장, 사진 9곳(관광공사 6 · 카카오 3), 2.3초 / 두 번째는 저장된 사진이라 0초
- `manage.py check` 문제 없음

---

## 2026-11-03 · 일정에 담은 장소에 카카오 ID 저장 (`p_kakao_id`) — 🟧 이수한
DB 변경 없음(칸은 이미 있었음). 받는 값 **추가만** → 🟦 보내 주면 됨, 🟩 영향 없음

- 장소 추가 `POST /schedule_place_add/`: `place_kakao_id`를 받으면 새 장소의 `p_kakao_id`에 저장
- 채팅에서 담은 장소(pin)로 일정 만들 때: pin의 `kakao_id`를 저장 (숫자로 와도 문자열로 저장, 없으면 비워 둠)
- 이 ID가 있어야 일정의 장소에 리뷰 별점(`review_summary`)·사진을 붙일 수 있음
- 아직 보내지 않아도 오류 없음 (지금처럼 비어 있게 저장)

### 🟦 요청
- [x] 장소 추가 폼에 `place_kakao_id` 함께 보내기 (검색 결과 장소의 카카오 id) (11-04 🟦 완료, 장소 검색 응답에 `kakao_id` 키 추가)
- [x] 채팅 추천 카드를 담을 때(pin) 카드의 `kakao_id`도 같이 담기 (11-04 🟦 완료, 기존 채팅·React 둘 다)

---

## 2026-11-03 · 부산 장소 표를 추천 후보로: 팀이 고른 곳 먼저, 추천 카드에 `pick` — 🟩 서지윤
DB 변경 없음. 응답 키 **추가만** (추천 카드 `pick`, `mock.json`에 예시 추가) → 🟦 화면에서 쓰면 됨, 🟧 영향 없음

### 바뀐 것 (`services/busan_spots.py` 새 파일)
- `docs/data/busan_spots_draft.csv`에서 **'고름'이 O인 31곳**만 읽음 (서버가 켜질 때 한 번. 표를 고치면 서버 다시 켜기)
- 부산 여행에서 추천 종류가 표의 컨셉과 맞으면 카카오 결과 **앞에 최대 2곳**을 넣고, 같은 곳은 카카오 결과에서 뺌
  - 바다·해수욕장 → 바다 / 카페 / 맛집·식당 → 음식 / 역사·박물관 → 역사 / 시장 → 전통문화 / 자연·산책 / 쇼핑·백화점 / 숙소·호텔 / 랜드마크·관광지 / 공원 / '실내'는 표의 실내 구경거리(박물관·백화점)
  - '해운대 근처'처럼 기준이 있으면 3km 안의 곳만, 가까운 순
- 표의 '실내/실외' → 카드 `indoor` (실내+실외는 `null`)
- 표의 '휴무 요일'(예: 월) → 관광공사에 쉬는 날 정보가 없을 때 그 요일에 카드에서 뺌
- 다른 지역(강릉 등)은 지금과 같음

### 추천 카드 `pick` (새 키)
- 팀이 고른 곳: `{"concept", "hours"(영업시간), "fee"(입장료), "parking"(주차), "memo", "rest"(매주 쉬는 요일)}` — 표에서 '확인 필요'·'-'·빈칸은 `null`
- 카카오에서 찾은 곳: `null`

### 같이 고친 것 (시험하다 찾음)
- 숙소 질문 뒤에 '바다 추천해줘'라고 하면 AI가 '바다 근처 숙소'로 읽고 숙소까지 골라 넣던 문제 → 사용자 말 그대로 바다 추천
- 앞 턴의 '해운대 근처'가 다음 추천('셋째 날 박물관')에 따라오던 문제 → 이번 말에 없는 기준 장소는 안 씀

### 🟦 요청
- [ ] `pick`이 있으면 카드에 'TRIPA 추천' 표시 + `hours`·`fee`·`memo` 작게 (선택)

### 시험
- 휴무 칸 읽기 6개 맞음 (`월`→매주 월요일, `화(이번 달 11/3)`·`확인 필요`→없음)
- 바다·카페·해운대 맛집·숙소·랜드마크·실내 모두 팀이 고른 곳 2곳이 앞에, 강릉은 그대로
- 실제 GPT: 부산 2박3일 '바다 추천해줘' → ★해운대·★광안리 / '둘째 날 해운대 근처 맛집' → ★고래사어묵(440m)·★대영횟집(2.6km) / '셋째 날(월) 박물관' → 부산박물관·임시수도기념관(월 휴관) 빠짐
- 숙소 추천 시험 3개 다시 돌려서 그대로 동작

## 2026-11-03 · 숙소 추천: 빈 밤·담아 둔 장소 근처·가격대 — 🟩 서지윤
DB 변경 없음, 응답 키 변경 없음 (기존 추천 카드 그대로, `kind: "숙박"`) → 🟦 🟧 영향 없음

### 바뀐 것 (`services/chat_service.py`의 `stay_recommend`)
- 전에는 "아직 안 정했어 추천해줘", "해운대 쪽으로 저렴한 데 추천해줘"에 숙소 카드가 안 나오고 AI가 동네를 되묻기만 했음 → 이제 바로 숙소 카드
- **며칠째 밤:** 사용자가 말하면 그날("둘째 날 숙소"), 아니면 숙소가 빈 첫 밤 → 카드의 `day`
- **어디 근처:** 말한 동네("해운대 쪽") → 그날 담아 둔 마지막 장소(없으면 다음 날 첫 장소) 근처 → 지역 중심
- **종류·가격:** 말한 종류(호텔·게스트하우스·펜션·리조트·모텔·호스텔) → "저렴한"이면 게스트하우스·호스텔·모텔 / "고급"이면 호텔·리조트 / 4명 이상이면 펜션·리조트 / 아니면 호텔 3 + 게스트하우스 1
- 숙소 추천 턴에는 AI가 숙소를 골라 `stays`에 넣지 못하게 함 (카드를 보기도 전에 넣는 경우가 있었음). 숙소는 사용자가 카드의 [N일차 숙소로 넣기]로 넣음
- '영업팀', '지사' 같은 사무실 이름은 숙소 카드에서 뺌

### 시험 (실제 GPT)
- 부산 2박3일: '아직 안 정했어 추천해줘' → 1일차 밤 호텔·게스트하우스 / '해운대 쪽으로 저렴한 데' → 해운대 130m~630m 게스트하우스·호스텔
- 1일차 숙소가 있고 2일차에 부산박물관을 담은 뒤 '숙소 추천해줘' → 2일차 밤, 부산박물관 근처 / '고급 호텔로' → 웨스틴조선·롯데호텔·리조트
- 강릉 5명: '펜션 추천해줘' → 펜션 / '카페 추천해줘'는 숙소 질문 뒤라도 카페 / '숙소는 ○○호텔로 할게'는 추천 아님

## 2026-11-03 · 비·눈 오는 날 실내 장소 먼저, '실내 추천', 추천 카드에 `indoor` — 🟩 서지윤
DB 변경 없음. 응답 키 **추가만** (추천 카드 `indoor`, `mock.json`에 이미 있던 키) → 🟦 화면에서 쓰면 됨, 🟧 영향 없음

### 1) 실내·야외 판단 (`services/indoor_service.py` 새 파일)
- 카카오 분류 이름을 자세한 쪽부터 읽음: 박물관·미술관·아쿠아리움·쇼핑몰·카페·식당·찜질방 → 실내 / 해수욕장·공원·테마파크·사찰·유적지·카페거리 → 야외
- 전망대·시장·체험장처럼 곳마다 다른 곳은 모름
- 추천 카드의 `indoor`: `true`(실내) / `false`(야외) / `null`(모름)

### 2) 비·눈 오는 날 추천
- 가는 날 예보가 비·눈이면 실내 카드를 앞에 두고 `notes`에 "11/05(목) 비 예보라 실내 장소를 앞에 두었어요."
- 카드가 모두 야외면(예: 해수욕장 추천) "… 실내 장소가 필요하면 '2일차 실내 추천'처럼 말해 주세요."
- 날짜가 정해질 때 나오는 비 안내도 같은 예시 문장으로 바꿈 (따라 말하면 바로 실내 추천)
- 당일치기는 '몇 일차'를 말하지 않아도 그날로 봄 (쉬는 날 빼기도 같이 적용)

### 3) '실내 추천'
- "실내로 추천해줘", "2일차 실내 추천" → 박물관·미술관(문화시설)과 쇼핑몰을 찾고 야외는 뺌

### 🟦 요청
- [ ] 추천 카드에 `indoor`가 `true`면 '실내' 작은 표시 (선택, `false`·`null`이면 숨김)

### 시험
- 실내·야외 판단 22개 맞음 (카카오 실제 분류 60여 종을 보고 정함)
- 실제 GPT (부산 11/05 비 예보): 날짜 정할 때 비 안내 → '관광지 추천' → 쇼핑몰 먼저 → '응 실내로 추천해줘' → 박물관·미술관 5곳
- 날씨 예보는 같은 곳·같은 날짜를 1시간 동안 저장 (추천할 때마다 다시 묻지 않게)
## 2026-11-03 · 여러 장소 리뷰 요약 API `review_summary` — 🟧 이수한
DB 변경 없음. 새 주소의 응답만 채움 → 🟦 추천 카드에서 쓰면 됨, 🟩 영향 없음

- 주소: `GET /review_summary/?kakao_ids=123,456,789` (쉼표로 여러 개, 공백·빈 값은 무시, 한 번에 최대 50개)
- 응답: `{"success": true, "reviews": {"123": {"rating": 4.5, "count": 2}, ...}}`
  - `rating`은 소수 첫째 자리까지 평균, `count`는 리뷰 수
  - **리뷰가 없는 장소는 `reviews`에 아예 없음** → 카드에서 `reviews[kakao_id]`가 없으면 별점 숨김
- `kakao_ids`가 없거나 비면 400 `{"success": false, "message": "kakao_ids가 필요합니다."}`

### 🟦 요청
- [ ] 채팅 추천 카드를 그릴 때 카드들의 `kakao_id`를 모아 한 번만 불러서 `review: {rating, count}` 자리에 넣기

---

## 2026-11-03 · 쉬는 날(휴무) 확인: 추천 카드에서 빼기 + AI 도구 `check_open`, 날짜 안정화 — 🟩 서지윤
DB 변경 없음. 응답 키 **추가만** (추천 카드 `open`) → 🟦 화면에서 쓰면 됨, 🟧 영향 없음

### 1) 쉬는 날 알아내기 (`services/tour_service.py` 새 파일)
- 관광공사 TourAPI에서 같은 장소(이름 + 300m 안)를 찾아 소개 정보의 쉬는 날 문장을 읽음
  - 관광지·박물관뿐 아니라 관광공사에 있는 식당·시장도 있음 (예: 이재모피자 '매주 일요일', 자갈치시장 '매월 첫째, 셋째, 다섯째 화요일')
- 읽는 말: `매주 월요일`, `토, 일요일`, `월·화요일`, `매월 첫째·셋째 화요일`, `둘째·넷째 주 일요일`, `마지막 월요일`, `1월 1일`, `연중무휴`
  - 괄호 안 예외('월요일이 공휴일이면 다음날')와 설날·추석(해마다 바뀜)은 읽지 않음
- 같은 장소는 7일 동안 다시 묻지 않음 (TourAPI 하루 호출 수 제한)
- 관광공사에 없는 장소는 '모름' → 빼지 않음

### 2) 추천 카드: 가는 날 쉬는 곳은 빼기 (`open` 추가)
- 가는 날 = 출발일 + `day` - 1. '셋째 날', '첫날', '2일차'도 서버가 읽음
- 쉬는 곳은 카드에서 빼고 `notes`에 "'부산박물관'은(는) 11/09(월) 정기 휴무라 추천에서 뺐어요."
- 남은 카드의 `open`: `{"closed": false, "reason": null, "text": "매주 월요일 / 1월 1일"}` 또는 `null`(모름·가는 날 모름)
- `reason`: `weekly_off` · `monthly_off` · `holiday` (`plan.days[].excluded[].reason`과 같은 값)

### 3) AI 도구 `check_open(place, date)`
- "부산박물관 11월 9일에 열어?" → AI가 도구를 불러 "정기 휴무"라고 답함. 여행 날짜가 아직 없어도 먼저 답함
- 이런 질문의 날짜는 여행 날짜로 읽지 않음 (날씨 질문도 같음)

### 4) 날짜 안정화 (시험하다 찾은 문제)
- 사용자가 날짜 이야기를 안 했는데 AI가 정해 둔 날짜를 바꾸던 문제 → 날짜 이야기가 없으면 이전 날짜 유지
- 코드가 AI의 날짜를 고쳤을 때 AI 답 문장에 틀린 날짜가 남던 문제 → 날짜 문장을 빼고 "출발일은 11월 7일(토), 종료일은 11월 9일(월)로 반영했어요."

### 🟦 요청
- [ ] 추천 카드에 `open.text`(쉬는 날)를 작게 표시해도 좋음 (`null`이면 숨김)

### 시험
- 쉬는 날 문장 16개, 날짜 문장 22개 모두 맞음
- 실제 GPT: 11/7~9 부산 → '셋째 날 박물관 추천' → 부산박물관(월요일 휴관) 빠짐 / '부산박물관 11월 9일에 열어?' → 휴무 / '자갈치시장 11월 17일' → 셋째 화요일 휴무
- 처음 보는 장소가 많으면 추천이 약 7~9초 (사진·쉬는 날 조회), 저장된 뒤에는 빨라짐

## 2026-11-03 · AI 대화를 LangChain 도구 호출 구조로, 첫 도구 '날씨' + 채팅 응답에 `weather` — 🟩 서지윤
DB 변경 없음. 응답 키 **추가만** (`/travel_chat/` 응답에 `weather`) → 🟦 화면에서 쓰면 됨, 🟧 영향 없음

### 1) 도구 호출 구조 (`services/agent_tools.py` 새 파일, `chat_service.call_llm`)
- AI가 답을 쓰기 전에 필요하면 **도구를 부름** → 서버가 실행해서 결과를 돌려줌 → AI가 결과를 보고 최종 답(JSON, 기존과 같은 모양)
- 한 턴에 최대 3번, 도구가 실패해도 대화는 이어짐
- 도구를 못 쓰는 모델(일부 Ollama 모델)이면 자동으로 **도구 없이** 기존처럼 답을 받음 (EXAONE·Llama 3.1로 확인)
- 새 도구 만드는 법은 `agent_tools.py` 맨 위 설명 참고 (`@tool` 함수 + `CHAT_TOOLS`에 추가). 휴무·숙소 추천도 여기에 붙일 예정

### 2) 첫 도구 `get_weather(place, start, end)` — 날씨 예보 (Open-Meteo, 키 필요 없음)
- 사용자가 "날씨 어때?"라고 하면 AI가 도구를 불러 답함. 비·눈이면 실내 장소를 권함
- 지역·날짜가 **이번 턴에 정해지거나 바뀌면 서버가 직접** 날씨를 봄 (날짜는 AI 답 뒤에 코드가 계산하므로)
- 비·눈 오는 날이 있으면 `notes`에 "11/08(비) 예보가 있어요. 실내 장소도 함께 추천해 드릴까요?"
- 예보는 **오늘부터 16일 안**만 있음. 그보다 먼 날짜면 `weather: null`

### 3) 채팅 응답에 `weather` 추가 (기존 키 변경 없음)
- `null` 또는 날짜별 목록. `kind`·`temp`는 `mock.json`의 `plan.days[].weather`와 같은 이름
```json
"weather": [{"date": "2026-11-07", "kind": "cloud", "label": "흐림", "temp": 12, "temp_min": 3, "rain_pct": 0}]
```
- `kind`: `sun` `cloud` `rain` `snow` · `temp`: 낮 최고(℃) · `rain_pct`: 비 올 확률(%)

### 🟦 요청
- [ ] 채팅 화면 일정 초안에 날짜별 날씨 표시 (`weather`가 `null`이면 숨김). 응답마다 오지 않으니 **마지막으로 받은 값을 들고 있다가** 날짜가 바뀌면 새 값으로

### 시험
- 실제 GPT: '부산 이번주 토요일부터 2박3일' → 날짜 정해지며 날씨 3일치 / '그날 날씨 어때?' → AI가 도구를 불러 날씨로 답함 / 52일 뒤 날짜 → 날씨 없음
- 응답 시간: 도구를 부르는 턴은 약 2~3초 늘어남 (2초 → 5초)
- 로컬 모델(EXAONE·Llama 3.1)은 오류 없이 동작하지만, 답 문장에 날짜를 틀리게 적는 경우가 있음 (초안 값은 맞음)
## 2026-11-03 · 장소별 리뷰 목록 API `review_list`, 마이그레이션 0009·0010 — 🟧 이수한

> ⚠️ **DB가 바뀌어요.** pull 뒤에 `python manage.py migrate`로 **0009**(리뷰 중복 기준 변경)와 **0010**(🟩 `0009_placephoto`와 잇는 병합, DB 작업 없음)을 적용하세요.

### 1) 리뷰 중복 기준 변경 (0009)
- 같은 회원이 같은 장소에 리뷰를 두 번 못 쓰게 막는 기준을 **(회원, place) → (회원, kakao_id)**로 바꿨어요. place가 비어 있으면 MariaDB가 중복을 못 막았어요.

### 2) 새 주소 `GET /review_list/?kakao_id=…&sort=helpful` (추가만)
- 로그인 없이도 볼 수 있어요. `sort`가 `helpful`이면 추천 많은 순, 아니면 최신순
- 응답: `{success, kakao_id, avg, count, reviews: [{rv_id, member_name, rating, content, tags, created_at, helpful_count, is_mine, is_helpful}]}`
- 리뷰가 없으면 `avg: 0, count: 0` → 🟦 화면에서는 `count`가 0이면 별점을 숨겨 주세요
- 실패: `kakao_id` 없음 400 (`{success: false, message}`)

### 3) 리뷰 쓰기·추천은 🟦 PR #29 것을 씀
- back에 만들던 같은 이름의 `review_write`·`review_helpful` 함수와 주소(`review_write/`, `review_helpful/`)는 지웠어요. 기존 이름 그대로 🟦 것(`review/write/`, `review/<rv_id>/helpful/`)만 남아요.

### 남은 일
- [x] 🟧 `review_summary` (여러 장소 평균을 한 번에) — 11/03 완료, 맨 위 항목 참고 → 채팅 추천 카드 `review: {rating, count}` 채우기 (지금은 빈 응답)

## 2026-11-03 · ✅ 결정: 기능별 역할 분담 — 🟧 이수한 (팀 3명 동의)

코드·DB·주소 변경 없음. 10/30 제안(아래 항목)에 셋이 동의했고, 일 두 개를 옮겨서 확정했어요.
한눈에 보기: [TRIPA 기능별 역할 분담](https://claude.ai/artifact/WREMzfhPWtDKpPGYSCBocq)

### 원칙
- 백엔드·프론트·AI로 나누지 않고, **각자 AI 기능 하나를 화면(React) → API(views·urls) → AI(service 파일)까지** 맡아요.
- 한 사람만 할 수 있는 일(서버 배포·DB, 공통 레이아웃·지도)은 지금 하던 사람이 계속 해요.
- AI 코드는 기능별 파일로 나눠요: `chat_service.py`(🟩) · `review_service.py`(🟧) · `budget_service.py`(🟦)
- 기존 응답 키·함수 이름은 바꾸지 않고 추가만 해요. 바꿀 땐 3명 합의.

### 🟧 이수한 — 리뷰 기반 맞춤 추천
- [ ] 리뷰 API (목록·쓰기·도움돼요·장소별 평균) — **진행 중**, `back`에 주소 4개 있음 (응답 모양은 완성 후 공유)
- [ ] 리뷰 게시판 본문(목록·글쓰기). 틀은 🟦가 만든 `review.html`
- [ ] 홈 '여행 리뷰 추천' 카드에 `review_picks` 넘기기 (키는 🟦가 정한 `region`·`place`·`rating`·`count`·`quote`·`url`)
- [ ] 리뷰 키워드 요약(LLM), 추천 점수(평점·리뷰 수·키워드 + 같은 성별·나이대 가중), 점수를 추천 카드 순서에 반영(🟩와 연결)
- 계속 담당: 서버 배포·DB·백업, 장소 `p_kakao_id` 저장, 서버 `.env`에 `TOUR_API_KEY` 넣기

### 🟦 임영준 — 예산 AI
- [ ] 장소·이동 비용 추정(6개 분류), 예산 넘으면 같은 분류의 더 싼 대안, 이동수단별 가격 비교
- [ ] 카테고리 예산 화면(React)
- [x] **카테고리 예산 저장 API** ← 🟧에서 옮김 (테이블 `travel_budget`은 이미 있음) — 11/05 완료 (`budget/<travel_id>/category/`, 맨 위 항목)
- 계속 담당: 반응형 공통 레이아웃, 지도 이동·팝업, 추천 카드 → 핀·장소 추가 폼에 `kakao_id` 담아 보내기

### 🟩 서지윤 — 대화형 일정 에이전트
- [ ] 채팅을 LangChain 도구 호출 방식으로 확장, 비 예보면 실내 장소로 대체, 휴무 장소 제외, 숙소 미정이면 숙소 추천
- [ ] 부산 장소 표(`docs/data/busan_spots_draft.csv`)를 추천 후보로 연결
- [ ] **장소 사진 테이블(카카오 ID당 1장) + 사진 찾기(관광공사 → 엄격한 카카오 검색 → 없으면 없음) + 장소 정보 API** ← 🟧에서 옮김

### 함께 정할 것
- [x] 세 기능이 같이 쓰는 채팅 추천 카드 응답 키(`mock.json`) → PR #27로 확정 (11/03, 3명 동의)
- [x] 🟩 사진 응답 키를 먼저 정해 공유 → `photo: {url, source}` 또는 `null` (PR #27)

## 2026-11-03 · 리뷰 게시판 기능, 여행 수정(날짜 옮기기), 추천 카드 사진 — 🟦 임영준
DB 변경 없음 → `migrate` 필요 없음. 🟧 `views.py`·`urls.py`는 **추가만** (기존 함수·주소 그대로, 단 아래 1)의 `review_board`는 🟦가 만든 함수라 내용 바꿈)

### 1) 리뷰 게시판 (기존 `Review`·`ReviewHelpful` 테이블 사용)
- `/review/` 전체 리뷰(최신순, 10개씩) + 오른쪽 '추천 많은 리뷰' 5개 + 글쓰기 버튼. 👍 추천/취소(내 리뷰는 추천 불가)
- `/review/write/` 리뷰 쓰기: **여행 카드 고르기 → 그 여행의 장소 고르기** → 별점 1~5·후기 100자·태그(선택)
  - 고를 수 있는 장소 = 내 여행 중 **시작한 여행**(`t_start` ≤ 오늘)의 장소, 이미 리뷰 쓴 장소는 빠짐 (한 장소에 한 번)
- 새 주소(🟧 추가): `review_write` (`review/write/`), `review_helpful` (`POST review/<rv_id>/helpful/` → `{success, helped, count}`)
- 화면: `review.html`·`review_write.html`, 스타일 `static/sherpaapp/css/review.css`, 하늘 배경(`trip-sky`)

### 2) 홈 '여행 리뷰 추천' 카드에 진짜 리뷰
- 🟧 `index`가 `review_picks`도 넘김 (도우미 `build_review_picks`): **지역(`t_place`)별** 평균 별점 높은 순 → 리뷰 많은 순 3곳, 대표 장소·한 줄 후기(추천 많은 리뷰)
- 리뷰가 없으면 '예시' 견본 대신 "아직 올라온 리뷰가 없어요" + 리뷰 쓰러 가기

### 3) 일정 상세 '여행 수정' 팝업 (이름·지역·날짜)
- 상세 위쪽의 동작 없던 '저장' 버튼 → **'여행 수정'** (내 여행에만 보임)
- 새 주소(🟧 추가): `travel_reschedule` (`POST travel_reschedule/<travel_id>/`, JSON)
  - 날짜를 옮기면 `Schedule.s_day`·`TravelDayPlan.plan_date`도 같은 만큼 옮김 (DAY 1은 계속 DAY 1, 장소·비용 그대로)
  - 기간이 늘면 뒤에 빈 DAY, 줄면 잘리는 DAY 삭제. 잘리는 DAY에 장소·비용이 있으면 `409 needs_confirm` → 화면에서 확인 후 `confirm=1`로 다시 보냄
  - 본인 여행만(403), 로그인 필요(401), 최대 30일
- 🟧 참고: 기존 `travel_update` 화면은 그대로 두었는데, 어디에도 연결돼 있지 않고 날짜만 바꾸면 일정이 화면에서 사라지는 문제가 있음 (DAY는 `t_start`~`t_end`로 만들고 `s_day`로 일정을 찾기 때문)

### 4) 채팅 추천 카드에 사진 (위 🟩 사진 항목의 🟦 요청)
- 기존 대화 화면(`travel_chat.js`)·React(`RecCards.jsx`, 빌드 `static/chat/chat.js`) 둘 다: `photo.url` 있으면 사진, 없거나 깨지면 종류 아이콘
- `source: "tour"`면 "사진: 한국관광공사", `review`·`cost` 값이 있으면 "★ 4.6 · 리뷰 23개", "예상 8,000원"

## 2026-11-03 · AI 대화 상대 날짜('이번주 토요일')·기간('2박 3일')을 코드로 계산 — 🟩 서지윤
DB·주소·응답 키 변경 없음 → 🟦🟧 영향 없음, pull만 하면 됨

- 문제: 로컬 LLM 시험 때 **모든 모델(GPT 포함)이** "이번주 토요일"을 틀림 (11-02 월요일 기준 11-07이 맞는데 11-05 등), '2박 3일' 종료일도 가끔 틀림
- 해결 (`chat_service.py`): 사용자 문장에서 날짜를 **코드로 계산해서 AI 값 대신 씀** (`guess_dates`, `guess_nights`, `_apply_guessed_dates`)
  - 읽는 말: `11월 7일` `11/7` `2026-11-07` · `11월 7일부터 9일까지` `11/20~11/22` · `이번주/다음주/다다음주/담주 ○요일` `토요일` · `이번 주말` `다음 주말` · `오늘` `내일` `모레` `글피` `3일 뒤` · `N박 M일` `당일치기`
  - 한 주는 월~일. '토요일'만 말하면 오늘 이후 가장 가까운 토요일
  - '수원 1박2일' → '다음주 금요일'처럼 기간을 먼저 말해도 이어서 계산, 출발일만 바꾸면 기간 유지
  - '11월 15일 숙소는…'처럼 숙소 이야기의 날짜, '3-4명' 같은 말은 날짜로 안 읽음
- 프롬프트에 **날짜표**(오늘부터 3주, 날짜·요일) 추가 → AI가 요일을 직접 세지 않게
- 날짜가 정해졌는데 AI 답이 "언제 출발하시나요?"를 또 물으면 그 문장을 뺌
- 시험: 날짜 문장 22개 모두 맞음, 실제 GPT 대화 4가지(이번주 토요일+2박3일 / 기간 먼저 → 다음주 금요일 / 20일부터 22일까지 / 다음 주말 → 다다음주 토요일로 변경) 모두 맞음

## 2026-11-03 · 채팅 추천 카드에서 엉뚱한 장소 거르기, '역사'·'전통문화' 검색 0개 수정 — 🟩 서지윤
DB·주소·응답 키 변경 없음 → 🟦 영향 없음, pull만 하면 됨

### 1) 추천 카드 거르기 (`chat_service.search_recommendations`)
- 전에는 '해운대 해수욕장' 추천에 공중화장실·수상구조대·환전소·PC방이, '전포 카페'에 KT 대리점이 나왔음
- **여행 장소 분류만 통과**: 분류 코드 관광·문화·음식·카페·숙박, 또는 맨 앞 분류가 여행·음식점·문화,예술·스포츠,레저. 사용자가 그 종류를 직접 찾으면(예: '주차장') 통과
- 화장실·관리사무소·공공기관·금융·통신 대리점·관광안내소 등은 따로 막음 (`CARD_JUNK_KINDS`)
- '카페'·'맛집'·'숙소'처럼 종류를 말하면 카카오 분류 코드로 그 종류만 찾음 (`KIND_GROUPS`)
- 걸러 낼 것을 생각해 카카오에서 15개(최대)를 받아 고름

### 2) 🟧 `place_service.CONCEPT_QUERIES` 검색어 수정 (함수·키 변경 없음)
- '역사'(`역사 유적지`+AT4), '전통문화'(`전통 문화 명소`+AT4)가 부산·강릉에서 **0개**였음. 유적지·문화재는 카카오 분류 코드가 없는 곳이 많아서
- → '역사' = `유적지` + `문화재`, '전통문화' = `문화재` + `전통시장`(시장만), 분류 코드 없이
- 🟧 장소 검색(`search_places`)도 같은 설정을 써서 함께 좋아짐: 부산 '역사' 0개 → 해운대석각·정과정유적지·황령산 봉수대 등
- 시험: 부산·강릉 × 역사·전통문화·랜드마크 모두 4개씩, 해운대 해수욕장·전포 카페·광안리 맛집·서면 숙소·감천문화마을 관광지에 엉뚱한 장소 없음

## 2026-11-03 · 장소 사진 테이블·사진 찾기, 채팅 추천 카드에 `photo` — 🟩 서지윤

> ⚠️ **DB가 바뀌어요.** pull 뒤에 `python manage.py migrate`로 **0009**(`place_photo` 테이블 새로 만듦)를 적용하세요. 기존 테이블은 그대로예요.

### 1) 새 테이블 `place_photo` (카카오 장소 ID당 한 장)
- `kakao_id`(겹치지 않음) · `url` · `source`(`tour` 관광공사 / `kakao` 카카오 / `none` 사진 없음) · `checked_at`
- '사진 없음'도 저장해서 같은 장소를 계속 찾지 않음. 30일 지나면 다시 찾음

### 2) 사진 찾기 `services/photo_service.py` (새 파일)
- 순서: 저장된 사진 → **관광공사 TourAPI**(이름이 맞고 **300m 안**일 때만) → **카카오 이미지 검색**('이름 + 시·구'로 좁혀서) → 없음
- 함수: `get_photo(kakao_id, name, addr, lat, lon)` 장소 하나 · `attach_photos(items)` 카드 목록에 `photo` 붙이기
- 돌려주는 모양은 `mock.json`과 같음: `{"url", "source"}` 또는 `None`
- 키 `TOUR_API_KEY`·`KAKAO_REST_API_KEY`가 없거나 API가 실패해도 오류 없이 `photo: None`

### 3) 채팅 추천 카드에 `photo` 추가 (기존 키 변경 없음, 추가만)
- `chat_service.search_recommendations`가 카드마다 `photo`를 붙임 → `/travel_chat/` 응답 `recommendation.items[].photo`
- 처음 보는 장소는 카드 검색이 약 2~3초 늘어남, 한 번 찾으면 저장돼서 다음엔 0.5초
- 시험(부산 12곳): 관광공사 2 · 카카오 8 · 없음 2. 서울 좌표로 '해운대해수욕장'을 찾으면 관광공사 사진을 안 씀(다른 지역 거르기 확인)

### 🟦 요청
- [x] 추천 카드에 `photo.url` 표시, `photo`가 `null`이면 기본 이미지 (11-03 🟦 완료: 기존 대화 화면·React 둘 다, 사진이 깨져도 아이콘으로)
- [x] `source`가 `tour`이면 사진 아래 작게 **"사진: 한국관광공사"** (관광공사 사진은 출처 표시 조건) (11-03 🟦 완료)

### 🟧 참고
- 기존 `place.p_image`(일정 장소 사진, 카카오 이미지 검색)는 그대로 둠. 나중에 `get_photo`로 바꾸면 일정·리뷰 화면 사진도 같은 기준이 됨
- [ ] 🟧 서버 반영 때 `migrate` 0009

### 🟩 남은 일
- [ ] 카카오 이미지 결과는 장소 이름으로 확인할 수 없어서 가끔 다른 사진일 수 있음 → 이상한 사진이 보이면 알려 주세요
- [ ] 일정 `stops`에도 `photo` 붙이기

## 2026-11-03 · `mock.json`에 추천 카드·사진 키 추가 — 🟩 서지윤 · ⚠️ 세 사람 합의 필요
역할 분담 문서의 🟩 요청 2개(추천 카드 응답 키, 사진 응답 키)예요. **추가만** 했고 기존 키·최상위 키(`reply` `facts` `hint` `plan` `places` `transport` `budget`)는 그대로예요. 지금 `/api/chat/`은 `mock.json`을 그대로 돌려줘서 이 모양으로 화면을 먼저 만들 수 있어요.

### 1) `places` = 채팅 추천 카드 묶음 (`null` → 예시 채움)
- 묶음: `title` `anchor`(기준 장소) `day` `time` `items[]` — 실제 `/travel_chat/`의 `recommendation`과 같은 이름
- 카드 기존 키(이미 실제 채팅에서 나옴): `name` `kakao_id` `kind` `addr` `lat` `lon` `phone` `url` `distance`
- 카드 새 키:

| 키 | 모양 | 담당 | 뜻 |
|---|---|---|---|
| `photo` | `{"url", "source"}` 또는 `null` | 🟩 | 사진 1장. `source`: `tour`(관광공사) / `kakao` |
| `open` | `{"closed": bool, "reason"}` | 🟩 | 방문 날 휴무 여부. `reason`은 `excluded`와 같은 값(`weekly_off` 등) |
| `indoor` | `true` / `false` / `null` | 🟩 | 실내 장소인지 (비 올 때 대체용) |
| `review` | `{"rating", "count"}` 또는 `null` | 🟧 | 평점·리뷰 수 |
| `cost` | `{"amount", "cat", "source"}` 또는 `null` | 🟦 | 예상 비용. `stops`의 `cost`와 같은 모양 |

### 2) 사진은 어디서나 `photo` 한 키
- `plan.days[].stops[]`에도 `photo` 추가 (같은 모양). 리뷰·예산 화면에서 장소 사진도 이 키를 씀
- 사진이 없으면 키를 빼지 않고 `"photo": null` → 화면은 기본 이미지

### 3) 날씨·휴무 결과는 기존 키 그대로
- 날씨 `plan.days[].weather`, 빠진 장소 `plan.days[].excluded`, 안내 `reply.notes`

### 확인할 것
- [ ] 🟦 🟧 키 이름·모양 동의 (바꾸고 싶으면 PR 댓글로)
- [ ] 🟦 추천 카드·일정 장소에 `photo` 표시, 없으면 기본 이미지 / `review` `cost`는 값이 있을 때만 표시
- [ ] 🟧 `review` 값 채우기 (리뷰 추천) · 🟦 `cost` 값 채우기 (예산 AI)
- [x] 🟩 실제 채팅 응답에 `photo` `open` `indoor` 채우기

## 2026-11-03 · 로컬 LLM 시험 결과 공유 — 🟩 서지윤
코드·설정 변경 없음 → 🟦🟧 pull만 하면 됨. 회의 자료예요.
- 보고서: `docs/reports/local-llm-test.html` (브라우저로 열기)
- 요약: `.env`의 `AI_BASE_URL`·`AI_MODEL`만 바꾸면 Ollama로 바로 전환됨. 품질은 GPT보다 낮아서 **배포는 GPT 유지, 로컬은 개발·시연용**을 제안
- 모든 모델이 "이번주 토요일" 같은 상대 날짜를 틀림 → 🟩 코드에서 날짜 계산하도록 고칠 예정

### 회의에서 정할 것
- [ ] 로컬 LLM을 쓸지, 쓴다면 어디에(개발·시연·가벼운 작업)
- [ ] Ollama가 꺼졌을 때 OpenAI로 넘어가는 처리를 넣을지
- [ ] 계속 시험할 모델 2개 (후보: EXAONE 3.5, Llama 3.1)

## 2026-11-03 · 리뷰 게시판 메뉴·화면 틀, 홈 리뷰 추천 카드 — 🟦 임영준

### 1) 리뷰 게시판 (화면 틀만) — 🟧 `views.py`·`urls.py` 추가
- 새 화면 `templates/sherpaapp/review.html` (메뉴 + 제목만, 본문은 비어 있음)
- 🟧 **추가만**: `views.py` `review_board` (로그인 확인 후 `member`만 넘김), `urls.py` `path('review/', ..., name='review_board')`. 기존 함수·주소 변경 없음
- 사이드바 메뉴 8곳에 '리뷰 게시판' 추가 (`budget`·`chat`·`place_search`·`schedule_empty`·`travel_create`·`travel_detail`·`travel_list`·`travel_update`)
- [ ] 🟧 리뷰 목록·글쓰기·저장은 아직 없음 (`Review` 모델은 이미 있음)

### 2) 홈 '여행 리뷰 추천' 카드 (틀만) → 🟧 데이터 요청
- 넓은 화면(1281px 이상)은 소개 | 내 여행 일정 | 리뷰 추천 세 칸, 두 카드 높이 같게. 지금은 **'예시' 표시가 붙은 견본 3줄**이 나옴
- [ ] 🟧 `index` 뷰가 `review_picks`를 넘기면 견본 대신 그 목록이 나옴. 항목 키: `region`(지역)·`place`(대표 장소)·`rating`(평점 예: 4.8)·`count`(리뷰 수)·`quote`(한 줄 후기)·`url`(누르면 갈 주소). 평점 높고 리뷰 많은 순으로 몇 개
- 홈 질문 박스가 조금 넓어짐 (예시 버튼 두 개가 한 줄에)

### 3) 일정 상세 이동 카드 문구 정리
- 이동 구간 카드에서 ODsay 안내 문장 두 개 삭제 ("ODsay 기본 경로를 불러오지 못해…", "700m 이내… ODsay를 호출하지 않고…"). 시간·출발 시각·도보 표시는 그대로. 🟧🟩 영향 없음

## 2026-11-02 · 프로필 캐릭터, 내 정보 여행 기록, 일정 순서 드래그, AI 컨셉 저장 — 🟦 임영준

> ⚠️ **DB가 바뀌어요.** pull 뒤에 `python manage.py migrate`로 **0008**(`member.PROFILE_IMG` 칸 추가)을 적용하세요. 빈 값을 허용해서 기존 회원 데이터는 그대로예요.

### 1) 프로필 캐릭터 18종 — 🟧 `models.py`·`views.py` 추가
- 그림: `static/sherpaapp/avatars/<키>.svg` 18개 (곰·고양이·여우·펭귄·토끼·강아지·판다·개구리·사자·코알라·햄스터·오리·너구리·돼지·원숭이·부엉이·호랑이·양, 모두 악세서리 착용)
- `models.py` **추가만**: `AVATAR_CHOICES`·`AVATAR_KEYS`, `Member.profile_img`(DB `PROFILE_IMG`, 빈 값 허용), 속성 `member.avatar_key`(값이 없는 기존 회원은 회원번호로 정해 늘 같은 캐릭터)
- 회원가입: `join.html`에 `name="profile_img"` 라디오. `join_ok`는 **안 고르거나 목록에 없는 값이면 랜덤**으로 저장. `join` 뷰가 `avatars` 목록을 넘김
- 내 정보: 증명사진 칸에 캐릭터. 내정보 수정: 사진 칸을 누르면 고르기가 열리고, '저장하기' 때 `mypage_edit`가 저장(목록에 있는 값만)
- 확인: 고른 값 저장·안 고르면 랜덤·이상한 값 무시·수정 저장·이메일 오류 땐 저장 안 함 (트랜잭션 되돌려서 시험 회원 안 남김)

### 2) 내 정보 '여행 기록' — 🟧 `views.py` 추가
- `mypage`가 `record`도 넘김(도우미 `build_travel_record`): 완성한 여행(끝난 여행)·여행한 날(끝난 여행 날짜 합)·담은 장소(일정 장소 수)·다가오는 여행, 총 지출(`Pay` 합)·여행당 평균 지출·평균 예산(`t_budget`)·자주 간 지역(`t_place`)·자주 고른 컨셉(`TravelCategory`)
- 기존 `member` 값은 그대로

### 3) 일정 상세: 사진 없는 간단 리스트 + 꾹 눌러 순서 바꾸기 — 🟧 새 주소 추가
- `travel_detail.html`: 장소를 한 줄 리스트로, 누르면 펼쳐져 사진·주소·체류시간·삭제, **0.25초 꾹 눌러 드래그**로 순서 변경
- 🟧 `views.py`·`urls.py` **추가만**: `POST /schedule_place_reorder/` (`sp_ids`=그날 장소 sp_id를 새 순서대로 쉼표로). 로그인·본인 여행·그날 장소 전부인지 확인(401/403/409/400), `visit_order` 다시 매기고 `recalculate_schedule_timeline`으로 시간 다시 계산. 첫 장소 도착 시각은 유지
- 응답: `{"success": true, "message": "순서를 바꿨습니다."}` (실패는 `success: false` + `message`)

### 4) AI 대화 컨셉이 저장 안 되던 문제 — 🟩 `services/chat_service.py` 수정 (응답 키 변경 없음)
- '수원 랜드마크 1박2일'처럼 다른 말과 섞이거나 '랜드마크'만 답해도 `categories`에 들어가게: 규칙 4에 예시 추가, AI가 빠뜨리면 서버가 사용자 말에서 DB 컨셉 이름을 찾음(`match_categories`·`guess_categories`, '빼줘·말고' 같은 말이 있으면 안 함)
- 컨셉 이름이 숙소·출발지로 잘못 들어가면 걸러냄, 컨셉이 정해졌는데 다시 묻는 문장은 지움, 새로 정해지면 "여행 컨셉은 '랜드마크'(으)로 반영했어요." 덧붙임
- 진짜 AI로 확인: 첫 문장에 섞어 말한 경우·마지막에 따로 답한 경우 모두 저장

## 2026-11-02 · 홈 '내 여행 일정'을 카드 목록으로 — 🟦 임영준
- 홈 오른쪽: 최근 일정 하나 → **최근 여행 4개 카드** (날짜·기간, D-day/여행 중/다녀옴, 장소 앞 3곳 +N, 누르면 상세)
- 🟧 `views.py` **추가만**: `index`가 `recent_travels`(카드용 목록)도 넘김, 도우미 `_home_trip_card` (기존 `_build_recent_travel` 재사용). 기존 `recent_travel`·함수 변경 없음
- 🟩 영향 없음
- **내 정보 이메일 등록·변경** (🟧 할 일을 함께 처리): `mypage_edit` 폼에 `name="email"` 추가, `views.py` `mypage_edit`가 이메일 저장
  - 형식 검사(`validate_email`), 다른 회원과 중복이면 저장 안 하고 오류 문구, **빈칸이면 기존 값 유지**(아이디 찾기에 필요해서 지우지 않음)
  - 내 정보 카드 폭 600→680px, 긴 이메일은 줄바꿈
  - 확인: 형식 오류·중복·등록·빈칸 유지·등록 후 아이디 찾기 (트랜잭션 되돌려서 시험 회원 안 남김)

## 2026-11-02 · 아이디/이메일 템플릿, 회원가입 성별·나이대, AI 대화 개선, React 채팅 전체, 하늘 배경 — 🟦 임영준

### 1) 아이디·이메일 분리 템플릿 (바로 아래 🟧 항목의 🟦 몫)
- `login.html` 아이디 칸 `name="user_id"` · `join.html` 아이디 칸 `user_id` + 중복확인 `?user_id=` + **이메일 칸 `email` 추가(필수)** · `idpw.html` 아이디 찾기 = 이름+이메일, 비밀번호 찾기 = **아이디+이메일+이름**(서버가 이름도 확인해서 남김) · `mypage*.html` 아이디/이메일 따로 (이메일 없으면 "미등록")
- 확인: 아래 항목 표의 10가지 모두 기대 결과대로 (시험 계정은 트랜잭션 되돌려서 DB에 안 남김)

### 2) 회원가입 성별·나이대·[선택] 동의 화면 (회의 안건 8) → 🟧 저장 요청
- 새 입력칸: `gender` (`""`·`M`·`F`) · `age_group` (`""`·`10`~`60`) · `agree_profile` (동의했을 때만 `"1"`)
- 화면 규칙: 성별·나이대를 골랐는데 동의 안 하면 막음, **[필수] 만 14세 이상** 체크(서버로 안 보냄)
- [x] 🟧 `join_ok`가 성별·나이대 저장 (11-02): `agree_profile == "1"`일 때만 `gender`(M/F)·`age_group`(10·20·…·60) 저장. 동의 안 함·선택 안 함·이상한 값(성별 X, 나이대 15·글자)은 빈 값(NULL)으로, 가입은 그대로 됨 — 8가지 경우 시험 통과

### 3) AI 대화 개선 — 🟩 `services/chat_service.py` 수정 (응답 키 변경 없음)
- 예산 성향 질문 없앰: `budget_style`은 키는 그대로 두고 **항상 null**, 예산은 총예산만 물음
- 지역이 저장 안 되던 문제: AI가 지역을 `stays`에 넣던 것 → 규칙 2-1·예시 추가 (지윤 님 규칙 문장과 **둘 다 남김**)
- AI가 이미 정한 값을 빼먹어도 이전 값 유지 (`_keep_previous`)
- 다음 질문이 끊기던 문제: `next_question()` (지역→날짜→컨셉→숙소→출발지·시각→이동수단)을 프롬프트에 넣고, 답에 질문이 없으면 서버가 덧붙임 (추천 카드 있을 땐 안 붙임). 화면용 `hint` 키는 그대로
- 출발 시각이 저장 안 돼 '첫날은 어디에서 몇 시쯤…' 질문이 반복되던 문제: 규칙 2-2(출발지·시각 함께, `'아침8시'→'08:00'`) 추가, AI가 빠뜨리면 출발을 말한 문장에서 시각을 읽음(`guess_start_time`, 숙소 도착 시각 등은 무시), 출발지만/시각만 비면 그것만 묻도록 질문 나눔
- 진짜 AI로 확인: '수원 1박2일' → '11월10일' → '랜드마크랑 음식' 순서로 지역·날짜·컨셉이 저장되고 질문이 이어짐

### 4) 여행 만들기 미리보기 지도: 대중교통이면 ODsay 실제 경로
- `travel_create.html`의 `#tcApp`에 `data-odsay-key` 추가 (일정 상세와 같은 웹 키)
- 구간마다 1건, **받은 구간은 localStorage에 저장**해서 다시 안 부름, 700m 이내는 부르지 않음. ⚠️ ODsay 무료 한도(30건)는 일정 상세와 같이 씀

### 5) React 채팅 `/chat/` — 기존 대화창 전체를 React로
- 위 10-30 🟦 항목의 1단계 → 이제 대화·추천 카드·초안·미리보기·지도(ODsay)·적용하기까지 옮김. 서버 주소는 기존과 같음(`/travel_chat/` 등)
- 기존 여행 만들기 화면은 그대로. 교체는 회의에서 정하기

### 6) 여행 만들기·일정 관리·비용 관리 배경 (디자인만)
- `main`에 `trip-sky` 클래스 → 홈과 같은 하늘·구름·산·빌딩·비행기, 카드는 반투명 유리판. 🟧🟩 영향 없음

## 2026-11-02 · 아이디와 이메일 분리, ID/PW 찾기 방식 변경 — 🟧 이수한 (🟦 템플릿 변경 필요)
지금까지 "아이디(이메일)"였지만 실제로는 이메일이 아닌 단순 아이디로도 가입이 돼서, **아이디와 이메일을 따로** 받도록 바꿔요.

> ⚠️ **백엔드가 main에 먼저 병합됐어요.** 🟦 템플릿이 바뀔 때까지 main을 pull한 로컬에서는 **로그인·가입·ID/PW 찾기가 안 돼요** (폼이 아직 `name="email"`로 보내서). 배포 서버에는 템플릿까지 바뀐 뒤 함께 반영해요. pull 뒤에는 `python manage.py migrate`로 0005~0007을 적용하세요.

| | 전 | 후 |
|---|---|---|
| 아이디 | `Member.email` (DB 컬럼 `ID`) | **`Member.user_id`** (DB 컬럼 `ID` 그대로, 데이터 그대로) |
| 이메일 | 없음 | **`Member.email`** 새 칸 (DB 컬럼 `EMAIL`, 중복 금지, 기존 회원은 빈 값) |
| 아이디 찾기 | 이름 + 닉네임 | **이름 + 이메일** |
| 비밀번호 찾기 | 아이디 + 이름 | **아이디 + 이메일** (이름은 그대로 받아도 되고, 안 써도 됨) |

- 마이그레이션 `0005`(이름만 바꾸기, DB 변화 없음) · `0006`(이메일 형식 검사 제거, DB 변화 없음) · `0007`(`EMAIL` 칸 추가)
- 백엔드 시험 완료: 아이디 중복·이메일 중복 가입 막기, 로그인, 아이디 찾기, 비밀번호 찾기, 내 정보 (새 폼 이름 기준)

### ⚠️ 폼 이름이 바뀌어요 → 🟦 템플릿을 같이 바꿔야 로그인·가입이 돼요
**아이디를 보내는 칸은 `name="user_id"`, 이메일 칸은 `name="email"`**로 바꿔요. 백엔드 PR과 🟦 템플릿 PR은 **같은 날 함께 병합**해요 (한쪽만 병합되면 로그인·가입이 안 됨).

| 파일 | 바꿀 것 |
|---|---|
| `sherpaapp/login.html` | 아이디 칸 `name="email"` → **`name="user_id"`** (57줄, 스크립트의 `f.email`도 `f.user_id`), 라벨·안내 "아이디(이메일)" → **"아이디"**, 이메일 모양 placeholder 정리 |
| `sherpaapp/join.html` | 아이디 칸 `name="email"` → **`name="user_id"`** (82줄), 중복 확인 주소 `?email=` → **`?user_id=`** (186줄, 주소 이름 `check_email`은 그대로), 스크립트 `f.email` → `f.user_id`, 안내 "이메일 중복확인" → "아이디 중복확인". **이메일 칸 새로 추가 `name="email"`** (필수, 이메일 형식) |
| `idpw.html` 아이디 찾기 | 닉네임 칸(117줄 `name="nickname"`) → **이메일 칸 `name="email"`**. 이름 칸(`name="name"`)은 그대로 |
| `idpw.html` 비밀번호 찾기 | 138줄 칸을 **아이디 칸 `name="user_id"`**로 (placeholder "아이디"), **이메일 칸 `name="email"` 추가**. 이름 칸은 남겨도 되고 빼도 됨 |
| `mypage.html` | 64줄 `{{ member.email }}`(아이디 자리) → **`{{ member.user_id }}`**, 이메일 줄 추가 `{{ member.email\|default:"미등록" }}` |
| `mypage_edit.html` | 68줄 아이디 표시 → **`member.user_id`**. 이메일 수정 칸은 🟧가 `mypage_edit` 저장 처리를 만든 뒤에 추가 |

### 🟦 템플릿 고친 뒤 확인하는 법
백엔드 변경은 main에 병합됐지만 `front` 브랜치에는 아직 없어요. **시험용 브랜치에서 합쳐 보고**, PR은 `front`에서 템플릿만 올려요 (`front`에 `back`을 직접 합치면 PR에 백엔드 커밋이 섞여요).

1. 템플릿 변경을 `front`에 먼저 커밋한 뒤, 시험용 브랜치 만들기
   ```
   git fetch origin
   git switch -c try-idpw origin/front
   git merge origin/back
   ```
2. 가상환경을 켜고 `pj_django` 폴더에서 `python manage.py migrate` → `0005`~`0007`이 `OK`
   - "테이블이 이미 있다" 오류가 나면 `python manage.py migrate sherpaapp --fake-initial` 먼저 하고 다시 `migrate`
3. `runserver` 켜고 화면에서 확인

| # | 할 것 | 기대 결과 |
|---|---|---|
| 1 | 가입: 이메일 모양이 **아닌** 아이디(예 `testjun`) + 이메일 | 아이디 중복 확인 통과 → "회원가입이 완료되었습니다!" |
| 2 | 같은 아이디로 다시 가입 | "이미 사용 중인 ID입니다." |
| 3 | 다른 아이디 + **같은 이메일**로 가입 | "이미 사용 중인 이메일입니다." |
| 4 | 로그인 (라벨이 "아이디"인지도) | 홈으로 이동 |
| 5 | 틀린 비밀번호로 로그인 | "비밀번호가 틀렸습니다." |
| 6 | 내 정보 | 아이디와 이메일이 **따로** 보임 |
| 7 | 아이디 찾기: 이름 + 이메일 | "회원님의 아이디는 testjun 입니다." |
| 8 | 아이디 찾기: 틀린 이메일 | "일치하는 회원정보가 없습니다." |
| 9 | 비밀번호 찾기: 아이디 + 이메일 + 새 비밀번호 | "비밀번호가 변경되었습니다." → 새 비밀번호로 로그인 |
| 10 | 비밀번호 찾기: 틀린 이메일 | "일치하는 회원정보가 없습니다." |

- 노란 Django 오류 화면이 나오면 대부분 `name=` 이름이 달라서예요. F12 → **Network** → 보낸 요청의 **Payload**에 `user_id`·`email`이 들어 있는지 확인
4. 끝나면 `git switch front`로 돌아가 템플릿 PR을 올리기 (백엔드는 이미 main에 있음). 시험 브랜치는 `git branch -D try-idpw`로 지워도 됨

### 남은 일
- [x] 🟧 백엔드 main 병합 (PR #20)
- [x] 🟦 위 템플릿 변경 → PR (바로 위 11-02 🟦 항목, 시험 10가지 통과)
- [x] 🟧 내 정보 수정에서 이메일 등록·변경 (기존 회원은 이메일이 비어 있어서 아이디 찾기를 못 함) → 🟦가 함께 처리 (11-02 홈 카드 항목 아래 참고)
- [ ] 🟧 (선택) 비밀번호 찾기에 이메일 인증 코드 추가 — 지금은 아이디+이메일만 알면 바꿀 수 있음
- [ ] 🟧 병합 후 서버 반영 (`migrate`로 0005~0007 적용)

## 2026-10-30 · 남은 일 역할 재분배 제안 (기능별 담당) — 🟧 이수한 · ✅ 11/03 결정
코드·DB·주소 변경 없음. **11/03에 동의해서 확정했어요.** 최종 분담과 체크리스트는 맨 위 "2026-11-03 · ✅ 결정: 기능별 역할 분담" 항목을 보세요 (카테고리 예산 저장 API → 🟦, 장소 사진·정보 API → 🟩로 옮김).

### 왜 바꾸나
- 지금은 층(🟦 화면 / 🟧 서버 / 🟩 AI)으로 나뉘어서, AI 코드가 `chat_service.py` 한 파일에 모이고 AI를 만지는 사람이 한 명뿐
- AX 프로젝트라 포트폴리오·면접에서 **세 사람 모두 "내가 만든 AI 기능"**을 말할 수 있어야 함
- 필수 조건인 **React가 아직 코드에 없음**

### 원칙
- **기능 단위로 나눔**: 각자 AI 기능 하나를 **화면(React) → API → AI**까지 끝까지 맡음
- 한 사람만 할 수 있는 일(서버 배포, 공통 레이아웃)은 지금 담당이 계속
- AI 코드는 **기능별 파일로 분리**: `chat_service.py`(일정 에이전트), `review_service.py`(리뷰 추천), `budget_service.py`(예산 AI) → 같은 파일 충돌 방지
- 세 기능 모두 결국 **채팅 추천 카드**로 모이므로, 연결 응답 키는 지금처럼 `mock.json`에 먼저 정하고 시작

### 🟩 서지윤 — 대화형 일정 에이전트
- [ ] 지금 채팅(`run_chat_turn`)을 LangChain **도구 호출** 방식으로 확장
- [ ] 비 예보면 실내 장소로 대체 (날씨 API 도구)
- [ ] 방문 날짜에 휴무인 장소 제외
- [ ] 숙소 미정이면 숙소 추천
- [ ] 부산 장소 표(`docs/data/busan_spots_draft.csv`)를 추천 후보 데이터로 연결
- 포트폴리오: LLM 에이전트 + 외부 API 도구 연동

### 🟧 이수한 — 리뷰 기반 추천
- [ ] 리뷰 API (목록·쓰기·도움돼요·장소별 평균). 테이블은 이미 있음
- [ ] 리뷰 게시판 화면을 **React**로 직접 구현
- [ ] LLM으로 장소별 리뷰 키워드 요약
- [ ] 추천 점수(평점·리뷰 수·키워드) 계산, **같은 성별·나이대 리뷰에 가중치** → 맞춤 추천
- [ ] 점수를 채팅 추천 카드 순서에 반영
- [ ] 계속 담당: 서버 배포, 장소 `kakao_id` 저장, 장소 사진·정보 API
- 포트폴리오: 데이터 설계 → LLM 요약·추천 순위 → 배포

### 🟦 임영준 — 예산 AI
- [ ] 장소·이동 비용 추정 (6개 분류 `sight` `food` `move` `stay` `shop` `etc`)
- [ ] 카테고리 예산을 넘으면 **같은 분류의 더 싼 대안** 제안
- [ ] 이동수단별 가격 비교
- [ ] 카테고리 예산 화면을 **React**로 구현
- [ ] 계속 담당: 반응형 공통 레이아웃(폰 탭바·태블릿 배치), 장소 선택 시 지도 이동·팝업
- 포트폴리오: 비용 예측·대안 추천을 화면까지 연결

### 회의에서 정할 것
- [x] 위 분담 동의 여부, 바꿀 부분 → 11/03 동의, 일 두 개 옮김
- [x] React를 어떻게 넣을지 → 🟦가 `frontend/`(Vite)에서 빌드해 `static/chat/`에 넣는 방식으로 `/chat/` 화면부터 붙임 (10/30)
- [ ] 세 기능이 추천 카드에 함께 쓰는 응답 키 (`mock.json`)

## 2026-10-30 · React 채팅 화면 `/chat/` 추가 (기존 AI 대화창을 React로 옮김) — 🟦 임영준
- 리포 최상위에 **`frontend/`** (Vite + React) 추가. 기존 여행 만들기 대화창(대화·추천 카드·일정 초안·미리보기·지도·ODsay 경로·적용하기)을 React 부품으로 옮김
- 서버는 **기존과 같은 진짜 AI 주소**(`/travel_chat/`·`_preview/`·`_apply/`)를 씀. 주소 호출은 `frontend/src/lib/api.js` 한 곳 → 나중에 `/api/chat/`(mock.json 모양)으로 바꿀 때 이 파일만 고치면 됨
- `npm run build` 결과가 **`sherpaapp/static/chat/chat.js`·`chat.css`** 로 나옴 (이름 고정). 배포 서버엔 Node가 없어서 **빌드 결과도 함께 커밋**
- 🟧 파일에 추가만 함: `urls.py`에 `chat/`(`name='chat_page'`), `views.py`에 `chat_page`(로그인 안 했으면 로그인 화면으로). 기존 주소·함수 변경 없음
- 새 템플릿 `templates/sherpaapp/chat.html` (`#root` + `{% static 'chat/chat.js' %}`)
- 기존 채팅 화면(`travel_create`, `travel_chat.js`)은 **그대로**. React 버전이 다 될 때까지 따로 시험

### 개발할 때 (🟦)
- Django는 **`http://localhost:8000`**, Vite는 `frontend`에서 `npm run dev` → **`http://localhost:5173`** (둘 다 `localhost`로 열어야 로그인 쿠키 공유)
- Vite proxy가 `/api`를 8000으로 넘기고, `Origin`을 8000으로 바꿔 보냄 (안 바꾸면 CSRF 403)
- 화면을 고친 뒤 Django에서 보려면 `npm run build` 다시 실행

### 🟧🟩
- 영향 없음. 배포 때는 커밋된 `static/chat/`이 `collectstatic`으로 그대로 나감

## 2026-10-30 · `.env.example` 추가, 관광공사 키, 장소 카카오 ID 응답 추가 — 🟧 이수한
장소 사진을 정확하게 보여 주기 위한 준비 단계예요. 사진은 앞으로 **카카오 장소 ID 기준**으로 찾아 저장해요 (① 한국관광공사 TourAPI 공식 사진 → ② 없으면 카카오 이미지 검색을 엄격하게 → ③ 애매하면 사진 없음·기본 이미지).

- **`pj_django/.env.example` 새로 만듦**: `settings.py`가 읽는 환경 변수 24개와 설명. 실제 값은 없음
  - 자기 `.env`와 비교해서 빠진 이름이 있는지 확인. 값은 개인 메시지로 받기
  - ⚠️ `이름=`처럼 **빈 값으로 두면 기본값이 아니라 빈 값**이 됨(`AI_TIMEOUT=`은 오류). 기본값을 쓰려면 예시처럼 `#`을 붙인 채로 둠
- **새 키 `TOUR_API_KEY`** (관광공사 TourAPI, 서버에서만 사용): 없어도 Django는 켜지고 장소 사진만 안 나옴
- **응답에 `kakao_id` 추가** (기존 키 변경 없음, 추가만)
  - `place_service.to_place` → 장소 검색 결과
  - `chat_service.search_recommendations`의 채팅 **추천 카드** → 🟩 파일이라 알림: 776줄 아래 `'kakao_id': doc.get('id')` 한 줄만 추가

### 🟦 요청 (장소에 카카오 ID 저장)
- [ ] 추천 카드를 일정 핀으로 옮길 때 카드의 `kakao_id`를 핀에 같이 담아 보내기 (채팅 '적용하기')
- [ ] 일정 상세 장소 직접 추가 폼에 숨은 칸 `place_kakao_id` 추가 (카카오 검색으로 고른 장소의 `kakao_id`)
- 백엔드는 위 값이 오면 `place.p_kakao_id`에 저장하도록 이어서 작업함

### 남은 일
- [ ] 🟧 장소 저장 두 곳에서 `p_kakao_id` 저장
- [ ] 🟧 사진 테이블(카카오 ID당 한 장) + 사진 찾기(관광공사 → 카카오) + 장소 정보 API에 사진 1장
- [ ] 🟧 서버 `.env`에 `TOUR_API_KEY` 넣기

## 2026-10-30 · 관리자 화면에 새 테이블·칸 추가 — 🟧 이수한
`admin.py`만 바뀜. DB·주소·응답 키 변경 없음 → 🟦🟩 영향 없음, pull만 하면 됨
- 회원: 목록에 성별·나이대 칸, 오른쪽 필터 추가
- 장소: 목록·검색에 카카오 장소 ID
- 여행 상세: 아래에 **분류별 예산** 표(분류·금액)를 바로 넣고 고칠 수 있음
- 리뷰: 새 메뉴. 목록(번호·장소 이름·회원·별점·한 줄·작성일), 별점·작성일 필터, 장소 이름·내용·카카오 ID·회원 이메일 검색, 최신순. 작성일은 고칠 수 없음
- 관리자 주소: `/admin/` (Django 관리자 계정 필요. 서버는 DB를 새로 만들어서 계정을 다시 만들어야 함)

### 남은 일
- [ ] 🟧 서버에 관리자 계정 만들기(`createsuperuser`)
- [ ] 🟧 (선택) 도움돼요 관리 화면, 리뷰 목록에 도움돼요 수 표시

## 2026-10-30 · 회원 선택 컬럼·카테고리 예산·리뷰 테이블 추가 (안건 2·4·8) — 🟧 이수한
DB 칸만 만든 단계예요. 화면·API는 아직 없음.

| 테이블 | 바뀐 것 |
|---|---|
| `member` | `GENDER`(`M` 남성 / `F` 여성), `AGE_GROUP`(`10`~`60`, 60은 60대 이상). 둘 다 선택이라 빈 값 가능 |
| `travel_budget` (새) | 여행별 분류 예산: `T_ID`, `CATEGORY`(`sight` `food` `move` `stay` `shop` `etc`), `AMOUNT`. 여행+분류 중복 금지. `mock.json`의 `budget.limit`이 여기서 나옴 |
| `place` | `P_KAKAO_ID` 추가 (카카오 장소 ID). 리뷰를 **같은 실제 장소끼리 묶는 기준** |
| `review` (새) | `M_ID`, `P_ID`, `KAKAO_ID`·`PLACE_NAME`(장소 정보 복사), `RATING`(1~5), `CONTENT`(한 줄 100자), `TAGS`(목록), `CREATED_AT`. 회원+장소 중복 금지 |
| `review_helpful` (새) | 도움돼요: `M_ID`, `RV_ID`. 회원+리뷰 중복 금지 |

- 리뷰는 여행을 지워도 남음: 장소 칸만 빈 값이 되고, 복사해 둔 카카오 ID·장소 이름으로 게시판에 계속 보임
- **카카오 장소 ID가 있는 장소만 리뷰 가능**으로 갈 예정. 지금은 장소를 저장할 때 ID가 안 들어감 → 아래 남은 일

### 🟦🟩 pull 뒤 할 일
가상환경을 켜고 `pj_django` 폴더에서 `python manage.py migrate` (0002~0004가 `OK`로 적용되면 끝)

### 남은 일
- [ ] 🟧 `place_service.to_place`에 카카오 `id` 포함 → 추천 카드·핀에 `kakao_id`가 실림
- [ ] 🟦🟧 장소 저장 두 경로에 카카오 ID 전달·저장: ① 일정 상세 장소 직접 추가 폼(`place_kakao_id` 숨은 칸 예정) ② 채팅 '적용하기' 핀
- [ ] 🟧 리뷰 API(목록·쓰기·도움돼요·장소별 평균), 카테고리 예산 저장 API
- [x] 🟧 관리자 화면 등록 → 위 항목
- [x] 🟧 서버 반영(`deploy.sh`의 `migrate`로 0002~0004 적용, 서버 데이터 유지)

## 2026-10-30 · 로그인·로그아웃 성공 팝업 없애고 바로 이동 — 🟦 임영준
- `views.py`(🟧 파일)의 `login_ok` 성공 두 곳과 `logout`에서 `alert('로그인되었습니다.')`·`alert('로그아웃되었습니다.')` 스크립트 응답을 **`redirect('index')`로 바꿈** (팝업 없이 바로 홈)
- 비밀번호 틀림·없는 이메일 안내 팝업은 **그대로**. 세션 키(`login_ok_user`), 주소, 함수 이름 변경 없음
- 🟧 `views.py`의 `login_ok`·`logout`을 고치고 있었다면 pull 후 이 부분만 확인 · 🟩 영향 없음

## 2026-10-30 · 모든 모델 `managed=True` 전환 + 마이그레이션 새로 시작 (안건 1) — 🟧 이수한
- **이제 모든 테이블을 Django 마이그레이션으로 관리함.** 컬럼을 바꿀 때는 `models.py` 수정 → `makemigrations` → `migrate`
- 옛 마이그레이션(`0001`, `0002`)은 현재 모델과 30곳 가까이 달라서 지우고, **현재 모델로 `0001_initial`을 새로 만듦**
- 모델을 실제 DB(`Create Table.sql`)와 똑같이 맞춤 → **로컬 DB 구조·데이터는 그대로**
  - `Member.email` 길이 100 + 중복 금지, `Travel`의 지역·제목·시작일·종료일 NOT NULL, `Place.p_addr` 255·NULL 허용, `Place.p_image` 긴 글(TextField), `Pay` 내용 255·금액·날짜 NOT NULL
  - `Schedule`에 여행+날짜 중복 금지 추가(DB에 원래 있음), `SchedulePlace`의 방문 순서 중복 금지는 삭제(DB에 없음. 있으면 순서 바꾸기에서 MariaDB 오류)
- 컨셉 9개 기초 데이터 파일 추가: `sherpaapp/fixtures/categories.json` (새 DB에서 `loaddata categories`로 넣음)

### 🟦🟩 pull 뒤 한 번만 할 일
가상환경을 켜고 `pj_django` 폴더에서:
```
python manage.py migrate sherpaapp --fake-initial
python manage.py makemigrations --check
```
- 첫 줄은 `Applying sherpaapp.0001_initial... FAKED`가 나오면 성공 (테이블이 이미 있으니 기록만 남김, 데이터 그대로)
- 둘째 줄은 `No changes detected`가 나오면 끝
- 오류가 나면 그대로 🟧에게 보내 주세요. **`migrations/` 파일을 직접 지우거나 고치지 마세요**
- 앞으로 `models.py`를 바꾸는 사람은 `makemigrations`로 만든 파일도 **같이 커밋**

### 확인된 점 / 남은 일
- [x] 로컬: `--fake-initial` FAKED, `makemigrations --check` 변경 없음, `manage.py check` 통과
- [ ] 🟧 서버 DB 새로 만들기: 비우고 `migrate` → `loaddata categories` (빈 대문자 테이블도 함께 정리)
- [ ] 🟧 이 위에 리뷰·카테고리 예산 테이블, 회원 선택 컬럼을 마이그레이션으로 추가

## 2026-10-30 · 모델 테이블 이름 소문자로 통일 (배포 서버 컨셉 저장 안 되던 문제) — 🟧 이수한
- 증상: 배포 주소의 AI 채팅에서 컨셉을 말하면 "반영했어요"라고 답하지만 일정 초안의 컨셉 칸이 비어 있음 (로컬은 정상)
- 원인: **서버(리눅스) MariaDB는 테이블 이름의 대소문자를 구분**함. 모델은 `CATEGORIES`를 읽는데 실제 데이터는 `categories`에 있어서, 서버에서는 컨셉 목록이 빈 것으로 보였음. 윈도우는 구분하지 않아서 로컬에서는 드러나지 않음
- 변경: `models.py`의 `db_table` 6개를 실제 테이블 이름으로 통일 → `categories`, `travel_category`, `place`, `schedule`, `schedule_places`, `pay` (DB 구조·데이터·응답 키 변경 없음)
- 앞으로 테이블 이름은 **소문자**로 씀 (`Create Table.sql`과 같게)
- 마이그레이션 파일은 만들지 않음 (`managed=True` 전환 때 함께 정리)

### 확인된 점 / 남은 일
- [x] 로컬 `manage.py check` 통과, 6개 테이블 모두 기존 데이터 그대로 조회
- [x] 🟧 병합 후 서버 반영 → 서버에서 컨셉 9개 정상 조회 (배포 주소 화면 확인은 남음)
- [ ] 🟧 서버에 남은 빈 대문자 테이블(`CATEGORIES`, `PLACE` 등) 정리 → 위 서버 DB 새로 만들 때 함께
- [ ] 🟦🟩 영향 없음. pull만 하면 됨

## 2026-10-30 · Django 실제 배포 + HTTPS — 🟧 이수한
- **배포 주소: https://3-106-104-143.sslip.io/** (`http://3.106.104.143`으로 들어와도 이 주소로 자동 이동)
  - 도메인이 없어서 IP를 이름으로 바꿔 주는 무료 주소(sslip.io)에 **Let's Encrypt 인증서**를 붙임(자동 갱신). 도메인을 사면 그 주소로 바꿈
- 서버 구성: nginx(HTTPS, 정적 파일) → gunicorn(3개) → Django, DB는 **서버 안 MariaDB 10.11**(`sherpa_schema`)
- 서버 DB에는 **테이블 구조와 분류(categories) 기초 데이터만** 넣음. 회원·여행 테스트 데이터는 옮기지 않음 → **배포 주소에서는 회원가입부터** 해서 시험
- 코드 반영: `main`에 합쳐진 코드를 서버 담당(🟧)이 `~/deploy.sh`로 반영 (받기 → 패키지 → `migrate` → 정적 파일 → 재시작). **main 병합만으로 자동 반영되지는 않음**
- 서버 `.env`는 서버 전용 값(DB 비밀번호, 새 SECRET_KEY, 허용 주소, HTTPS 쿠키)으로 따로 관리. 팀원 `.env`와 다름

### 확인된 점 / 남은 일
- [x] 메인·로그인 화면 200, 정적 파일, HTTPS 로그인 폼(CSRF) 정상
- [x] 🟧 카카오 개발자 콘솔 JavaScript SDK 도메인에 `https://3-106-104-143.sslip.io` 등록 (배포 주소에서 지도 SDK 로드 확인)
- [x] 🟧 **ODsay** 웹 키에 `3-106-104-143.sslip.io` URI 등록 (일정 상세의 대중교통 경로를 브라우저에서 부르므로 필요)
- [ ] 🟧 `settings.py`: 지금은 `DEPLOY=True`면 SQLite를 써서, 서버는 `DEPLOY=False`+`DEBUG=False`로 우회 중 → **DEPLOY=True에서 MariaDB를 쓰도록 수정** (인수인계 문제 3번), 프록시 HTTPS 인식 설정 추가
- [ ] 🟧 `makemigrations` 경고: 모델 변경이 마이그레이션에 없음 → 안건 1(`managed=True` 전환) 때 함께 정리. 전환 후 서버 DB는 비우고 `migrate`로 새로 만듦
- [ ] 🟦🟩 배포 주소에서 화면·AI 채팅 동작 확인 (AI 키는 서버 `.env`에 들어 있음)

## 2026-10-30 · AWS 빈 화면 배포 (1주차 목표) — 🟧 이수한
- 배포 주소: **http://3.106.104.143/** ("TRIPA 배포 준비 중" 화면. 아직 Django는 연결 전)
- AWS: 이수한 계정, **무료 플랜**(크레딧 소진 전엔 과금 없음), 리전 **시드니 `ap-southeast-2`** (새로운 AWS 경험은 프로젝트 리전 하나만 사용 가능 → 서울 불가, 수업 기간엔 그대로 사용)
- 서버: EC2 t3.small · Ubuntu 24.04 · nginx, 고정 IP. 요금 알림 설정 완료
- SSH 접속은 서버 담당(🟧)만. 키와 계정 정보는 공유하지 않음

### 다음 단계
- [ ] 🟧 Django + gunicorn 연결, 서버용 DB(MariaDB) 결정·설치, `.env` 서버 설정
- [ ] 🟧 카카오 개발자 콘솔 JavaScript SDK 도메인에 `http://3.106.104.143` 등록 (도메인 생기면 교체)
- [ ] 🟧 도메인 + HTTPS(Let's Encrypt) — PWA·앱 확장에 필요
- [ ] 🟦🟩 영향 없음. Django 연결 후 배포 주소에서 화면·AI 동작 확인 예정

## 2026-10-30 · 회의 결정 사항 (안건 1~9) — 🟧 이수한 정리
| 안건 | 결정 | 할 사람 |
|---|---|---|
| 1. `managed=False` 테이블 | **`managed = True`로 전환**, 이후 컬럼 변경은 `makemigrations`·`migrate`로 | 🟧 (전환 후 모두 `migrate`) |
| 2. 리뷰 테이블 | 계획의 `spot_feedback`과 **하나로 합침** (회원·여행·장소·별점·한 줄·태그·작성일, 방문 인증 = 적용한 여행의 장소만) | 🟧 테이블·API, 🟦 게시판, 🟩 추천 점수 |
| 3. 비용 분류 키 | **기존 코드의 6개**로 통일: `sight` `food`(카페 포함) `move` `stay` `shop` `etc`. **`mock.json` 수정함** (`budget.limit`·`budget.by`) | 모두 |
| 4. 카테고리 예산 저장 | **여행별 카테고리 예산 테이블**(여행, 분류, 금액) | 🟧 |
| 5. 채팅 주소 | 적용 전 대화는 `POST /api/chat/` (id 없음) 확정 | 확인 완료 |
| 6. 임시 저장 회원별 분리 | 🟦 확인 완료 | 🟦 |
| 7. 장소 검색 | `place_search` 화면·주소 **삭제**. 대신 채팅 추천 카드에서 **사진 제거**, 장소를 고르면 **지도를 그 장소로 가운데 이동 + 사진·정보 카드 팝업** (목업 '채팅 + 일정') | 🟦 화면, 🟧 삭제·장소 정보 제공 |
| 8. 성별·나이대 | **선택 항목**으로 변경(필수 아님). "알려주면 맞춤 추천" 안내 문구, 넣으면 [선택] 동의 필요, 내 정보에서 수정·삭제 가능 (목업 '회원가입') | 🟦 화면, 🟧 저장(비워도 가입) |
| 9. 배포 | AWS는 **이수한 계정**, 요금 알림 설정, 배포 주소 정해지면 카카오 지도 도메인 등록 | 🟧 |

### 🟦 프론트
- [ ] 목업과 실제 화면의 분류 이름은 위 6개 기준 (목업 '카테고리 예산'의 `카페`·`입장` 표기는 예시)
- [ ] 채팅 추천 카드 사진 제거, 카드 선택 → 지도 가운데 + 팝업 (사진은 **고른 장소만** 불러오기: 카카오 이미지 검색 횟수 절약)
- [ ] 회원가입·내 정보: 성별·나이대 `(선택)` 표시, 혜택 안내, [선택] 동의

### 🟧 백엔드
- [ ] `managed=True` 전환 → 리뷰·카테고리 예산·회원 선택 컬럼 추가
- [x] `place_search`·`place_search_search` 주소·뷰·템플릿 삭제 (남은 `{% url 'place_search' %}` 없는지 확인) → ✅ 11/10 삭제 (🟧)
- [ ] 팝업용 장소 정보(사진 1장·주소·영업시간·게시판 평점)를 **고른 장소 하나만** 돌려주는 API

### 🟩 AI
- [ ] 금액 추정·분류를 6개 키로 (`cafe`·`ticket` 쓰지 않음)

## 2026-10-29 · 채팅 응답에 `hint` 추가 — 🟩 서지윤
- `travel_chat/` 응답에 `hint` 키 **추가** (기존 `missing`·`ready`는 그대로)
- 값: `region`(지역) → `date`(날짜) → `concept`(컨셉) → `stay`(숙소 부족) → `arrival`(첫날 출발 시각) → `done`. 가장 먼저 물어볼 빈 항목 하나
- `stay`·`arrival`은 비어 있어도 `ready`에는 영향 없음 (적용 버튼은 지금처럼)
- 🟦 입력창 안내 문구를 `hint` 값별로 만들어 쓰면 됨 (문장은 화면이 언어별로) · 🟧 영향 없음

## 2026-10-29 · `mock.json`을 돌려주는 API 주소 추가 — 🟧 이수한
가이드 🟧 3번. 지금은 **고정된 `mock.json` 내용을 그대로** 돌려줍니다. 화면·AI를 진짜 주소에 먼저 붙이고, 백엔드가 실제 값으로 하나씩 바꿀 예정이에요.

| 주소 | 방식 | 언제 | 지금 응답 |
|---|---|---|---|
| `/api/chat/` | POST | 적용 전 대화 (여행 id 없음) | `mock.json` |
| `/api/trips/<id>/` | GET | 저장된 여행 열기 (id는 아무 숫자나) | `mock.json` |

- 로그인 필요: 아니면 `401` (기존 `travel_chat/`과 같은 오류 모양 `{ok: false, error, login: true}`)
- `/api/chat/`은 POST 전용 (GET은 `405`). POST에는 기존 채팅처럼 `X-CSRFToken` 헤더 필요
- 기존 `travel_chat/`·`travel_chat_apply/`·`travel_chat_preview/`는 **그대로**. 새 주소는 추가만 함
- 코드: `urls.py`의 `api_chat`·`api_trip`, `views.py`의 `_read_mock()`(여기만 실제 계산으로 바꾸면 됨)

### 🟦 프론트
- [ ] 화면을 이 주소에 붙여 `mock.json` 키(`reply`, `facts`, `hint`, `plan`, `places`, `transport`, `budget`)로 그리기 시험. 기존 `travel_chat/` 화면은 그대로 두고 따로 시험

### 🟩 AI
- [ ] `run_chat_turn` 출력을 이 응답 모양으로 맞추는 작업의 기준 주소. 백엔드가 `_read_mock()` 자리를 AI 결과로 바꿀 때 함께 확인

## 2026-10-29 · 채팅 임시 저장을 회원별로 나누기 (결정) — 🟧 이수한
배경: 여행은 지금처럼 **"이 일정 적용하기" 때 생성**하고, 그 전 대화·초안은 브라우저 탭 `sessionStorage`(`tripa_chat_v1`)에 임시 저장하는 방식을 유지하기로 함. 다만 같은 탭에서 로그아웃 → 다른 계정 로그인 시 **앞 사람 초안이 보이고, 적용하면 뒷사람 여행으로 저장되는** 문제가 있어 저장 이름에 회원 구분값을 넣기로 결정.

### 🟦 프론트가 할 일
- [ ] `travel_create.html`의 `#tcApp`에 회원 구분값 속성 추가 (예: `data-member="{{ member.m_id }}"`). 뷰가 이미 `member`를 넘기고 있어 백엔드 수정 없음
- [ ] `travel_chat.js`의 `STORE_KEY`를 회원별 이름으로 (예: `tripa_chat_v1_` + 회원 번호). `load`·`save`·`clearStore`가 같은 이름을 쓰게
- [ ] 예전 이름(`tripa_chat_v1`)으로 남아 있는 저장값은 한 번 지우기 (누구 것인지 알 수 없으므로)
- [ ] 확인: A로 채팅 → 로그아웃 → 같은 탭에서 B 로그인 → 여행 만들기 화면이 **빈 상태**, 다시 A로 로그인하면 **A 초안 복원**

### 🟧 백엔드 · 🟩 AI
- 영향 없음. 회원 번호(`m_id`)만 화면에 쓰고 이메일은 넣지 않음

### 함께 정해진 것 (회의에서 최종 확인)
- 적용 전 대화는 id 없는 주소, 저장된 여행은 id 주소: `mock.json`의 `POST /api/trips/<id>/chat/` → `POST /api/chat/` 로 바꾸는 안. 응답 키는 그대로

## 2026-10-29 · 비밀번호 해시 적용 — 🟧 이수한
- 가입(`join_ok`)·로그인(`login_ok`)·비밀번호 찾기(`pw_find`)·탈퇴(`member_delete`)가 Django 해시(`pbkdf2_sha256`)를 사용. `Member.pwd` 길이 30 → 255 (DB 컬럼과 맞춤)
- 기존 평문 회원은 **첫 로그인 때 자동으로 해시로 바뀜** (`login_ok`의 임시 `elif`, 모두 바뀌면 삭제 예정). pull 뒤 각자 로컬 DB의 테스트 계정도 로그인하면 바뀌어요
- **테스트 계정은 DB에 직접 넣지 말고 회원가입 화면으로 만들기** (DB에 평문을 넣으면 이전용 갈래로만 로그인됨)
- 🟦 영향 없음 (화면·폼 이름 그대로) · 🟩 영향 없음

## 2026-10-29 · `call_llm`을 LangChain으로 교체 — 🟩 서지윤
- `chat_service.call_llm`이 `requests` 대신 LangChain(`ChatOpenAI`)으로 AI를 부름. 함수 이름·인자·반환값·오류 문구는 그대로
- `requirements.txt`에 `langchain-core`, `langchain-openai` 추가 → **pull 뒤 `pip install -r pj_django/requirements.txt`**
- 🟧 영향 없음 (`run_chat_turn` 입출력 그대로) · 🟦 영향 없음 (응답 키 그대로)


## 2026-10-29 · 목업 개편 (예산 성향 삭제, 리뷰 게시판, 폰·태블릿·앱) — 🟧 이수한

### 바뀐 결정
| 항목 | 이전 | 지금 |
|---|---|---|
| 예산 입력 | 예산 성향(가성비/비싸도 괜찮음) 필수 | **삭제** (10/28 회의). 총 예산 + **카테고리 예산**(숙소·교통·식비·카페·문화입장) |
| `mock.json` | `facts.budget: "value"` | `facts.budget` 삭제, `budget` = `{total, planned, limit{카테고리}, by{카테고리}}` |
| PC 디자인 | 새 색(초록) 목업 | **1차(옛 버전) 색·왼쪽 메뉴 유지**: 파랑 `#2d6cdf`, 배경 `#f5f7fb`, 220px 왼쪽 메뉴, 산 아이콘 + TRIPA 로고 |
| 왼쪽 메뉴 | 내 여행 · 여행 만들기 · 일정 관리 · 비용 관리 · 장소 검색 | 내 여행 · 여행 만들기 · 일정 관리 · 비용 관리 · (카테고리 예산) · **리뷰 게시판(신규)**. 장소 검색 메뉴는 삭제됨(프론트 PR #1) |
| 화면 크기 | PC + 폰 | **PC(1080px↑) · 태블릿(768px 전후) · 폰(360px 전후) · 앱** |

### 🟦 프론트가 할 일 (목업을 참고해 직접 구현, 세부 모양은 프론트가 결정)
- [ ] 예산 성향 버튼·문구 삭제 (메인, 채팅 '모인 정보'의 예산 칸)
- [ ] 카테고리 예산 화면 (목업 '카테고리 예산' 탭): 카테고리별 금액 입력, 계획 대비 막대, 넘치면 같은 카테고리 대안 제안
- [ ] 리뷰 게시판 화면 (목업 '리뷰 게시판' 탭): 목록·분류 필터·정렬, 별점·한 줄 리뷰·좋았던 점 태그로 쓰기, 도움돼요, 리뷰 기반 추천 카드
- [ ] 반응형: 폰은 아래 탭바 5개(대화·일정·지도·게시판·내 정보), 태블릿은 왼쪽 아이콘 메뉴 + 2단, PC는 옛 왼쪽 메뉴
- [ ] 폰 지도 화면 (목업 '모바일 화면' ④): 날짜 칩 → 핀·동선·아래 목록 시트가 같이 바뀜. 지도는 지금처럼 카카오맵 JavaScript SDK
- [ ] 태블릿 (목업 ⑤): 아이콘 메뉴 | 대화칸 | 일정칸이 나란히(겹치지 않음). 일정칸 위 **[일정 | 지도] 전환**으로 같은 칸에서 지도와 장소 목록을 봄. 좁은 세로 태블릿(대략 700px 미만)은 폰 배치로
- [ ] 새 아이콘: `i-board`(게시판), `i-star`(별점), `i-bell`(알림) — 기존 `icons.svg`에 추가
- [ ] 바뀐 화면 id·form name·fetch 주소가 있으면 PR 설명과 이 파일에 적기

### 🟧 백엔드가 할 일
- [ ] **리뷰 저장 구조 설계** (DB 변경 → 팀 합의 필요): 리뷰(회원, 여행, 장소, 별점 1~5, 한 줄, 좋았던 점 태그, 작성일), 도움돼요(회원, 리뷰). 계획에 있던 `spot_feedback`과 합칠지 결정
- [ ] **방문 인증 규칙**: '적용하기'로 저장한 여행(`travel`/`travel_day_plan`)의 장소에만 리뷰 허용, 같은 여행·장소는 1개
- [ ] 게시판 API: 목록(분류·정렬·지역), 쓰기, 도움돼요 토글, 장소별 평균·리뷰 수 집계
- [ ] 카테고리 예산 저장: 여행별 카테고리 금액, `pay`에 `PAY_CATEGORY`(stay·move·food·cafe·ticket) 연결, `mock.json`의 `budget`과 같은 키로 응답
- [x] `place_search` 화면: 메뉴에서만 빠짐. 주소·뷰를 지울지 팀 결정 후 처리 → ✅ 11/10 삭제 (지울 때 다른 템플릿의 `{% url 'place_search' %}`가 남아 있지 않은지 확인)
- [ ] 앱 대비: HTTPS 배포, 화면이 쓰는 데이터는 JSON API로 (자세한 건 `APP_GUIDE.md`)
- [ ] 카카오맵: 배포 도메인이 정해지면 카카오 콘솔 JavaScript SDK 도메인에 등록. 웹 지도·앱 지도가 같은 JSON(이름·위도·경도·순서·날짜)을 받게 유지 (`APP_GUIDE.md` '지도 주의점')

### 🟩 AI가 할 일
- [ ] 추천 점수에 **게시판 평점·리뷰 수·자주 나온 좋은 점 키워드** 반영 (채팅 추천 카드와 게시판 '리뷰 기반 추천'이 같은 점수 사용)
- [ ] 리뷰 키워드 요약은 LLM, 점수 계산은 코드
- [ ] 예산 성향 대신 **카테고리별 상한**(카테고리 예산 ÷ 장소 수)을 검색 조건으로 사용 — LangChain 검색 프롬프트 수정
- [ ] 출력 JSON에서 `facts.budget` 제거, `budget`은 `mock.json` 모양
- [ ] (앱) 알림 문구: 날씨 변경 제안, 여행 후 리뷰 요청 — 문장은 화면이 언어별로 만들고 AI는 키만 보내는 기존 규칙 유지

---

## 2026-10-29 · `mock.json` 추가·수정 (PR #2) — 🟧 이수한
- 리포 최상위에 `mock.json` 추가. 예산 성향 키 삭제, 카테고리 예산 구조로 변경
- `requirements.txt`에 `django-environ` 추가 → **pull 뒤 `pip install -r pj_django/requirements.txt`**

## 2026-10-28 · 일정 관리 3칸 배치, 장소 검색 메뉴 삭제 (PR #1) — 🟦 임영준
- `travel_detail`이 [여행 정보·비용 | DAY 탭+일정 | 지도] 3칸. JS가 쓰는 id(`dayList`, `timelineContainer`, `payBox`, `map`)는 그대로
- 왼쪽 메뉴 6곳에서 '장소 검색' 삭제 (페이지·url은 유지)
- 🟧 영향 없음 (응답 키 `pays`, `pay_context`, `pay_pay`, `total_pay` 그대로) · 🟩 영향 없음
