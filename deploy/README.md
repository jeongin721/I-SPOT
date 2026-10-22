# 배포 (AWS 시연 서버)

상담사 웹(`counselor-web`)과 Backend 를 AWS 서버 한 대에 올리는 스크립트와 설명입니다.
지금 주소: <https://15-165-250-143.sslip.io/>

> 비밀번호 · 키 · DB 주소 · 계정 정보는 이 폴더에 넣지 않습니다. 서버의 `/opt/ispot/backend.env` 에만 있습니다.

## 다시 배포하기

서버에 SSH 로 들어가서:

```bash
cd /opt/ispot/I-SPOT && sudo git pull --ff-only
sudo bash deploy/web-deploy.sh
```

- 먼저 `git pull` 하는 것은 스크립트 자신도 최신으로 받기 위해서입니다. 스크립트도 시작할 때 `origin/main` 을 다시 받아 fast-forward 합니다(main 만 배포).
- 여러 번 돌려도 됩니다. 돌릴 때마다 화면을 새로 빌드하고 Backend 컨테이너를 다시 만듭니다. 그동안 잠깐 접속이 끊깁니다.
- **성공 판정은 직접 봅니다.** 1/5~5/5 중 한 단계라도 실패하면 스크립트는 그 자리에서 멈추고 0 이 아닌 값으로 끝납니다. 마지막 확인(`/health`)은 경우에 따라 다릅니다.
  - Backend 에 아예 연결되지 않으면(`curl` 연결 실패) 그 자리에서 멈춥니다. 0 이 아닌 값, `WEB-DEPLOY DONE` 없음.
  - Backend 가 답은 했지만 상태가 정상이 아니면(예: DB 연결 실패) 그대로 보여 주고 `DONE` 을 찍고 정상(0) 종료합니다.
  - Backend 는 정상인데 HTTPS 확인이 실패해도 `(HTTPS 아직 준비 안 됨 …)` 을 보여 주고 `DONE` 을 찍고 정상(0) 종료합니다.

  그래서 `DONE` 이 나와도 그 위의 두 줄을 봅니다.
  - `-- 백엔드:` 줄에 `"status":"ok"` 와 `"database":"ok"` 가 있어야 합니다. 비어 있거나 다른 값이면 `sudo docker logs --tail 50 ispot-backend` 로 원인을 봅니다. 로그의 오류 trace 에는 예외 종류 · 위치만 나오고 문구는 빠집니다(상담 발화 보호, `backend/README.md` 7절). 종류(예: `OperationalError`)로 짐작이 안 되면 `backend.env` 의 `DATABASE_URL` 과 DB 상태를 직접 확인합니다.
  - `-- HTTPS:` 줄도 같은 내용이어야 합니다. `(HTTPS 아직 준비 안 됨 …)` 이면 인증서 발급을 기다리는 중일 수 있으니 1~2분 뒤 브라우저에서 `https://<주소>/health` 로 다시 확인합니다.
- **중간에 멈췄을 때**: 앞 단계는 이미 반영된 채로 남습니다. 예를 들어 3/5(DB 마이그레이션)에서 멈추면 화면(2/5)은 새것으로 바뀌었고 `backend.env` 의 `CORS_ORIGINS` 도 고쳐졌지만 Backend 는 옛 컨테이너 그대로입니다. 원인을 고친 뒤 스크립트를 다시 돌립니다.
  - `ENV=production` 에서 `AI_PROVIDER=pipeline` 이고 `AI_PIPELINE_ALLOW_UNMASKED=true` 가 없으면(기본 false) Backend 설정 검사가 시작을 막아 3/5 에서 멈춥니다(상담 원문이 비식별 없이 외부로 나가는 경로라서). `AI_PROVIDER=modeling` 도 `AI_MODELING_ALLOW_IN_PRODUCTION=true` 가 없으면 같은 곳에서 멈춥니다(외부로 보내기 전 가리기가 아직 완전하지 않은 경로라서). `AI_PROVIDER=modeling` 이면 `AI_DEADLINE_MARGIN_SECONDS`(기본 10)가 `AI_TIMEOUT_SECONDS`(기본 180)보다 작지 않을 때도 같은 곳에서 멈춥니다. 다시 배포 전에 `sudo grep -E '^(ENV|AI_PROVIDER|AI_PIPELINE_ALLOW_UNMASKED|AI_MODELING_ALLOW_IN_PRODUCTION|AI_TIMEOUT_SECONDS|AI_DEADLINE_MARGIN_SECONDS)=' /opt/ispot/backend.env` 로 확인합니다.
