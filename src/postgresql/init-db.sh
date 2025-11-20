#!/bin/bash
set -e

# Initialize PostgreSQL data directory if it doesn't exist
if [ ! -f /var/lib/postgresql/14/main/PG_VERSION ]; then
  echo "Initializing PostgreSQL data directory..."
  su - postgres -c "/usr/lib/postgresql/14/bin/initdb -D /var/lib/postgresql/14/main"
fi

# Start PostgreSQL temporarily to run initialization
su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main -o '-c config_file=/etc/postgresql/14/main/postgresql.conf' start"

# Wait for PostgreSQL to be ready
until su - postgres -c "pg_isready" > /dev/null 2>&1; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 1
done

# Set password for postgres user
su - postgres -c "psql -c \"ALTER USER postgres WITH PASSWORD 'postgres';\""

# Create database if it doesn't exist
su - postgres -c "psql -c \"CREATE DATABASE vuhitra;\" 2>/dev/null || true"

# Run initialization SQL
if [ -f /docker-entrypoint-initdb.d/init.sql ]; then
  echo "Running initialization SQL..."
  su - postgres -c "psql -d vuhitra -f /docker-entrypoint-initdb.d/init.sql"
fi

# Stop PostgreSQL (supervisor will manage it)
su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main stop"

echo "Database initialization complete"
