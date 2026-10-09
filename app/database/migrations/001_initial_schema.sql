-- ==============================================================================
-- AI FILE SEARCH — Initial Schema Migration (Section 6 & 7)
-- ==============================================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Files table
CREATE TABLE IF NOT EXISTS files (
    id BIGSERIAL PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    extension VARCHAR(16) NOT NULL,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    modified_at TIMESTAMPTZ NOT NULL,
    content_hash CHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Document Chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    file_id BIGINT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    page_no INTEGER,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(384),
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Monitored Folders table
CREATE TABLE IF NOT EXISTS monitored_folders (
    id BIGSERIAL PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Indexes (Section 7)
CREATE UNIQUE INDEX IF NOT EXISTS ux_files_path ON files(path);
CREATE INDEX IF NOT EXISTS ix_files_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS ix_files_status ON files(status);
CREATE INDEX IF NOT EXISTS ix_files_modified ON files(modified_at DESC);
CREATE INDEX IF NOT EXISTS ix_chunks_file_id ON document_chunks(file_id);

-- Vector HNSW index for cosine distance
CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
ON document_chunks USING hnsw (embedding vector_cosine_ops);