- 주소를 바꿀 때만 `SITE` 를 넘깁니다(기본값은 지금 주소, 영문 · 숫자 · 점 · 하이픈만). `sudo` 는 설정에 따라 환경변수를 넘기지 않을 수 있어 이렇게 씁니다.

  ```bash
  sudo env SITE=<새 주소> bash deploy/web-deploy.sh
  ```

  새 주소도 이 서버를 가리켜야 HTTPS 인증서가 발급됩니다. `backend.env` 의 `CORS_ORIGINS` 는 스크립트가 `https://<주소>` 로 고칩니다.
- 이전 버전으로 되돌리는 기능은 없습니다. 되돌리려면 main 에서 되돌리는 커밋을 머지한 뒤 다시 배포합니다.

## 스크립트가 하는 일 (`web-deploy.sh`)

| 단계 | 하는 일 |
| --- | --- |
| 1/5 | `/opt/ispot/I-SPOT` 에서 `origin/main` 을 받아 fast-forward |
| 2/5 | Node 컨테이너(`node:22.12.0-alpine`)에서 `counselor-web` 을 `npm ci` · `npm run build` 하고 결과를 `/opt/ispot/web` 에 복사 |
| 3/5 | Backend 이미지(`ispot-backend`)를 다시 만들고 `alembic upgrade head` 로 DB 를 최신 구조로 |
| 4/5 | Backend 컨테이너를 `127.0.0.1:8000` 에서만 받도록 다시 띄움(`--proxy-headers --forwarded-allow-ips 127.0.0.1`) |
| 5/5 | Caddy 설정(`/opt/ispot/Caddyfile`)을 다시 쓰고 Caddy 컨테이너(`caddy:2.8.4`)를 다시 띄움 |

## 서버 구성

```text
브라우저 ──HTTPS(443)──▶ Caddy (같은 서버, HTTPS 인증서 자동 발급)
                          ├─ /api/v1/* · /health · /docs · /openapi.json ──▶ Backend 127.0.0.1:8000
                          └─ 그 밖의 경로 ──▶ 화면 파일(/opt/ispot/web = counselor-web 빌드 결과)
Backend ──▶ PostgreSQL(RDS)
```

| 구성 | 내용 |
| --- | --- |
| Caddy | 컨테이너 `ispot-web`. 화면 파일을 내주고 API 경로만 Backend 로 넘깁니다. 인증서는 `ispot_caddy_data` 볼륨에 남습니다 |
| Backend | 컨테이너 `ispot-backend`. 서버 밖에서는 직접 닿지 않고(`127.0.0.1:8000`), 앞의 Caddy 가 넘긴 접속 IP 만 믿습니다(접속 기록에 실제 IP 가 남음) |
| 설정 | `/opt/ispot/backend.env`(서버에만 있음, 저장소에 넣지 않음) |
| 음성 파일 | `/opt/ispot/storage` (Backend 컨테이너의 `/app/storage`) |
| DB | RDS PostgreSQL. 주소는 `backend.env` 의 `DATABASE_URL` |

### 보안 그룹 (들어오는 연결)

| 포트 | 허용 | 쓰임 |
| --- | --- | --- |
| 80 | 전체 | HTTPS 인증서 발급 확인, HTTP → HTTPS 넘기기 |
| 443 | 허용한 IP 만 | 화면 · API |
| 22 | 관리용(범위는 AWS 콘솔 설정) | SSH 접속 · 배포 |

Backend 포트 8000 은 열지 않습니다(Caddy 만 서버 안에서 부릅니다).
