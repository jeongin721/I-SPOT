#!/bin/bash
# 온담 시니어(고령자 돌봄관리) 데모 사이트 배포 — feature/senior 전용(2026-11-17). 여러 번 실행해도 된다.
#
# 아동 데모(web-deploy.sh, /opt/ispot · ispot-backend · ispot-web)와 폴더 · 컨테이너 · DB 를 모두 따로 쓴다:
#   폴더 /opt/onda(저장소 /opt/onda/I-SPOT, 설정 /opt/onda/backend.env, 녹음 /opt/onda/storage, 화면 /opt/onda/web)
#   컨테이너 onda-backend(127.0.0.1:$BACKEND_PORT) · onda-web(Caddy, 80 · 443)
#   DB 는 backend.env 의 DATABASE_URL — 같은 RDS 안의 고령자 전용 데이터베이스(ispot_senior)를 쓴다. ispot 데이터베이스를 쓰면 안 된다
#   (고령자 마이그레이션이 올라가면 main · 아동 데모 배포가 alembic 에서 멈춘다).
# Caddy 가 80 · 443 을 쓰므로 아동 데모와 같은 서버에는 올릴 수 없다(민규 11/16: 백엔드 서버를 따로).
#
# 서버에서(처음 한 번 · deploy/SENIOR.md):
#   sudo mkdir -p /opt/onda && sudo git clone -b feature/senior https://github.com/jeongin721/I-SPOT.git /opt/onda/I-SPOT
#   sudo cp /opt/onda/I-SPOT/deploy/senior.env.example /opt/onda/backend.env   # 값 채우기
# 배포:
#   sudo env SITE=<주소, 예: 1-2-3-4.sslip.io> WITH_STT=1 bash /opt/onda/I-SPOT/deploy/senior-deploy.sh
# backend.env 가 SENIOR_AI_PROVIDER=modeling 이면 WITH_MODELING=1 을 더한다(이름 가리기 모델 · OpenAI 패키지를 이미지에 담는다).
# 고령자는 학대 분류 모델 파일(.pth) · GPU 를 쓰지 않는다 — WITH_GPU 는 받지 않는다.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "sudo 로 실행해 주세요"; exit 1; }
SITE="${SITE:-}"
[ -n "$SITE" ] || { echo "SITE(사이트 주소)를 넘겨 주세요: sudo env SITE=<주소> bash deploy/senior-deploy.sh"; exit 1; }
[[ "$SITE" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || { echo "SITE 는 영문 · 숫자 · 점 · 하이픈만 쓸 수 있습니다: $SITE"; exit 1; }
ROOT=/opt/onda
REPO=$ROOT/I-SPOT
ENV_FILE=$ROOT/backend.env
BACKEND_PORT="${BACKEND_PORT:-8000}"
[[ "$BACKEND_PORT" =~ ^[0-9]{2,5}$ ]] || { echo "BACKEND_PORT 는 숫자입니다: $BACKEND_PORT"; exit 1; }
[ -f "$ENV_FILE" ] || { echo "설정 파일이 없습니다: $ENV_FILE (deploy/senior.env.example 을 복사해 채워 주세요)"; exit 1; }

WITH_MODELING="${WITH_MODELING:-0}"
[[ "$WITH_MODELING" =~ ^[01]$ ]] || { echo "WITH_MODELING 은 0 또는 1 입니다: $WITH_MODELING"; exit 1; }
WITH_STT="${WITH_STT:-0}"
[[ "$WITH_STT" =~ ^[01]$ ]] || { echo "WITH_STT 은 0 또는 1 입니다: $WITH_STT"; exit 1; }

# 아동 데모 DB 를 잘못 가리키는 실수를 막는다(데이터베이스 이름이 ispot 이면 멈춘다).
DB_NAME=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | sed -E 's|.*/([^/?]+)(\?.*)?$|\1|' || true)
[ -n "$DB_NAME" ] || { echo "backend.env 에 DATABASE_URL 이 없습니다."; exit 1; }
[ "$DB_NAME" != "ispot" ] || { echo "DATABASE_URL 이 아동 데모 데이터베이스(ispot)를 가리킵니다. 고령자 전용 데이터베이스로 바꿔 주세요."; exit 1; }

if [ "$WITH_MODELING" = 1 ]; then
  # 이름 가리기(KoELECTRA NER) 모델은 첫 분석 때 Hugging Face 에서 받는다. 컨테이너를 다시 만들어도 다시 받지 않게 둔다.
  mkdir -p $ROOT/hf-cache
  MODELING_MOUNTS=(-v $ROOT/hf-cache:/hf-cache)
  grep -qE '^OPENAI_API_KEY=.+' "$ENV_FILE" || echo "주의: backend.env 에 OPENAI_API_KEY 가 없습니다. AI 요약이 실패하고 규칙 요약도 나오지 않습니다."
elif grep -qE '^SENIOR_AI_PROVIDER=modeling[[:space:]]*$' "$ENV_FILE"; then
  echo "backend.env 가 SENIOR_AI_PROVIDER=modeling 입니다. 이름 가리기 모델 · OpenAI 패키지가 든 이미지가 필요해 WITH_MODELING=1 로 실행해 주세요."
  exit 1
else
  MODELING_MOUNTS=()
fi
if [ "$WITH_STT" = 1 ]; then
  grep -qE '^(ELEVENLABS_API_KEY|DEEPGRAM_API_KEY|I_SPOT_STT_API_KEY)=.+' "$ENV_FILE" \
    || echo "주의: backend.env 에 STT 키가 없습니다. STT_PROVIDER=module 이면 전사가 실패합니다."
elif grep -qE '^STT_PROVIDER=module[[:space:]]*$' "$ENV_FILE"; then
  echo "backend.env 가 STT_PROVIDER=module 입니다. WITH_STT=1 로 실행해 주세요."
  exit 1
fi
if grep -qE '^ENV=production[[:space:]]*$' "$ENV_FILE" \
  && ! { grep -qE '^PII_ENCRYPTION_KEYS=[[:space:]]*[^[:space:]]' "$ENV_FILE" \
         && grep -qE '^PII_INDEX_KEY=[[:space:]]*[^[:space:]]' "$ENV_FILE"; }; then
  echo "backend.env 가 ENV=production 인데 PII_ENCRYPTION_KEYS · PII_INDEX_KEY 가 없습니다(아동 데모와 다른 새 키로)."
  exit 1
fi

echo "== 1/5 최신 ${DEPLOY_BRANCH:-feature/senior} 받기"
cd "$REPO"
# 받은 뒤 이 파일이 바뀌었으면 새 판으로 처음부터 다시 시작한다(web-deploy.sh 와 같은 방식).
{
  DEPLOY_BRANCH="${DEPLOY_BRANCH:-feature/senior}"
  OLD=$(git rev-parse --short HEAD)
  OLD_SCRIPT=$(git hash-object deploy/senior-deploy.sh)
  git fetch -q origin "$DEPLOY_BRANCH"
  git checkout -q "$DEPLOY_BRANCH"
  git merge -q --ff-only "origin/$DEPLOY_BRANCH"
  echo "code $OLD -> $(git rev-parse --short HEAD)"
  if [ "$(git hash-object deploy/senior-deploy.sh)" != "$OLD_SCRIPT" ]; then
    [ -z "${SENIOR_DEPLOY_RESTARTED:-}" ] || { echo "배포 스크립트가 다시 시작한 뒤에도 바뀌었습니다. 한 번 더 실행해 주세요."; exit 1; }
    echo "배포 스크립트가 바뀌어 새 판으로 처음부터 다시 시작합니다"
    exec env SENIOR_DEPLOY_RESTARTED=1 bash "$REPO/deploy/senior-deploy.sh"
  fi
}

echo "== 2/5 화면(senior-web) 빌드"
# senior-web 은 counselor-web 의 api · data 를 가져다 쓴다(@cw). 그쪽 패키지도 깔아야 빌드된다.
docker run --rm -v "$REPO:/w" -w /w node:22.12.0-alpine sh -c \
  "cd counselor-web && npm ci --no-audit --no-fund --loglevel=error && cd ../senior-web && npm ci --no-audit --no-fund --loglevel=error && npm run build"
mkdir -p $ROOT/web
find $ROOT/web -mindepth 1 -delete
cp -r "$REPO/senior-web/dist/." $ROOT/web/

if docker buildx version >/dev/null 2>&1; then export DOCKER_BUILDKIT=1; fi
echo "== 3/5 백엔드 이미지 다시 만들기 + DB 마이그레이션"
docker build -q -t onda-backend --build-arg WITH_MODELING="$WITH_MODELING" --build-arg WITH_STT="$WITH_STT" --build-arg WITH_GPU=0 \
  -f "$REPO/backend/Dockerfile" "$REPO"
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://$SITE|" "$ENV_FILE"
docker run --rm --env-file "$ENV_FILE" onda-backend alembic upgrade head

echo "== 4/5 백엔드를 127.0.0.1:$BACKEND_PORT 으로만 다시 띄우기"
mkdir -p $ROOT/storage
docker rm -f onda-backend >/dev/null 2>&1 || true
docker run -d --name onda-backend --restart unless-stopped --network host \
  --env-file "$ENV_FILE" -v $ROOT/storage:/app/storage ${MODELING_MOUNTS[@]+"${MODELING_MOUNTS[@]}"} onda-backend \
  uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --proxy-headers --forwarded-allow-ips 127.0.0.1

echo "== 5/5 Caddy(화면 + API + HTTPS)"
cat > $ROOT/Caddyfile <<EOF
$SITE {
    encode gzip
    header {
        X-Content-Type-Options nosniff
        Referrer-Policy no-referrer
        -Server
    }
    @api path /api/v1/* /health
    handle @api {
        reverse_proxy 127.0.0.1:$BACKEND_PORT
    }
    handle {
        root * /srv
        file_server
    }
}
EOF
docker rm -f onda-web >/dev/null 2>&1 || true
docker run -d --name onda-web --restart unless-stopped --network host \
  -v $ROOT/Caddyfile:/etc/caddy/Caddyfile:ro -v $ROOT/web:/srv:ro \
  -v onda_caddy_data:/data -v onda_caddy_config:/config caddy:2.8.4

sleep 20
echo "-- 백엔드:"; curl -s "http://127.0.0.1:$BACKEND_PORT/health"; echo
echo "-- HTTPS:"; curl -s --max-time 20 --resolve "$SITE:443:127.0.0.1" "https://$SITE/health" || echo "(HTTPS 아직 준비 안 됨 - 아래 기록 확인)"; echo
docker logs --tail 15 onda-web 2>&1 | grep -iE "certificate|error|obtain" || true
echo "SENIOR-DEPLOY DONE  https://$SITE/"
