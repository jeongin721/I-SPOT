# 서버를 띄우는 명령이 접속 IP 를 믿지 않게 되어 있는지 확인하는 테스트.
#
# uvicorn 은 기본으로 127.0.0.1 에서 온 요청의 X-Forwarded-For 를 믿고 request.client.host 를 그 값으로 바꾼다.
# 앱은 바뀐 뒤의 값만 볼 수 있어 코드로는 막을 수 없다. 감사 로그 IP 를 위조하지 못하게 하려면
# 서버를 띄우는 명령마다 --no-proxy-headers 를 붙여야 한다. 새 실행 명령을 더하고 이 옵션을 빼먹으면 여기서 실패한다.

import re
from pathlib import Path
from typing import Iterator, Tuple

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

# uvicorn 으로 서버를 여는 명령이 들어 있는 파일. 파일을 더하면 여기에도 더한다.
LAUNCH_FILES = [
    REPO / "README.md",
    BACKEND / "README.md",
    BACKEND / "Dockerfile",
    REPO / "docker-compose.yml",
    REPO / ".cursor" / "environment.json",
]

# 서버를 여는 명령 한 줄(앱 경로 app.main:app 이 들어 있는 줄). Dockerfile 은 "uvicorn", "app.main:app" 모양이다.
_COMMAND = re.compile(r"uvicorn[\"', ]+app\.main:app")


def _launch_lines(path: Path) -> Iterator[Tuple[int, str]]:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _COMMAND.search(line) and not line.lstrip().startswith("#"):
            yield number, line


@pytest.mark.parametrize("path", LAUNCH_FILES, ids=lambda p: p.name)
def test_every_server_launch_command_ignores_forwarded_headers(path: Path) -> None:
    lines = list(_launch_lines(path))

    assert lines, f"{path.name} 에서 서버 실행 명령을 찾지 못했다 — 파일 목록이나 찾는 규칙을 고쳐야 한다"

    missing = [f"{path.name}:{number}: {line.strip()}" for number, line in lines if "--no-proxy-headers" not in line]

    assert not missing, "아래 실행 명령에 --no-proxy-headers 가 없다(감사 로그 IP 위조 가능):\n" + "\n".join(missing)
