# I-SPOT — VSCode 실행판

Figma Make 최신 I-SPOT 소스를 로컬 VSCode에서 실행할 수 있게 정리한 React + TypeScript + Vite 프로젝트입니다.

## 실행 방법
0. Backend 를 먼저 켭니다(`backend/README.md` 부록 A.1~A.4). 로그인과 사례 · 회기 화면이 모두 Backend API 를 씁니다.
   개발 서버(vite)가 `/api/v1` 요청을 `127.0.0.1:8000` 으로 넘깁니다. Backend 주소가 다르면 `VITE_BACKEND_URL` 환경변수로 바꿉니다.
1. 압축을 풀고 해당 폴더를 VSCode에서 엽니다.
2. VSCode 터미널에서 아래 명령을 실행합니다.

```bash
npm install
npm run dev
```

3. 브라우저에서 `http://localhost:5173`을 엽니다.

## 테스트 로그인
로그인은 Backend 계정으로 합니다. 이 화면에 들어 있는 계정은 없습니다.

- `backend` 폴더에서 `PYTHONPATH=. python scripts/seed_users.py --demo` 로 데모 계정을 만듭니다.
  - 상담사: `counselor@ispot.example.com`
  - 관리자: `admin@ispot.example.com` (관리자 화면은 아직 Backend 에 연결되지 않아 예시 데이터로 보입니다)
- 비밀번호는 계정을 처음 만들 때 위 명령이 출력한 값입니다. `SEED_USER_PASSWORD` 환경변수를 정해 두었으면 그 값이고, `.cursor/start.sh` 로 만들었으면 그 파일의 `SEED_USER_PASSWORD` 기본값입니다.
- 이미 있는 계정은 명령을 다시 돌려도 비밀번호가 바뀌지 않고, 비밀번호를 출력하지도 않습니다. 모르면 `backend/README.md` 부록 A.7 대로 DB 를 지우고 다시 만들거나, `backend` 폴더에서 `python -m scripts.unlock_user --email <이메일> --reset-password` 로 임시 비밀번호를 받습니다.
- 로그인을 5번 틀리면 계정이 잠기고 저절로 풀리지 않습니다(그 뒤로는 맞는 비밀번호도 거절). `python -m scripts.unlock_user --email <이메일>` 로 풉니다(`backend/README.md` 2.5).
- 자세한 것은 `backend/README.md` 부록 A.3 · A.5 를 봅니다.
- 2단계 인증(OTP)은 아직 없습니다(팀 결정 대기).

## 주요 URL
- `/dashboard`
- `/cases`
- `/follow-up`
- `/stt-cases`
- `/case-management`
- `/ai-cases`
- `/plan-cases`
- `/closure-cases`
- `/report-cases`
- `/profile`

## 기술 스택
React 19 / TypeScript / React Router / Tailwind CSS 4 / Vite 8

Figma Make 전용 Vite 플러그인 의존성은 제거하여 일반 VSCode/Vite 환경에서 실행되도록 구성했습니다.
