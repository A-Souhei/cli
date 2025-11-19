FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install PostgreSQL and Python dependencies
RUN apt-get update && apt-get install -y \
    postgresql-14 \
    postgresql-client-14 \
    postgresql-contrib-14 \
    postgresql-server-dev-14 \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install pgvector extension
RUN git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git /tmp/pgvector && \
    cd /tmp/pgvector && \
    make && \
    make install && \
    rm -rf /tmp/pgvector

# Install Flask and related packages
RUN pip3 install --no-cache-dir \
    flask \
    flask-sqlalchemy \
    psycopg2-binary \
    python-dotenv \
    pgvector \
    sentry-sdk

# Configure PostgreSQL
RUN echo "host all all 0.0.0.0/0 md5" >> /etc/postgresql/14/main/pg_hba.conf && \
    echo "listen_addresses='*'" >> /etc/postgresql/14/main/postgresql.conf

# Create directory for Flask app
RUN mkdir -p /app /app/src_shared
WORKDIR /app

# Copy shared source code from parent directory
COPY src /app/src_shared
ENV PYTHONPATH="/app/src_shared:${PYTHONPATH}"

# Copy initialization SQL script
COPY init.sql /docker-entrypoint-initdb.d/init.sql
COPY init-db.sh /docker-entrypoint-initdb.d/init-db.sh
RUN chmod +x /docker-entrypoint-initdb.d/init-db.sh

# Expose PostgreSQL and Flask ports
EXPOSE 5432 5000

# Create volume for data persistence
VOLUME ["/var/lib/postgresql/14/main"]

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Start supervisor to manage both PostgreSQL and Flask
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
