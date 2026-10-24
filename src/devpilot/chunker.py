
import json
from pathlib import Path

INPUT_FILE = Path("data/repository_files.jsonl")
OUTPUT_FILE = Path("data/code_chunks.jsonl")

CHUNK_SIZE = 80
CHUNK_OVERLAP = 15


def split_into_chunks(content: str) -> list[dict]:
    """Split source code into overlapping chunks while tracking line numbers."""
    lines = content.splitlines()
    chunks = []

    start = 0

    while start < len(lines):
        end = min(start + CHUNK_SIZE, len(lines))

        chunk_text = "\n".join(lines[start:end])

        if chunk_text.strip():
            chunks.append({
                "start_line": start + 1,
                "end_line": end,
                "content": chunk_text,
            })

        if end == len(lines):
            break

        start = end - CHUNK_OVERLAP

    return chunks


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"{INPUT_FILE} not found. Run the GitHub connector first."
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    total_files = 0

    with INPUT_FILE.open("r", encoding="utf-8") as source, \
         OUTPUT_FILE.open("w", encoding="utf-8") as output:

        for line in source:
            record = json.loads(line)
            file_chunks = split_into_chunks(record["content"])

            for index, chunk in enumerate(file_chunks):
                output_record = {
                    "repository": record["repository"],
                    "branch": record["branch"],
                    "file_path": record["file_path"],
                    "chunk_index": index,
                    **chunk,
                }

                output.write(json.dumps(output_record) + "\n")
                total_chunks += 1

            total_files += 1

    print("DevPilot AI - Code Chunker")
    print("--------------------------")
    print(f"files_processed: {total_files}")
    print(f"chunks_created: {total_chunks}")
    print(f"output: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
