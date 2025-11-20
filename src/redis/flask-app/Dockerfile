FROM python:3.10-slim

# Create app directory
WORKDIR /app

# Keep apt cache for faster rebuilds
RUN rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

# Install system dependencies with cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with cache mount
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --no-cache-dir \
    Flask==2.3.2 \
    redis==5.0.1 \
    requests==2.31.0 \
    sentry-sdk[flask]==1.29.2

# Copy shared source code
COPY src/sentry_config.py /app/src_shared/sentry_config.py
ENV PYTHONPATH="/app/src_shared:${PYTHONPATH}"

# Copy Flask application
COPY src/redis/flask-app/app.py /app/

# Expose Flask port
EXPOSE 5000

# Start Flask app
CMD ["python3", "app.py"]
