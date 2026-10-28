# 빌드 컨텍스트는 저장소 루트다(AI_PROVIDER=modeling 이 쓰는 ai/ · agent/, STT_PROVIDER=module 이 쓰는 stt/ 도 담아야 해서).
# 넣는 것은 루트 .dockerignore 가 고른다.
#   docker build -t ispot-backend -f backend/Dockerfile .
# AI_PROVIDER=modeling 으로 띄울 이미지는 --build-arg WITH_MODELING=1, STT_PROVIDER=module 이면 --build-arg WITH_STT=1 을
# 더한다(deploy/README.md '모델까지 띄우기' · 'STT 까지 띄우기').
FROM python:3.12-slim

# NUMBA_CACHE_DIR: 구간별 음성 참고 표시(stt/voice_marks, VOICE_MARKS_PROVIDER=module)가 쓰는 numba 의 컴파일 캐시 자리.
# 컨테이너는 root 로 돌아 /tmp 에 쓸 수 있다. 없으면 numba 가 패키지 폴더에 쓰려다 실패할 수 있다.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/hf-cache \
    NUMBA_CACHE_DIR=/tmp/numba-cache

WORKDIR /app

COPY backend/requirements.txt backend/requirements-modeling.txt backend/requirements-stt.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# modeling 은 ai/modeling/abuse 의 torch · transformers 모델과 OpenAI 를 쓴다. 기본(WITH_GPU=0)은 CPU 판 torch 를
# 따로 받는다(PyPI 의 torch 는 CUDA 판이라 몇 GB 더 크다). GPU 인스턴스(2026-10-22 ispot-backend g4dn.xlarge)에서는
# WITH_GPU=1 로 PyPI 의 CUDA 판을 받는다 — 모델 코드(infer_abuse_qa_v3.py)는 torch.cuda.is_available() 이면 알아서 GPU 를 쓴다.
# 컨테이너에서 GPU 가 보이려면 서버에 NVIDIA 드라이버 · nvidia-container-toolkit 이 있고 docker run 에 --gpus all 을 줘야
# 한다(deploy/gpu-setup.sh · deploy/web-deploy.sh). 버전은 requirements-modeling.txt 와 같은 이유로 고정한다.
ARG WITH_MODELING=0
ARG WITH_GPU=0
RUN if [ "$WITH_MODELING" = "1" ]; then \
        if [ "$WITH_GPU" = "1" ]; then \
            pip install --no-cache-dir torch==2.14.1; \
        else \
            pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.14.1; \
        fi \
        && pip install --no-cache-dir -r requirements-modeling.txt; \
    fi

# STT 모듈(stt/transcribe_service)은 ElevenLabs(기본) · Deepgram SDK 를 쓴다. 키는 backend.env 에서 온다.
ARG WITH_STT=0
RUN if [ "$WITH_STT" = "1" ]; then \
        pip install --no-cache-dir -r requirements-stt.txt; \
    fi

# app.core.config 의 REPO_ROOT 는 /app 의 부모(/)라서, module_loader 가 ai/ · agent/ · stt/ 를 찾는 자리도 / 이다.
# 학대 분류 모델 파일(ai/modeling/abuse/weight/)은 저장소에 없어 이미지에 넣지 않고, 띄울 때 붙인다(deploy/web-deploy.sh).
# speaker_role_runtime.py 는 stt/ispot_stt.py 가 부르는 저장소 루트 파일이다.
COPY ai/ /ai/
COPY agent/ /agent/
COPY stt/ /stt/
# law/ 는 STT 검수 '관련 조문'(ai/modeling/abuse/legal_reference_adapter.py)이 쓴다. 법령 본문 캐시(law_cache/)는
# 저장소에 없어 이미지에 넣지 않고 띄울 때 /law_cache 에 붙인다(deploy/web-deploy.sh, law/config.py 의 기본 자리).
COPY law/ /law/
COPY speaker_role_runtime.py /speaker_role_runtime.py
COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--no-proxy-headers", "--host", "0.0.0.0", "--port", "8000"]
