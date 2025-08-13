from pathlib import Path

from chunker.helpers.nearest_tests import nearest_tests


def test_nearest_tests_ranks_expected_files(tmp_path):
    # Create a few files
    (tmp_path / "tests").mkdir()
    t1 = tmp_path / "tests" / "test_utils.py"
    t1.write_text("def test_x(): pass\n# utils in name", encoding="utf-8")
    t2 = tmp_path / "utils_test.js"
    t2.write_text("// utils referenced here", encoding="utf-8")
    irrel = tmp_path / "tests" / "test_irrelevant.py"
    irrel.write_text("def test_y(): pass", encoding="utf-8")

    results = nearest_tests(["utils"], str(tmp_path))
    assert results, "expected some candidates"
    paths = [r["path"] for r in results]
    # Top results should include our utils-named files
    assert str(t1) in paths
    assert str(t2) in paths
