from __future__ import annotations

from pathlib import Path

from research_school_radar.atomic_io import write_text_atomic


def test_atomic_text_write_retries_transient_permission_error(monkeypatch, tmp_path) -> None:
    target = tmp_path / "feed.xml"
    target.write_text("old", encoding="utf-8")
    original_replace = Path.replace
    attempts = 0

    def flaky_replace(path: Path, destination: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("temporarily locked")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    monkeypatch.setattr("research_school_radar.atomic_io.time.sleep", lambda _seconds: None)

    write_text_atomic(target, "complete")

    assert attempts == 2
    assert target.read_text(encoding="utf-8") == "complete"
    assert not list(tmp_path.glob("*.tmp"))
