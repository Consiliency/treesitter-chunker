import json

import pytest

from chunker.boundary import dumps_boundary_ir
from tests.boundary_ir_conformance import (
    GOLDEN_ROOT,
    SUPPORTED_BOUNDARY_LANGUAGES,
    extract_fixture_ir,
    normalize_ir_for_golden,
)


@pytest.mark.parametrize("language", SUPPORTED_BOUNDARY_LANGUAGES)
def test_boundary_ir_golden_snapshot(language: str):
    actual_ir = normalize_ir_for_golden(extract_fixture_ir(language))
    golden_path = GOLDEN_ROOT / f"{language}.json"

    assert golden_path.exists(), (
        f"Missing Boundary IR golden snapshot for {language}; regenerate "
        "tests/fixtures/boundary_ir/golden/<language>.json after reviewing "
        "the canonical conformance output."
    )
    expected_ir = json.loads(golden_path.read_text(encoding="utf-8"))

    assert actual_ir == expected_ir, (
        f"Boundary IR golden snapshot changed for {language}; review the "
        "canonical output and update the snapshot intentionally."
    )
    assert dumps_boundary_ir(actual_ir) == dumps_boundary_ir(expected_ir)
