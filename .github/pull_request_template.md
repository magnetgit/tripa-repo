## 바뀐 것
-

## 다른 파트 영향 (해당하면 체크하고 한 줄 설명)
- [ ] 화면 id·`form` `name`·`{% url %}` 이름이 바뀜 → 🟧
- [ ] `fetch` 주소·요청 body·읽는 응답 키가 바뀜 → 🟧 🟩
- [ ] `mock.json`·응답 키가 바뀜 → 🟦 🟧 🟩 (세 사람 합의 필요)
- [ ] DB(`models.py`, `Table/*.sql`)가 바뀜 → 모두 DB 반영 필요
- [ ] `requirements.txt`·`.env.example`이 바뀜 → 모두 설치·설정 필요
- [ ] 영향 없음 (디자인·문구만)

## 확인
- [ ] `docs/TEAM_UPDATES.md`에 항목 추가 (영향이 있을 때)
- [ ] `python manage.py check` 통과, 바뀐 화면을 runserver로 열어 봄
