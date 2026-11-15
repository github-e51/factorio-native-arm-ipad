"""Machine-local paths and strict validation against analyzed source profiles."""

import hashlib
import json
import os
import plistlib
from pathlib import Path

from source_profiles import BASE_2077, SOURCE_PROFILES, SourceProfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".local-config.json"
SETTINGS = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
STEAM_APP = (
    Path.home()
    / "Library/Application Support/Steam/steamapps/common/Factorio/factorio.app"
)
DEFAULT_APP = Path(
    os.environ.get("FACTORIO_APP") or SETTINGS.get("factorio_app") or STEAM_APP
).expanduser()
CMAKE = os.environ.get("FACTORIO_CMAKE") or SETTINGS.get("cmake") or "cmake"
DEFAULT_BUNDLE_ID = "local.factorio.loaderprobe"
SUPPORTED_SHA256 = BASE_2077.sha256


def source_profile(app: Path) -> SourceProfile:
    """Validate the executable hash, app version, and edition-specific assets."""
    binary = app / "Contents/MacOS/factorio"
    if not binary.is_file():
        raise ValueError(
            f"Factorio executable not found: {binary}. Run tools/setup.py --app /path/to/factorio.app"
        )
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    profile = SOURCE_PROFILES.get(digest)
    if profile is None:
        supported = ", ".join(item.key for item in SOURCE_PROFILES.values())
        raise ValueError(
            f"Unsupported Factorio executable SHA-256: {digest}\n"
            f"Analyzed builds: {supported}. Do not bypass the executable hash check.\n"
            "For the baseline in Steam: Factorio > Properties > Betas > 2.0.77; disable Space Age DLC.\n"
            "Wait for the download to finish. See docs/IPAD_SETUP.ja.md."
        )
    metadata = app / "Contents/Info.plist"
    if not metadata.is_file():
        raise ValueError("Incomplete Factorio app: missing Contents/Info.plist")
    try:
        info = plistlib.loads(metadata.read_bytes())
        if info.get("CFBundleShortVersionString") != profile.version:
            raise ValueError(
                "Factorio Info.plist version differs from the supported executable"
            )
        for mod, version in profile.mods:
            mod_info = app / f"Contents/data/{mod}/info.json"
            if not mod_info.is_file():
                raise ValueError(
                    f"Incomplete Factorio app: missing {mod_info.relative_to(app)}"
                )
            content = json.loads(mod_info.read_text())
            if version is not None and content.get("version") != version:
                raise ValueError(
                    f"Factorio {mod} assets differ from {version}; finish the Steam download"
                )
    except (plistlib.InvalidFileException, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid Factorio metadata: {app}") from error
    return profile


def validate_source(app: Path) -> str:
    """Return the exact source hash after validating its profile and assets."""
    return source_profile(app).sha256
