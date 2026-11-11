"""Deploy the assistant to a Hugging Face Space (free, Docker runtime).

What it does, idempotently:

1. Uploads the private manual data (PDF, processed text, Chroma index, exported
   figures) to a PRIVATE dataset repo, so the public Space never contains it.
2. Creates (or updates) a Docker Space from the git-tracked project files.
3. Sets the Space's secrets (GROQ_API_KEY, HF_TOKEN, DEMO_ACCESS_CODE) and
   variables (provider, limits) from your local .env.

Usage (needs a Hugging Face token with write access, from
https://huggingface.co/settings/tokens):

    # put HF_TOKEN=hf_xxx in .env (git-ignored), or set it in the environment
    python -m scripts.deploy_hf_space

Options: --space NAME (default plum360-assistant), --skip-data to reuse an
already uploaded dataset, --private to make the Space itself private.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRIVATE_DATA = [
    "data/raw/manuals",
    "data/processed",
    "data/chroma_db",
    "frontend/public/manual-figures",
]

SPACE_README_HEADER = """---
title: Plum 360 Assistant
emoji: "\U0001FA7A"
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Manual-grounded assistant for the Plum 360 infusion pump
---

"""


def _tracked_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files"], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    ).stdout
    return [line for line in output.splitlines() if line.strip()]


def _env_file_values() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = PROJECT_ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy to a Hugging Face Space.")
    parser.add_argument("--owner", default=None, help="Your Hugging Face username (default: the token's account).")
    parser.add_argument("--space", default="plum360-assistant", help="Space name.")
    parser.add_argument("--data-repo", default=None, help="Private dataset name (default: <space>-data).")
    parser.add_argument("--skip-data", action="store_true", help="Do not re-upload the private data.")
    parser.add_argument("--private", action="store_true", help="Make the Space private too.")
    args = parser.parse_args()

    env = _env_file_values()
    token = os.getenv("HF_TOKEN", "").strip() or env.get("HF_TOKEN", "")
    if not token:
        parser.error("Set HF_TOKEN (environment or .env) to a Hugging Face token with write access.")

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    owner = args.owner or api.whoami().get("name")
    if not owner:
        parser.error("Could not determine the account name; pass --owner.")
    space_id = f"{owner}/{args.space}"
    data_id = f"{owner}/{args.data_repo or args.space + '-data'}"

    # 1. Private data -> private dataset repo.
    api.create_repo(data_id, repo_type="dataset", private=True, exist_ok=True)
    if args.skip_data:
        print(f"[1/3] Keeping existing data in {data_id}")
    else:
        for relative in PRIVATE_DATA:
            folder = PROJECT_ROOT / relative
            if not folder.is_dir():
                print(f"      skip {relative} (not found)")
                continue
            print(f"      uploading {relative} ...")
            api.upload_folder(
                folder_path=str(folder), path_in_repo=relative, repo_id=data_id,
                repo_type="dataset", commit_message=f"Update {relative}",
            )
        print(f"[1/3] Private data uploaded to {data_id}")

    # 2. Space from the git-tracked files (+ a README with Space metadata).
    api.create_repo(space_id, repo_type="space", space_sdk="docker",
                    private=args.private, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        for relative in _tracked_files():
            source = PROJECT_ROOT / relative
            if not source.is_file() or relative.endswith(".pdf"):
                continue
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        (staging / "README.md").write_text(SPACE_README_HEADER + readme, encoding="utf-8")
        api.upload_folder(
            folder_path=str(staging), repo_id=space_id, repo_type="space",
            commit_message="Deploy Plum 360 Assistant", delete_patterns=["**"],
        )
    print(f"[2/3] Space files uploaded to {space_id}")

    # 3. Secrets and variables.
    secrets = {
        "GROQ_API_KEY": env.get("GROQ_API_KEY", ""),
        "HF_TOKEN": token,
        "DEMO_ACCESS_CODE": env.get("DEMO_ACCESS_CODE", ""),
    }
    for key, value in secrets.items():
        if value:
            api.add_space_secret(space_id, key, value)
    variables = {
        "HF_DATA_REPO": data_id,
        "LLM_PROVIDER": "groq",
        "EMBEDDING_PROVIDER": "local",
        "APP_ENV": "production",
        "RATE_LIMIT_PER_HOUR": env.get("RATE_LIMIT_PER_HOUR", "20"),
        "DAILY_REQUEST_BUDGET": env.get("DAILY_REQUEST_BUDGET", "300"),
        "MAX_QUESTION_CHARS": env.get("MAX_QUESTION_CHARS", "600"),
    }
    for key, value in variables.items():
        api.add_space_variable(space_id, key, value)
    print("[3/3] Secrets and variables set")

    print(f"\nDone. The Space builds for a few minutes, then runs at:\n"
          f"  https://huggingface.co/spaces/{space_id}\n"
          f"  https://{owner}-{args.space}.hf.space"
          + (f"/?code={secrets['DEMO_ACCESS_CODE']}" if secrets["DEMO_ACCESS_CODE"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
