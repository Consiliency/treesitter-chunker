"""Go source constraints and module declarations keep their precedence."""

from pathlib import Path

import pytest

from chunker import get_parser
from chunker.languages.version_detection import go_detector
from chunker.languages.version_detection.go_detector import (
    GoVersionDetector,
    GoVersionInfo,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/boundary_ir/repos/go/service.go"
)


@pytest.mark.parametrize(
    ("versions", "expected"),
    [
        (("1.9", "1.10"), "1.10"),
        (("1.10", "1.9"), "1.10"),
        (("1.99", "2.0"), "2.0"),
        (("2.0", "1.99"), "2.0"),
    ],
)
def test_go_build_constraint_versions_are_numeric(
    tmp_path: Path, versions: tuple[str, str], expected: str
) -> None:
    # Legacy lines are AND-ed; they must be followed by a blank line, as
    # go/build requires. (Two //go:build lines are invalid: see
    # test_go_build_header_placement_matches_go_build.)
    constraints = "".join(f"// +build go{version}\n" for version in versions)
    source = constraints + "\n" + FIXTURE.read_text(encoding="utf-8")
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error

    detector = GoVersionDetector()
    hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    assert hints["build_constraints"] == expected
    assert detector.get_primary_version(hints) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "go1.10 && go1.9",
        "go1.9 && go1.10",
        "go1.21 && go1.9 && go1.10",
        "go1.9 && go1.21 && go1.10",
        "go1.9 && go1.10 && go1.21",
        "go1.10 && go1.9 && go1.10",
        "go1.10\t&&\tgo1.9",
    ],
)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_positive_go_conjunction_retains_all_release_tags(
    tmp_path: Path, expression: str, newline: str
) -> None:
    source = f"//go:build {expression}{newline}{newline}" + FIXTURE.read_text(
        encoding="utf-8"
    )
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8", newline="")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error

    detector = GoVersionDetector()
    hints = detector.detect_version(source, source_path)
    expected = "1.21" if "go1.21" in expression else "1.10"
    assert hints["build_constraints"] == expected
    assert detector.get_primary_version(hints) == expected


def test_modern_go_conjunction_precedes_legacy_hint(tmp_path: Path) -> None:
    source = "//go:build go1.10 && go1.9\n// +build go1.22\n\n" + FIXTURE.read_text(
        encoding="utf-8"
    )
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error
    detector = GoVersionDetector()
    hints = detector.detect_version(source, source_path)
    assert hints["build_constraints"] == "1.10"
    assert detector.get_primary_version(hints) == "1.10"


def test_go_mod_version_precedes_source_build_constraint(tmp_path: Path) -> None:
    source = "//go:build go1.21\n" + FIXTURE.read_text(encoding="utf-8")
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error

    mod_path = tmp_path / "go.mod"
    mod_path.write_text("module example.com/fixture\ngo 1.22\n", encoding="utf-8")

    detector = GoVersionDetector()
    source_hints = detector.detect_version(
        source_path.read_text(encoding="utf-8"), source_path
    )
    mod_hints = detector.detect_version(mod_path.read_text(encoding="utf-8"), mod_path)
    assert source_hints["file_type"] == "source"
    assert source_hints["build_constraints"] == "1.21"
    assert mod_hints["file_type"] == "module"
    assert mod_hints["go_mod_version"] == "1.22"

    combined = {**source_hints, "go_mod_version": mod_hints["go_mod_version"]}
    primary = detector.get_primary_version(combined)
    assert primary == "1.22"
    serialized = GoVersionInfo(
        go_version=primary,
        build_constraints=[source_hints["build_constraints"]],
        source="go.mod",
    ).to_dict()
    assert serialized["go_version"] == "1.22"
    assert serialized["build_constraints"] == ["1.21"]
    assert serialized["source"] == "go.mod"


