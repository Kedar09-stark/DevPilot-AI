
from pathlib import PurePosixPath

import requests

from devpilot.github_connector import (
    GitHubConnectorError,
    make_session,
    parse_github_url,
    download_source,
)

DEFAULT_REPOSITORY_URL = (
    "https://github.com/Kedar09-stark/Attend-AI"
)


def get_source_file(
    file_path: str,
    repository: str = "Kedar09-stark/Attend-AI",
) -> dict:
    """Fetch a source file from a validated public GitHub repository."""

    path = PurePosixPath(file_path)

    if (
        not file_path
        or path.is_absolute()
        or "\\" in file_path
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise ValueError("Invalid repository file path.")

    if (
        len(repository.split("/")) != 2
        or any(not part for part in repository.split("/"))
    ):
        raise ValueError("Invalid repository name.")

    repository_url = f"https://github.com/{repository}"
    owner, repo = parse_github_url(repository_url)
    """Fetch a source file from a validated public GitHub repository."""

    path = PurePosixPath(file_path)

    if (
        not file_path
        or path.is_absolute()
        or "\\" in file_path
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise ValueError("Invalid repository file path.")

    owner, repo = parse_github_url(repository_url)
    session = make_session()

    try:
        metadata_response = session.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            timeout=20,
        )

        if metadata_response.status_code == 404:
            raise ValueError("Repository not found or not public.")

        metadata_response.raise_for_status()
        metadata = metadata_response.json()

        if metadata.get("private", True):
            raise ValueError("Only public repositories are supported.")

        branch = metadata.get("default_branch")

        if not branch:
            raise ValueError("Could not determine the default branch.")

        content = download_source(
            session, owner, repo, branch, file_path
        )

    except requests.RequestException as error:
        raise RuntimeError(
            f"Could not fetch source file: {error}"
        ) from error
    except GitHubConnectorError as error:
        raise RuntimeError(str(error)) from error

    return {
        "repository": f"{owner}/{repo}",
        "branch": branch,
        "file_path": file_path,
        "lines": [
            {"line_number": number, "content": line}
            for number, line in enumerate(content.splitlines(), start=1)
        ],
    }
