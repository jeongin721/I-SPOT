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

- 먼저 `git pull` 하는 것은 스크립트 자신도 최신으로 받기 위해서입니다. 스크립트도 시작할 때 `origin/main` 을 다시 받아 fast-forward 합니다(main 만 배포). 그때 스크립트 자신이 바뀌었으면 새 판으로 처음부터 다시 시작합니다(`배포 스크립트가 바뀌어 새 판으로 처음부터 다시 시작합니다`). 이 기능은 2026-10-22 판부터라, 그보다 옛 판이 서버에 있으면 `git pull` 을 빼먹었을 때 옛 판이 끝까지 돌아 새 main 의 이미지를 옛 방식으로 만들다 멈출 수 있습니다(`COPY failed … backend/requirements.txt`). 그때는 한 번 더 돌리면 됩니다.
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

### 머지 전 브랜치를 데모로 확인하기 (`DEPLOY_BRANCH`)

스크립트는 1/5 단계에서 기본으로 `main` 으로 바꿔 빌드합니다. PR 브랜치를 머지 전에 데모로 보려면 그 브랜치로 바꾼 뒤(옵션이 든 스크립트를 쓰려고) `DEPLOY_BRANCH` 를 넘깁니다. 저장소(GitHub)에는 아무것도 올리지 않습니다.

```bash
cd /opt/ispot/I-SPOT && sudo git fetch origin && sudo git checkout feature/infra-integration
sudo env DEPLOY_BRANCH=feature/infra-integration WITH_MODELING=1 WITH_STT=1 WITH_GPU=1 bash deploy/web-deploy.sh
```

머지된 뒤 `DEPLOY_BRANCH` 없이 실행하면 다시 `main` 으로 바꿔 배포합니다. DB 구조가 다른 브랜치면 migration 이 그 브랜치 기준으로 돌기 때문에, main 으로 돌아오기 전에 확인합니다.

## 모델까지 띄우기 (`AI_PROVIDER=modeling`)

기본 이미지는 mock · pipeline 만 돌립니다. modeling(`ai/modeling/abuse`, 학대 유형 분류 모델 + 이름 가리기 + OpenAI)은 이미지에 torch · transformers · openai 와 모델 파일이 더 있어야 해서 따로 켭니다.

1. **모델 파일 두 개를 서버에 둡니다.** `roberta_abuse_qa_child_v3_best.pth` · `roberta_abuse_note_v1_best.pth` 는 저장소에 없습니다(`.gitignore`). 기본 자리는 `/opt/ispot/I-SPOT/ai/modeling/abuse/weight/` 이고, 다른 폴더면 `MODELING_WEIGHT_DIR` 로 줍니다. 이미지에 넣지 않고 컨테이너의 `/ai/modeling/abuse/weight` 에 읽기 전용으로 붙입니다.
2. **`backend.env` 를 고칩니다.** `AI_PROVIDER=modeling`, `OPENAI_API_KEY=<키>`. `ENV=production` 이면 `AI_MODELING_ALLOW_IN_PRODUCTION=true` 도 있어야 뜹니다 — **가상 데이터만 있는 서버에서만** 켭니다(가리기가 아직 완전하지 않음, 위 '중간에 멈췄을 때').
3. **`WITH_MODELING=1` 로 배포합니다.**

   ```bash
   sudo env WITH_MODELING=1 bash deploy/web-deploy.sh
   ```

   - 이미지에 CPU 판 torch(`download.pytorch.org/whl/cpu`) · `backend/requirements-modeling.txt` 를 더 깝니다. 처음 빌드는 몇 분 더 걸리고 이미지가 커집니다.
   - 모델 파일이 없으면 시작 전에 멈춥니다. `backend.env` 가 `AI_PROVIDER=modeling` 인데 `WITH_MODELING=1` 없이 돌려도 멈춥니다(torch 가 없는 이미지로 뜨면 첫 분석에서야 실패하므로).
   - 이름 인식(`Leo97/KoELECTRA-small-v3-modu-ner`) · klue 토크나이저는 첫 분석 때 Hugging Face 에서 받아 `/opt/ispot/hf-cache` 에 둡니다(서버에서 인터넷이 돼야 함). 첫 분석은 그만큼 늦습니다.
   - 분류 모델 두 개와 이름 인식 모델을 메모리에 올리므로 서버 메모리가 넉넉해야 합니다(얼마나 쓰는지는 재지 않았습니다).
   - **STT 검수의 '관련 조문'** 은 법령 캐시(`law_cache/아동복지법.json` 등, `.gitignore`)를 읽습니다. `/opt/ispot/I-SPOT/law_cache/` 에 두면(다른 폴더면 `LAW_CACHE_HOST_DIR`) 컨테이너의 `/law_cache` 에 붙입니다. 캐시를 만드는 곳에서 복사해 오거나, 분석은 캐시만 읽고(오래됐어도) 국가법령정보센터를 부르지 않습니다. 법령이 개정돼 캐시를 새로 받으려면 `backend.env` 에 `LAW_API_OC=<국가법령정보센터 OC>` 를 넣고 `docker exec ispot-backend python -m law.refresh_cache` 를 돌립니다. 컨테이너를 `LAW_API_OC` 없이 띄운 뒤에 넣었다면 `web-deploy.sh` 로 컨테이너를 다시 만든 다음 돌려야 합니다(env-file 은 컨테이너를 만들 때만 읽혀서, 실행 중인 컨테이너의 `docker exec` 에는 새 값이 없습니다). 캐시가 없으면 분석은 되고 조문만 비어 오며 분석 경고에 한 줄 남습니다.

