"""Prevent assets from an older game or edition remaining in a rebuilt app."""

from pathlib import Path

import pytest
from bundle_assets import sync_assets


def make_data(path: Path) -> Path:
    """Create enough fixture metadata to represent a complete game data directory."""
    for mod in ("base", "core"):
        (path / mod).mkdir(parents=True)
        (path / mod / "info.json").write_text("{}")
    return path


def test_replaces_stale_assets_and_removes_dlc(tmp_path: Path) -> None:
    """Switch editions without keeping Space Age files from the earlier build."""
    source = make_data(tmp_path / "source")
    (source / "space-age").mkdir()
    (source / "space-age/planet.lua").write_text("old")
    destination = tmp_path / "app/data"
    sync_assets(source, destination, "expansion")
    base_source = make_data(tmp_path / "base-only")
    (base_source / "base/new.lua").write_text("new")
    sync_assets(base_source, destination, "base")
    assert not (destination / "space-age").exists()
    assert (destination / "base/new.lua").read_text() == "new"


def test_failed_copy_keeps_previous_assets(tmp_path: Path) -> None:
    """Reject incomplete data without removing the last complete build copy."""
    source = make_data(tmp_path / "source")
    destination = tmp_path / "app/data"
    sync_assets(source, destination, "old")
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    with pytest.raises(ValueError, match="incomplete"):
        sync_assets(incomplete, destination, "new")
    assert (destination / "base/info.json").is_file()
    assert "old" in (destination / ".factorio-source.json").read_text()


def test_rejects_overlapping_source_and_destination(tmp_path: Path) -> None:
    """Keep an invalid build destination from modifying original game files."""
    source = make_data(tmp_path / "source")
    with pytest.raises(ValueError, match="separate"):
        sync_assets(source, source / "nested", "new")
