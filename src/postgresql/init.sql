-- Initialize database and create tables

-- Create table for storing conversation ratings
CREATE TABLE IF NOT EXISTS conversation_ratings (
    id SERIAL PRIMARY KEY,
    user_rating INTEGER CHECK (user_rating >= 0 AND user_rating <= 10),
    prompt_text TEXT,
    response_text TEXT,
    tags JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on rating for filtering
CREATE INDEX IF NOT EXISTS idx_user_rating ON conversation_ratings(user_rating);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_conversation_ratings_updated_at 
    BEFORE UPDATE ON conversation_ratings 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
