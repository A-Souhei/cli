#!/bin/bash
set -e

# Script to update PostgreSQL schema without reinitializing the database
# This is useful when adding new tables or modifying existing schema

echo "PostgreSQL Schema Update Script"
echo "================================"
echo ""

# Check if we're running in Docker or local environment
if [ -f /.dockerenv ] || [ -n "$DOCKER_CONTAINER" ]; then
    # Running inside Docker container
    echo "Running inside Docker container..."

    # Apply schema updates directly
    echo "Applying schema updates..."
    psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-vuhitra}" -f /docker-entrypoint-initdb.d/init.sql

    echo "✓ Schema updated successfully"
else
    # Running on host machine - need to connect to Docker container
    echo "Running on host machine..."

    # Get container name from docker-compose
    CONTAINER=$(docker compose ps -q postgres 2>/dev/null)

    if [ -z "$CONTAINER" ]; then
        echo "Error: PostgreSQL container not found or not running"
        echo "Please start the containers with: make up"
        exit 1
    fi

    echo "Found PostgreSQL container: $CONTAINER"

    # Copy the SQL file to the container
    echo "Copying init.sql to container..."
    docker cp src/postgresql/init.sql "$CONTAINER":/tmp/init.sql

    # Execute the SQL in the container
    echo "Applying schema updates..."
    docker exec -i "$CONTAINER" psql -U postgres -d vuhitra -f /tmp/init.sql

    # Clean up
    docker exec -i "$CONTAINER" rm /tmp/init.sql

    echo ""
    echo "✓ Schema updated successfully"
fi

echo ""
echo "You can verify the tables with:"
echo "  make exec-postgres"
echo "  Then run: \\dt"
echo ""
