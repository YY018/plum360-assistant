"""Download the private manual data (index, text, PDF, figures) at start-up.

The public repository does not contain the copyrighted manual or anything
derived from it. A deployed server fetches that data from a separate PRIVATE
GitHub repository when these variables are set:

* ``DATA_REPO``        - "owner/name" of the private data repository
* ``DATA_REPO_TOKEN``  - a fine-grained token with read-only "Contents" access
                         to that one repository
* ``DATA_REPO_REF``    - branch or tag to download (default: main)

With ``DATA_REPO`` unset (local development) this does nothing. It never fails
the start-up: if the download fails the API reports a clear error instead.
"""

from __future__ import annotations

import io
import os
import tarfile
import urllib.request
from pathlib import PurePosixPath
from pathlib import Path
from typing import BinaryIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Only these locations are written; nothing else in the archive is extracted.
ALLOWED_PREFIXES = (
    "data/raw/manuals/",
    "data/processed/",
    "data/chroma_db/",
    "frontend/public/manual-figures/",
)


def extract_archive(
    fileobj: BinaryIO, destination: Path, allowed_prefixes: tuple[str, ...] = ALLOWED_PREFIXES
) -> int:
    """Extract allowed files from a GitHub tarball into ``destination``.

    GitHub wraps the repository in one top-level folder, which is stripped.
    Absolute paths, ``..`` segments, links, and anything outside the allowed
    prefixes are skipped. Returns the number of files written.
    """
    written = 0
    destination = destination.resolve()
    with tarfile.open(fileobj=fileobj, mode="r|gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts[1:]  # drop the top-level folder
            if not parts or any(part in ("..", "") or part.startswith("/") for part in parts):
                continue
            relative = "/".join(parts)
            if not relative.startswith(allowed_prefixes):
                continue
            target = (destination / relative).resolve()
            if destination not in target.parents:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                continue
            with source, open(target, "wb") as handle:
                while chunk := source.read(1024 * 1024):
                    handle.write(chunk)
            written += 1
    return written


def download_tarball(repo: str, token: str, ref: str = "main") -> io.BytesIO:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/tarball/{ref}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "plum360-assistant-startup",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return io.BytesIO(response.read())


def main() -> int:
    repo = os.getenv("DATA_REPO", "").strip()
    if not repo:
        print("fetch_private_data: DATA_REPO not set; using local data/.")
        return 0
    token = os.getenv("DATA_REPO_TOKEN", "").strip()
    if not token:
        print("fetch_private_data: DATA_REPO is set but DATA_REPO_TOKEN is missing.")
        return 0
    ref = os.getenv("DATA_REPO_REF", "").strip() or "main"
    try:
        archive = download_tarball(repo, token, ref)
        count = extract_archive(archive, PROJECT_ROOT)
        print(f"fetch_private_data: wrote {count} files from {repo}@{ref}.")
    except Exception as exc:  # start the server anyway; the API will explain
        print(f"fetch_private_data: could not fetch {repo}: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
