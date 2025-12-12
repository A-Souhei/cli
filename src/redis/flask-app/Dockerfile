FROM python:3.10-slim

# Create app directory
WORKDIR /app

# Install Python dependencies with cache mount
# IMPORTANT: Using cache mount means packages are downloaded once and reused across builds
RUN --mount=type=cache,target=/root/.cache/pip \
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