## GPU 로 띄우기 (`WITH_GPU=1`)

modeling 의 분류 모델(`infer_abuse_qa_v3.py`)은 `torch.cuda.is_available()` 이면 알아서 GPU 를 씁니다. 그러려면 서버 · 이미지 · 컨테이너 셋 다 준비돼야 합니다. STT 는 클라우드 API(ElevenLabs · Deepgram)라 GPU 와 상관없습니다.

2026-10-22 `ispot-backend` 를 t3.xlarge 에서 **g4dn.xlarge**(T4 16 GB, 서울 온디맨드 시간당 0.647 USD, 켜 둔 시간만큼 요금)로 바꿨습니다. 쓰지 않을 때는 끕니다.

1. **서버 한 번 준비** (드라이버 + nvidia-container-toolkit, 처음 한 번):

   ```bash
   cd /opt/ispot/I-SPOT && sudo git pull --ff-only && sudo bash deploy/gpu-setup.sh && sudo reboot
   ```

   재부팅 뒤 `nvidia-smi -L` 에 GPU 한 줄이 나오고, `sudo docker run --rm --gpus all python:3.12-slim nvidia-smi -L` 도 같은 줄을 찍어야 합니다. Ubuntu 의 `ubuntu-drivers --gpgpu install` 이 고른 드라이버를 씁니다(어느 판인지는 실행 기록에 남음).
2. **`WITH_MODELING=1 WITH_GPU=1` 로 배포합니다.**

   ```bash
   sudo env WITH_MODELING=1 WITH_GPU=1 bash deploy/web-deploy.sh
   ```

   - 이미지에 CPU 판 대신 PyPI 의 CUDA 판 torch 를 깝니다(몇 GB 더 큼, 처음 빌드가 더 오래 걸림). 디스크가 모자라면 `sudo docker system prune -f` 로 옛 이미지를 지우거나 볼륨을 늘립니다.
   - 컨테이너를 `--gpus all` 로 띄웁니다. 드라이버 · nvidia 런타임이 없으면 스크립트가 시작 전에 멈춥니다. `WITH_GPU=1` 은 `WITH_MODELING=1` 과 같이 써야 합니다.
   - GPU 가 있는 서버에서 `WITH_GPU=1` 없이 돌리면 주의만 찍고 CPU 판으로 띄웁니다(돌긴 하지만 느림).
   - 컨테이너 안에서 GPU 를 쓰는지 확인: `sudo docker exec ispot-backend python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` → `True NVIDIA T4` 같은 한 줄.

## STT 까지 띄우기 (`STT_PROVIDER=module`)

기본 이미지의 STT 는 mock 입니다. 실제 STT 모듈(`stt/transcribe_service`, 기본 ElevenLabs · 실패하면 Deepgram)을 쓰려면 이미지에 `stt/` 와 두 SDK 가 더 있어야 해서 따로 켭니다.

