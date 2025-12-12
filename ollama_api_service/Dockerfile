FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Keep apt cache for faster rebuilds
RUN rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

# Install system dependencies with cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY ollama_api_service/requirements.txt .

# Install Python dependencies from pre-downloaded packages (bind mount)
RUN --mount=type=bind,source=packages,target=/packages \
    pip install --find-links=/packages -r requirements.txt

# Copy the API service code (context is CLI root directory)
COPY ollama_api_service/ /app/ollama_api_service/

# Note: src/ directory will be mounted from host at runtime
# This allows us to use existing CLI code without copying/modifying it

# Expose port
EXPOSE 8080

# Set Python path to include parent directory for imports
ENV PYTHONPATH=/app:/app/ollama_api_service

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the FastAPI server
CMD ["uvicorn", "ollama_api_service.app:app", "--host", "0.0.0.0", "--port", "8080"]
