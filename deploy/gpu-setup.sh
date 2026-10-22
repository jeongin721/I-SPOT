#!/bin/bash
# GPU 인스턴스(g4dn 등) 한 번 준비: NVIDIA 드라이버 + nvidia-container-toolkit(Docker 가 컨테이너에 GPU 를 넘기게).
# Ubuntu(24.04 · 26.04) 기준. 2026-10-22 ispot-backend 를 t3.xlarge → g4dn.xlarge 로 바꾸면서 만들었다.
# 여러 번 실행해도 된다. 드라이버를 새로 깔았으면 마지막에 재부팅하라고 알린다(재부팅 전엔 nvidia-smi 가 안 보인다).
#
# 서버에서: cd /opt/ispot/I-SPOT && sudo git pull --ff-only && sudo bash deploy/gpu-setup.sh && sudo reboot
# (2026-10-22 ispot-backend 에서 겪은 것: ① 브라우저 터미널(EC2 Instance Connect)에서 apt-get 이 터미널 신호로 T(정지) 상태가 돼
#  멈췄다. 그래서 apt 류는 setsid 로 제어 터미널 없이 돌린다. 그래도 멈추면 다른 터미널에서
#  `sudo kill -CONT $(pgrep -x apt-get)`. 출력을 | tee 로 받지 않는다(파이프가 겹치면 더 잘 멈춘다).
#  ② --gpgpu 는 install 뒤에 붙는 옵션이다. Ubuntu 26.04 의 ubuntu-drivers 0.10.9 에서 앞에 두면 No such option.)
# 재부팅 뒤 확인: nvidia-smi -L                                    (GPU 한 줄이 나와야 한다)
#                 sudo docker run --rm --gpus all python:3.12-slim nvidia-smi -L   (컨테이너 안에서도 같은 줄)
# 그다음 배포: sudo env WITH_MODELING=1 WITH_GPU=1 bash deploy/web-deploy.sh   (deploy/README.md 'GPU 로 띄우기')
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "sudo 로 실행해 주세요"; exit 1; }
export DEBIAN_FRONTEND=noninteractive

echo "== 1/3 NVIDIA 드라이버"
if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then
  echo "이미 있음: $(nvidia-smi -L)"
  NEED_REBOOT=0
else
  setsid -w apt-get update -q
  setsid -w apt-get install -y -q ubuntu-drivers-common
  # 서버용(화면 없음) 드라이버를 Ubuntu 가 고른 판으로 깐다. 어느 판을 골랐는지 기록에 남긴다.
  ubuntu-drivers devices || true
  setsid -w ubuntu-drivers install --gpgpu
  NEED_REBOOT=1
fi

echo "== 2/3 nvidia-container-toolkit"
if docker info 2>/dev/null | grep -q nvidia; then
  echo "Docker 에 nvidia 런타임 이미 있음"
else
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  setsid -w apt-get update -q
  setsid -w apt-get install -y -q nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
fi

echo "== 3/3 확인"
docker info 2>/dev/null | grep -i "runtimes" || true
if [ "$NEED_REBOOT" = 1 ]; then
  echo "드라이버를 새로 깔았습니다. 재부팅한 뒤 nvidia-smi -L 로 확인해 주세요:  sudo reboot"
else
  docker run --rm --gpus all python:3.12-slim nvidia-smi -L && echo "GPU-SETUP DONE (컨테이너 안에서 GPU 보임)"
fi