1. **`backend.env` 를 고칩니다.** `STT_PROVIDER=module`, `I_SPOT_STT_PROVIDER=elevenlabs`, `ELEVENLABS_API_KEY=<키>`(되돌림까지 살리려면 `DEEPGRAM_API_KEY` 도). 둘 다 유료 API 라 어느 키를 쓸지는 팀에서 정합니다. 키가 하나도 없으면 스크립트가 주의를 찍고 계속 가지만, 전사 요청은 모두 실패합니다.
2. **`WITH_STT=1` 로 배포합니다.** modeling 과 같이 쓰면 둘 다 넘깁니다.

   ```bash
   sudo env WITH_STT=1 bash deploy/web-deploy.sh
   sudo env WITH_MODELING=1 WITH_STT=1 bash deploy/web-deploy.sh
   ```

   - 이미지에 `backend/requirements-stt.txt`(deepgram-sdk · elevenlabs · librosa · numba · soundfile)를 더 깝니다. `backend.env` 가 `STT_PROVIDER=module` 인데 `WITH_STT=1` 없이 돌리면 멈춥니다.
   - 구간별 음성 참고 표시(정담원 님 `stt/voice_marks`)까지 켜려면 `backend.env` 에 `VOICE_MARKS_PROVIDER=module` 을 더합니다. 같은 `WITH_STT=1` 이미지에 librosa · numba · soundfile 이 들어 있고, numba 캐시 자리(`NUMBA_CACHE_DIR=/tmp/numba-cache`)는 이미지가 정합니다. 기본(`off`)이면 아무것도 하지 않습니다. 참고 표시일 뿐 판정이 아닙니다(`backend/docs/API_CONTRACT.md` 16절).
   - `openai-whisper`(`I_SPOT_STT_PROVIDER=whisper` 일 때만) · `pyannote`(별도 화자 분리 때만) · `ffmpeg`(기본 꺼진 `I_SPOT_SINGLE_SPEAKER_FALLBACK` 때만)는 넣지 않았습니다. 그 설정을 켜려면 이미지에 더해야 합니다.
   - 전사 한 번에 최대 `STT_TIMEOUT_SECONDS`(기본 600초)까지 기다립니다. 음성 파일은 `/opt/ispot/storage`(컨테이너 `/app/storage`)에 있어 그대로 읽습니다.

## 개인 식별 정보 키 (`PII_ENCRYPTION_KEYS` · `PII_INDEX_KEY`)

아동 실명 · 생년월일 · 가족 정보는 이 두 키로 암호화해 저장합니다(2026-10-30, `backend/README.md` 7절). `backend.env` 가
`ENV=production` 인데 두 키가 없으면 스크립트가 1/5 전에 멈춥니다(키 없이 Backend 가 뜨지 않으므로). **처음 한 번만** 아래를 합니다.

1. 키 두 개를 만듭니다(각각 따로, 서로 다른 값): `python3 -c "import base64, secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"`
2. AWS SSM Parameter Store 에 **SecureString** 으로 둡니다(예: `/ispot/backend/PII_ENCRYPTION_KEYS` 값 `k1:<첫 키>`, `/ispot/backend/PII_INDEX_KEY` 값 `<둘째 키>`).
3. **사본 1부를 AWS 밖 비밀번호 관리자**에 둡니다. 키를 잃으면 저장한 실명을 되살릴 수 없습니다. 키 값은 메신저 · 메일 · 저장소로 주고받지 않습니다.
4. 서버의 `/opt/ispot/backend.env` 에 두 줄(`PII_ENCRYPTION_KEYS=k1:…`, `PII_INDEX_KEY=…`)을 넣고 스크립트를 다시 돌립니다. 터미널 기록에 남지 않게 편집기로 넣습니다.

- 한 번 저장을 시작한 뒤 키를 바꾸면 옛 값을 풀 수 없습니다. 바꿀 때는 `backend/README.md` 7절의 '키 바꾸기' 순서(새 키를 맨 앞에 넣고 `scripts.reencrypt_personal_info`)를 따릅니다.
- 개발용 키(`backend/.env.example` 의 값)는 `ENV=production` 에서 거절됩니다.

## 디스크 · 빌더

2026-10-28 에 빌드가 두 번 `no space left on device` 로 끊긴 뒤 바꾼 것입니다.

- **루트 볼륨 64GB**(30GB 에서 늘림, gp3). modeling · GPU · STT 를 다 넣은 이미지가 약 9.5GB 라, 돌고 있는 이미지 한 벌 + 새 이미지 한 벌 + 빌드 캐시(약 10GB)가 함께 있어야 배포가 됩니다. 배포 전 `df -h /` 로 여유를 보고, 도커가 얼마나 쓰는지는 `sudo docker system df` 로 봅니다. 볼륨을 더 늘리면 콘솔 '볼륨 수정' 뒤 서버에서 `sudo growpart /dev/nvme0n1 1 && sudo resize2fs /dev/nvme0n1p1`(끄지 않고 됨).
- **BuildKit**: 서버에 `docker-buildx`(0.30.1, apt)를 깔았고, 스크립트는 buildx 가 있으면 `DOCKER_BUILDKIT=1` 로 이미지를 만듭니다. 옛 빌더는 RUN 층을 commit 할 때 한 번 더 복사해 디스크를 두 배로 쓰고, 그러다 끊기면 그 단계의 임시 컨테이너(무작위 이름, 5.9GB)가 `sudo docker ps -a` 에 `Exited` 로 남습니다 — `sudo docker rm <이름>` 으로 지우고, 태그 없는 이미지는 `sudo docker image prune -f` 로 지웁니다. 빌드 캐시가 커지면 `sudo docker buildx prune -f`(다음 빌드가 torch 를 다시 받습니다).
- g4dn 에 달린 116GB 로컬 NVMe(`nvme1n1`)는 서버를 끄면 비워지는 임시 디스크라 이미지 저장소로 쓰지 않습니다.
- 구간별 음성 참고 표시 모듈의 시험(루트 `tests/test_voice_marks.py`, 22개)은 이미지에 들어 있지 않습니다. 이미지 안의 librosa · numba 로 돌려 보려면:

  ```bash
  sudo docker run --rm -v /opt/ispot/I-SPOT/tests:/tests:ro -w / ispot-backend sh -c "pip install -q pytest==9.1.1 && python -B -m pytest /tests/test_voice_marks.py -q -p no:cacheprovider"
  ```

  켜진 뒤에는 `sudo docker logs ispot-backend 2>&1 | grep '음성 참고 표시'` 에 "모듈 준비 완료"(warm-up) 가 찍히고, 업로드 · STT 뒤 "저장 … status=ANALYZED" 가 찍힙니다.

