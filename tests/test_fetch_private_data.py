"""Tests for the start-up download of private manual data."""

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import fetch_private_data


def _archive(files: dict[str, bytes], extra_members=()) -> io.BytesIO:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        for info in extra_members:
            archive.addfile(info)
    buffer.seek(0)
    return buffer


class ExtractArchiveTests(unittest.TestCase):
    def test_extracts_only_allowed_paths_and_strips_the_top_folder(self) -> None:
        archive = _archive({
            "owner-repo-abc123/data/processed/manual.json": b"{}",
            "owner-repo-abc123/data/chroma_db/chroma.sqlite3": b"db",
            "owner-repo-abc123/data/raw/manuals/manual.pdf": b"%PDF",
            "owner-repo-abc123/frontend/public/manual-figures/figures.json": b"[]",
            "owner-repo-abc123/README.md": b"ignored",
            "owner-repo-abc123/data/models/model.onnx": b"must not be overwritten",
            "owner-repo-abc123/backend/main.py": b"must not be overwritten",
        })
        with tempfile.TemporaryDirectory() as tmp:
            written = fetch_private_data.extract_archive(archive, Path(tmp))
            found = sorted(str(p.relative_to(tmp)).replace("\\", "/") for p in Path(tmp).rglob("*") if p.is_file())
        self.assertEqual(written, 4)
        self.assertEqual(found, [
            "data/chroma_db/chroma.sqlite3",
            "data/processed/manual.json",
            "data/raw/manuals/manual.pdf",
            "frontend/public/manual-figures/figures.json",
        ])

    def test_path_traversal_and_links_are_skipped(self) -> None:
        link = tarfile.TarInfo("owner-repo-abc/data/processed/link.json")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archive = _archive(
            {
                "owner-repo-abc/data/processed/../../../escape.txt": b"x",
                "owner-repo-abc/data/processed/ok.json": b"{}",
            },
            extra_members=[link],
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            root.mkdir()
            written = fetch_private_data.extract_archive(archive, root)
            self.assertEqual(written, 1)
            self.assertTrue((root / "data" / "processed" / "ok.json").is_file())
            self.assertFalse((Path(tmp) / "escape.txt").exists())


class MainTests(unittest.TestCase):
    def test_does_nothing_without_a_data_repo(self) -> None:
        with mock.patch.dict("os.environ", {"DATA_REPO": "", "DATA_REPO_TOKEN": ""}), \
                mock.patch.object(fetch_private_data, "download_tarball") as download:
            self.assertEqual(fetch_private_data.main(), 0)
        download.assert_not_called()

    def test_a_failed_download_never_stops_start_up(self) -> None:
        with mock.patch.dict("os.environ", {"DATA_REPO": "me/data", "DATA_REPO_TOKEN": "t"}), \
                mock.patch.object(fetch_private_data, "download_tarball", side_effect=OSError("offline")):
            self.assertEqual(fetch_private_data.main(), 0)

    def test_requests_the_private_repo_tarball_with_the_token(self) -> None:
        captured = {}

        class _Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): return False

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            return _Response(b"data")

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            fetch_private_data.download_tarball("me/data", "tok123", "main")
        self.assertEqual(captured["url"], "https://api.github.com/repos/me/data/tarball/main")
        self.assertEqual(captured["auth"], "Bearer tok123")


if __name__ == "__main__":
    unittest.main()
