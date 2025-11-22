FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the API service code
COPY . /app/ollama_api_service/

# Note: src/ directory will be mounted from host at runtime
# This allows us to use existing CLI code without copying/modifying it

# Expose port
EXPOSE 8080

# Set Python path to include parent directory for imports
ENV PYTHONPATH=/app:/app/ollama_api_service

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health', timeout=5.0)" || exit 1

# Run the FastAPI server
CMD ["uvicorn", "ollama_api_service.app:app", "--host", "0.0.0.0", "--port", "8080"]