## 스크립트가 하는 일 (`web-deploy.sh`)

| 단계 | 하는 일 |
| --- | --- |
| 1/5 | `/opt/ispot/I-SPOT` 에서 `origin/main` 을 받아 fast-forward. 스크립트 자신이 바뀌었으면 새 판으로 처음부터 다시 시작(한 번만) |
| 2/5 | Node 컨테이너(`node:22.12.0-alpine`)에서 `counselor-web` 을 `npm ci` · `npm run build` 하고 결과를 `/opt/ispot/web` 에 복사 |
| 3/5 | Backend 이미지(`ispot-backend`)를 저장소 루트에서 다시 만들고(`-f backend/Dockerfile`, 넣는 것은 루트 `.dockerignore`, `WITH_MODELING=1` 이면 modeling 패키지(`WITH_GPU=1` 이면 CUDA 판 torch), `WITH_STT=1` 이면 STT SDK 까지) `alembic upgrade head` 로 DB 를 최신 구조로 |
| 4/5 | Backend 컨테이너를 `127.0.0.1:8000` 에서만 받도록 다시 띄움(`--proxy-headers --forwarded-allow-ips 127.0.0.1`, `WITH_MODELING=1` 이면 모델 파일 · Hugging Face 캐시 폴더를 붙임, `WITH_GPU=1` 이면 `--gpus all`) |
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

## 법령 · 매뉴얼 AI 질문 켜기 (`LAW_QA_PROVIDER=modeling`)

LawGuide 화면의 'AI 에게 묻기'(API_CONTRACT 17절)는 기본 `mock`(고정 답변)으로 뜹니다. 실제로 켜려면:

1. 이미지는 `WITH_MODELING=1` 로 만든 것이어야 합니다(openai 가 들어 있음). 이미지에 `law/` · `manual/` 이 복사됩니다(사진 폴더는 넣지 않음).
2. `backend.env` 에 `LAW_QA_PROVIDER=modeling`, `OPENAI_API_KEY=<키>`. `ENV=production` 이면 `LAW_QA_ALLOW_IN_PRODUCTION=true` 도 있어야 뜹니다 — **가상 데이터만 있는 서버에서만**(질문이 가려진 채 OpenAI 로 나가지만 등록 실명 대조는 돌지 않음).
3. 법령 캐시: 위 '관련 조문' 과 같은 `/law_cache` 를 씁니다. 캐시가 없으면 서버 시작 때(그리고 첫 질문 때) 국가법령정보센터를 조회하므로 `LAW_API_OC=<OC>` 를 넣거나 캐시를 복사해 둡니다. 조회에 실패하면 질문은 `503 LAW_SOURCE_UNAVAILABLE` 입니다.
4. **매뉴얼 사진은 올리지 않습니다.** 기관 대외비라 `MANUAL_QA_ATTACH_IMAGES` 는 기본 끔이고 `backend.env` 에 적지 않습니다(기관 허락 전에는 켜지 않음). 꺼져 있으면 법령만으로 답하고 응답의 `sources.manual` 은 빈 목록입니다.
5. 비용 · 한도: 호출마다 법령 전문(약 9.8만 자)이 OpenAI 로 나갑니다. 사용자당 분당 6회(`LAW_QA_RATE_LIMIT_PER_MINUTE`) · 서버 동시 2건(`LAW_QA_MAX_CONCURRENCY`)이 기본이고, 데모 서버의 키가 개인 키면 비용이 그 키로 나갑니다.

확인: `curl -s -X POST http://localhost:8000/api/v1/law-guide/questions -H "Authorization: Bearer <토큰>" -H "Content-Type: application/json" -d '{"question":"응급조치 기간은 얼마나 돼요?"}'` 가 200 과 `sources.laws` 를 돌려주면 됩니다.
