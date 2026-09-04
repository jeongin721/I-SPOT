#!/usr/bin/env bash
#
# Cloud Agent install phase — durable, idempotent repository setup.
#
# 여기서는 재부팅해도 유지되는 것만 준비한다.
#   - 시스템 패키지 (PostgreSQL, Python venv 도구)
#   - Python 가상환경 + Backend 의존성
#   - .env (없을 때만 생성)
# PostgreSQL 프로세스 기동 / migration / seed 는 start.sh 에서 수행한다.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[install] 시스템 패키지 설치 (PostgreSQL / Python venv)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  postgresql postgresql-contrib \
  python3-venv python3-dev build-essential

echo "[install] Python 가상환경 및 Backend 의존성 설치"
cd "$REPO_ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip -q
pip install -r requirements-dev.txt

echo "[install] .env 준비"
if [ ! -f .env ]; then
  cp .env.example .env
  JWT="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
  python - "$JWT" <<'PY'
import sys, pathlib
jwt = sys.argv[1]
path = pathlib.Path(".env")
text = path.read_text()
text = text.replace(
    "JWT_SECRET_KEY=replace-this-with-a-long-random-value",
    f"JWT_SECRET_KEY={jwt}",
)
path.write_text(text)
PY
  echo "[install] .env 생성 완료 (임의 JWT_SECRET_KEY 주입)"
else
  echo "[install] 기존 .env 유지"
fi

echo "[install] 완료"
