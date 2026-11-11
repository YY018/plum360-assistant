"""Download the private manual data (index, text, PDF, figures) at start-up.

Used by the Docker image. Reads:

* ``HF_DATA_REPO``  - private Hugging Face dataset, e.g. "user/plum360-assistant-data"
* ``HF_TOKEN``      - a token that can read it

Does nothing when ``HF_DATA_REPO`` is unset (local development), and never
fails the start-up: the API reports a clear error instead if data is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    repo = os.getenv("HF_DATA_REPO", "").strip()
    if not repo:
        print("fetch_private_data: HF_DATA_REPO not set; using local data/.")
        return 0
    token = os.getenv("HF_TOKEN", "").strip() or None
    try:
        from huggingface_hub import snapshot_download

        path = snapshot_download(
            repo_id=repo, repo_type="dataset", token=token, local_dir=str(PROJECT_ROOT)
        )
        print(f"fetch_private_data: downloaded {repo} into {path}")
    except Exception as exc:  # start the server anyway; the API will explain
        print(f"fetch_private_data: could not download {repo}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
