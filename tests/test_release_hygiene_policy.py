"""Release hygiene policy checks for warnings and skip markers."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
POLICY_TEST = Path(__file__).name
FALLBACK_TEST_FILES = [
    TESTS / "test_auto.py",
    TESTS / "test_fallback_chunking.py",
    TESTS / "test_overlapping_fallback.py",
]


def _test_sources() -> list[Path]:
    return [
        path
        for path in TESTS.rglob("test_*.py")
        if path.name != POLICY_TEST and "__pycache__" not in path.parts
    ]


def test_no_xfail_markers_or_calls_in_tests():
    """Release test suites should not hide expected failures."""
    forbidden = ("pytest.mark.xfail", "pytest.xfail(")
    offenders = []
    for path in _test_sources():
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT)}: {marker}")

    assert offenders == []


def test_conftest_has_no_collection_time_policy_mutation():
    """Keep xfail/skip and fallback-warning policy local to tests."""
    text = (TESTS / "conftest.py").read_text(encoding="utf-8")

    assert "pytest_collection_modifyitems" not in text
    assert "FallbackWarning" not in text
    assert "filterwarnings" not in text


def test_no_global_fallback_warning_filter():
    """Expected fallback warnings should be asserted where they are triggered."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "filterwarnings" not in text
    assert "FallbackWarning" not in text


def test_fallback_warning_tests_use_scoped_assertions():
    """Fallback-warning tests should assert local warning contracts."""
    for path in FALLBACK_TEST_FILES:
        text = path.read_text(encoding="utf-8")
        assert "warnings.catch_warnings(record=True)" not in text
        assert "pytest.warns" in text
        assert "FallbackWarning" in text
