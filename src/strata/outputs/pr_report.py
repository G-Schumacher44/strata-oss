"""Build a PR comment markdown string from Strata validation scope results."""

from __future__ import annotations

from typing import Any


def build_pr_comment(
    changed_files: list[str],
    file_to_views: dict[str, list[str]],
    scope: dict[str, Any],
    dead_code: list[dict[str, Any]],
) -> str:
    explores = scope.get("explores", [])
    dead_names = {item["name"] for item in dead_code}
    n = len(changed_files)

    lines: list[str] = ["## Strata Analysis", ""]
    lines.append(f"**Changed files:** {n} LookML {'file' if n == 1 else 'files'}")
    lines.append("")

    if not explores:
        unmatched = scope.get("unmatched", [])
        if unmatched:
            lines.append(
                "No explores affected — changed views are not referenced by any explore in this repo."
            )
        else:
            lines.append("No explores affected by these changes.")
        lines.append("")
    else:
        view_to_explores: dict[str, list[str]] = {}
        for exp in explores:
            label = f"{exp['model']}.{exp['explore']}"
            for view in exp.get("impacted_views", []):
                view_to_explores.setdefault(view, []).append(label)

        lines.append("| Changed file | Views | Explores to revalidate |")
        lines.append("|---|---|---|")
        for f in changed_files:
            views = file_to_views.get(f, [])
            if not views:
                lines.append(f"| `{f}` | — | no IR match |")
                continue
            exps: set[str] = set()
            for v in views:
                exps.update(view_to_explores.get(v, []))
            view_str = ", ".join(f"`{v}`" for v in sorted(views))
            exp_count = str(len(exps)) if exps else "none"
            lines.append(f"| `{f}` | {view_str} | {exp_count} |")

        lines.append("")
        lines.append(f"<details><summary>Explores to revalidate ({len(explores)})</summary>")
        lines.append("")
        for exp in sorted(explores, key=lambda e: (e["model"], e["explore"])):
            label = f"{exp['model']}.{exp['explore']}"
            dead_flag = " ⚠️ **dead code**" if label in dead_names else ""
            via = ", ".join(f"`{v}`" for v in exp.get("impacted_views", []))
            lines.append(f"- `{label}`{dead_flag} — via {via}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    dead_touched = [e for e in explores if f"{e['model']}.{e['explore']}" in dead_names]
    if dead_touched:
        names = ", ".join(f"`{e['explore']}`" for e in dead_touched)
        verb = "is" if len(dead_touched) == 1 else "are"
        lines.append(
            f"> **Note:** {names} {verb} already flagged as dead code (0 queries in L1 facts)."
            " Consider removing rather than modifying."
        )
        lines.append("")

    lines.append("_Run `make ci` locally to verify all explores pass before merging._")
    lines.append("")
    lines.append("<!-- strata-pr-comment -->")

    return "\n".join(lines)
