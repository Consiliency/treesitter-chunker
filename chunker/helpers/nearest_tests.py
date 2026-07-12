from __future__ import annotations

import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

TEST_PATTERNS = [
    re.compile(r"^test_.*\.(py|js|ts|tsx|java|go|rb|rs)$", re.IGNORECASE),
    re.compile(r".*_test\.(py|js|ts|tsx|java|go|rb|rs)$", re.IGNORECASE),
]


def _is_test_file(path: Path) -> bool:
    name = path.name
    return any(pat.match(name) for pat in TEST_PATTERNS)


def _score_test_file(path: Path, symbols: Iterable[str]) -> float:
    score = 0.0
    name = path.name.lower()
    text = ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        pass
    # Name-based boost
    for sym in symbols:
        s = str(sym).lower()
        if s in name:
            score += 2.0
        if s and s in text.lower():
            score += 3.0
    # Directory proximity (common test folders)
    parts = [p.lower() for p in path.parts]
    if any(seg in parts for seg in ["tests", "__tests__", "spec"]):
        score += 1.0
    return score


def nearest_tests(symbols: list[str], repo_root: str) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    candidates: list[tuple[Path, float]] = []
    # followlinks=False (default) stops directory-symlink descent; we additionally
    # skip file symlinks and anything resolving outside root so a planted symlink
    # cannot read/expose files from elsewhere on disk (APISAFE hardening).
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.is_symlink():
                continue
            resolved = fpath.resolve()
            if root != resolved and root not in resolved.parents:
                continue
            if _is_test_file(fpath):
                s = _score_test_file(fpath, symbols)
                if s > 0:
                    candidates.append((fpath, s))
    # Sort by score desc, then shorter path (tie-breaker)
    candidates.sort(key=lambda t: (-t[1], len(str(t[0]))))
    results: list[dict[str, Any]] = []
    for fpath, s in candidates[:50]:
        results.append(
            {
                "path": str(fpath),
                "score": float(s),
                "symbols": symbols,
            },
        )
    return results
