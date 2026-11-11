
import os
import pytest

from app.tools.file_scanner import scan_directory


def test_root_symlink_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()

    link = tmp_path / "linked_root"

    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic-link creation is unavailable.")

    with pytest.raises(ValueError, match="Reparse-point"):
        scan_directory(str(link))


def test_nested_symlink_is_skipped(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "secret.txt").write_text("NEUROCORE")

    root = tmp_path / "scan_root"
    root.mkdir()

    link = root / "linked_folder"

    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic-link creation is unavailable.")

    files, warnings = scan_directory(str(root))

    assert files == []
    assert warnings == []

def test_excluded_directory_is_skipped(tmp_path):
    protected = tmp_path / "Windows"
    protected.mkdir()
    (protected / "system.txt").write_text("protected")

    files, warnings = scan_directory(str(tmp_path))

    assert files == []
    assert warnings == []


def test_inaccessible_directory_is_skipped(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.mkdir()

    original_scandir = os.scandir

    def mocked_scandir(path):
        if os.fspath(path) == str(blocked):
            raise PermissionError("Access denied")

        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", mocked_scandir)

    files, warnings = scan_directory(str(tmp_path))

    assert files == []
    assert len(warnings) == 1
    assert warnings[0]["category"] == "access_denied"
    assert warnings[0]["path"] == "blocked"
