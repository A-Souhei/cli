FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install PostgreSQL and Python dependencies
RUN apt-get update && apt-get install -y \
    postgresql-14 \
    postgresql-client-14 \
    postgresql-contrib-14 \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Flask and related packages
RUN pip3 install --no-cache-dir \
    flask \
    flask-sqlalchemy \
    psycopg2-binary \
    python-dotenv

# Configure PostgreSQL
RUN echo "host all all 0.0.0.0/0 md5" >> /etc/postgresql/14/main/pg_hba.conf && \
    echo "listen_addresses='*'" >> /etc/postgresql/14/main/postgresql.conf

# Create directory for Flask app
RUN mkdir -p /app
WORKDIR /app

# Expose PostgreSQL and Flask ports
EXPOSE 5432 5000

# Create volume for data persistence
VOLUME ["/var/lib/postgresql/14/main"]

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Start supervisor to manage both PostgreSQL and Flask
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
