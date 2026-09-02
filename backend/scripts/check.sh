#!/usr/bin/env bash
#
# 로컬 검증 게이트. push 전에 실행한다.
# .github/workflows/backend-ci.yml 과 같은 항목을 확인하므로
# 여기서 통과하면 CI 도 통과할 가능성이 높다.
#
# 사용법 (backend/ 또는 어디서든):
#   ./scripts/check.sh
#
# 04_DEVELOPMENT.md §4 의 PR 최소 조건(Lint / Test 성공)을 로컬에서 먼저 확인한다.

set -euo pipefail

# 스크립트 위치 기준으로 backend/ 로 이동한다.
cd "$(dirname "$0")/.."

# venv 가 있으면 그 인터프리터를 쓴다. Windows 는 Scripts/, 그 외는 bin/.
PY="python"
if [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
fi

echo "인터프리터: $("$PY" --version 2>&1)"

echo
echo "[1/3] Lint (ruff)"
"$PY" -m ruff check .

echo
echo "[2/3] Test (pytest)"
"$PY" -m pytest -q

echo
echo "[3/3] Migration 정합성 (alembic)"

# 실제 개발 DB 를 건드리지 않도록 임시 SQLite 를 사용한다.
TMP_DB=".check-$$.db"
export DATABASE_URL="sqlite+pysqlite:///./${TMP_DB}"

cleanup() { rm -f "${TMP_DB}"; }
trap cleanup EXIT

"$PY" -m alembic upgrade head >/dev/null
"$PY" -m alembic check
"$PY" -m alembic downgrade base >/dev/null

echo
echo "모든 검사 통과."
