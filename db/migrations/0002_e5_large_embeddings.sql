-- Switch dense retrieval to intfloat/multilingual-e5-large (1024-d).
--
-- pgvector cannot cast a 384-d vector to 1024-d, and padding/truncating would produce meaningless vectors,
-- so the old embeddings are cleared and the column is retyped. No rows are deleted: sources, documents,
-- chunks (content, search_text, metadata) are kept as-is. `seed` (docker compose) or `npm run db:reindex`
-- re-embeds every chunk with the new model; until then dense search simply finds no vectors.

DROP INDEX IF EXISTS chunks_embedding_hnsw;

UPDATE chunks SET embedding = NULL, embedding_model = NULL;

ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1024);

CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
