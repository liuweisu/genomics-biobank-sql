"""Assemble the GitHub Pages site: demo page, freshly built database, query manifest."""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from biobank import generate  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "_site")
if out.exists():
    shutil.rmtree(out)
shutil.copytree(ROOT / "docs", out)
generate.build(out / "biobank.db")
manifest = [{"name": f.stem, "sql": f.read_text()} for f in sorted((ROOT / "queries").glob("*.sql"))]
(out / "queries.json").write_text(json.dumps(manifest, indent=1))
(out / ".nojekyll").touch()
print(f"site written to {out}")
