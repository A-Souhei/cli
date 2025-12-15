FROM python:3.10-slim

# Create app directory
WORKDIR /app

# Install Python dependencies from pre-downloaded packages (bind mount)
RUN --mount=type=bind,source=packages,target=/packages \
    pip install --find-links=/packages \
    Flask==2.3.2 \
    Flask-SQLAlchemy==3.0.5 \
    psycopg2-binary==2.9.6 \
    sentry-sdk[flask]==1.29.2 \
    requests==2.31.0 \
    pyyaml==6.0

# Copy shared source code
COPY src/sentry_config.py /app/src_shared/sentry_config.py
COPY src/utils/shared_mcp_tools_loader.py /app/src_shared/shared_mcp_tools_loader.py
ENV PYTHONPATH="/app/src_shared:${PYTHONPATH}"

# Copy Flask application
COPY src/postgresql/app /app

# Copy system_mcps for dynamic tool loading
COPY system_mcps /app/system_mcps

# Expose Flask port
EXPOSE 5000

# Start Flask app
CMD ["python3", "app.py"]
