"""Exercise version rejection and preservation without proprietary game files."""

import hashlib
import json
import plistlib
from dataclasses import replace
from pathlib import Path

import config
import pytest
from setup import preserve_source
from source_profiles import BASE_2077


def make_app(path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal fixture and pin its hash for source validation tests."""
    binary = path / "Contents/MacOS/factorio"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"test-only executable")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    monkeypatch.setattr(
        config, "SOURCE_PROFILES", {digest: replace(BASE_2077, sha256=digest)}
    )
    (path / "Contents/Info.plist").write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": "2.0.77"})
    )
    for mod, info in (("base", {"version": "2.0.77"}), ("core", {"name": "core"})):
        metadata = path / f"Contents/data/{mod}/info.json"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(json.dumps(info))
    return path


def test_source_requires_exact_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject a changed executable even when the metadata still says 2.0.77."""
    app = make_app(tmp_path / "original.app", monkeypatch)
    (app / "Contents/MacOS/factorio").write_bytes(b"different executable")
    with pytest.raises(ValueError, match="Betas > 2.0.77"):
        config.validate_source(app)


def test_source_requires_matching_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject newer assets paired with the supported executable."""
    app = make_app(tmp_path / "original.app", monkeypatch)
    (app / "Contents/data/base/info.json").write_text('{"version":"2.1.24"}')
    with pytest.raises(ValueError, match="base assets differ"):
        config.validate_source(app)


def test_source_requires_matching_plist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject app metadata left over from a different version."""
    app = make_app(tmp_path / "original.app", monkeypatch)
    (app / "Contents/Info.plist").write_bytes(
        plistlib.dumps({"CFBundleShortVersionString": "2.1.24"})
    )
    with pytest.raises(ValueError, match="Info.plist version differs"):
        config.validate_source(app)


def test_source_requires_complete_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject an incomplete download even when the executable matches."""
    app = make_app(tmp_path / "original.app", monkeypatch)
    (app / "Contents/data/core/info.json").unlink()
    with pytest.raises(ValueError, match="Incomplete Factorio app"):
        config.validate_source(app)


def test_preserved_source_survives_steam_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep a separate validated copy after the installed executable changes."""
    source = make_app(tmp_path / "original.app", monkeypatch)
    destination = tmp_path / "build/source/factorio.app"
    assert preserve_source(source, destination) == destination
    (source / "Contents/MacOS/factorio").write_bytes(b"Steam update")
    assert (
        config.validate_source(destination)
        == hashlib.sha256(b"test-only executable").hexdigest()
    )
    assert not list(destination.parent.glob(".factorio-*"))


def test_preserve_reuses_valid_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leave an existing valid copy intact on a repeated setup."""
    source = make_app(tmp_path / "original.app", monkeypatch)
    destination = tmp_path / "copy.app"
    preserve_source(source, destination)
    marker = destination / "marker"
    marker.write_text("keep")
    assert preserve_source(source, destination) == destination
    assert marker.read_text() == "keep"


def test_preserve_never_overwrites_bad_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Require intervention for a damaged copy instead of silently replacing it."""
    source = make_app(tmp_path / "original.app", monkeypatch)
    destination = tmp_path / "copy.app"
    destination.mkdir()
    marker = destination / "marker"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="executable not found"):
        preserve_source(source, destination)
    assert marker.read_text() == "keep"


def test_preserve_rejects_nested_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prevent recursive copies inside the source app."""
    source = make_app(tmp_path / "original.app", monkeypatch)
    with pytest.raises(ValueError, match="outside the original"):
        preserve_source(source, source / "nested.app")
