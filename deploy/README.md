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
- 끝에 `WEB-DEPLOY DONE` 과 `/health` 결과가 나오면 성공입니다. 브라우저에서 `https://<주소>/health` 로도 확인합니다.
- 주소를 바꿀 때만 `SITE` 를 넘깁니다(기본값은 지금 주소). `sudo` 는 환경변수를 넘기지 않으므로 이렇게 씁니다.

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
