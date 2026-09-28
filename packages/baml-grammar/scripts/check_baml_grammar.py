"""Verify pinned BAML grammar provenance; regenerate only on explicit request."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    pin = json.loads((ROOT / "pin.json").read_text(encoding="utf-8"))
    locked = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    cli = locked["packages"]["node_modules/tree-sitter-cli"]
    assert cli["version"] == pin["generator"]["version"]
    assert cli["integrity"] == pin["generator"]["npm_integrity"]

    checks = {
        ROOT / "src/grammar.js": pin["overlay"]["grammar_sha256"],
        ROOT / "overlay.patch": pin["overlay"]["patch_sha256"],
        ROOT / "src/parser.c": pin["generated"]["parser_sha256"],
        ROOT / "src/node-types.json": pin["generated"]["node_types_sha256"],
        ROOT / "src/tree_sitter/parser.h": pin["upstream"]["parser_header_sha256"],
        ROOT / "tree-sitter.json": pin["upstream"]["tree_sitter_config_sha256"],
        ROOT / "LICENSE": pin["upstream"]["license_sha256"],
    }
    for path, expected in checks.items():
        actual = sha256(path)
        if actual != expected:
            raise SystemExit(f"hash mismatch: {path.relative_to(ROOT)}")

    patched = (ROOT / "src/grammar.js").read_bytes()
    before = b"field('value', $.raw_string)"
    after = b"field('value', choice($.raw_string, $.backtick_string))"
    if patched.count(after) != 1:
        raise SystemExit("overlay is absent or appears more than once")
    original = patched.replace(after, before, 1)
    if hashlib.sha256(original).hexdigest() != pin["upstream"]["grammar_sha256"]:
        raise SystemExit(
            "vendored grammar differs from the pinned source plus one-rule overlay"
        )
    return pin


def regenerate(pin: dict, cli: Path) -> None:
    cli = cli.resolve(strict=True)
    if sha256(cli) != pin["generator"]["executable_sha256"]:
        raise SystemExit("Tree-sitter CLI executable hash does not match pin.json")
    version = subprocess.run(
        [str(cli), "--version"], capture_output=True, text=True, check=True
    )
    if (
        version.stdout.strip()
        != f"tree-sitter {pin['generator']['version']} (da6fe9beb4f7f67beb75914ca8e0d48ae48d6406)"
    ):
        raise SystemExit("Tree-sitter CLI version does not match pin.json")
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        shutil.copy2(ROOT / "src/grammar.js", work / "grammar.js")
        shutil.copy2(ROOT / "tree-sitter.json", work / "tree-sitter.json")
        result = subprocess.run(
            [str(cli), "generate", "--abi", str(pin["generated"]["abi"]), "--json"],
            cwd=work,
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip() or result.stderr.strip():
            raise SystemExit("grammar generation emitted a conflict or warning")
        for name in ("parser.c", "node-types.json"):
            if (work / "src" / name).read_bytes() != (ROOT / "src" / name).read_bytes():
                raise SystemExit(f"regenerated {name} differs from vendored output")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--cli", type=Path)
    args = parser.parse_args()
    pin = verify()
    if args.regenerate:
        if args.cli is None:
            parser.error("--regenerate requires --cli")
        regenerate(pin, args.cli)
    print("BAML grammar pin and generated outputs verified")


if __name__ == "__main__":
    main()
