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


@pytest.mark.parametrize("prefix", ["//go:build", "// +build"])
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
    tmp_path: Path, prefix: str, versions: tuple[str, str], expected: str
) -> None:
    constraints = "".join(f"{prefix} go{version}\n" for version in versions)
    source = constraints + FIXTURE.read_text(encoding="utf-8")
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
    treated as false) and ``M438-legacy-last-tag``.
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
