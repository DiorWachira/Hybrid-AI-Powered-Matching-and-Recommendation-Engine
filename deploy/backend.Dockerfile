# FastAPI backend with the CPU-only sentence encoder baked in. Builds on amd64 and arm64
# (Oracle Ampere A1). Build context: repository root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app

# CPU wheels only: the default PyPI torch on amd64 pulls several GB of CUDA libraries.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0 \
    && pip install -r backend/requirements.txt

COPY backend/ backend/
COPY data_pipeline/ data_pipeline/

# Download the pinned encoder revision named by the promoted artifact, so the API never
# fetches model files at runtime.
RUN python -c "import json; from sentence_transformers import SentenceTransformer; a = json.load(open('data_pipeline/artifacts/hybrid_match_weights.json')); SentenceTransformer(a['embedding_model'], revision=a.get('encoder_revision'))"

RUN useradd --system --uid 10001 --home-dir /app jobbridge \
    && chown -R jobbridge /app/data_pipeline \
    && chmod +x backend/docker-entrypoint.sh
USER jobbridge

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD python -c "import json, urllib.request; s = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=8)); raise SystemExit(s['status'] != 'ok')"
ENTRYPOINT ["backend/docker-entrypoint.sh"]
