#!/usr/bin/env python3
"""Reproduce load-sensitive deadline outcomes under CPU contention (Linux).

treesitter-chunker#207 (``nm`` symbol analysis) and treesitter-chunker#143
(the language-pack parse smoke) both use a five-second wall deadline. Under
host load the deadline can expire for a healthy grammar. This harness makes
that happen on purpose: it pins busy-loop processes to one CPU, runs the real
analyzer and smoke probes, and places only the processes they start (``nm``
and the parse child) on that CPU at low priority. Two controls, an unknown
language and a non-ELF file, show that real failures keep their own
classification under the same load. The probing interpreter
itself stays unloaded, so each deadline is measured accurately. Outcomes are
printed as JSON.

A control run without contention comes first. The harness is a heavy run:
check ``free -g`` and the host caps before starting it. Scratch lives under
the inherited ``TMPDIR`` and is removed on exit.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/baml-grammar/src"

PROBE = r"""
import json, os, sys
from pathlib import Path

cpu, niceness, library, root = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
sys.path.insert(0, root)

from chunker.languages.compatibility.grammar_analyzer import GrammarAnalyzer
from tests import language_smoke

# Only the processes the probes start contend for the loaded CPU.
if cpu >= 0:
    import subprocess

    def _place():
        os.sched_setaffinity(0, {cpu})
        os.nice(niceness)

    class _PlacedPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            kwargs["preexec_fn"] = _place
            super().__init__(*args, **kwargs)

    subprocess.Popen = _PlacedPopen
analyzer = GrammarAnalyzer(Path(library).parent)


def nm_outcome(path):
    symbols = analyzer.analyze_grammar_symbols(Path(path))
    return {
        "analysis": symbols.get("analysis", "<not reported>"),
        "symbol_count": sum(len(v) for v in symbols.values() if isinstance(v, list)),
    }


# Healthy targets show the deadline outcome; the controls show that a real
# failure keeps its own classification under the same load.
report = {
    "nm": nm_outcome(library),
    "nm_non_elf": nm_outcome(Path(library).parent / "not-elf.so"),
    "load_python": list(language_smoke.load_language("python")),
    "load_unknown": list(language_smoke.load_language("not_a_pack_language")),
}
print(json.dumps(report))
"""


def _compile(directory: Path) -> Path:
    library = directory / "baml.so"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-I",
            str(SOURCE),
            str(SOURCE / "parser.c"),
            "-o",
            str(library),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    (directory / "not-elf.so").write_bytes(b"not an ELF object\n")
    return library


def _probe(library: Path, cpu: int, niceness: int) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", PROBE, str(cpu), str(niceness), str(library), str(ROOT)],
        capture_output=True,
        check=False,
        text=True,
        timeout=900,
    )
    if result.returncode != 0:
        return {"probe_error": result.stderr.strip()[-2000:]}
    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("The load harness needs Linux CPU affinity.", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hogs", type=int, default=64, help="busy processes")
    parser.add_argument("--nice", type=int, default=19, help="probe niceness")
    parser.add_argument(
        "--cpu",
        type=int,
        default=max(os.sched_getaffinity(0)),
        help="CPU shared by the hogs and the probe",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="cifast-load-harness-") as scratch:
        library = _compile(Path(scratch))
        report = {
            "settings": {"cpu": args.cpu, "hogs": args.hogs, "nice": args.nice},
            "control": _probe(library, -1, 0),
        }
        hogs: list[subprocess.Popen] = []
        try:
            for _ in range(args.hogs):
                hog = subprocess.Popen(
                    [sys.executable, "-c", "while True: pass"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                hogs.append(hog)
                os.sched_setaffinity(hog.pid, {args.cpu})
            report["loaded"] = _probe(library, args.cpu, args.nice)
        finally:
            for hog in hogs:
                hog.kill()
            for hog in hogs:
                hog.wait(timeout=30)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
