"""Cover SDK 27 system stubs and exclude unrelated Apple platforms."""

from pathlib import Path

import pytest
from audit import sdk_exports, supports_ios_arm64


@pytest.mark.parametrize("target", [
    "arm64-ios", "arm64-ios-simulator", "arm64e-ios", "arm64e.x1-ios"
])
def test_accepts_ios_arm64_stubs(target: str) -> None:
    """Include device system variants that Apple's ARM64 linker accepts."""
    assert supports_ios_arm64([target])


@pytest.mark.parametrize("target", [
    "arm64-maccatalyst", "arm64e-macos", "arm64e.x1-macos", "x86_64-ios-simulator", "arm64_32-watchos"
])
def test_excludes_other_platforms(target: str) -> None:
    """Do not treat a macOS or Catalyst export as an iOS implementation."""
    assert not supports_ios_arm64([target])


def test_sdk27_exports_and_recursive_reexports(tmp_path: Path) -> None:
    """Read arm64e classes and follow reexports without following cycles forever."""
    (tmp_path / "usr/lib").mkdir(parents=True)
    (tmp_path / "usr/lib/Parent.tbd").write_text('''--- !tapi-tbd
tbd-version: 4
targets: [ arm64e-ios, arm64e.x1-ios ]
install-name: /usr/lib/Parent.dylib
exports:
  - targets: [ arm64e-ios, arm64e.x1-ios ]
    symbols: [ _device ]
    objc-classes: [ NSArray ]
  - targets: [ arm64-maccatalyst ]
    symbols: [ _catalyst_only ]
reexported-libraries:
  - targets: [ arm64e-ios, arm64e.x1-ios ]
    libraries: [ /usr/lib/Child.dylib ]
''')
    (tmp_path / "usr/lib/Child.tbd").write_text('''--- !tapi-tbd
tbd-version: 4
install-name: /usr/lib/Child.dylib
exports:
  - targets: [ arm64e-ios ]
    symbols: [ _child ]
reexported-libraries:
  - targets: [ arm64e-ios ]
    libraries: [ /usr/lib/Parent.dylib ]
''')
    assert sdk_exports(tmp_path, "/usr/lib/Parent.dylib") == {
        "_device", "_child", "_OBJC_CLASS_$_NSArray", "_OBJC_METACLASS_$_NSArray"
    }
