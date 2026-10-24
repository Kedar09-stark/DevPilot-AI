
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import requests


API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".php", ".rb", ".swift", ".kt",
    ".html", ".css", ".scss", ".sql",
    ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".sh", ".ps1",
    ".xml", ".gradle",
}

IGNORED_DIRECTORIES = {
    ".git", ".venv", "venv", "env",
    "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".next", ".nuxt", "dist", "build",
    "coverage", ".idea", ".vscode",
}

IGNORED_FILENAMES = {
    ".env", ".env.local", ".env.development",
    ".env.production", ".env.test",
    "id_rsa", "id_ed25519",
}

IGNORED_EXTENSIONS = {
    ".lock", ".pyc", ".pyo", ".pem", ".key",
    ".p12", ".pfx", ".crt", ".cer", ".der",
    ".sqlite", ".sqlite3", ".db",
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".ico", ".pdf", ".zip", ".gz", ".exe", ".dll",
}

MAX_FILE_BYTES = 500_000
MAX_FILES = 200
MAX_TOTAL_BYTES = 10_000_000
TIMEOUT_SECONDS = 20


class GitHubConnectorError(Exception):
    """Raised when a public repository cannot be retrieved safely."""


def parse_github_url(url: str) -> tuple[str, str]:
    """Accept a GitHub repository URL, not arbitrary URLs."""
    parsed = urlparse(url.strip())

    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise GitHubConnectorError(
            "Enter an HTTPS URL from github.com."
        )

    parts = parsed.path.strip("/").split("/")

    if len(parts) != 2:
        raise GitHubConnectorError(
            "Use a repository URL like "
            "https://github.com/owner/repository"
        )

    owner, repo = parts
    repo = repo.removesuffix(".git")

    valid_name = re.compile(r"^[A-Za-z0-9_.-]+$")

    if not valid_name.fullmatch(owner) or not valid_name.fullmatch(repo):
        raise GitHubConnectorError("Invalid repository URL.")

    if owner in {".", ".."} or repo in {".", ".."}:
        raise GitHubConnectorError("Invalid repository URL.")

    return owner, repo


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Accept": "application/vnd.github+json",
        "User-Agent": "DevPilot-AI-Repository-Reader",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return session


