# Simple PyPI server to serve local packages
FROM python:3.11-slim

# Install pypiserver
RUN pip install pypiserver

# Create directory for packages
RUN mkdir -p /packages

# Copy packages from host
COPY packages/ /packages/

# Expose port 8080
EXPOSE 8080

# Run pypiserver serving packages directory
CMD ["pypi-server", "--host", "0.0.0.0", "--port", "8080", "--disable-fallback", "/packages"]