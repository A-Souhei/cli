#!/bin/bash
set -e

# Start PostgreSQL temporarily to run initialization
su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main -o '-c config_file=/etc/postgresql/14/main/postgresql.conf' start"

# Wait for PostgreSQL to be ready
until su - postgres -c "pg_isready" > /dev/null 2>&1; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 1
done

# Create database and user if they don't exist
su - postgres -c "psql -c \"CREATE DATABASE ${POSTGRES_DB:-vuhitra};\" 2>/dev/null || true"
su - postgres -c "psql -c \"CREATE USER ${POSTGRES_USER:-postgres} WITH PASSWORD '${POSTGRES_PASSWORD:-postgres}';\" 2>/dev/null || true"
su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB:-vuhitra} TO ${POSTGRES_USER:-postgres};\" 2>/dev/null || true"

# Run initialization SQL
if [ -f /docker-entrypoint-initdb.d/init.sql ]; then
  echo "Running initialization SQL..."
  su - postgres -c "psql -d ${POSTGRES_DB:-vuhitra} -f /docker-entrypoint-initdb.d/init.sql"
fi

# Stop PostgreSQL (supervisor will manage it)
su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main stop"

echo "Database initialization complete"
