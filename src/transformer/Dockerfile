# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Keep apt cache for faster rebuilds (and use a stable cache id)
RUN rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

# Install system dependencies with cache mounts (stable ids)
# Use id=apt-cache so BuildKit reuses the same cache across builds.
RUN --mount=type=cache,target=/var/cache/apt,id=apt-cache,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,id=apt-lib-cache,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      gcc \
      g++ \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (best practice)
COPY src/transformer/requirements-base.txt .
COPY src/transformer/requirements.txt .

# Install base requirements from pre-downloaded packages (bind mount from host)
# Using --find-links without --no-index allows pip to resolve dependencies while preferring local packages
RUN --mount=type=bind,source=packages,target=/packages \
    pip install --find-links=/packages -r requirements-base.txt

# Install heavy dependencies (torch/transformers) from pre-downloaded packages
# Pin versions explicitly here if you need exact reproducibility
# Using PIP_NO_INDEX to force pip to only use local packages
RUN --mount=type=bind,source=packages,target=/packages \
    PIP_FIND_LINKS=/packages PIP_NO_INDEX=1 \
    pip install \
      torch==2.1.2 \
      transformers==4.36.2 \
      sentence-transformers==2.7.0

# Install remaining (lighter) dependencies from pre-downloaded packages
RUN --mount=type=bind,source=packages,target=/packages \
    pip install --find-links=/packages \
      flask==2.3.3 \
      flask-cors==4.0.0 \
      keybert==0.8.5 \
      sentry-sdk==1.40.6 \
      "protobuf>=3.20.0"

# Create cache directory for huggingface / transformers models (use stable id)
# Using cache mount (below) lets model files persist across builds without bloating the image.
RUN mkdir -p /root/.cache/huggingface

# OPTION A (recommended): Pre-download models into a BuildKit cache (not baked into image)
# This will store models in BuildKit 'hf-cache' and not enlarge the final image.
# The downloaded model files are available to subsequent RUN steps during the build, and
# to containers if you mount a volume at runtime.
RUN --mount=type=cache,target=/root/.cache/huggingface,id=hf-cache,sharing=locked \
    python3 -c "from sentence_transformers import SentenceTransformer; \
        print('Downloading sentence-transformers model to hf-cache...'); \
        model = SentenceTransformer('paraphrase-mpnet-base-v2'); \
        print('Model downloaded')"

RUN --mount=type=cache,target=/root/.cache/huggingface,id=hf-cache,sharing=locked \
    python3 -c "from transformers import AutoTokenizer, AutoModel; \
        print('Downloading CodeBERT to hf-cache...'); \
        tokenizer = AutoTokenizer.from_pretrained('microsoft/codebert-base'); \
        model = AutoModel.from_pretrained('microsoft/codebert-base'); \
        print('CodeBERT downloaded')"

# OPTION B (if you explicitly want the models baked into the final image)
# Uncomment the two RUN lines above and remove the '--mount=type=cache,...' or
# run a dedicated step that downloads models without cache mounts. Note: image size will grow by ~1GB+.

# Copy application code after all heavy installs so code changes don't invalidate earlier layers
COPY src/transformer/ .

# Copy shared source code from parent directory (only sentry_config.py)
COPY src/sentry_config.py /app/src_shared/sentry_config.py
ENV PYTHONPATH="/app/src_shared:${PYTHONPATH}"

EXPOSE 5050
CMD ["python", "app.py"]
