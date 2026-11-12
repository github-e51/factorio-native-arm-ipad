"""Keep bundled game data tied to the executable used for the current build."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def sync_assets(source: Path, destination: Path, source_sha256: str) -> None:
    """Replace stale build assets only after a complete private copy is available."""
    source = source.resolve()
    destination = destination.resolve()
    if (
        source == destination
        or source.is_relative_to(destination)
        or destination.is_relative_to(source)
    ):
        raise ValueError("Source and bundled data directories must be separate")
    identity = {"source_sha256": source_sha256}
    marker_name = ".factorio-source.json"
    marker = destination / marker_name
    if marker.is_file() and json.loads(marker.read_text()) == identity:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".factorio-assets-", dir=destination.parent
    ) as staging:
        candidate = Path(staging) / "data"
        try:
            subprocess.run(
                ["cp", "-cR", str(source), str(candidate)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            if candidate.exists():
                shutil.rmtree(candidate)
            shutil.copytree(source, candidate, symlinks=True)
        if (
            not (candidate / "base/info.json").is_file()
            or not (candidate / "core/info.json").is_file()
        ):
            raise ValueError("Copied Factorio data is incomplete")
        (candidate / marker_name).write_text(json.dumps(identity, indent=2) + "\n")
        previous = Path(staging) / "previous"
        if destination.exists():
            destination.rename(previous)
        try:
            candidate.rename(destination)
        except OSError:
            if previous.exists():
                previous.rename(destination)
            raise
