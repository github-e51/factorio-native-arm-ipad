"""Machine-local settings; only the example belongs in version control."""

import hashlib
import json
import os
import plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".local-config.json"
SETTINGS = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
STEAM_APP = Path.home() / "Library/Application Support/Steam/steamapps/common/Factorio/factorio.app"
DEFAULT_APP = Path(
    os.environ.get("FACTORIO_APP") or SETTINGS.get("factorio_app") or STEAM_APP
).expanduser()
CMAKE = os.environ.get("FACTORIO_CMAKE") or SETTINGS.get("cmake") or "cmake"
DEFAULT_BUNDLE_ID = "local.factorio.loaderprobe"
SUPPORTED_VERSION = "2.0.77"
SUPPORTED_SHA256 = "00b014d78df07e05ab1cee853904c8f7b3814ca652c043461a9d49fbad46cdf6"
PRESERVED_APP = ROOT / "build/source" / f"factorio-{SUPPORTED_VERSION}.app"


def validate_source(app: Path) -> str:
    """Require the audited executable and matching base assets before patching."""
    binary = app / "Contents/MacOS/factorio"
    if not binary.is_file():
        raise ValueError(
            f"Factorio executable not found: {binary}. "
            "Run tools/setup.py --app /path/to/factorio.app"
        )
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != SUPPORTED_SHA256:
        raise ValueError(
            f"Unsupported Factorio executable SHA-256: {digest}\n"
            f"Required: {SUPPORTED_SHA256} (2.0.77, build 84539, macOS Steam universal binary).\n"
            "In Steam: Factorio > Properties > Betas > 2.0.77; disable Space Age DLC.\n"
            "Wait for the download to finish.\n"
            "Then run: uv run python tools/setup.py --preserve-source\n"
            "See docs/IPAD_SETUP.ja.md. Do not bypass the executable hash check."
        )
    for relative in (
        "Contents/Info.plist", "Contents/data/base/info.json", "Contents/data/core/info.json"
    ):
        if not (app / relative).is_file():
            raise ValueError(f"Incomplete Factorio app: missing {relative}")
    try:
        info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
        base = json.loads((app / "Contents/data/base/info.json").read_text())
    except (ValueError, plistlib.InvalidFileException) as error:
        raise ValueError(f"Invalid Factorio metadata: {app}") from error
    if info.get("CFBundleShortVersionString") != SUPPORTED_VERSION:
        raise ValueError("Factorio Info.plist version differs from the supported executable")
    if base.get("version") != SUPPORTED_VERSION:
        raise ValueError("Factorio base assets differ from 2.0.77; finish the Steam download")
    return digest
