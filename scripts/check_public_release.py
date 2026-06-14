#!/usr/bin/env python3
"""Read-only guardrail for candidate public releases."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass

DEFAULT_DENY_PATHS = (
    ".cursor/*",
    ".mcp.json",
    ".strata",
    ".strata/*",
    "caches/*",
    "conductor/benchmark-matrix.md",
    "conductor/handoff-archive.md",
    "conductor/handoff-log.md",
    "conductor/review/*",
    "conductor/archive/*",
    "conductor/revert-spec.md",
    "conductor/slice-*.md",
    "output/*",
)

LOCAL_PATH_PATTERN = re.compile(
    "|".join(
        re.escape(marker)
        for marker in (
            "/" + "Volumes/",
            "/" + "Users/",
            "/" + "private/var/",
        )
    )
)

CONTENT_PATTERNS = (
    ("local machine path", LOCAL_PATH_PATTERN),
    ("private key marker", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    (
        "hard-coded credential value",
        re.compile(
            r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_./+=-]{24,}['\"]"
        ),
    ),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
)

# Guardrails should not flag their own detection patterns or tests.
SELF_EXCLUDE_PATHS = {
    "scripts/check_public_release.py",
    "tests/test_check_public_release.py",
}

TEXT_EXTENSIONS = {
    "",
    ".cfg",
    ".css",
    ".csv",
    ".ini",
    ".json",
    ".lkml",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class Finding:
    severity: str
    path: str
    reason: str


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def changed_paths(base: str, target: str) -> list[str]:
    output = run_git(["diff", "--name-status", "--find-renames", f"{base}..{target}"])
    paths: list[str] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        if status.startswith("D"):
            continue
        paths.append(parts[-1])
    return paths


def load_publicignore(path: str = ".publicignore") -> list[str]:
    try:
        with open(path, encoding="utf-8") as handle:
            patterns = []
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(f"{line}*" if line.endswith("/") else line)
            return patterns
    except FileNotFoundError:
        return list(DEFAULT_DENY_PATHS)


def path_denials(paths: list[str], deny_patterns: list[str] | None = None) -> list[Finding]:
    patterns = deny_patterns or load_publicignore()
    findings: list[Finding] = []
    for path in paths:
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                findings.append(Finding("error", path, f"matches private path rule `{pattern}`"))
                break
    return findings


def is_text_path(path: str) -> bool:
    if "." not in path.rsplit("/", 1)[-1]:
        return True
    suffix = "." + path.rsplit(".", 1)[-1].lower()
    return suffix in TEXT_EXTENSIONS


def read_file_at_ref(ref: str, path: str) -> str | None:
    try:
        return run_git(["show", f"{ref}:{path}"])
    except subprocess.CalledProcessError:
        return None


def content_findings(target: str, paths: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not is_text_path(path) or path in SELF_EXCLUDE_PATHS:
            continue
        content = read_file_at_ref(target, path)
        if content is None:
            continue
        for reason, pattern in CONTENT_PATTERNS:
            if pattern.search(content):
                findings.append(Finding("error", path, f"contains {reason}"))
    return findings


def audit(base: str, target: str) -> list[Finding]:
    try:
        run_git(["rev-parse", "--verify", base])
    except subprocess.CalledProcessError:
        print(f"Error: public baseline ref `{base}` not found.", file=sys.stderr)
        print("Run `git fetch public` or check your remote configuration.", file=sys.stderr)
        sys.exit(2)

    paths = changed_paths(base, target)
    return [*path_denials(paths), *content_findings(target, paths)]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit a candidate public release ref against public/main."
    )
    parser.add_argument("--base", default="public/main", help="public baseline ref")
    parser.add_argument("--target", default="HEAD", help="candidate release ref")
    parser.add_argument("--json", action="store_true", help="emit machine-readable findings")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        findings = audit(args.base, args.target)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.strip() or str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([finding.__dict__ for finding in findings], indent=2))
    elif findings:
        print("Public release audit failed:")
        for finding in findings:
            print(f"- {finding.severity}: {finding.path}: {finding.reason}")
    else:
        print(f"Public release audit passed for {args.base}..{args.target}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
