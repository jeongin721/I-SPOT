# 온담 시니어 데모 서버 (feature/senior 전용)

아동 데모(`web-deploy.sh`, ispot-backend 서버)와 **서버 · 폴더 · 컨테이너 · 데이터베이스를 모두 따로** 쓴다(민규 11/16 · 11/17).

## 구성

| 항목 | 값 |
|---|---|
| 서버 | 새 EC2 1대(GPU 없음, 예: t3.large · 디스크 40GB gp3). **EBS 암호화 켜고 만들기 · 고정 IP(Elastic IP) 붙이기** — IP 가 바뀌면 주소와 인증서도 바뀐다 |
| 위치 | ispot-db 와 같은 VPC. RDS 보안그룹에 이 서버에서 5432 허용 |
| 열 포트 | 80 · 443(HTTPS 인증서 발급 · 접속). 22 는 EC2 Instance Connect |
| 주소 | `<고정 IP 를 - 로 이은 것>.sslip.io` (Caddy 가 Let's Encrypt 로 자동 HTTPS) |
| DB | 같은 RDS(ispot-db) 안의 `ispot_senior` 데이터베이스 + 전용 계정(민규님). 실증 기간 ispot-db 는 끄지 않는다 |
| 키 | JWT_SECRET_KEY · PII_ENCRYPTION_KEYS · PII_INDEX_KEY 는 데모와 다른 새 값 |
| 서버 안 폴더 | `/opt/onda` — 저장소 `I-SPOT`(feature/senior), `backend.env`, `storage`(녹음), `web`(화면), `hf-cache` |
| 컨테이너 | `onda-backend`(127.0.0.1:8000) · `onda-web`(Caddy) |

## 처음 한 번

```bash
# Docker 설치(Amazon Linux 2023): sudo dnf install -y docker git && sudo systemctl enable --now docker
sudo mkdir -p /opt/onda
sudo git clone -b feature/senior https://github.com/jeongin721/I-SPOT.git /opt/onda/I-SPOT
sudo cp /opt/onda/I-SPOT/deploy/senior.env.example /opt/onda/backend.env
sudo chmod 600 /opt/onda/backend.env      # 값 채우기
```

## 배포 (여러 번 해도 됨)

```bash
sudo env SITE=<주소> WITH_STT=1 bash /opt/onda/I-SPOT/deploy/senior-deploy.sh
# SENIOR_AI_PROVIDER=modeling 이면 WITH_MODELING=1 을 더한다
```

## 계정 · 합성 데이터

```bash
# 관리자 · 담당자 계정(비밀번호는 출력됨, 처음 로그인 때 바꿀 필요 없는 값)
sudo docker exec -it onda-backend python -m scripts.seed_users --email <이메일> --name <이름> --role COUNSELOR
# 개발 · 확인 기간 합성 어르신 3명(실제 정보 아님). STT 가 mock 일 때 대본이 맞는다
sudo docker exec -it onda-backend python -m scripts.seed_senior_demo --email <담당자 이메일> --password '<비밀번호>'
```

## 실제 어르신 정보를 넣기 전 (첫 동행 전)

1. 본문 암호화 1단계를 feature/senior 에 얹고 이 DB 에서 `alembic upgrade` → `scripts.encrypt_content_columns`(dry-run → `--apply` → `--check`).
2. 동의서: 민감정보 수집 + 국외 이전(녹음 원본 → ElevenLabs, 가린 글 → OpenAI) 두 항목, 동의 일시 · 받은 담당자 기록.
3. 합성 데이터 지우기, 실제 계정만 남기기.
4. SENIOR_AI_PROVIDER=modeling 을 켤지 정하기(SENIOR_AI_ALLOW_IN_PRODUCTION 잠금).

## 12/11 실증 뒤 정리 (민규님과 정하기)

데이터베이스 `ispot_senior` 삭제(필요하면 먼저 정해진 사람만 볼 수 있는 곳에 내보내기) · RDS 스냅샷 중 이 DB 가 든 것 처리 ·
`/opt/onda/storage` 녹음 삭제 · EC2 · EBS · 고정 IP 반납 · 외부 API(ElevenLabs · OpenAI) 쪽 보관 데이터 확인.
