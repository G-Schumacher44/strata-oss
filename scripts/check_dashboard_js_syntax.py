"""Build a dashboard from fixture data and syntax-check every generated <script> block with
`node --check`, then the workbench's hand-written static scripts (`assets/js/*.js`, not the
vendored `*.min.js`) the same way. Catches page-fatal JS syntax errors the Python test suite can't see — the
guardrail test asserts strings inside the generated HTML, it never executes the JS (issue #29,
round-1 precedent: a regex bug in the fixed generator killed every script on the page and was
only caught by a live browser pass).

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

from strata_lookml.outputs import build_artifacts  # noqa: E402
from strata_lookml.outputs.dashboard import build_dashboard_html  # noqa: E402
from strata_lookml.pipeline import build_graph  # noqa: E402

FIXTURE_REPO = ROOT / "tests" / "lookml" / "enterprise_mono"
FIXTURE_USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
FIXTURE_SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"

# Hand-written scripts served from the workbench /static/ allow-list (not generated, but
# never executed by the Python suite either).
# Every hand-written script (not a vendored *.min.js) in the package's JS assets.
STATIC_SCRIPTS = tuple(
    p
    for p in sorted((ROOT / "src" / "strata_lookml" / "assets" / "js").glob("*.js"))
    if not p.name.endswith(".min.js")
)

SCRIPT_BLOCK_RE = re.compile(r"<script>(.*?)</script>", re.DOTALL)


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("node not found on PATH — skipping dashboard JS syntax check", file=sys.stderr)
        return 0

    graph = build_graph(FIXTURE_REPO, FIXTURE_USAGE, FIXTURE_SCHEMA)
    html = build_dashboard_html(build_artifacts(graph), graph)

    blocks = SCRIPT_BLOCK_RE.findall(html)
    if not blocks:
        print("no <script> blocks found in generated dashboard HTML", file=sys.stderr)
        return 1

    failures = 0
    for script in STATIC_SCRIPTS:
        result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
        if result.returncode != 0:
            failures += 1
            print(f"--- syntax error in {script.name} ---", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, block in enumerate(blocks):
            # Skip blocks that are just external script tags with no inline body, or that are
            # JSON payloads (application/json <script> tags never reach SCRIPT_BLOCK_RE's plain
            # <script> match, but guard anyway in case a future block is whitespace-only).
            if not block.strip():
                continue
            js_path = Path(tmpdir) / f"dashboard_block_{i}.js"
            js_path.write_text(block, encoding="utf-8")
            result = subprocess.run(
                [node, "--check", str(js_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                failures += 1
                print(f"--- syntax error in <script> block {i} ---", file=sys.stderr)
                print(result.stderr, file=sys.stderr)

    if failures:
        print(f"{failures} script(s) failed node --check", file=sys.stderr)
        return 1

    print(
        f"{len(blocks)} generated <script> block(s) and {len(STATIC_SCRIPTS)} static script(s) "
        "passed node --check"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
