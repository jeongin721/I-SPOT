#!/bin/bash
# I-SPOT 화면 + HTTPS 배포. 여러 번 실행해도 된다(최신 main 으로 화면 · 백엔드를 다시 만든다).
# 결과: https://15-165-250-143.sslip.io/ 에 화면, /api/v1 · /health · /docs · /openapi.json 은 백엔드로.
# 백엔드는 서버 안쪽 127.0.0.1:8000 에서만 받고, 앞의 Caddy(같은 서버)만 믿는다(실제 접속 IP 가 기록에 남음).
#
# 서버에서: cd /opt/ispot/I-SPOT && sudo git pull --ff-only && sudo bash deploy/web-deploy.sh
# 주소를 바꾸려면 SITE 를 넘긴다(sudo 는 설정에 따라 환경변수를 넘기지 않을 수 있어 sudo 뒤에 env 로 쓴다):
#   sudo env SITE=<새 주소> bash deploy/web-deploy.sh
# backend.env 가 AI_PROVIDER=modeling 이면 WITH_MODELING=1 을 넘긴다(torch · transformers 를 더 깔고 모델 파일을 붙인다,
# deploy/README.md '모델까지 띄우기'):
#   sudo env WITH_MODELING=1 bash deploy/web-deploy.sh
# 비밀번호 · 키 · DB 주소는 이 파일이 아니라 서버의 /opt/ispot/backend.env 에 있다(저장소에 넣지 않는다). deploy/README.md 참고.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "sudo 로 실행해 주세요"; exit 1; }
SITE="${SITE:-15-165-250-143.sslip.io}"
# SITE 는 아래 sed 치환 · Caddyfile 에 그대로 들어간다. 호스트 이름 · IP 글자만 받는다(| & 공백 따옴표 등은 설정을 깨뜨린다).
[[ "$SITE" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || { echo "SITE 는 영문 · 숫자 · 점 · 하이픈만 쓸 수 있습니다: $SITE"; exit 1; }
REPO=/opt/ispot/I-SPOT
ENV_FILE=/opt/ispot/backend.env

WITH_MODELING="${WITH_MODELING:-0}"
[[ "$WITH_MODELING" =~ ^[01]$ ]] || { echo "WITH_MODELING 은 0 또는 1 입니다: $WITH_MODELING"; exit 1; }
# 학대 분류 모델 파일은 저장소에 없다(.gitignore). 이 폴더에 두면 컨테이너의 /ai/modeling/abuse/weight 에 읽기 전용으로 붙인다.
WEIGHT_DIR="${MODELING_WEIGHT_DIR:-$REPO/ai/modeling/abuse/weight}"
MODELING_MOUNTS=()
if [ "$WITH_MODELING" = 1 ]; then
  for f in roberta_abuse_qa_child_v3_best.pth roberta_abuse_note_v1_best.pth; do
    [ -f "$WEIGHT_DIR/$f" ] || { echo "modeling 모델 파일이 없습니다: $WEIGHT_DIR/$f (MODELING_WEIGHT_DIR 로 다른 폴더를 줄 수 있습니다)"; exit 1; }
  done
  # 이름 인식 · klue 토크나이저는 첫 분석 때 Hugging Face 에서 받는다. 컨테이너를 다시 만들어도 다시 받지 않게 서버에 둔다.
  mkdir -p /opt/ispot/hf-cache
  MODELING_MOUNTS=(-v "$WEIGHT_DIR:/ai/modeling/abuse/weight:ro" -v /opt/ispot/hf-cache:/hf-cache)
elif grep -qE '^AI_PROVIDER=modeling[[:space:]]*$' "$ENV_FILE"; then
  echo "backend.env 가 AI_PROVIDER=modeling 입니다. torch · 모델 파일이 든 이미지가 필요해 WITH_MODELING=1 로 실행해 주세요:"
  echo "  sudo env WITH_MODELING=1 bash deploy/web-deploy.sh"
  exit 1
fi

echo "== 1/5 최신 main 받기"
cd "$REPO"
# main 을 받아 이 파일이 바뀌었으면 새 판으로 처음부터 다시 시작한다. 옛 판이 끝까지 돌면 새 main 의 Dockerfile 을
# 옛 빌드 명령으로 만들다 멈춘다(2026-10-22 데모 서버: git pull 없이 돌려 3/5 의 COPY backend/requirements.txt 에서 멈춤).
# { } 묶음은 bash 가 다 읽은 뒤 실행하므로, 그 안에서 이 파일이 바뀌어도 묶음은 읽은 그대로 끝까지 돈다.
{
  OLD=$(git rev-parse --short HEAD)
  OLD_SCRIPT=$(git hash-object deploy/web-deploy.sh)
  git fetch -q origin main
  git checkout -q main
  git merge -q --ff-only origin/main
  echo "code $OLD -> $(git rev-parse --short HEAD)"
  if [ "$(git hash-object deploy/web-deploy.sh)" != "$OLD_SCRIPT" ]; then
    # 다시 시작한 판이 또 바뀌었으면(그사이 main 에 새 배포 스크립트가 들어옴) 되풀이하지 않고 멈춘다.
    [ -z "${WEB_DEPLOY_RESTARTED:-}" ] || { echo "배포 스크립트가 다시 시작한 뒤에도 바뀌었습니다. 한 번 더 실행해 주세요."; exit 1; }
    echo "배포 스크립트가 바뀌어 새 판으로 처음부터 다시 시작합니다"
    exec env WEB_DEPLOY_RESTARTED=1 bash "$REPO/deploy/web-deploy.sh"
  fi
}

echo "== 2/5 화면(counselor-web) 빌드"
docker run --rm -v "$REPO/counselor-web:/w" -w /w node:22.12.0-alpine \
  sh -c "npm ci --no-audit --no-fund --loglevel=error && npm run build"
mkdir -p /opt/ispot/web
find /opt/ispot/web -mindepth 1 -delete
cp -r "$REPO/counselor-web/dist/." /opt/ispot/web/

echo "== 3/5 백엔드 이미지 다시 만들기 + DB 마이그레이션"
# 저장소 루트가 빌드 컨텍스트다(ai/ · agent/ 도 담음). 넣는 것은 루트 .dockerignore 가 고른다.
docker build -q -t ispot-backend --build-arg WITH_MODELING="$WITH_MODELING" -f "$REPO/backend/Dockerfile" "$REPO"
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://$SITE|" "$ENV_FILE"
docker run --rm --env-file "$ENV_FILE" ispot-backend alembic upgrade head

echo "== 4/5 백엔드를 127.0.0.1:8000 으로만 다시 띄우기"
docker rm -f ispot-backend >/dev/null 2>&1 || true
docker run -d --name ispot-backend --restart unless-stopped --network host \
  --env-file "$ENV_FILE" -v /opt/ispot/storage:/app/storage ${MODELING_MOUNTS[@]+"${MODELING_MOUNTS[@]}"} ispot-backend \
  uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1

echo "== 5/5 Caddy(화면 + API + HTTPS)"
cat > /opt/ispot/Caddyfile <<EOF
$SITE {
    encode gzip
    header {
        X-Content-Type-Options nosniff
        Referrer-Policy no-referrer
        -Server
    }
    @api path /api/v1/* /health /docs /docs/* /openapi.json
    handle @api {
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        root * /srv
        file_server
    }
}
EOF
docker rm -f ispot-web >/dev/null 2>&1 || true
docker run -d --name ispot-web --restart unless-stopped --network host \
  -v /opt/ispot/Caddyfile:/etc/caddy/Caddyfile:ro -v /opt/ispot/web:/srv:ro \
  -v ispot_caddy_data:/data -v ispot_caddy_config:/config caddy:2.8.4

sleep 20
echo "-- 백엔드:"; curl -s http://127.0.0.1:8000/health; echo
echo "-- HTTPS:"; curl -s --max-time 20 --resolve "$SITE:443:127.0.0.1" "https://$SITE/health" || echo "(HTTPS 아직 준비 안 됨 - 아래 기록 확인)"; echo
docker logs --tail 15 ispot-web 2>&1 | grep -iE "certificate|error|obtain" || true
echo "WEB-DEPLOY DONE  https://$SITE/"
