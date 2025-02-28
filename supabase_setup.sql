-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the entry_metadata table if it doesn't exist
CREATE TABLE IF NOT EXISTS entry_metadata (
    entry_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE,
    published TIMESTAMP WITH TIME ZONE,
    preamble TEXT,
    authors TEXT[],
    content_hash TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    title_embedding VECTOR(1536),
    content_embedding VECTOR(1536)
);

-- Create the entry_content table if it doesn't exist
CREATE TABLE IF NOT EXISTS entry_content (
    entry_id TEXT PRIMARY KEY REFERENCES entry_metadata(entry_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    markdown TEXT,
    toc JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create function for vector similarity search
CREATE OR REPLACE FUNCTION match_entries(
    query_embedding VECTOR(1536),
    similarity_threshold FLOAT DEFAULT 0.75,
    match_count INT DEFAULT 10,
    search_type TEXT DEFAULT 'content'
) RETURNS TABLE (
    entry_id TEXT,
    title TEXT,
    similarity FLOAT,
    preamble TEXT,
    authors TEXT[],
    last_updated TIMESTAMP WITH TIME ZONE,
    published TIMESTAMP WITH TIME ZONE
) LANGUAGE plpgsql AS $$
BEGIN
    IF search_type = 'content' THEN
        RETURN QUERY
        SELECT
            e.entry_id,
            e.title,
            1 - (e.content_embedding <=> query_embedding) AS similarity,
            e.preamble,
            e.authors,
            e.last_updated,
            e.published
        FROM
            entry_metadata e
        WHERE
            e.content_embedding IS NOT NULL
            AND 1 - (e.content_embedding <=> query_embedding) > similarity_threshold
        ORDER BY
            similarity DESC
        LIMIT match_count;
    ELSE
        RETURN QUERY
        SELECT
            e.entry_id,
            e.title,
            1 - (e.title_embedding <=> query_embedding) AS similarity,
            e.preamble,
            e.authors,
            e.last_updated,
            e.published
        FROM
            entry_metadata e
        WHERE
            e.title_embedding IS NOT NULL
            AND 1 - (e.title_embedding <=> query_embedding) > similarity_threshold
        ORDER BY
            similarity DESC
        LIMIT match_count;
    END IF;
END;
$$;

-- Create indexes for faster vector searches
CREATE INDEX IF NOT EXISTS entry_metadata_content_embedding_idx ON entry_metadata USING ivfflat (content_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS entry_metadata_title_embedding_idx ON entry_metadata USING ivfflat (title_embedding vector_cosine_ops) WITH (lists = 100);

-- Create a function to execute SQL from the REST API (if needed)
CREATE OR REPLACE FUNCTION exec(query text)
RETURNS VOID AS $$
BEGIN
    EXECUTE query;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER; 