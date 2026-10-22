# Backend 이미지가 AI_PROVIDER=modeling 에 필요한 ai/ · agent/ 를 담고, 비밀값 · 로컬 환경은 담지 않는지 확인하는 테스트.
#
# app.adapters.module_loader 는 REPO_ROOT(backend 의 부모)를 sys.path 에 넣어 ai/ · agent/ 를 import 한다. 이미지를 backend/
# 폴더만으로 만들면 그 자리에 ai/ 가 없어, 데모 서버에서 AI_PROVIDER=modeling 이 "No module named 'ai'" 로 막혔다
# (2026-10-22 이경진 님). 그래서 빌드 컨텍스트를 저장소 루트로 바꿨다. 루트 컨텍스트에서는 backend/.dockerignore 를
# 읽지 않으므로, 루트 .dockerignore 가 넣을 폴더만 고르고 비밀값을 뺀다. 이 둘 중 하나가 되돌아가면 여기서 실패한다.

import re
from pathlib import Path
from typing import List

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


def _lines(path: Path) -> List[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]


def _active(path: Path) -> List[str]:
    return [line for line in _lines(path) if line and not line.startswith("#")]


def test_backend_image_copies_ai_and_agent_to_repo_root_of_container() -> None:
    # 컨테이너에서 backend 는 /app 이라 REPO_ROOT 는 / 이다. contract_adapter 는 ai.modeling.abuse 와
    # agent.summary_converter 를 부른다.
    lines = _active(BACKEND / "Dockerfile")

    assert "WORKDIR /app" in lines
    assert "COPY ai/ /ai/" in lines
    assert "COPY agent/ /agent/" in lines
    assert "COPY backend/ ." in lines


def test_backend_image_copies_stt_module_and_its_root_helper() -> None:
    # STT_PROVIDER=module 은 stt.transcribe_service 를 부르고, stt/ispot_stt.py 는 저장소 루트의 speaker_role_runtime.py 를
    # 함수 안에서 import 한다. 데모 서버에서 modeling 을 켠 뒤 STT 도 켜려다 "No module named 'stt'" 로 막혔다(2026-10-22 이경진 님).
    lines = _active(BACKEND / "Dockerfile")

    assert "COPY stt/ /stt/" in lines
    assert "COPY speaker_role_runtime.py /speaker_role_runtime.py" in lines
    assert {"!stt/", "!speaker_role_runtime.py"} <= set(_active(REPO / ".dockerignore"))
    assert (REPO / "backend" / "requirements-stt.txt").exists()

    deploy = (REPO / "deploy" / "web-deploy.sh").read_text(encoding="utf-8")
    assert '--build-arg WITH_STT="$WITH_STT"' in deploy


def test_root_dockerignore_sends_only_backend_ai_agent_and_keeps_secrets_out() -> None:
    lines = _active(REPO / ".dockerignore")

    assert lines[0] == "*", "맨 처음에 전부 빼고 필요한 폴더만 다시 넣어야 한다(experiments · results 등 큰 폴더가 넘어가지 않게)"
    assert {"!backend/", "!ai/", "!agent/"} <= set(lines)
    for secret_or_local in ["backend/.env", "backend/.env.*", "backend/.venv/", "backend/storage/", "backend/*.db"]:
        assert secret_or_local in lines, f"{secret_or_local} 가 이미지에 들어갈 수 있다"
    # 모델 파일은 저장소에 없고 띄울 때 붙인다(deploy/web-deploy.sh). 서버 체크아웃에 있어도 이미지에 굽지 않는다.
    assert "ai/modeling/abuse/weight/" in lines
    # 루트 컨텍스트에서는 쓰이지 않는 파일이라, 남아 있으면 그 규칙이 지켜진다고 잘못 믿게 된다.
    assert not (BACKEND / ".dockerignore").exists()


def test_every_backend_image_build_uses_repo_root_context() -> None:
    deploy = (REPO / "deploy" / "web-deploy.sh").read_text(encoding="utf-8")
    builds = [line for line in deploy.splitlines() if re.search(r"^\s*docker build\b", line)]

    assert builds, "deploy/web-deploy.sh 에서 docker build 를 찾지 못했다"
    for line in builds:
        assert '-f "$REPO/backend/Dockerfile" "$REPO"' in line, line

    compose = _lines(REPO / "docker-compose.yml")
    backend_build = compose[compose.index("build:") + 1:compose.index("container_name: ispot-backend")]

    assert "context: ." in backend_build
    assert "dockerfile: backend/Dockerfile" in backend_build


def test_gpu_build_uses_cuda_torch_and_passes_gpu_to_container() -> None:
    # 2026-10-22 ispot-backend 를 g4dn.xlarge 로 바꿨다. 모델 코드는 torch.cuda.is_available() 이면 GPU 를 쓰지만, 이미지가
    # CPU 판 torch 이거나 컨테이너에 --gpus 가 없으면 GPU 인스턴스에서도 CPU 로 돈다. 둘 중 하나가 되돌아가면 여기서 실패한다.
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG WITH_GPU=0" in dockerfile
    assert 'if [ "$WITH_GPU" = "1" ]' in dockerfile
    # CPU 판은 기본값으로 남는다(GPU 없는 서버 · 로컬 docker-compose).
    assert "--index-url https://download.pytorch.org/whl/cpu torch==" in dockerfile

    deploy = (REPO / "deploy" / "web-deploy.sh").read_text(encoding="utf-8")
    assert '--build-arg WITH_GPU="$WITH_GPU"' in deploy
    assert "GPU_FLAGS=(--gpus all)" in deploy
    run_lines = [line for line in deploy.splitlines() if "docker run -d --name ispot-backend" in line]
    assert len(run_lines) == 1
    run_block = deploy[deploy.index(run_lines[0]):]
    run_block = run_block[:run_block.index("uvicorn")]
    assert '${GPU_FLAGS[@]+"${GPU_FLAGS[@]}"}' in run_block
    # 서버 준비 스크립트가 있고 드라이버 · nvidia 런타임을 둘 다 깐다.
    setup = (REPO / "deploy" / "gpu-setup.sh").read_text(encoding="utf-8")
    assert "ubuntu-drivers install --gpgpu" in setup
    assert "nvidia-container-toolkit" in setup
    assert "nvidia-ctk runtime configure --runtime=docker" in setup
