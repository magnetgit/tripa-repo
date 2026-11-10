#!/bin/bash
# TRIPA DB 백업 → ~/db_backup/<DB이름>_YYYYmmdd_HHMMSS[_이유].sql.gz (한국 시각), 14일 지난 백업은 지움
# 사용: ~/backup_db.sh [이유]
#   - cron: 매일 04:00 (한국 시각) → ~/db_backup/backup.log
#   - deploy.sh: migrate 바로 앞에서 ~/backup_db.sh deploy
# 되살리기: gunzip -c ~/db_backup/<파일>.sql.gz | mysql --defaults-extra-file=<접속 설정> <DB이름>  (docs/SERVER_BACKUP.md)
set -uo pipefail

ENV_FILE="$HOME/tripa-repo/pj_django/.env"
DIR="$HOME/db_backup"
KEEP_DAYS=14
mkdir -p "$DIR"

# .env 에서 값 읽기 (값은 화면·로그에 찍지 않음)
get() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']\$//"; }
DB_NAME=$(get DB_NAME); DB_USER=$(get DB_USER); DB_PASSWORD=$(get DB_PASSWORD)
DB_HOST=$(get DB_HOST); DB_PORT=$(get DB_PORT)

# 비밀번호가 명령 목록(ps)에 보이지 않게 잠깐 쓰는 접속 설정 파일 (권한 600, 끝나면 지움)
CNF=$(mktemp)
chmod 600 "$CNF"
trap 'rm -f "$CNF"' EXIT
printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n' "$DB_USER" "$DB_PASSWORD" "${DB_HOST:-127.0.0.1}" "${DB_PORT:-3306}" > "$CNF"

TAG=${1:+_$1}
OUT="$DIR/${DB_NAME}_$(TZ=Asia/Seoul date +%Y%m%d_%H%M%S)${TAG}.sql.gz"

# --single-transaction: 서비스를 멈추지 않고 한 시점의 모습으로 뜸 / --routines --triggers: 트리거도 같이
if ! mysqldump --defaults-extra-file="$CNF" --single-transaction --routines --triggers \
        --default-character-set=utf8mb4 "$DB_NAME" | gzip > "$OUT"; then
    rm -f "$OUT"
    echo "$(TZ=Asia/Seoul date '+%F %T') 백업 실패"
    exit 1
fi

# 오래된 백업 지우기 (손으로 뜬 .sql 은 그대로 둠)
find "$DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$KEEP_DAYS" -delete

echo "$(TZ=Asia/Seoul date '+%F %T') 백업: $(basename "$OUT") ($(du -h "$OUT" | cut -f1))"
