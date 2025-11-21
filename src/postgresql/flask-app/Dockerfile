FROM python:3.10-slim

# Create app directory
WORKDIR /app

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --no-cache-dir \
    Flask==2.3.2 \
    Flask-SQLAlchemy==3.0.5 \
    psycopg2-binary==2.9.6 \
    sentry-sdk[flask]==1.29.2 \
    requests==2.31.0

# Copy shared source code
COPY src/sentry_config.py /app/src_shared/sentry_config.py
ENV PYTHONPATH="/app/src_shared:${PYTHONPATH}"

# Copy Flask application
COPY src/postgresql/app /app

# Expose Flask port
EXPOSE 5000

# Start Flask app
CMD ["python3", "app.py"]
