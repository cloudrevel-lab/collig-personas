#!/usr/bin/env python3
"""
Validate the collig-personas market repository.

Rules are deliberately conservative: a persona is data only.  The validator
never executes anything from a persona folder, refuses symlinks and unexpected
files, caps file sizes, verifies the generated index, and looks for
high-confidence credential patterns before a PR can merge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

SCHEMA = 1
PERSONAS_DIR = "personas"
REQUIRED_FILES = ("PERSONALITY.md", "meta.json")
OPTIONAL_FILES = ("sources.md",)
ALLOWED_FILES = set(REQUIRED_FILES) | set(OPTIONAL_FILES)
MAX_BYTES = {
    "PERSONALITY.md": 512 * 1024,
    "meta.json": 128 * 1024,
    "sources.md": 1024 * 1024,
}
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_ALIASES = 100
MAX_SOURCES = 100

SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "assignment-secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"
        ),
    ),
)

SENSITIVE_META_KEYS = {
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "credential",
    "credentials",
    "private_key",
}


class Report:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.personas: List[Dict[str, Any]] = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug_problem(slug: str) -> str:
    if not isinstance(slug, str) or not slug.strip():
        return "slug must be a non-empty string"
    if len(slug) > 80:
        return "slug must be at most 80 characters"
    if slug in {".", ".."}:
        return "slug cannot be '.' or '..'"
    if slug.startswith("."):
        return "slug cannot start with a dot"
    if "/" in slug or "\\" in slug:
        return "slug cannot contain a path separator"
    if any(ord(char) < 32 for char in slug):
        return "slug cannot contain control characters"
    if slug != slug.strip():
        return "slug cannot start or end with whitespace"
    return ""


def secret_hits(text: str) -> List[str]:
    found = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            found.append(name)
    return found


def _read_text(path: Path, report: Report) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report.error(str(path.relative_to(path.parents[1])) + ": not valid UTF-8")
    except OSError as exc:
        report.error(str(path) + ": " + str(exc))
    return ""


def _validate_meta(meta: Any, persona_dir: Path, report: Report) -> None:
    rel = str(persona_dir)
    if not isinstance(meta, dict):
        report.error(rel + "/meta.json: must be a JSON object")
        return

    lower_keys = {str(key).lower() for key in meta}
    for key in sorted(lower_keys & SENSITIVE_META_KEYS):
        report.error(rel + "/meta.json: sensitive key is not allowed: " + key)

    slug = meta.get("slug")
    problem = slug_problem(slug if isinstance(slug, str) else "")
    if problem:
        report.error(rel + "/meta.json: " + problem)
    elif slug != persona_dir.name:
        report.error(rel + "/meta.json: slug must equal the folder name " + repr(persona_dir.name))

    name = str(meta.get("name") or "").strip()
    if not name:
        report.error(rel + "/meta.json: name is required")
    elif len(name) > 200:
        report.error(rel + "/meta.json: name is too long")

    description = meta.get("description")
    if description is not None and (not isinstance(description, str) or len(description) > 2000):
        report.error(rel + "/meta.json: description must be a string of at most 2000 characters")

    updated_at = meta.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        report.error(rel + "/meta.json: updated_at is required (ISO-8601 string)")
    elif len(updated_at) > 64:
        report.error(rel + "/meta.json: updated_at is too long")

    aliases = meta.get("aliases")
    if aliases is not None:
        if not isinstance(aliases, list):
            report.error(rel + "/meta.json: aliases must be a list")
        else:
            if len(aliases) > MAX_ALIASES:
                report.error(rel + "/meta.json: too many aliases")
            for alias in aliases:
                if not isinstance(alias, str) or not alias.strip() or len(alias) > 200:
                    report.error(rel + "/meta.json: aliases must be non-empty strings of at most 200 characters")

    sources = meta.get("sources")
    if sources is not None:
        if not isinstance(sources, list):
            report.error(rel + "/meta.json: sources must be a list")
        else:
            if len(sources) > MAX_SOURCES:
                report.error(rel + "/meta.json: too many sources")
            for index, source in enumerate(sources):
                if not isinstance(source, dict):
                    report.error(rel + "/meta.json: sources[" + str(index) + "] must be an object")
                    continue
                url = source.get("url")
                if url is not None and (not isinstance(url, str) or len(url) > 2000):
                    report.error(rel + "/meta.json: sources[" + str(index) + "].url is invalid")
                title = source.get("title")
                if title is not None and (not isinstance(title, str) or len(title) > 1000):
                    report.error(rel + "/meta.json: sources[" + str(index) + "].title is invalid")


def validate_persona(persona_dir: Path, report: Report) -> Dict[str, Any] | None:
    rel = str(persona_dir)
    if persona_dir.is_symlink():
        report.error(rel + ": symlinks are not allowed")
        return None
    if not persona_dir.is_dir():
        report.error(rel + ": not a directory")
        return None

    problem = slug_problem(persona_dir.name)
    if problem:
        report.error(rel + ": folder name is invalid: " + problem)
        return None

    entries = sorted(persona_dir.iterdir(), key=lambda item: item.name)
    names = {entry.name for entry in entries}
    for entry in entries:
        if entry.is_symlink():
            report.error(rel + "/" + entry.name + ": symlinks are not allowed")
        elif entry.name not in ALLOWED_FILES:
            report.error(rel + "/" + entry.name + ": unexpected file (only PERSONALITY.md, meta.json, sources.md are allowed)")
        elif not entry.is_file():
            report.error(rel + "/" + entry.name + ": must be a regular file")

    for name in REQUIRED_FILES:
        if name not in names:
            report.error(rel + "/" + name + ": required file is missing")

    total = 0
    for entry in entries:
        if not entry.is_file() or entry.name not in ALLOWED_FILES:
            continue
        size = entry.stat().st_size
        total += size
        if size > MAX_BYTES.get(entry.name, MAX_TOTAL_BYTES):
            report.error(rel + "/" + entry.name + ": file is too large")
        text = _read_text(entry, report)
        hits = secret_hits(text)
        if hits:
            report.error(rel + "/" + entry.name + ": possible credential material (" + ", ".join(hits) + ")")

    if total > MAX_TOTAL_BYTES:
        report.error(rel + ": persona exceeds the total size limit")

    meta: Dict[str, Any] | None = None
    meta_path = persona_dir / "meta.json"
    if meta_path.is_file() and not meta_path.is_symlink():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            report.error(rel + "/meta.json: invalid JSON: " + str(exc))
        else:
            _validate_meta(meta, persona_dir, report)

    dossier = persona_dir / "PERSONALITY.md"
    if dossier.is_file() and not dossier.is_symlink():
        text = _read_text(dossier, report).lstrip("\ufeff").strip()
        if not text:
            report.error(rel + "/PERSONALITY.md: must not be empty")
        elif not text.startswith("# "):
            report.error(rel + "/PERSONALITY.md: must start with a level-1 Markdown heading")

    if not isinstance(meta, dict):
        return None

    files = {
        name: sha256_file(persona_dir / name)
        for name in ALLOWED_FILES
        if (persona_dir / name).is_file() and not (persona_dir / name).is_symlink()
    }
    aliases = meta.get("aliases") if isinstance(meta.get("aliases"), list) else []
    source_count = 0
    if isinstance(meta.get("sources"), list):
        source_count = len(meta["sources"])
    elif isinstance(meta.get("source_count"), int):
        source_count = max(0, int(meta["source_count"]))

    return {
        "slug": persona_dir.name,
        "name": str(meta.get("name") or persona_dir.name),
        "display_name": str(meta.get("display_name") or meta.get("name") or persona_dir.name),
        "canonical_name": str(meta.get("canonical_name") or meta.get("name") or persona_dir.name),
        "description": str(meta.get("description") or ""),
        "aliases": [str(alias) for alias in aliases],
        "updated_at": str(meta.get("updated_at") or ""),
        "source_count": source_count,
        "files": files,
    }


def collect(root: Path) -> Report:
    report = Report()
    base = root / PERSONAS_DIR
    if not base.is_dir():
        report.error("missing personas/ directory")
        return report
    persona_dirs = sorted(
        (item for item in base.iterdir() if item.is_dir() and not item.name.startswith(".")),
        key=lambda item: item.name,
    )
    if not persona_dirs:
        report.error("personas/ contains no personas")
        return report

    seen_slugs: set[str] = set()
    names: Dict[str, str] = {}
    for persona_dir in persona_dirs:
        if persona_dir.name in seen_slugs:
            report.error("duplicate slug: " + persona_dir.name)
            continue
        seen_slugs.add(persona_dir.name)
        entry = validate_persona(persona_dir, report)
        if entry is None:
            continue
        report.personas.append(entry)
        canonical = entry["canonical_name"].strip().casefold()
        if canonical:
            if canonical in names:
                report.warn(
                    "duplicate canonical name "
                    + repr(entry["canonical_name"])
                    + " in "
                    + names[canonical]
                    + " and "
                    + entry["slug"]
                )
            else:
                names[canonical] = entry["slug"]
    return report


def build_index(root: Path) -> Dict[str, Any]:
    report = collect(root)
    if report.errors:
        raise ValueError("\n".join(report.errors))
    personas = sorted(report.personas, key=lambda item: item["slug"])
    updated = max((item.get("updated_at") or "" for item in personas), default="")
    return {
        "schema": SCHEMA,
        "generated_by": "scripts/build_index.py",
        "updated_at": updated,
        "persona_count": len(personas),
        "personas": personas,
    }


def render_index(root: Path) -> str:
    return json.dumps(build_index(root), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def validate_repository(root: Path, check_index: bool = True) -> Report:
    report = collect(root)
    if report.errors:
        return report
    if check_index:
        index_path = root / "index.json"
        if not index_path.is_file():
            report.error("index.json is missing; run scripts/build_index.py --write")
        else:
            try:
                actual = index_path.read_text(encoding="utf-8")
            except OSError as exc:
                report.error("index.json: " + str(exc))
            else:
                expected = render_index(root)
                if actual != expected:
                    report.error("index.json is stale; run scripts/build_index.py --write")
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the collig-personas repository")
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--check-index", action="store_true", help="also require index.json to be up to date")
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.root).expanduser().resolve()
    report = validate_repository(root, check_index=args.check_index)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "personas": report.personas,
                    "errors": report.errors,
                    "warnings": report.warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for warning in report.warnings:
            print("WARN: " + warning)
        for error in report.errors:
            print("ERROR: " + error)
        if report.ok:
            print("OK: " + str(len(report.personas)) + " persona(s) validated")
        else:
            print("FAILED: " + str(len(report.errors)) + " error(s)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
