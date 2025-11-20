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

-- Create table for storing MCP tools with embeddings
CREATE TABLE IF NOT EXISTS mcp_tools (
    id SERIAL PRIMARY KEY,
    mcp_name TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    description TEXT NOT NULL,
    embedding JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mcp_name, tool_name)
);

-- Create indexes for MCP tools
CREATE INDEX IF NOT EXISTS idx_mcp_name ON mcp_tools(mcp_name);
CREATE INDEX IF NOT EXISTS idx_tool_name ON mcp_tools(tool_name);

-- Create trigger to update updated_at timestamp for mcp_tools
CREATE TRIGGER update_mcp_tools_updated_at
    BEFORE UPDATE ON mcp_tools
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
