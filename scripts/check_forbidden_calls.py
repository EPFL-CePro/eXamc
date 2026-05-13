#!/usr/bin/env python3
"""Fail when forbidden high-risk call patterns are present in Python code."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


SKIP_DIR_NAMES = {"migrations", "tests", "__pycache__"}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if should_skip(path):
            continue
        yield path


def scan_file(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    findings = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name) and node.func.id == "eval":
            findings.append((node.lineno, "eval(...) call"))

        if isinstance(node.func, ast.Attribute) and node.func.attr == "extractall":
            findings.append((node.lineno, ".extractall(...) call"))

        for kw in node.keywords:
            if kw.arg != "shell":
                continue
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                findings.append((node.lineno, "shell=True call"))

    return findings


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    app_root = repo_root / "examc_app"
    all_findings = []

    for py_file in iter_python_files(app_root):
        findings = scan_file(py_file)
        for line, message in findings:
            all_findings.append(f"{py_file.relative_to(repo_root)}:{line}: {message}")

    if all_findings:
        print("ERROR: forbidden high-risk calls detected:")
        for finding in sorted(all_findings):
            print(f"  - {finding}")
        return 1

    print("OK: no forbidden high-risk calls detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())