def get_json(session: requests.Session, url: str) -> dict:
    """Fetch a GitHub API response with readable errors."""
    try:
        response = session.get(url, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise GitHubConnectorError(
            f"Could not connect to GitHub: {exc}"
        ) from exc

    if response.status_code == 404:
        raise GitHubConnectorError(
            "Repository or branch not found, or repository is not public."
        )

    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            raise GitHubConnectorError(
                "GitHub API rate limit reached. Wait and try again."
            )

        raise GitHubConnectorError(
            "GitHub denied the request. Check API limits or repository access."
        )

    if response.status_code == 429:
        raise GitHubConnectorError(
            "GitHub rate limit reached. Wait and try again."
        )

    if not response.ok:
        raise GitHubConnectorError(
            f"GitHub API returned HTTP {response.status_code}."
        )

    try:
        return response.json()
    except ValueError as exc:
        raise GitHubConnectorError(
            "GitHub returned an invalid JSON response."
        ) from exc


def should_skip_file(path: str, size: int) -> bool:
    """Filter dependencies, secrets, binary files, and oversized files."""
    parts = path.split("/")
    filename = parts[-1].lower()
    extension = Path(filename).suffix.lower()

    if any(part.lower() in IGNORED_DIRECTORIES for part in parts[:-1]):
        return True

    if filename in IGNORED_FILENAMES or filename.startswith(".env."):
        return True

    if extension in IGNORED_EXTENSIONS:
        return True

    if filename.endswith((".pem", ".key", ".secret")):
        return True

    if size < 0 or size > MAX_FILE_BYTES:
        return True

    return extension not in SUPPORTED_EXTENSIONS


def download_source(
    session: requests.Session,
    owner: str,
    repo: str,
    branch: str,
    path: str,
) -> str:
    """Download source text from the public raw-content endpoint."""
    encoded_branch = quote(branch, safe="/")
    encoded_path = quote(path, safe="/")
    url = (
        f"{RAW_BASE}/{owner}/{repo}/"
        f"{encoded_branch}/{encoded_path}"
    )

    try:
        response = session.get(url, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise GitHubConnectorError(
            f"Failed to download {path}: {exc}"
        ) from exc

    if response.status_code == 404:
        raise GitHubConnectorError(
            f"Source file disappeared during retrieval: {path}"
        )

    if not response.ok:
        raise GitHubConnectorError(
            f"Could not download {path}: HTTP {response.status_code}."
        )

    if len(response.content) > MAX_FILE_BYTES:
        raise GitHubConnectorError(
            f"Downloaded file exceeded the size limit: {path}"
        )

    try:
        return response.content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GitHubConnectorError(
        f"Skipped non-UTF-8 source file: {path}"
      ) from exc

   


def fetch_repository(url: str) -> tuple[list[dict], dict]:
    owner, repo = parse_github_url(url)
    session = make_session()

    metadata = get_json(
        session, f"{API_BASE}/repos/{owner}/{repo}"
    )

    if metadata.get("private", True):
        raise GitHubConnectorError(
            "This milestone supports public repositories only."
        )

    branch = metadata.get("default_branch")
    if not branch:
        raise GitHubConnectorError(
            "Could not determine the default branch."
        )

    encoded_branch = quote(branch, safe="")
    tree_data = get_json(
        session,
        f"{API_BASE}/repos/{owner}/{repo}/git/trees/"
        f"{encoded_branch}?recursive=1",
    )

    if tree_data.get("truncated"):
        raise GitHubConnectorError(
            "GitHub returned an incomplete file tree. "
            "This repository is too large for the current MVP."
        )

    records = []
    skipped = 0
    total_bytes = 0

    for item in tree_data.get("tree", []):
        if item.get("type") != "blob":
            continue

        path = item.get("path", "")
        size = item.get("size", -1)

        if should_skip_file(path, size):
            skipped += 1
            continue

        if len(records) >= MAX_FILES:
            break

        if total_bytes + size > MAX_TOTAL_BYTES:
            skipped += 1
            continue

        
        try:
            content = download_source(
                session, owner, repo, branch, path
            )
        except GitHubConnectorError as exc:
            if "non-UTF-8 source file" in str(exc):
                skipped += 1
                print(f"Skipping unreadable file: {path}")
                continue
            raise

        

        # Raw content may not match the earlier tree size if the
        # branch changed during scanning, so check the actual size too.
        actual_size = len(content.encode("utf-8"))

        if total_bytes + actual_size > MAX_TOTAL_BYTES:
            skipped += 1
            continue

        records.append({
            "repository": f"{owner}/{repo}",
            "branch": branch,
            "file_path": path,
            "extension": Path(path).suffix.lower(),
            "sha": item.get("sha"),
            "size_bytes": actual_size,
            "content": content,
        })

        total_bytes += actual_size

    summary = {
        "repository": f"{owner}/{repo}",
        "branch": branch,
        "files_downloaded": len(records),
        "files_skipped": skipped,
        "bytes_downloaded": total_bytes,
    }

    return records, summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch source files from a public GitHub repository."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="HTTPS URL of a public GitHub repository.",
    )
    parser.add_argument(
        "--output",
        default="data/repository_files.jsonl",
        help="Output JSONL file.",
    )
    args = parser.parse_args()

    try:
        records, summary = fetch_repository(args.repo)

        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as output:
            for record in records:
                output.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )

        print("\nDevPilot AI - GitHub Connector")
        print("-" * 36)
        for key, value in summary.items():
            print(f"{key}: {value}")
        print(f"output: {output_path}")

        if not records:
            print("Warning: No supported source files were downloaded.")

    except GitHubConnectorError as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
