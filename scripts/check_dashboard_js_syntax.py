"""Write the workbench's static export from fixture data and syntax-check every inline
<script> in it with `node --check`, then every hand-written workbench script (`assets/js/*.js`,
not the vendored `*.min.js`) the same way. Catches page-fatal JS syntax errors the Python suite
can't see: the tests assert strings in the generated HTML and run a few marked functions under
node, but never load a whole page (issue #29: a regex bug in a generator killed every script
on the page and was only caught by a live browser pass).

Usage: python scripts/check_dashboard_js_syntax.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strata_lookml.pipeline import build_graph  # noqa: E402
from strata_lookml.workbench.export import export  # noqa: E402
from strata_lookml.workbench.index import index_graph  # noqa: E402

FIXTURE_REPO = ROOT / "tests" / "lookml" / "enterprise_mono"
FIXTURE_USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
FIXTURE_SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"

# Every hand-written script (not a vendored *.min.js) in the package's JS assets: the live
# workbench serves them from /static/, the export inlines them.
STATIC_SCRIPTS = tuple(
    p
    for p in sorted((ROOT / "src" / "strata_lookml" / "assets" / "js").glob("*.js"))
    if not p.name.endswith(".min.js")
)

# Executable inline scripts only: the JSON payload is <script type="application/json">.
SCRIPT_BLOCK_RE = re.compile(r"<script>(.*?)</script>", re.DOTALL)


def _check(node: str, path: Path, label: str) -> bool:
    result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"--- syntax error in {label} ---", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
    return result.returncode == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("node not found on PATH — skipping dashboard JS syntax check", file=sys.stderr)
        return 0

    graph = build_graph(FIXTURE_REPO, FIXTURE_USAGE, FIXTURE_SCHEMA)
    workbench = index_graph(
        graph, repo=FIXTURE_REPO, usage_fixture=None, schema_fixture=None, inputs={}
    )
    html = export(workbench)

    blocks = SCRIPT_BLOCK_RE.findall(html)
    if not blocks:
        print("no <script> blocks found in the generated export", file=sys.stderr)
        return 1

    failures = sum(not _check(node, script, script.name) for script in STATIC_SCRIPTS)
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, block in enumerate(blocks):
            js_path = Path(tmpdir) / f"export_block_{i}.js"
            js_path.write_text(block, encoding="utf-8")
            failures += not _check(node, js_path, f"<script> block {i}")

    if failures:
        print(f"{failures} script(s) failed node --check", file=sys.stderr)
        return 1

    print(
        f"{len(blocks)} export <script> block(s) and {len(STATIC_SCRIPTS)} static script(s) "
        "passed node --check"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
