# I-SPOT — VSCode 실행판

Figma Make 최신 I-SPOT 소스를 로컬 VSCode에서 실행할 수 있게 정리한 React + TypeScript + Vite 프로젝트입니다.

## 실행 방법
1. 압축을 풀고 해당 폴더를 VSCode에서 엽니다.
2. VSCode 터미널에서 아래 명령을 실행합니다.

```bash
npm install
npm run dev
```

3. 브라우저에서 `http://localhost:5173`을 엽니다.

## 테스트 로그인
### 상담사
- ID: `이서연`
- 비밀번호: `1234`
- OTP: `123456`

### 관리자
- ID: `김민준`
- 비밀번호: `admin1234`
- OTP: `123456`

## 주요 URL
- `/dashboard`
- `/cases`
- `/recording`
- `/stt-cases`
- `/ai-cases`
- `/plan-cases`
- `/closure-cases`
- `/report-cases`
- `/profile`

## 기술 스택
React 19 / TypeScript / React Router / Tailwind CSS 4 / Vite 8

Figma Make 전용 Vite 플러그인 의존성은 제거하여 일반 VSCode/Vite 환경에서 실행되도록 구성했습니다.
