import pytest

from chunker._internal.path_confinement import resolve_within_root
from chunker._internal.vfs import LocalFileSystem


def test_resolve_within_root_rejects_absolute_and_parent_escapes(tmp_path):
    outside = tmp_path.parent / "outside.py"
    outside.write_text("outside", encoding="utf-8")

    with pytest.raises(ValueError):
        resolve_within_root(outside, tmp_path)
    with pytest.raises(ValueError):
        resolve_within_root("../outside.py", tmp_path)


def test_resolve_within_root_rejects_symlink_escapes_for_read_and_write(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("secret", encoding="utf-8")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        resolve_within_root("linked/secret.py", tmp_path)
    with pytest.raises(ValueError):
        resolve_within_root("linked/new.py", tmp_path)


def test_local_vfs_applies_confinement_to_reads_and_writes(tmp_path):
    vfs = LocalFileSystem(tmp_path)

    with pytest.raises(ValueError):
        vfs.open("../outside.py")
    with pytest.raises(ValueError):
        vfs.open(str(tmp_path.parent / "outside.py"), "w")
