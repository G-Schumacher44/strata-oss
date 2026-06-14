"""In-house LookML parser for the Phase 1 IR surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FIELD_KINDS = {"dimension", "measure", "filter", "parameter"}
LIST_KEYS = FIELD_KINDS | {"view", "explore", "join", "include", "dashboard", "lookml_dashboard"}


@dataclass(frozen=True)
class ParsedDeclaration:
    kind: str
    name: str
    body: dict[str, Any]
    source_file: str
    refinement: bool = False


@dataclass(frozen=True)
class ParsedFile:
    path: str
    file_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    declarations: list[ParsedDeclaration] = field(default_factory=list)


class LookMLParseError(ValueError):
    """Raised when the Phase 1 parser cannot read a LookML fixture."""


class _LookMLScanner:
    def __init__(self, text: str, source: str) -> None:
        self.text = text
        self.source = source
        self.pos = 0

    def parse(self) -> list[tuple[str, Any]]:
        entries: list[tuple[str, Any]] = []
        while True:
            self._skip_space_and_comments()
            if self._eof():
                return entries
            if self._peek() == "}":
                self.pos += 1
                return entries
            entries.append(self._statement())

    def _statement(self) -> tuple[str, Any]:
        key = self._read_key()
        self._skip_horizontal_space()
        self._expect(":")
        value = self._value(key)
        return key, value

    def _value(self, key: str) -> Any:
        self._skip_horizontal_space()
        if self._eof():
            return ""
        if _is_semicolon_terminated(key):
            return self._semicolon_value()
        ch = self._peek()
        if ch == "{":
            return self._block()
        if ch == "[":
            return self._list()
        if ch in {'"', "'"}:
            value = self._quoted()
            self._skip_horizontal_space()
            if not self._eof() and self._peek() == "{":
                return {"name": value, "body": self._block()}
            return value
        value = self._raw_value()
        self._skip_horizontal_space()
        if not self._eof() and self._peek() == "{":
            return {"name": value, "body": self._block()}
        return value

    def _semicolon_value(self) -> str:
        start = self.pos
        while not self._eof():
            if self.text.startswith(";;", self.pos):
                value = self.text[start : self.pos].strip()
                self.pos += 2
                return value
            self.pos += 1
        return self.text[start : self.pos].strip()

    def _block(self) -> list[tuple[str, Any]]:
        self._expect("{")
        return self.parse()

    def _list(self) -> list[Any]:
        self._expect("[")
        items: list[Any] = []
        raw = ""
        while not self._eof():
            ch = self._peek()
            if ch in {'"', "'"}:
                if raw.strip():
                    items.extend(self._split_raw_list(raw))
                    raw = ""
                items.append(self._quoted())
                continue
            if ch == "]":
                self.pos += 1
                if raw.strip():
                    items.extend(self._split_raw_list(raw))
                return items
            raw += ch
            self.pos += 1
        raise LookMLParseError(f"{self.source}: unterminated list")

    def _quoted(self) -> str:
        quote = self._peek()
        self.pos += 1
        chars: list[str] = []
        while not self._eof():
            ch = self._peek()
            self.pos += 1
            if ch == "\\" and not self._eof():
                chars.append(self._peek())
                self.pos += 1
                continue
            if ch == quote:
                return "".join(chars)
            chars.append(ch)
        raise LookMLParseError(f"{self.source}: unterminated string")

    def _raw_value(self) -> str:
        start = self.pos
        while not self._eof():
            if self.text.startswith(";;", self.pos):
                value = self.text[start : self.pos].strip()
                self.pos += 2
                return value
            ch = self._peek()
            if ch in "\n}":
                return self.text[start : self.pos].strip()
            if ch == "{":
                return self.text[start : self.pos].strip()
            self.pos += 1
        return self.text[start : self.pos].strip()

    def _read_key(self) -> str:
        start = self.pos
        while not self._eof():
            ch = self._peek()
            if ch == ":":
                key = self.text[start : self.pos].strip()
                if not key:
                    raise LookMLParseError(f"{self.source}: empty key")
                return key
            if ch in "{}\n":
                break
            self.pos += 1
        raise LookMLParseError(f"{self.source}: expected ':' near {self.text[start : self.pos]!r}")

    def _skip_space_and_comments(self) -> None:
        while not self._eof():
            ch = self._peek()
            if ch.isspace():
                self.pos += 1
                continue
            if ch == "#":
                self._skip_line()
                continue
            if self.text.startswith("//", self.pos):
                self._skip_line()
                continue
            return

    def _skip_horizontal_space(self) -> None:
        while not self._eof() and self._peek() in " \t\r":
            self.pos += 1

    def _skip_line(self) -> None:
        while not self._eof() and self._peek() != "\n":
            self.pos += 1

    def _split_raw_list(self, raw: str) -> list[str]:
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _expect(self, text: str) -> None:
        if not self.text.startswith(text, self.pos):
            raise LookMLParseError(f"{self.source}: expected {text!r} at offset {self.pos}")
        self.pos += len(text)

    def _peek(self) -> str:
        return self.text[self.pos]

    def _eof(self) -> bool:
        return self.pos >= len(self.text)


def parse_file(path: str | Path, repo_root: str | Path | None = None) -> ParsedFile:
    file_path = Path(path)
    source = _source_name(file_path, repo_root)
    entries = _LookMLScanner(file_path.read_text(encoding="utf-8"), source).parse()
    properties: dict[str, Any] = {}
    declarations: list[ParsedDeclaration] = []

    for key, value in entries:
        if isinstance(value, dict) and "name" in value and "body" in value:
            name = str(value["name"])
            refinement = name.startswith("+")
            body = _body_to_dict(value["body"])
            declarations.append(
                ParsedDeclaration(
                    kind=_normalize_kind(key),
                    name=name[1:] if refinement else name,
                    body=body,
                    source_file=source,
                    refinement=refinement,
                )
            )
        else:
            _merge_property(properties, key, value)

    return ParsedFile(
        path=source,
        file_type=_file_type(file_path),
        properties=properties,
        declarations=declarations,
    )


def parse_repo(repo_path: str | Path) -> list[ParsedFile]:
    root = Path(repo_path)
    paths = sorted(root.rglob("*.lkml"))
    return [parse_file(path, root) for path in paths]


def _body_to_dict(entries: list[tuple[str, Any]]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for key, value in entries:
        if isinstance(value, dict) and "name" in value and "body" in value:
            item = {"name": value["name"], **_body_to_dict(value["body"])}
            _merge_property(body, _normalize_kind(key), item)
        elif isinstance(value, list) and value and all(isinstance(item, tuple) for item in value):
            _merge_property(body, _normalize_kind(key), _body_to_dict(value))
        else:
            _merge_property(body, _normalize_kind(key), value)
    return body


def _merge_property(target: dict[str, Any], key: str, value: Any) -> None:
    norm = _normalize_kind(key)
    if norm in LIST_KEYS:
        existing = target.setdefault(norm, [])
        if isinstance(value, list) and norm not in FIELD_KINDS | {"join"}:
            existing.extend(value)
        else:
            existing.append(value)
        return
    if norm in target:
        existing = target[norm]
        if not isinstance(existing, list):
            target[norm] = [existing]
        target[norm].append(value)
        return
    target[norm] = value


def _normalize_kind(kind: str) -> str:
    return kind.strip().replace("-", "_")


def _is_semicolon_terminated(key: str) -> bool:
    key = _normalize_kind(key)
    return key.startswith("sql") or key in {"html", "expression", "sql_table_name"}


def _file_type(path: Path) -> str:
    name = path.name
    if name.endswith(".view.lkml"):
        return "view"
    if name.endswith(".model.lkml"):
        return "model"
    if name.endswith(".dashboard.lookml"):
        return "lookml_dashboard"
    return "lookml"


def _source_name(path: Path, repo_root: str | Path | None) -> str:
    if repo_root is None:
        return path.as_posix()
    try:
        return path.relative_to(Path(repo_root)).as_posix()
    except ValueError:
        return path.as_posix()
