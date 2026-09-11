#!/usr/bin/env bash
#
# Cloud Agent start phase — 매 부팅마다 실행하는 서비스 초기화.
#
#   - PostgreSQL 클러스터 기동 (이미 떠 있으면 그대로 둔다)
#   - ispot role / database 보장
#   - alembic migration (alembic 이 버전을 추적하므로 반복 실행 안전)
#   - 데모 계정 seed (이미 있으면 건너뛴다)
# 전부 idempotent 하게 작성해 재부팅/재실행에 안전하다.
# 장시간 실행되는 uvicorn 서버는 여기서 띄우지 않고 terminals 에서 띄운다.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# PostgreSQL major 버전을 자동 감지한다 (기본 16).
PG_VERSION="$(ls /etc/postgresql 2>/dev/null | sort -V | tail -n1 || echo 16)"

echo "[start] PostgreSQL(${PG_VERSION}) 클러스터 기동"
sudo pg_ctlcluster "$PG_VERSION" main start 2>/dev/null || true

echo "[start] DB 준비 대기"
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then
    break
  fi
  sleep 1
done

echo "[start] ispot role / database 보장"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='ispot'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE USER ispot WITH PASSWORD 'ispot' CREATEDB;"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='ispot'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE DATABASE ispot OWNER ispot;"

echo "[start] migration + 데모 계정 seed"
cd "$REPO_ROOT/backend"
# shellcheck disable=SC1091
. .venv/bin/activate
alembic upgrade head

# 데모 계정 비밀번호. 로컬 개발 전용이며 합성 데이터에만 사용한다.
# (docker-compose.yml 의 ispot:ispot DB 자격증명과 동일한 성격의 dev-only 값)
export SEED_USER_PASSWORD="${SEED_USER_PASSWORD:-ispot-demo-1234}"
python -m scripts.seed_users --demo || true

echo "[start] 완료 — admin@ispot.example.com / counselor@ispot.example.com (비밀번호: \$SEED_USER_PASSWORD)"
