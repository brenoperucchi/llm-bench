#!/usr/bin/env python3
"""Inventory evidence and verify documentation links, offline and with stdlib only."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("artifacts/manifest.json")
EVIDENCE_DIRS = ("results", "baseline-3080ti", "prompts")
EVIDENCE_FILES = (
    "goldset_chat.json", "bench.py", "bench_engine_ab.py", "run_chat.py",
    "ollama-restart.ps1", "requirements.txt", "SESSOES.md",
    "rtx5090-modelos-parametrizacao.md",
)
HISTORICAL_PATTERNS = ("ACHADO*.md", "MIGRACAO*.md", "PLANO*.md", "RELATORIO*.md")
CACHE_DIRS = {".venv", "venv", "__pycache__", ".cache", ".pytest_cache",
              ".mypy_cache", ".ruff_cache", ".git"}
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]*>|[^\s)]*(?:\([^\s)]*\)[^\s)]*)*)")
REFERENCE_LINK = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]*>|\S+)", re.MULTILINE)


def evidence_paths(root):
    paths = set()
    for directory in EVIDENCE_DIRS:
        for path in (root / directory).rglob("*"):
            relative = path.relative_to(root)
            if set(relative.parts) & CACHE_DIRS:
                continue
            if path.is_file() and relative.as_posix() != "baseline-3080ti/README.md":
                paths.add(path)
    for name in EVIDENCE_FILES:
        if (root / name).is_file():
            paths.add(root / name)
    for pattern in HISTORICAL_PATTERNS:
        paths.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def inventory(root):
    entries = []
    for path in evidence_paths(root):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Evidence must be a local regular file: {path.relative_to(root)}")
        data = path.read_bytes()
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "type": path.suffix.lower().lstrip(".") or "file",
        })
    return {"schema_version": 1, "entries": entries}


def validate_json(root, entries):
    errors = []
    for entry in entries:
        if entry["type"] == "json":
            try:
                json.loads((root / entry["path"]).read_text(encoding="utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                errors.append(f"Invalid JSON: {entry['path']}: {error}")
    return errors


def markdown_without_code(source):
    lines = []
    fence = None
    for line in source.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return re.sub(r"(`+).*?\1", "", "\n".join(lines))


def validate_links(root):
    documents = sorted(root.glob("README*.md")) + [root / "baseline-3080ti/README.md"]
    documents += sorted((root / "docs").rglob("*.md"))
    errors = []
    for document in documents:
        relative = document.relative_to(root)
        if relative.parts[:2] == ("docs", "history") or not document.is_file():
            continue
        source = markdown_without_code(document.read_text(encoding="utf-8"))
        targets = [match.group(1) for regex in (INLINE_LINK, REFERENCE_LINK)
                   for match in regex.finditer(source)]
        for target in targets:
            target = target.removeprefix("<").removesuffix(">")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
                continue
            destination = (document.parent / unquote(parsed.path)).resolve()
            if not destination.is_relative_to(root.resolve()) or not destination.exists():
                errors.append(f"Broken relative link: {relative}: {target}")
    return errors


def check(root, actual):
    errors = []
    expected = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if expected != actual:
        errors.append("Evidence manifest differs; inspect changes and run: python3 tools/inventory.py update")
    errors.extend(validate_json(root, actual["entries"]))
    errors.extend(validate_links(root))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("update", "check"))
    args = parser.parse_args()
    try:
        actual = inventory(ROOT)
        if args.command == "update":
            errors = validate_json(ROOT, actual["entries"])
            if not errors:
                destination = ROOT / MANIFEST
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            errors = check(ROOT, actual)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(f"{args.command}: OK ({len(actual['entries'])} evidence files)")
        return 0
    except (OSError, UnicodeError, ValueError) as error:
        print(f"{args.command}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
