import inspect

from chunker.boundary import extract_boundary_ir
from chunker.boundary.types import (
    BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS,
    BOUNDARY_CACHE_KEY_FIELDS,
    BOUNDARY_CACHE_KEY_PREFIX,
    BOUNDARY_CACHE_VERSION,
)


def test_boundary_cache_constants_freeze_key_contract():
    assert BOUNDARY_CACHE_VERSION == "1"
    assert BOUNDARY_CACHE_KEY_PREFIX == "boundary:v1:"
    assert BOUNDARY_CACHE_KEY_FIELDS == (
        "path",
        "content_hash",
        "language",
        "grammar_version",
        "tool_version",
        "schema_version",
        "resolution_mode",
        "fail_fast",
        "include_retrieval_metadata",
    )
    assert BOUNDARY_CACHE_EXCLUDED_OPTION_FIELDS == (
        "created_at",
        "canonical",
        "include_timings",
        "incremental",
        "cache_dir",
        "force_rebuild",
    )


def test_extract_boundary_ir_incremental_signature_is_additive():
    signature = inspect.signature(extract_boundary_ir)
    params = signature.parameters

    assert params["incremental"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["cache_dir"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["force_rebuild"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["incremental"].default is False
    assert params["cache_dir"].default is None
    assert params["force_rebuild"].default is False
