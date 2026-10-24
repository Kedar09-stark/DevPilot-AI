import os

from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import CrossEncoder, SentenceTransformer

load_dotenv()

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

RERANKER_MODEL_NAME = os.getenv(
    "RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
)

# Load both models once and reuse them across searches.
model = SentenceTransformer(MODEL_NAME)
reranker = CrossEncoder(RERANKER_MODEL_NAME)

DEPENDENCY_TERMS = (
    "dependency",
    "dependencies",
    "package-lock",
    "lockfile",
    "lock file",
    "npm",
    "vulnerability",
    "vulnerabilities",
    "security advisory",
)

# Files that orient a reader in ANY repository: docs and build/dependency
# manifests across common ecosystems, plus conventional entry points.
# Earlier entries rank higher. Matched against the file's base name.
OVERVIEW_FILES = (
    "readme",
    "package.json",
    "requirements",
    "pyproject.toml",
    "setup.py",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "cargo.toml",
    "composer.json",
    "gemfile",
    "docker-compose",
    "dockerfile",
    "manage.py",
    "settings.py",
    "main.py",
    "app.py",
    "app.tsx",
    "app.jsx",
    "app.js",
    "index.js",
    "main.tsx",
    "main.jsx",
)

NOISE_FILTER = """
    AND file_path NOT ILIKE '%%package-lock.json'
    AND file_path NOT ILIKE '%%yarn.lock'
    AND file_path NOT ILIKE '%%pnpm-lock.yaml'
    AND file_path NOT ILIKE '%%node_modules%%'
    AND file_path NOT ILIKE '%%/migrations/%%'
    AND file_path NOT ILIKE '%%/admin.py'
    AND file_path NOT ILIKE '%%/apps.py'
    AND file_path NOT ILIKE '%%/asgi.py'
    AND file_path NOT ILIKE '%%/wsgi.py'
"""


# Styling, generated and type-declaration files rarely explain what a
# project does. Used for broad (whole-project) questions only.
ASSET_FILTER = """
    AND file_path NOT ILIKE '%%.css'
    AND file_path NOT ILIKE '%%.scss'
    AND file_path NOT ILIKE '%%.svg'
    AND file_path NOT ILIKE '%%.map'
    AND file_path NOT ILIKE '%%.min.js'
    AND file_path NOT ILIKE '%%.d.ts'
    AND file_path NOT ILIKE '%%.snap'
"""


def search_code(
    question: str,
    limit: int = 5,
    repository: str = "Kedar09-stark/Attend-AI",
    include_lockfiles: bool | None = None,
    max_per_file: int | None = None,
    exclude_assets: bool = False,
) -> list[dict]:
    """Retrieve code chunks using vector similarity, then rerank them.

    include_lockfiles:
        None  -> auto-detect from the question (dependency questions
                 may include lockfiles).
        False -> never include lockfiles.
    max_per_file:
        Limit how many chunks one file can contribute, so results cover
        more of the repository.
    """

    if limit < 1:
        return []

    question_embedding = model.encode(question).tolist()

    if include_lockfiles is None:
        question_lower = question.lower()
        include_lockfiles = any(
            term in question_lower for term in DEPENDENCY_TERMS
        )

    file_filter = "" if include_lockfiles else NOISE_FILTER

    if exclude_assets:
        file_filter += ASSET_FILTER

    # Retrieve more candidates than the final result count.
    # The reranker will select the most relevant candidates.
    candidate_limit = min(max(limit * 10, 30), 100)

    with psycopg.connect(**DB_CONFIG) as conn:
        register_vector(conn)

        rows = conn.execute(
            f"""
            SELECT
                repository,
                file_path,
                start_line,
                end_line,
                content,
                embedding <=> %s::vector AS distance
            FROM code_chunks
            WHERE repository = %s
            {file_filter}
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (
                question_embedding,
                repository,
                question_embedding,
                candidate_limit,
            ),
        ).fetchall()

    results = [
        {
            "repository": row[0],
            "file_path": row[1],
            "start_line": row[2],
            "end_line": row[3],
            "content": row[4],
            "distance": round(float(row[5]), 4),
        }
        for row in rows
    ]

    if not results:
        return []

    # Score each question and code-chunk pair. The file path goes into the
    # document side so it can actually influence the ranking.
    pairs = [
        (
            question,
            f"File: {result['file_path']}\n{result['content']}",
        )
        for result in results
    ]

    scores = reranker.predict(pairs)

    for result, score in zip(results, scores):
        result["rerank_score"] = float(score)

    # Cross-encoder scores are ranking scores, not probabilities.
    results.sort(
        key=lambda result: result["rerank_score"],
        reverse=True,
    )

    if max_per_file:
        per_file: dict[str, int] = {}
        diverse = []

        for result in results:
            count = per_file.get(result["file_path"], 0)

            if count >= max_per_file:
                continue

            per_file[result["file_path"]] = count + 1
            diverse.append(result)

        results = diverse

    # Return only the requested number of best-ranked chunks.
    return results[:limit]


def get_overview_files(
    repository: str = "Kedar09-stark/Attend-AI",
    limit: int = 6,
) -> list[dict]:
    """Return the first chunk of orienting files (README, dependency
    manifests, conventional entry points) for any repository."""

    patterns = [f"%{name}%" for name in OVERVIEW_FILES]

    with psycopg.connect(**DB_CONFIG) as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT ON (file_path)
                repository,
                file_path,
                start_line,
                end_line,
                content
            FROM code_chunks
            WHERE repository = %s
            AND file_path ILIKE ANY(%s::text[])
            {NOISE_FILTER}
            ORDER BY file_path, start_line;
            """,
            (repository, patterns),
        ).fetchall()

    def rank(file_path: str) -> tuple[int, int] | None:
        lowered = file_path.lower()
        base = lowered.rsplit("/", 1)[-1]

        for index, name in enumerate(OVERVIEW_FILES):
            if base.startswith(name):
                # Prefer files closer to the repository root.
                return index, lowered.count("/")

        return None

    ranked = []

    for row in rows:
        file_rank = rank(row[1])

        if file_rank is None:
            continue

        ranked.append(
            (
                file_rank,
                {
                    "repository": row[0],
                    "file_path": row[1],
                    "start_line": row[2],
                    "end_line": row[3],
                    "content": row[4],
                    "distance": 0.0,
                    "rerank_score": 0.0,
                },
            )
        )

    ranked.sort(key=lambda item: item[0])

    return [item[1] for item in ranked[:limit]]


