"""Check PNG pixel conversion, worker decoding, and ownership on macOS."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("xcrun") is None,
    reason="Bitmap compatibility checks require the Apple frameworks and compiler",
)
def test_bitmap_pixels_and_worker_lifetimes(tmp_path: Path) -> None:
    """Exercise real ImageIO decoding, alpha conversion, and returned image lifetimes."""
    root = Path(__file__).resolve().parents[1]
    binary = tmp_path / "bitmap-compat-tests"
    subprocess.run(
        [
            "xcrun",
            "clang",
            "-fobjc-arc",
            "-framework",
            "Foundation",
            "-framework",
            "CoreGraphics",
            "-framework",
            "ImageIO",
            str(root / "tests/BitmapCompatTests.m"),
            str(root / "probe/BitmapCompat.m"),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    subprocess.run(
        [str(binary)], check=True, capture_output=True, text=True, timeout=30
    )
