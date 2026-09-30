# 시연용 설치 · 데이터 준비 도우미 (demo/1001 브랜치 전용).
#
# setup.cmd · reset.cmd · start.cmd 가 부른다. 직접 부를 때:
#   py -3 demo\prepare.py setup   설치 + 시연 데이터
#   py -3 demo\prepare.py reset   시연 데이터만 처음 상태로
#   py -3 demo\prepare.py open    서버가 뜰 때까지 기다렸다가 브라우저를 연다
#
# 데이터는 전부 합성이다. STT · AI 는 mock 이라 설치가 끝나면 인터넷 · API 키가 필요 없다.
# 설정은 backend/.env 가 아니라 backend/.env.demo 에 쓴다(원래 .env 는 건드리지 않는다).
# .env.demo · demo.db · .demo-storage · 샘플 음성은 .gitignore 대상이라 커밋되지 않는다.

import argparse
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import wave
import webbrowser
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "ispotvscode"
VENV_PY = BACKEND / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
    "python.exe" if os.name == "nt" else "python"
)
ENV_FILE = BACKEND / ".env.demo"
DB_FILE = BACKEND / "demo.db"
STORAGE_DIR = BACKEND / ".demo-storage"
SAMPLE_AUDIO = ROOT / "demo" / "sample-audio.wav"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173
# 시연 데이터를 만들 때만 잠깐 띄우는 서버. 시연 서버(8000)와 겹치지 않게 따로 둔다.
SEED_PORT = 8765

COUNSELOR_EMAIL = "counselor@ispot.example.com"
ENV_MARKER = "# demo/1001 시연 전용 설정"


def say(message: str) -> None:
    print(f"[시연 준비] {message}", flush=True)


def fail(message: str) -> None:
    print(f"\n[중단] {message}", flush=True)
    sys.exit(1)


def run(command: List[str], cwd: Path, env: Dict[str, str] = None, what: str = "") -> None:
    result = subprocess.run(command, cwd=str(cwd), env=env)

    if result.returncode != 0:
        fail(f"{what or command[0]} 이(가) 실패했습니다(종료 코드 {result.returncode}). 위 메시지를 확인해 주세요.")


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_http(url: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except OSError:
            pass

        time.sleep(0.5)

    return False


# ---------------------------------------------------------------- 확인


def check_python() -> None:
    version = sys.version_info

    if version < (3, 11):
        fail(f"Python {version.major}.{version.minor} 입니다. 3.11 ~ 3.13 을 설치해 주세요(https://www.python.org/downloads/).")

    if version >= (3, 14):
        say(f"Python {version.major}.{version.minor} 입니다. 3.11 ~ 3.13 에서 확인했습니다. 설치가 실패하면 3.13 을 설치해 주세요.")


def find_npm() -> str:
    node = shutil.which("node")
    npm = shutil.which("npm")

    if not node or not npm:
        fail("Node.js 가 없습니다. 22 LTS 를 설치해 주세요(https://nodejs.org/). 설치 뒤 이 창을 닫고 다시 실행합니다.")

    raw = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    match = re.match(r"v(\d+)\.(\d+)", raw)

    if not match:
        fail(f"Node.js 버전을 읽지 못했습니다({raw!r}).")

    major, minor = int(match.group(1)), int(match.group(2))

    # 화면(ispotvscode)이 쓰는 vite 8 은 Node 20.19 이상 또는 22.12 이상이 필요하다.
    too_old = major < 20 or (major == 20 and minor < 19) or major == 21 or (major == 22 and minor < 12)

    if too_old:
        fail(f"Node.js {raw} 입니다. 22 LTS(22.12 이상)를 설치해 주세요(https://nodejs.org/).")

    return npm


# ---------------------------------------------------------------- 설치


def ensure_venv() -> None:
    if not VENV_PY.exists():
        say("Backend 가상환경을 만듭니다.")
        run([sys.executable, "-m", "venv", str(BACKEND / ".venv")], ROOT, what="가상환경 만들기")

    say("Backend 패키지를 설치합니다(처음에는 1~3분).")
    run(
        [str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check", "-q",
         "-r", "requirements-dev.txt"],
        BACKEND,
        what="pip install",
    )


def install_frontend(npm: str) -> None:
    say("화면(ispotvscode) 패키지를 설치합니다(처음에는 1~3분).")
    run([npm, "ci", "--no-audit", "--no-fund"], FRONTEND, what="npm ci")


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return

    lines = [
        ENV_MARKER,
        "# 로컬 시연 전용. 커밋하지 않는다(.gitignore 의 .env.*).",
        "ENV=local",
        "DEBUG=false",
        "DATABASE_URL=sqlite+pysqlite:///./demo.db",
        "AUDIO_STORAGE_ROOT=./.demo-storage/audio",
        # 이 컴퓨터에서만 쓰는 임의 값. 매번 새로 만들고 어디에도 적어 두지 않는다.
        f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}",
        "STT_PROVIDER=mock",
        "AI_PROVIDER=mock",
        "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173",
        "LOG_LEVEL=INFO",
    ]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    say("시연 설정 파일(backend/.env.demo)을 만들었습니다.")


def demo_env() -> Dict[str, str]:
    """시연 설정을 환경변수로 올린다. 환경변수가 .env 보다 먼저라 원래 .env 가 있어도 시연 값이 쓰인다."""

    env = dict(os.environ)

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()

    env["PYTHONIOENCODING"] = "utf-8"
    env["SEED_USER_PASSWORD"] = demo_password()

    return env


