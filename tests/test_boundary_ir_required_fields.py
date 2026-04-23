import pytest

from tests.boundary_ir_conformance import (
    P0_BOUNDARY_LANGUAGES,
    assert_required_fields,
    extract_fixture_ir,
)


@pytest.mark.parametrize("language", P0_BOUNDARY_LANGUAGES)
def test_boundary_ir_required_fields_for_p0_fixtures(language: str):
    ir = extract_fixture_ir(language)

    assert_required_fields(ir)
