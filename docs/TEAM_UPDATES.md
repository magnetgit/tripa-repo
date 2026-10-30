# 팀 변경 기록 (TEAM_UPDATES)

`git pull`로 받은 변경이 **내 파트(🟦 프론트 / 🟧 백엔드 / 🟩 AI)에 무엇을 바꾸는지** 적는 곳입니다.
최신 항목이 맨 위입니다. 다른 파트에 영향을 주는 변경(화면 id·주소·응답 키·DB·설정)을 올릴 때는 여기에 한 항목을 추가해 주세요.

- 기준 목업: [TRIPA 화면 목업](https://claude.ai/artifact/BqZEgyPi2NH36UjyHwbYBk) (화면 모양 참고용, 코드가 아님). 같은 내용의 사본이 `docs/mockup/tripa-mockup.html`에 있어서 브라우저로 바로 열 수 있어요 (가장 최신은 링크 쪽)
- 기준 응답 모양: 리포 최상위 `mock.json`
- pull 뒤 확인 방법: [`docs/PULL_CHECKLIST.md`](PULL_CHECKLIST.md)
- 앱 확장 가이드: [`docs/APP_GUIDE.md`](APP_GUIDE.md)

---

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
- [ ] 🟧 리뷰 API(목록·쓰기·도움돼요·장소별 평균), 카테고리 예산 저장 API, 관리자 화면 등록
- [ ] 🟧 서버 반영(`deploy.sh`의 `migrate`로 적용)

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
- [ ] `place_search`·`place_search_search` 주소·뷰·템플릿 삭제 (남은 `{% url 'place_search' %}` 없는지 확인)
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
- [ ] `place_search` 화면: 메뉴에서만 빠짐. 주소·뷰를 지울지 팀 결정 후 처리 (지울 때 다른 템플릿의 `{% url 'place_search' %}`가 남아 있지 않은지 확인)
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
