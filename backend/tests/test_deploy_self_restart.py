# 배포 스크립트(deploy/web-deploy.sh)가 1/5 에서 main 을 받아 자기 자신이 바뀌면 새 판으로 다시 시작하는지 확인하는 테스트.
#
# 2026-10-22 데모 서버에서 git pull 없이 스크립트를 돌리자, 옛 판이 1/5 에서 새 main 을 받고도 끝까지 돌아 3/5 에서 새 Dockerfile 을
# 옛 빌드 명령(backend/ 만 컨텍스트)으로 만들다 멈췄다. 실제 서버 · Docker 없이, 1/5 의 { } 묶음만 떼어 임시 git 저장소
# (원격 하나 + 서버 체크아웃 하나)에서 돌린다.

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "deploy" / "web-deploy.sh"
BASH = shutil.which("bash")
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(BASH is None or GIT is None, reason="bash · git 이 있어야 돌릴 수 있다")

NEW_SCRIPT = '#!/bin/bash\necho "NEW-SCRIPT restarted=${WEB_DEPLOY_RESTARTED:-}"\n'


def _step1_block() -> str:
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('echo "== 1/5'))
    opening = lines.index("{", start)
    closing = lines.index("}", opening)
    return "\n".join(lines[opening:closing + 1])


def _env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "WEB_DEPLOY_RESTARTED"}
    env.update({
        "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
    })
    env.update(extra or {})
    return env


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        [GIT, "-c", "core.autocrlf=false", *args], cwd=cwd, env=_env(), check=True, capture_output=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))  # bash 가 읽으므로 줄끝은 LF 그대로


@pytest.fixture
def repos(tmp_path: Path):
    """원격(main 에 1/5 묶음을 가진 옛 스크립트)과, 그것을 받아 둔 서버 체크아웃."""

    origin, work, server = tmp_path / "origin.git", tmp_path / "work", tmp_path / "server"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    old_script = (
        "#!/bin/bash\nset -euo pipefail\n"
        f'REPO="{server.as_posix()}"\ncd "$REPO"\n'
        + _step1_block()
        + '\necho "OLD-SCRIPT-CONTINUED"\n'
    )
    _write(work / "deploy" / "web-deploy.sh", old_script)
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "old")
    _git(work, "push", "-q", str(origin), "main")
    _git(tmp_path, "clone", "-q", "-c", "core.autocrlf=false", str(origin), str(server))
    return origin, work, server


def _push(origin: Path, work: Path, path: str, text: str) -> str:
    _write(work / path, text)
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", f"change {path}")
    _git(work, "push", "-q", str(origin), "main")
    return _git(work, "rev-parse", "HEAD")


def _run(server: Path, extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        # 스크립트는 한글을 UTF-8 로 찍는다. Windows 기본 인코딩(cp949)으로 읽으면 stdout 이 None 이 된다.
        [BASH, "deploy/web-deploy.sh"], cwd=server, env=_env(extra), capture_output=True, encoding="utf-8",
        errors="replace", timeout=60,
    )


def test_restarts_with_new_script_when_main_changed_it(repos) -> None:
    origin, work, server = repos
    new_head = _push(origin, work, "deploy/web-deploy.sh", NEW_SCRIPT)

    result = _run(server)

    assert result.returncode == 0, result.stderr
    assert "새 판으로 처음부터 다시 시작합니다" in result.stdout
    assert "NEW-SCRIPT restarted=1" in result.stdout
    assert "OLD-SCRIPT-CONTINUED" not in result.stdout
    assert _git(server, "rev-parse", "HEAD") == new_head


def test_keeps_going_when_main_did_not_change_the_script(repos) -> None:
    origin, work, server = repos
    new_head = _push(origin, work, "README.md", "다른 파일만 바뀜\n")

    result = _run(server)

    assert result.returncode == 0, result.stderr
    assert "OLD-SCRIPT-CONTINUED" in result.stdout
    assert "다시 시작" not in result.stdout
    assert _git(server, "rev-parse", "HEAD") == new_head


def test_stops_instead_of_restarting_twice(repos) -> None:
    # 다시 시작한 판에서 또 바뀌면(그사이 main 에 새 배포 스크립트) 되풀이하지 않고 멈춘다.
    origin, work, server = repos
    _push(origin, work, "deploy/web-deploy.sh", NEW_SCRIPT)

    result = _run(server, {"WEB_DEPLOY_RESTARTED": "1"})

    assert result.returncode == 1
    assert "다시 시작한 뒤에도 바뀌었습니다" in result.stdout
    assert "NEW-SCRIPT" not in result.stdout


def test_deploys_named_branch_with_deploy_branch(repos) -> None:
    """DEPLOY_BRANCH 를 넘기면 main 대신 그 브랜치를 받아 바꾼다(머지 전 브랜치를 데모로 확인, 2026-10-30)."""

    origin, work, server = repos
    _git(work, "checkout", "-q", "-b", "feature/x")
    _write(work / "README.md", "브랜치에만 있는 변경\n")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "branch change")
    _git(work, "push", "-q", str(origin), "feature/x")
    branch_head = _git(work, "rev-parse", "HEAD")

    result = _run(server, {"DEPLOY_BRANCH": "feature/x"})

    assert result.returncode == 0, result.stderr
    assert "OLD-SCRIPT-CONTINUED" in result.stdout
    assert _git(server, "rev-parse", "--abbrev-ref", "HEAD") == "feature/x"
    assert _git(server, "rev-parse", "HEAD") == branch_head
