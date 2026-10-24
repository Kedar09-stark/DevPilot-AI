
import json
import os
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

INPUT_FILE = Path("data/code_chunks.jsonl")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "55432")),
    "dbname": os.getenv("DB_NAME", "devpilot"),
    "user": os.getenv("DB_USER", "devpilot_app"),
    "password": os.getenv("DB_PASSWORD"),
}

MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

EMBEDDING_DIMENSIONS = 384
BATCH_SIZE = 16


def load_chunks() -> list[dict]:
    """Read code chunks from the JSONL file."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"{INPUT_FILE} not found. Run the chunker first."
        )

    chunks = []

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                chunks.append(json.loads(line))

    if not chunks:
        raise ValueError(
            "No code chunks found. Check code_chunks.jsonl."
        )

    return chunks


def create_table(connection) -> None:
    """Enable pgvector and create the code storage table."""
    connection.execute(
        "CREATE EXTENSION IF NOT EXISTS vector;"
    )

    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS code_chunks (
            id BIGSERIAL PRIMARY KEY,
            repository TEXT NOT NULL,
            branch TEXT NOT NULL,
            file_path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector({EMBEDDING_DIMENSIONS})
                NOT NULL,
            UNIQUE (
                repository,
                branch,
                file_path,
                chunk_index
            )
        );
        """
    )


def main() -> None:
    chunks = load_chunks()

    print(f"Loaded chunks: {len(chunks)}")
    print(f"Loading embedding model: {MODEL_NAME}")

    model = SentenceTransformer(MODEL_NAME)

    print("Connecting to PostgreSQL...")

    with psycopg.connect(**DB_CONFIG) as connection:
        create_table(connection)
        register_vector(connection)

        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start:start + BATCH_SIZE]

            texts = [item["content"] for item in batch]

            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            for item, embedding in zip(batch, embeddings):
                connection.execute(
                    """
                    INSERT INTO code_chunks (
                        repository,
                        branch,
                        file_path,
                        chunk_index,
                        start_line,
                        end_line,
                        content,
                        embedding
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (
                        repository,
                        branch,
                        file_path,
                        chunk_index
                    )
                    DO UPDATE SET
                        start_line = EXCLUDED.start_line,
                        end_line = EXCLUDED.end_line,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        item["repository"],
                        item["branch"],
                        item["file_path"],
                        item["chunk_index"],
                        item["start_line"],
                        item["end_line"],
                        item["content"],
                        embedding,
                    ),
                )

            completed = min(start + BATCH_SIZE, len(chunks))
            print(f"Processed {completed}/{len(chunks)} chunks")

    print("\nDevPilot AI - Embedding Pipeline")
    print("--------------------------------")
    print(f"Chunks stored: {len(chunks)}")
    print("Database: devpilot")
    print("Table: code_chunks")
    print("Embedding dimensions: 384")


if __name__ == "__main__":
    main()