def get_repository_map(
    repository: str = "Kedar09-stark/Attend-AI",
    max_files: int = 80,
) -> list[str]:
    """Return indexed file paths (shallowest first) so the model can see
    the real project structure instead of guessing it."""

    with psycopg.connect(**DB_CONFIG) as conn:
        rows = conn.execute(
            f"""
            SELECT file_path
            FROM (
                SELECT DISTINCT file_path
                FROM code_chunks
                WHERE repository = %s
                {NOISE_FILTER}
            ) AS files
            ORDER BY
                array_length(string_to_array(file_path, '/'), 1),
                file_path
            LIMIT %s;
            """,
            (repository, max_files),
        ).fetchall()

    return [row[0] for row in rows]


def get_repository_files(
    repository: str = "Kedar09-stark/Attend-AI",
    max_chunks: int = 8000,
) -> dict[str, dict]:
    """Rebuild the full text of every indexed source file.

    Chunks overlap by a few lines, so overlapping lines are dropped when
    chunks are joined. Returns {file_path: {"text": str, "end_line": int}}.
    """

    with psycopg.connect(**DB_CONFIG) as conn:
        rows = conn.execute(
            f"""
            SELECT file_path, start_line, end_line, content
            FROM code_chunks
            WHERE repository = %s
            {NOISE_FILTER}
            {ASSET_FILTER}
            ORDER BY file_path, start_line
            LIMIT %s;
            """,
            (repository, max_chunks),
        ).fetchall()

    pieces: dict[str, dict] = {}

    for file_path, start_line, end_line, content in rows:
        entry = pieces.setdefault(
            file_path, {"lines": [], "end_line": 0}
        )

        lines = content.split("\n")
        overlap = entry["end_line"] - start_line + 1

        if overlap > 0:
            lines = lines[overlap:]

        entry["lines"].extend(lines)
        entry["end_line"] = max(entry["end_line"], end_line)

    return {
        path: {
            "text": "\n".join(entry["lines"]),
            "end_line": entry["end_line"],
        }
        for path, entry in pieces.items()
    }


def list_repositories() -> list[str]:
    """Return all repositories currently indexed in the database."""

    with psycopg.connect(**DB_CONFIG) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT repository
            FROM code_chunks
            ORDER BY repository;
            """
        ).fetchall()

    return [row[0] for row in rows]


def get_repository_stats() -> dict:
    """Return repository and indexed chunk counts."""

    with psycopg.connect(**DB_CONFIG) as conn:
        total_chunks = conn.execute(
            "SELECT COUNT(*) FROM code_chunks"
        ).fetchone()[0]

        repository_count = conn.execute(
            "SELECT COUNT(DISTINCT repository) FROM code_chunks"
        ).fetchone()[0]

    return {
        "repository_count": repository_count,
        "total_chunks": total_chunks,
    }


if __name__ == "__main__":
    print("Indexed repositories:", list_repositories())

    while True:
        question = input(
            "\nAsk about your code (or type 'exit'): "
        ).strip()

        if question.lower() == "exit":
            break

        if not question:
            continue

        try:
            matches = search_code(question)

            if not matches:
                print("No code chunks found.")
                continue

            for index, match in enumerate(matches, start=1):
                print(f"\n--- Match {index} ---")
                print(f"File: {match['file_path']}")
                print(
                    f"Lines: {match['start_line']}"
                    f"-{match['end_line']}"
                )
                print(f"Vector distance: {match['distance']}")
                print(f"Rerank score: {match['rerank_score']:.4f}")
                print(match["content"])

        except Exception as error:
            print(f"Search failed: {error}")