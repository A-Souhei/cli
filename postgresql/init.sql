-- Initialize pgvector extension and create tables

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create table for storing conversation embeddings with ratings
CREATE TABLE IF NOT EXISTS conversation_ratings (
    id SERIAL PRIMARY KEY,
    prompt_embedding vector(768),  -- Adjust dimension based on your embedding model
    response_embedding vector(768),  -- Adjust dimension based on your embedding model
    user_rating INTEGER CHECK (user_rating >= 0 AND user_rating <= 10),
    prompt_text TEXT,  -- Optional: store original text for reference
    response_text TEXT,  -- Optional: store original text for reference
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for vector similarity search
CREATE INDEX IF NOT EXISTS idx_prompt_embedding ON conversation_ratings 
USING ivfflat (prompt_embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_response_embedding ON conversation_ratings 
USING ivfflat (response_embedding vector_cosine_ops) WITH (lists = 100);

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
