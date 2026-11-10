# 서버 DB 백업과 되살리기

서버(AWS, `ubuntu@` 배포 서버)의 MariaDB를 매일 자동으로 백업해요. 서버 작업은 🟧 이수한이 해요.

## 언제 백업되나
| 언제 | 파일 이름 | 누가 |
|---|---|---|
| **매일 04:00 (한국 시각)** | `sherpa_schema_YYYYmmdd_040000.sql.gz` | cron (`0 19 * * *`, 서버는 UTC) |
| **배포할 때 `migrate` 바로 앞** | `…_deploy.sql.gz` | `~/deploy.sh` → `~/backup_db.sh deploy` (백업이 실패하면 배포를 멈춤) |
| 손으로 | `…_이유.sql.gz` | `~/backup_db.sh 이유` |

- 위치: 서버 `~/db_backup/` (실행 기록은 `~/db_backup/backup.log`)
- **14일 지난 자동 백업(`.sql.gz`)은 지워져요.** 손으로 뜬 `.sql`(압축 안 한 파일)은 그대로 둬요
- 스크립트 원본: 이 저장소 `deploy/backup_db.sh` (서버에는 `~/backup_db.sh`로 복사해 둠, 권한 700)
- DB 접속 정보는 서버 `pj_django/.env`의 `DB_*`에서 읽고, 화면·로그에 찍지 않아요. 비밀번호는 잠깐 쓰는 설정 파일(권한 600, 끝나면 지움)로 넘겨요
- `--single-transaction`: 서비스를 멈추지 않고 한 시점의 모습으로 떠요. `--triggers`: DB 트리거도 같이 떠요

## 되살리는 방법 (잘못된 마이그레이션·데이터 사고 때)
1. 서비스 멈추기: `sudo systemctl stop tripa`
2. **지금 상태도 한 번 더 떠 두기:** `~/backup_db.sh before_restore`
3. 되살릴 파일 고르기: `ls -t ~/db_backup/`
4. 되살리기 (DB 이름·접속 정보는 `.env` 값으로):
   ```bash
   gunzip -c ~/db_backup/<파일>.sql.gz | mysql -u <DB_USER> -p <DB_NAME>
   ```
   비밀번호는 물어볼 때 입력해요 (명령에 직접 쓰지 않기)
5. 서비스 켜기: `sudo systemctl start tripa` → 배포 주소 확인
6. 되살린 백업보다 나중의 마이그레이션이 있었다면 `python manage.py showmigrations`로 확인

## 확인 (11/10)
- 한 번 실행: `sherpa_schema_20261110_103640_test.sql.gz` 36KB, `gunzip -t` 통과, 표 30개
- `crontab -l`에 등록, `cron` 서비스 active, `deploy.sh`·`backup_db.sh` 문법 검사 통과
- 배포 때 백업: 11/10 #87 배포에서 `sherpa_schema_20261110_115531_deploy.sql.gz` 36KB 생성 확인 (그 뒤 migrate)
