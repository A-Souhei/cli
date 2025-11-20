#!/bin/bash
# Script to apply the session_id migration to the PostgreSQL database

set -e

echo "🔄 Applying session_id migration..."

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install docker-compose first."
    exit 1
fi

# Get the PostgreSQL container name
POSTGRES_CONTAINER=$(docker-compose ps -q postgres 2>/dev/null || docker ps -q -f name=postgres)

if [ -z "$POSTGRES_CONTAINER" ]; then
    echo "❌ PostgreSQL container not found. Is the service running?"
    echo "   Try: docker-compose up -d"
    exit 1
fi

echo "✓ Found PostgreSQL container: $POSTGRES_CONTAINER"

# Apply the migration
echo "📝 Applying migration..."
docker exec -i "$POSTGRES_CONTAINER" psql -U postgres -d vuhitra < migrations/add_session_id.sql

if [ $? -eq 0 ]; then
    echo "✅ Migration applied successfully!"
    echo ""
    echo "You can now use the session feature with:"
    echo "  • session start"
    echo "  • session end"
    echo "  • session info"
else
    echo "❌ Migration failed. Please check the error above."
    exit 1
fi