def demo_password() -> str:
    """공용 데모 비밀번호. 저장소의 .cursor/start.sh 에 이미 공개된 개발용 값을 그대로 쓴다."""

    start_sh = ROOT / ".cursor" / "start.sh"
    match = re.search(r"SEED_USER_PASSWORD=(\S+)", start_sh.read_text(encoding="utf-8"))

    if not match:
        fail(".cursor/start.sh 에서 데모 비밀번호를 찾지 못했습니다.")

    return match.group(1).strip("'\"")


def make_sample_audio() -> None:
    """업로드 시연용 무음 WAV(30초). 실제 상담 음성이 아니다. mock STT 는 내용과 관계없이 예시 문장을 준다."""

    SAMPLE_AUDIO.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(SAMPLE_AUDIO), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(b"\x00\x00" * 8000 * 30)


# ---------------------------------------------------------------- 시연 데이터


def reset_data() -> None:
    if port_in_use(BACKEND_PORT):
        fail("시연 서버가 켜져 있습니다. 'I-SPOT Backend' · 'I-SPOT Frontend' 창을 닫고 다시 실행해 주세요.")

    if port_in_use(SEED_PORT):
        fail(f"{SEED_PORT} 포트를 다른 프로그램이 쓰고 있습니다. 그 프로그램을 끄고 다시 실행해 주세요.")

    ensure_env_file()
    env = demo_env()

    say("이전 시연 데이터를 지웁니다.")
    for path in (DB_FILE, BACKEND / "demo.db-journal"):
        if path.exists():
            path.unlink()
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)

    say("DB 를 만듭니다.")
    run([str(VENV_PY), "-m", "alembic", "upgrade", "head"], BACKEND, env, what="alembic upgrade")

    say("데모 계정을 만듭니다.")
    run([str(VENV_PY), "-m", "scripts.seed_users", "--demo"], BACKEND, env, what="seed_users")

    say("시연 데이터를 만듭니다.")
    server = subprocess.Popen(
        [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(SEED_PORT)],
        cwd=str(BACKEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        if not wait_http(f"http://127.0.0.1:{SEED_PORT}/health", 60):
            fail("데이터를 만들 서버가 뜨지 않았습니다.")

        run(
            [str(VENV_PY), str(Path(__file__).resolve()), "seed", "--base-url", f"http://127.0.0.1:{SEED_PORT}"],
            BACKEND,
            env,
            what="시연 데이터 만들기",
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()

    make_sample_audio()


def seed(base_url: str) -> None:
    """상담사 계정으로 사례 6건을 만들고, 회기를 상태마다 하나씩 진행해 둔다(venv 파이썬으로 실행)."""

    sys.path.insert(0, str(BACKEND))
    from scripts.seed_demo_data import DEMO_CASES, TARGET_STATES, ApiClient, advance_session

    api = ApiClient(base_url)

    try:
        api.login(COUNSELOR_EMAIL, os.environ["SEED_USER_PASSWORD"])

        for index, (target, description) in enumerate(TARGET_STATES):
            case = api.call("POST", "/api/v1/cases", 201, json=dict(DEMO_CASES[index % len(DEMO_CASES)]))
            session = api.call(
                "POST", f"/api/v1/cases/{case['id']}/sessions", 201,
                json={"title": f"{index + 1}회기 상담"},
            )
            status = advance_session(api, session["id"], target)
            print(f"  {case['case_number']}  {status:<20} {description}", flush=True)
    finally:
        api.close()


# ---------------------------------------------------------------- 명령


def print_login() -> None:
    print("", flush=True)
    print("  화면        http://localhost:5173", flush=True)
    print("  API 문서    http://localhost:8000/docs", flush=True)
    print(f"  로그인      {COUNSELOR_EMAIL}", flush=True)
    print(f"  비밀번호    {demo_password()}   (공개된 개발용 데모 값)", flush=True)
    print("", flush=True)


def cmd_setup() -> None:
    check_python()
    npm = find_npm()
    ensure_venv()
    install_frontend(npm)
    reset_data()
    say("설치가 끝났습니다. demo\\start.cmd 로 실행합니다.")
    print_login()


def cmd_reset() -> None:
    if not VENV_PY.exists():
        fail("먼저 demo\\setup.cmd 를 실행해 주세요.")

    reset_data()
    say("시연 데이터를 처음 상태로 되돌렸습니다. demo\\start.cmd 로 실행합니다.")
    print_login()


def cmd_open() -> None:
    say("서버가 뜨기를 기다립니다.")

    if not wait_http(f"http://127.0.0.1:{BACKEND_PORT}/health", 90):
        fail("Backend 가 뜨지 않았습니다. 'I-SPOT Backend' 창의 메시지를 확인해 주세요.")

    if not wait_http(f"http://127.0.0.1:{FRONTEND_PORT}/", 90):
        fail("화면 서버가 뜨지 않았습니다. 'I-SPOT Frontend' 창의 메시지를 확인해 주세요.")

    webbrowser.open(f"http://localhost:{FRONTEND_PORT}/")
    say("브라우저를 열었습니다. 끝낼 때는 서버 창 두 개를 닫습니다.")
    print_login()


def main() -> None:
    parser = argparse.ArgumentParser(description="I-SPOT 시연 준비")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup")
    sub.add_parser("reset")
    sub.add_parser("open")
    seed_parser = sub.add_parser("seed")
    seed_parser.add_argument("--base-url", required=True)

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup()
    elif args.command == "reset":
        cmd_reset()
    elif args.command == "open":
        cmd_open()
    else:
        seed(args.base_url)


if __name__ == "__main__":
    main()
