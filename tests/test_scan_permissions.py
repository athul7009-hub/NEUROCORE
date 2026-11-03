
import pytest

from app.tools.scan_pipeline import run_scan
from app.core.config import settings


def test_unapproved_directory_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_scan_roots", [])

    with pytest.raises(PermissionError):
        run_scan(str(tmp_path))


def test_approved_directory_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [str(tmp_path)]
    )

    result = run_scan(str(tmp_path))

    assert result["total_files"] == 0
