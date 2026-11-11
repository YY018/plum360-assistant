"""Export selected manual figures for the product guide.

Writes PNGs and a figures.json manifest to frontend/public/manual-figures/.
The output contains copyrighted manual artwork: it is git-ignored and meant for
private or portfolio use only; do not redistribute it without permission.

    python -m scripts.export_manual_figures
"""

from __future__ import annotations

import json

from plum360_assistant.manual_pages import FIGURES, PROJECT_ROOT, render_figure_png

OUTPUT_DIR = PROJECT_ROOT / "frontend" / "public" / "manual-figures"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for figure in FIGURES:
        filename = f"{figure.slug}.png"
        (OUTPUT_DIR / filename).write_bytes(render_figure_png(figure))
        manifest.append({
            "src": f"/manual-figures/{filename}",
            "caption": figure.caption,
            "ref": figure.label,
            "page": figure.page,
        })
        print(f"wrote {filename} (manual {figure.label}, PDF page {figure.page})")

    (OUTPUT_DIR / "figures.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
