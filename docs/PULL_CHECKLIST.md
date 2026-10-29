# pull 받은 뒤 확인할 것 (PULL_CHECKLIST)

다른 팀원(특히 🟦 프론트)이 올린 변경을 `git pull`로 받았을 때, **내 작업에 영향이 있는지** 이 순서로 확인합니다.
Claude Code에게 "pull 받은 변경 확인해줘"라고 하면 이 문서대로 정리해 줍니다(`.claude/rules/team-updates.md`).

## 1. 무엇이 바뀌었나
```bash
git log --oneline ORIG_HEAD..HEAD
```
```bash
git diff --stat ORIG_HEAD..HEAD
```
- `ORIG_HEAD`는 pull 직전 위치입니다. merge로 받았다면 `git log --oneline HEAD~1..HEAD`처럼 범위를 바꿔서 봅니다.
- 먼저 [`docs/TEAM_UPDATES.md`](TEAM_UPDATES.md) 최신 항목에서 내 파트 체크리스트를 확인합니다.

## 2. 바뀐 파일 → 확인할 사람·내용
| 바뀐 파일 | 🟧 백엔드가 확인 | 🟩 AI가 확인 | 🟦 프론트가 확인 |
|---|---|---|---|
| `templates/**/*.html` | `{% url '이름' %}`이 `urls.py`에 있는지, 화면이 쓰는 context 변수(`{{ }}`)를 뷰가 넘기는지, `<form>`의 `name=`이 뷰가 읽는 키와 같은지 | 거의 없음 (채팅 화면이면 `hint`·`notes` 키 표시 방식) | — |
| `static/**/*.js` | `fetch` 주소·메서드, 보내는 body 키, 읽는 응답 키가 뷰와 같은지 | 채팅 응답(`reply`, `facts`, `hint`, `plan`, `places`)을 읽는 부분이 바뀌었는지 | — |
| `static/**/*.css`, 아이콘 | 영향 없음 | 영향 없음 | — |
| `mock.json` | 응답을 같은 키로 맞추기 | 출력 JSON을 같은 키로 맞추기 | 화면이 읽는 키 맞추기 |
| `views.py`, `urls.py` | — | `run_chat_turn` 입출력이 바뀌었는지 | 주소·응답 키가 바뀌었는지 |
| `models.py`, `Table/*.sql` | 내 DB에 반영 (`managed=False` 테이블은 SQL로) | 저장 필드가 바뀌었는지 | 화면에 새 필드가 필요한지 |
| `services/chat_service.py`, AI 코드 | 뷰가 부르는 함수 이름·인자·반환 키 | — | `reply`·`hint` 등 응답 키 |
| `requirements.txt` | `pip install -r pj_django/requirements.txt` | 같음 | 같음 |
| `.env.example` | 내 `.env`에 새 키 추가 (값은 Slack DM 등으로 받기) | 같음 | 같음 |

## 3. 빠르게 찾는 명령
```bash
git diff ORIG_HEAD..HEAD -- "*.html" | grep -E "^[-+].*(id=|name=|\{% url)"
```
```bash
git diff ORIG_HEAD..HEAD -- "*.js" | grep -E "^[-+].*(fetch\(|\.json\(\)|data\.)"
```
```bash
git diff ORIG_HEAD..HEAD -- mock.json
```
- `-`로 시작하는 줄이 **없어진 것**입니다. 없어진 id·주소·키를 내 코드가 아직 쓰고 있으면 고쳐야 합니다.

## 4. 실행해서 확인
```bash
cd pj_django
```
```bash
python manage.py check
```
```bash
python manage.py runserver
```
- 바뀐 화면을 직접 열어 보고, 브라우저 개발자 도구 콘솔에 404·500·JS 오류가 없는지 봅니다.

## 5. 영향이 있으면
- 고칠 게 내 파트면 내 브랜치(`front`/`back`/`ai`)에서 고칩니다.
- 응답 키·주소·DB처럼 **세 사람이 같이 쓰는 약속**이 바뀌어야 하면 혼자 바꾸지 말고 회의 → `mock.json`·`TEAM_UPDATES.md`부터 수정합니다.