@pytest.mark.parametrize(
    ("conjunction", "expected"),
    [
        ("go1.10,go1.9", "1.10"),
        ("go1.9,go1.10", "1.10"),
        ("go1.21,go1.9,go1.10", "1.21"),
        ("go1.9,go1.21,go1.10", "1.21"),
        ("go1.10,go1.9,go1.21", "1.21"),
        ("go1.10,go1.9,linux", "1.10"),
        ("linux,go1.10,cgo,go1.9", "1.10"),
        ("go2.0,go1.99", "2.0"),
        # Go tags allow Unicode letters and decimal digits, "_" and ".".
        ("go1.10,café,go1.9", "1.10"),
        ("go1.9,café,go1.10", "1.10"),
        ("tag\u0663,go1.10,ünï_1.x,go1.9", "1.10"),
    ],
)
@pytest.mark.parametrize("comment", ["// +build", "//+build"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_legacy_comma_conjunction_retains_every_release_tag(
    tmp_path: Path, conjunction: str, expected: str, comment: str, newline: str
) -> None:
    """treesitter-chunker#437: a legacy comma conjunction needs its highest tag.

    Named mutation ``M437-last-tag`` (keep only the greedy last tag) fails
    every case whose highest release tag is not the last one.
    """
    source = f"{comment} {conjunction}{newline}{newline}" + FIXTURE.read_text(
        encoding="utf-8"
    )
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8", newline="")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error

    detector = GoVersionDetector()
    hints = detector.detect_version(source, source_path)
    assert hints["build_constraints"] == expected
    assert detector.get_primary_version(hints) == expected


def test_modern_constraint_precedes_legacy_comma_conjunction(tmp_path: Path) -> None:
    source = "//go:build go1.11\n// +build go1.22,go1.9\n\n" + FIXTURE.read_text(
        encoding="utf-8"
    )
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error
    detector = GoVersionDetector()
    hints = detector.detect_version(source, source_path)
    assert hints["build_constraints"] == "1.11"
    assert detector.get_primary_version(hints) == "1.11"
    combined = {**hints, "go_mod_version": "1.23"}
    assert detector.get_primary_version(combined) == "1.23"


def _hints(tmp_path: Path, header: str, newline: str = "\n") -> dict:
    source = (
        header.replace("\n", newline) + newline + FIXTURE.read_text(encoding="utf-8")
    )
    source_path = tmp_path / "service.go"
    source_path.write_text(source, encoding="utf-8", newline="")
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error
    return GoVersionDetector().detect_version(source, source_path)


@pytest.mark.parametrize(
    ("header", "minimum", "status"),
    [
        # treesitter-chunker#438 issue forms.
        ("//go:build go1.18 && !go1.21\n", "1.18", "minimum"),
        ("//go:build go1.18 || go1.21\n", "1.18", "minimum"),
        ("//go:build go1.21 || go1.18\n", "1.18", "minimum"),
        ("//go:build go1.21 && go1.9\n", "1.21", "minimum"),
        ("//go:build (go1.18 || go1.20) && linux\n", "1.18", "minimum"),
        ("//go:build go1.20 && (go1.18 || windows)\n", "1.20", "minimum"),
        ("//go:build !(go1.18 && !go1.20)\n", None, "unconstrained"),
        ("//go:build !go1.18 || go1.20\n", None, "unconstrained"),
        ("//go:build (linux || darwin) && go1.19 && !go1.22\n", "1.19", "minimum"),
        ("//go:build !go1.21\n", None, "unconstrained"),
        ("//go:build go1.18 || linux\n", None, "unconstrained"),
        ("//go:build linux && amd64\n", None, "unconstrained"),
        ("//go:build go1.21 && !go1.18\n", None, "unknown"),
        ("//go:build go1.18 && !go1.18\n", None, "unknown"),
        ("//go:build linux && !linux\n", None, "unknown"),
        ("//go:build go1.18 &&\n", None, "unknown"),
        ("//go:build (go1.18 || go1.20\n", None, "unknown"),
        ("//go:build go1.18 & go1.20\n", None, "unknown"),
        ("//go:build go1.18 go1.20\n", None, "unknown"),
        # Legacy: fields OR, commas AND, ! negates; lines AND.
        ("// +build go1.18,!go1.21\n", "1.18", "minimum"),
        ("// +build go1.18 go1.21\n", "1.18", "minimum"),
        ("// +build go1.21 go1.18\n", "1.18", "minimum"),
        ("// +build !go1.21\n", None, "unconstrained"),
        ("// +build linux go1.20\n", None, "unconstrained"),
        ("// +build go1.18 go1.20\n// +build go1.19\n", "1.19", "minimum"),
        ("// +build go1.21,!go1.18\n", None, "unknown"),
        ("// +build !!go1.18\n", None, "unknown"),
        ("// +build go1.18,,linux\n", None, "unknown"),
        # Go tags allow Unicode letters and decimal digits, "_" and ".".
        ("//go:build go1.18 && café\n", "1.18", "minimum"),
        ("// +build go1.18,café\n", "1.18", "minimum"),
        ("//go:build go1.18 && tag\u0663\n", "1.18", "minimum"),
        ("//go:build go1.20 || ünïcödé_1.x\n", None, "unconstrained"),
        ("//go:build go\u0661.\u0661\u0668\n", None, "unconstrained"),
        ("//go:build go1.18 && a\u00b2\n", None, "unknown"),
        ("//go:build go1.18 && li-nux\n", None, "unknown"),
        # Modern lines take precedence over legacy ones.
        ("//go:build go1.18 || go1.21\n// +build go1.22\n", "1.18", "minimum"),
        ("//go:build !go1.21\n// +build go1.22\n", None, "unconstrained"),
        ("", None, "absent"),
    ],
)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_go_build_expressions_report_truthful_minimums(
    tmp_path: Path, header: str, minimum: str | None, status: str, newline: str
) -> None:
    """treesitter-chunker#438: Boolean build expressions.

    Named mutations, each failing at least one case: ``M438-or-as-and`` (OR
    takes the highest minimum), ``M438-not-as-positive`` (``!goX.Y`` treated
    as ``goX.Y``), ``M438-unsat-as-max`` (an unsatisfiable expression
    reports its highest release), ``M438-free-tag-false`` (non-release tags
    treated as false), ``M438-legacy-last-tag`` and ``M438-ascii-tags``
    (ASCII-only tag characters).
    """
    hints = _hints(tmp_path, header, newline)
    assert hints["build_constraints"] == minimum
    assert hints["build_constraints_status"] == status
    detector = GoVersionDetector()
    assert detector.get_primary_version(hints) == minimum
    analysis = detector.analyze_build_constraints(header.replace("\n", newline))
    assert (analysis["minimum"], analysis["status"]) == (minimum, status)
    assert bool(analysis["reason"]) is (status == "unknown")


@pytest.mark.parametrize(
    "header",
    [
        "//go:build go1.21 && !go1.18\n",
        "//go:build go1.18 ||\n",
        "//go:build !go1.21\n",
        "// +build linux go1.20\n",
    ],
)
def test_go_mod_and_features_take_over_from_uninformative_constraints(
    tmp_path: Path, header: str
) -> None:
    hints = _hints(tmp_path, header)
    assert hints["build_constraints"] is None
    assert hints["build_constraints_status"] in {"unknown", "unconstrained"}
    detector = GoVersionDetector()
    assert detector.get_primary_version({**hints, "go_mod_version": "1.22"}) == "1.22"
    fallback = {**hints, "min_version_from_features": "1.18"}
    assert detector.get_primary_version(fallback) == "1.18"
    assert detector.get_primary_version(hints) not in {"unknown", "unconstrained"}


def test_go_mod_precedes_compound_build_minimum(tmp_path: Path) -> None:
    hints = _hints(tmp_path, "//go:build go1.18 && !go1.21\n")
    assert hints["build_constraints"] == "1.18"
    detector = GoVersionDetector()
    assert detector.get_primary_version({**hints, "go_mod_version": "1.22"}) == "1.22"


def test_large_build_expressions_are_bounded(tmp_path: Path) -> None:
    detector = GoVersionDetector()
    chain = " && ".join(f"tag{i}" for i in range(400))
    assert detector.analyze_build_constraints(f"//go:build go1.18 && {chain}\n") == {
        "minimum": None,
        "status": "unknown",
        "reason": "too many build tags",
    }
    many = " || ".join(f"go1.{i}" for i in range(1, 400))
    assert detector.analyze_build_constraints(f"//go:build {many}\n")["minimum"] == (
        "1.1"
    )
    too_long = " || ".join(["go1.18"] * 600)
    assert detector.analyze_build_constraints(f"//go:build {too_long}\n") == {
        "minimum": None,
        "status": "unknown",
        "reason": "expression too large",
    }
    nested = "(" * 150 + "go1.18" + ")" * 150
    assert detector.analyze_build_constraints(f"//go:build {nested}\n")["status"] == (
        "unknown"
    )
    hard = " && ".join(f"(t{i} || t{i + 1} || !t{i + 2})" for i in range(30))
    # Satisfiable with the free tags: the search finds it within its bound.
    assert detector.analyze_build_constraints(f"//go:build go1.20 && ({hard})\n") == {
        "minimum": "1.20",
        "status": "minimum",
        "reason": None,
    }


def test_build_expression_search_has_a_step_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pigeonhole: 5 pigeons cannot sit in 4 holes. Unsatisfiable; within the
    # default budget the search proves it, and under a small budget it stops
    # with an explicit unknown instead of searching on.
    pigeons, holes = range(5), range(4)
    every_pigeon_seated = [
        "(" + " || ".join(f"p{p}h{h}" for h in holes) + ")" for p in pigeons
    ]
    no_shared_hole = [
        f"(!p{a}h{h} || !p{b}h{h})"
        for h in holes
        for a in pigeons
        for b in pigeons
        if a < b
    ]
    expression = " && ".join(["go1.18", *every_pigeon_seated, *no_shared_hole])
    line = f"//go:build {expression}\n"
    detector = GoVersionDetector()
    assert detector.analyze_build_constraints(line) == {
        "minimum": None,
        "status": "unknown",
        "reason": "no Go release satisfies the constraint",
    }
    monkeypatch.setattr(go_detector, "_GO_MAX_SEARCH_STEPS", 50)
    assert detector.analyze_build_constraints(line) == {
        "minimum": None,
        "status": "unknown",
        "reason": "expression too complex",
    }


# Go 1.26.8 ``go/build`` ``Context.MatchFile`` results (GOOS=linux, lowest
# go1.N accepted; "1.1" means no constraint) are noted per case. Go reads
# constraints only from the file header (treesitter-chunker#438).
@pytest.mark.parametrize(
    ("source", "minimum", "status"),
    [
        pytest.param(
            "//go:build go1.18\n\npackage sample\n\nconst tmpl = `\n//go:build go1.23\n`\n",
            "1.18",
            "minimum",
            id="go-00",  # Go: 1.18
        ),
        pytest.param(
            "//go:build go1.18\n\npackage sample\n\nfunc F() int {\n\t//go:build go1.22\n\treturn 1\n}\n",
            "1.18",
            "minimum",
            id="go-01",  # Go: 1.18
        ),
        pytest.param(
            "/*\n//go:build go1.22\n*/\n\npackage sample\n",
            None,
            "absent",
            id="go-02",  # Go: 1.1
        ),
        pytest.param(
            "// +build go1.21\npackage sample\n",
            None,
            "absent",
            id="go-03",  # Go: 1.1
        ),
        pytest.param(
            "//go:build go1.18\n\npackage sample\n\nconst tmpl = `\n//go:build go1.21 &&\n`\n",
            "1.18",
            "minimum",
            id="go-04",  # Go: 1.18
        ),
        pytest.param(
            "//go:build go1.18\n//go:build go1.21\n\npackage sample\n",
            None,
            "unknown",
            id="go-05",  # Go: error: multiple //go:build comments
        ),
        pytest.param(
            "//go:build\n\npackage sample\n",
            None,
            "unknown",
            id="go-06",  # Go: error: unexpected end of expression
        ),
        pytest.param(
            "//go:build\n// +build go1.22\n\npackage sample\n",
            None,
            "unknown",
            id="go-07",  # Go: error: unexpected end of expression
        ),
        pytest.param(
            "//go:build !!go1.18\n\npackage sample\n",
            None,
            "unknown",
            id="go-08",  # Go: error: double negation not allowed
        ),
        pytest.param(
            "//go:build !(!go1.18)\n\npackage sample\n",
            "1.18",
            "minimum",
            id="go-09",  # Go: 1.18
        ),
        pytest.param(
            "//go:build go1.20\npackage sample\n",
            "1.20",
            "minimum",
            id="go-10",  # Go: 1.20
        ),
        pytest.param(
            "// Copyright 2026\n\n//go:build go1.20\n\npackage sample\n",
            "1.20",
            "minimum",
            id="go-11",  # Go: 1.20
        ),
        pytest.param(
            "/* c */\n// +build go1.21\n\npackage sample\n",
            None,
            "absent",
            id="go-12",  # Go: 1.1
        ),
        pytest.param(
            "// +build go1.21\n\n/* c */\npackage sample\n",
            "1.21",
            "minimum",
            id="go-13",  # Go: 1.21
        ),
        pytest.param(
            "// +build go1.18 go1.20\n// +build go1.19\n\npackage sample\n",
            "1.19",
            "minimum",
            id="go-14",  # Go: 1.19
        ),
        pytest.param(
            "  //go:build go1.20\n\npackage sample\n",
            "1.20",
            "minimum",
            id="go-15",  # Go: 1.20
        ),
        pytest.param(
            "//go:build go1.20\r\n\r\npackage sample\r\n",
            "1.20",
            "minimum",
            id="go-16",  # Go: 1.20
        ),
        pytest.param(
            "// +build go1.21\r\n\r\npackage sample\r\n",
            "1.21",
            "minimum",
            id="go-17",  # Go: 1.21
        ),
        pytest.param(
            "// +build\n\npackage sample\n",
            None,
            "unknown",
            id="go-18",  # Go: never
        ),
        pytest.param(
            "//go:buildgo1.20\n\npackage sample\n",
            None,
            "absent",
            id="go-19",  # Go: 1.1
        ),
    ],
)
def test_go_build_header_placement_matches_go_build(
    source: str, minimum: str | None, status: str
) -> None:
    """Named mutations: ``M438-whole-file``, ``M438-and-duplicates``,
    ``M438-bare-absent``, ``M438-double-negation``, ``M438-slash-star`` and
    ``M438-legacy-no-blank``."""
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error
    detector = GoVersionDetector()
    analysis = detector.analyze_build_constraints(source)
    assert (analysis["minimum"], analysis["status"]) == (minimum, status)
    assert bool(analysis["reason"]) is (status == "unknown")
    hints = detector.detect_version(source, Path("service.go"))
    assert hints["build_constraints"] == minimum
    assert hints["build_constraints_status"] == status
    assert detector.get_primary_version({**hints, "go_mod_version": "1.23"}) == "1.23"


@pytest.mark.parametrize(
    "header",
    [
        "//go:build go1." + "9" * 4500 + "\n",
        "//go:build go" + "9" * 4500 + ".1\n",
        "//go:build go1.20 || go1." + "9" * 4500 + "\n",
        "// +build go1." + "9" * 4500 + "\n",
        "//go:build go1.1000000000\n",
    ],
    ids=["minor-4500", "major-4500", "or-4500", "legacy-4500", "minor-10-digits"],
)
def test_oversized_release_numbers_are_unknown_not_errors(header: str) -> None:
    """Codex round 2: int() of a huge component must not escape.

    Go 1.26.8 never builds ``go1.<4500 nines>`` alone, and builds the OR form
    at 1.20; ``unknown`` is the conservative answer here. Named mutation
    ``M438-unbounded-int`` (no digit bound) raises ``ValueError`` through
    every public method.
    """
    source = (
        header + "\npackage sample\n\nfunc Same[T any](value T) T { return value }\n"
    )
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error
    detector = GoVersionDetector()
    analysis = detector.analyze_build_constraints(source)
    assert analysis["status"] == "unknown"
    assert analysis["minimum"] is None
    assert "release number too long" in analysis["reason"]
    assert detector.detect_from_build_constraints(source) is None
    hints = detector.detect_version(source, Path("service.go"))
    assert hints["build_constraints"] is None
    assert hints["build_constraints_status"] == "unknown"
    assert "generics" in hints["detected_features"]
    assert hints["min_version_from_features"] == "1.18"
    assert detector.get_primary_version(hints) == "1.18"
    assert detector.get_primary_version({**hints, "go_mod_version": "1.22"}) == "1.22"


def test_nine_digit_release_numbers_still_count() -> None:
    detector = GoVersionDetector()
    source = "//go:build go1.999999999\n\npackage sample\n"
    assert not get_parser("go").parse(source.encode("utf-8")).root_node.has_error
    assert detector.analyze_build_constraints(source) == {
        "minimum": "1.999999999",
        "status": "minimum",
        "reason": None,
    }


@pytest.mark.parametrize(
    ("source", "minimum"),
    [
        ("﻿//go:build go1.20\n\npackage sample\n", "1.20"),
        ("﻿// +build go1.21\n\npackage sample\n", "1.21"),
        ("﻿//go:build go1.20\r\n\r\npackage sample\r\n", "1.20"),
    ],
    ids=["modern", "legacy", "modern-crlf"],
)
def test_leading_byte_order_mark_is_skipped(source: str, minimum: str) -> None:
    """Go 1.26.8 go/build reads these headers at 1.20 and 1.21.

    Named mutation ``M438-bom`` (keep the BOM) makes them ``absent``.
    """
    detector = GoVersionDetector()
    analysis = detector.analyze_build_constraints(source)
    assert (analysis["minimum"], analysis["status"]) == (minimum, "minimum")
    assert detector.detect_from_build_constraints(source) == minimum
