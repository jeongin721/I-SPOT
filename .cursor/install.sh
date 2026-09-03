#!/usr/bin/env bash
# Idempotent repository bootstrap for the I-SPOT Cloud Agent environment.
# Installs system packages, Python deps (backend) and Node deps (frontend).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Installing system packages (postgresql, python venv)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  postgresql postgresql-contrib python3-venv

echo "==> Backend: creating virtualenv and installing dependencies"
cd "$REPO_ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip -q
pip install -q -r requirements-dev.txt
deactivate

echo "==> Frontend: installing npm dependencies"
cd "$REPO_ROOT/frontend"
npm install

echo "==> install.sh complete"
