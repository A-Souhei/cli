FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Keep apt cache for faster rebuilds
RUN rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

# Install PostgreSQL and Python dependencies with cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
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

# Install Flask and related packages with cache mount
# IMPORTANT: Using cache mount means packages are downloaded once and reused across builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --no-cache-dir \
    flask \
    flask-sqlalchemy \
    psycopg2-binary \
    python-dotenv \
    pgvector \
    sentry-sdk \
    pyyaml

# Configure PostgreSQL
RUN echo "host all all 0.0.0.0/0 md5" >> /etc/postgresql/14/main/pg_hba.conf && \
    echo "listen_addresses='*'" >> /etc/postgresql/14/main/postgresql.conf

# Initialize PostgreSQL database with simple credentials
RUN rm -rf /var/lib/postgresql/14/main && \
    su - postgres -c "/usr/lib/postgresql/14/bin/initdb -D /var/lib/postgresql/14/main" && \
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main -o '-c config_file=/etc/postgresql/14/main/postgresql.conf' start" && \
    sleep 5 && \
    su - postgres -c "psql -c \"ALTER USER postgres WITH PASSWORD 'postgres';\"" && \
    su - postgres -c "psql -c \"CREATE DATABASE vuhitra;\"" && \
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main stop"

# Create directory for Flask app
RUN mkdir -p /app /app/src_shared
WORKDIR /app

# Copy shared source code from parent directory
COPY src/sentry_config.py /app/src_shared/sentry_config.py
ENV PYTHONPATH="/app/src_shared:${PYTHONPATH}"

# Copy initialization SQL script
COPY src/postgresql/init.sql /docker-entrypoint-initdb.d/init.sql

# Copy Flask application
COPY src/postgresql/app /app

# Run initialization SQL
RUN su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main -o '-c config_file=/etc/postgresql/14/main/postgresql.conf' start" && \
    sleep 5 && \
    su - postgres -c "psql -d vuhitra -f /docker-entrypoint-initdb.d/init.sql" && \
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main stop"

# Expose PostgreSQL and Flask ports
EXPOSE 5432 5000

# Create volume for data persistence
VOLUME ["/var/lib/postgresql/14/main"]

# Copy supervisor configuration
COPY src/postgresql/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Start supervisor to manage both PostgreSQL and Flask
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
