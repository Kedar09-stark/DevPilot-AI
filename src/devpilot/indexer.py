
from devpilot.github_connector import (
    fetch_repository,
    GitHubConnectorError,
)
from devpilot.chunker import split_into_chunks
from devpilot.embed_store import (
    DB_CONFIG,
    MODEL_NAME,
    BATCH_SIZE,
    create_table,
)
from sentence_transformers import SentenceTransformer
from pgvector.psycopg import register_vector
import psycopg


def index_repository(url: str) -> dict:
    """Fetch a public GitHub repository and index its code in PostgreSQL."""

    # 1. Fetch source files directly from GitHub.
    records, summary = fetch_repository(url)

    if not records:
        raise GitHubConnectorError(
            "No supported source files were found in this repository."
        )

    # 2. Split source files into searchable chunks.
    chunks = []

    for record in records:
        for index, chunk in enumerate(
            split_into_chunks(record["content"])
        ):
            chunks.append({
                "repository": record["repository"],
                "branch": record["branch"],
                "file_path": record["file_path"],
                "chunk_index": index,
                **chunk,
            })

    if not chunks:
        raise GitHubConnectorError(
            "No code chunks could be created."
        )

    # 3. Generate embeddings before modifying the database.
    model = SentenceTransformer(MODEL_NAME)
    stored = 0

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]

        embeddings = model.encode(
            [item["content"] for item in batch],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        for item, embedding in zip(batch, embeddings):
            item["embedding"] = embedding

    # 4. Replace the selected repository branch in one transaction.
    repository = chunks[0]["repository"]
    branch = chunks[0]["branch"]

    with psycopg.connect(**DB_CONFIG) as connection:
        create_table(connection)
        register_vector(connection)

        with connection.transaction():
            connection.execute(
                """
                DELETE FROM code_chunks
                WHERE repository = %s AND branch = %s
                """,
                (repository, branch),
            )

            for start in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[start:start + BATCH_SIZE]

                for item in batch:
                    connection.execute(
                        """
                        INSERT INTO code_chunks (
                            repository, branch, file_path,
                            chunk_index, start_line, end_line,
                            content, embedding
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            item["repository"],
                            item["branch"],
                            item["file_path"],
                            item["chunk_index"],
                            item["start_line"],
                            item["end_line"],
                            item["content"],
                            item["embedding"],
                        ),
                    )

                stored += len(batch)

    return {
        **summary,
        "chunks_indexed": stored,
        "status": "success",
    }
