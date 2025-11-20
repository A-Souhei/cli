-- Migration: Add session_id column to conversation_ratings table
-- Date: 2025-11-20
-- Description: Adds support for session-based context tracking

-- Add session_id column to conversation_ratings
ALTER TABLE conversation_ratings
ADD COLUMN IF NOT EXISTS session_id TEXT;

-- Add index on session_id for efficient session-based queries
CREATE INDEX IF NOT EXISTS idx_conversation_ratings_session_id
ON conversation_ratings(session_id);

-- Add comment for documentation
COMMENT ON COLUMN conversation_ratings.session_id IS 'Session ID for grouping related prompts and responses with persistent context';
