"""Validate local prerequisites and optionally preserve the supported Steam app."""

import argparse
import json
import logging
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from config import (
    CONFIG_PATH,
    DEFAULT_APP,
    ROOT,
    STEAM_APP,
    source_profile,
    validate_source,
)

logger = logging.getLogger(__name__)


def preserve_source(source: Path, destination: Path | None = None) -> Path:
    """Publish a validated private copy without replacing an existing directory."""
    source = source.resolve()
    profile = source_profile(source)
    destination = (
        destination or ROOT / "build/source" / f"factorio-{profile.key}.app"
    ).resolve()
    if destination.exists():
        if source_profile(destination) != profile:
            raise ValueError("The existing preserved app belongs to a different build")
        return destination
    if destination.is_relative_to(source):
        raise ValueError("The preserved app must be outside the original app")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".factorio-", dir=destination.parent
    ) as staging:
        candidate = Path(staging) / "factorio.app"
        shutil.copytree(source, candidate, symlinks=True)
        validate_source(candidate)
        candidate.rename(destination)
    return destination


def main() -> None:
    """Check tools, synchronize uv dependencies, and save validated local paths."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument(
        "--app", type=Path, default=DEFAULT_APP, help="Your macOS factorio.app"
    )
    sources.add_argument(
        "--steam",
        action="store_true",
        help="Read Steam even if a preserved source is configured",
    )
    parser.add_argument(
        "--preserve-source", action="store_true", help="Keep a copy under build/source"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate app and tools without writing files",
    )
    args = parser.parse_args()
    if sys.version_info < (3, 12):  # noqa: UP036 -- also support direct invocation outside uv
        parser.error("Python 3.12 or newer is required.")
    if sys.platform != "darwin" or platform.machine() != "arm64":
        parser.error("Run natively on an Apple Silicon Mac (not under Rosetta).")
    app = (STEAM_APP if args.steam else args.app).expanduser().resolve()
    try:
        validate_source(app)
    except ValueError as error:
        parser.error(str(error))
    cmake = shutil.which("cmake")
    if not cmake:
        parser.error("CMake is missing. Install it and retry.")
    subprocess.run(["xcodebuild", "-version"], check=True)
    sdk = subprocess.check_output(
        ["xcrun", "--sdk", "iphoneos", "--show-sdk-version"], text=True
    ).strip()
    if int(sdk.split(".")[0]) < 26:
        parser.error(f"iOS SDK 26 or newer is required; found {sdk}.")
    if args.check:
        logger.info(
            "Source and build tools verified. No app has been built or installed."
        )
        return
    uv = shutil.which("uv")
    if not uv:
        parser.error("uv is required. Install uv, then run uv sync --locked.")
    subprocess.run([uv, "sync", "--locked", "--project", str(ROOT)], check=True)
    for directory in ("build", "reports"):
        (ROOT / directory).mkdir(exist_ok=True)
    if args.preserve_source:
        app = preserve_source(app)
    CONFIG_PATH.write_text(
        json.dumps({"factorio_app": str(app), "cmake": cmake}, indent=2) + "\n"
    )
    logger.info("Setup complete. Source: %s", app)
    logger.info(
        "Local paths are saved in .local-config.json. See docs/IPAD_SETUP.ja.md."
    )


if __name__ == "__main__":
    main()
