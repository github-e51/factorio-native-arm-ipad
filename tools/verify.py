"""Verify source provenance, documented patches, bundled data, and app signatures."""

import argparse
import json
import logging
import plistlib
import re
import struct
import subprocess
from pathlib import Path

import yaml
from audit import TBDLoader, mobile_path, sdk_path
from config import DEFAULT_APP, ROOT, source_profile
from macho import MachO
from source_profiles import BASE_2077, SourceProfile

logger = logging.getLogger(__name__)


def require(condition: object, message: str) -> None:
    """Stop verification when an invariant does not hold."""
    if not condition:
        raise RuntimeError(message)


def benchmark_checksum(log: str) -> str:
    """Require a completed 120-update simulation and return its reported checksum."""
    checksums = re.findall(r"^\s*checksum: (\d+)\s*$", log, re.MULTILINE)
    require(len(checksums) == 1, "Expected exactly one simulation checksum")
    require("Performed 120 updates" in log and "Goodbye" in log, "Incomplete benchmark")
    require(
        "Factorio crashed." not in log and "FACTORIO_PROBE_UNIMPLEMENTED:" not in log,
        "Benchmark crashed",
    )
    return checksums[0]


def verify_assets(app: Path, profile: SourceProfile) -> None:
    """Require all edition-specific metadata and the executable's data identity."""
    for mod, version in profile.mods:
        path = app / f"data/{mod}/info.json"
        require(path.is_file(), f"Missing bundled {mod} assets")
        metadata = json.loads(path.read_text())
        if version is not None:
            require(metadata.get("version") == version, f"Wrong bundled {mod} version")
    marker = app / "data/.factorio-source.json"
    require(
        marker.is_file(),
        "Missing bundled data source identity; rebuild with --bundle-data",
    )
    require(
        json.loads(marker.read_text()).get("source_sha256") == profile.sha256,
        "Bundled data belongs to another executable",
    )


def main() -> None:
    """Validate a device or simulator product against its exact original game."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app", type=Path, default=DEFAULT_APP, help="Original macOS game app"
    )
    parser.add_argument(
        "--sdk", choices=["iphoneos", "iphonesimulator"], default="iphoneos"
    )
    parser.add_argument("--signed-app", type=Path, help="Also check this Xcode product")
    parser.add_argument("--bundle-id", help="Expected identifier of --signed-app")
    parser.add_argument(
        "--benchmark-log",
        type=Path,
        help="Log from the 120-update ported-engine benchmark",
    )
    parser.add_argument(
        "--reference-benchmark-log",
        type=Path,
        help="Native Mac benchmark of the same save, game version, and mods",
    )
    args = parser.parse_args()
    profile = source_profile(args.app)
    source = MachO(args.app / "Contents/MacOS/factorio")
    sdk = args.sdk
    platform = 2 if sdk == "iphoneos" else 7
    app = ROOT / (
        "build/iphoneos/FactorioProbe.app"
        if sdk == "iphoneos"
        else "build/FactorioProbe.app"
    )
    patched = MachO(app / "FactorioProbe")
    manifest = json.loads((ROOT / f"reports/entrypoint-patch-{sdk}.json").read_text())
    require(
        manifest.get("source_sha256") == profile.sha256,
        "Patch manifest belongs to a different executable",
    )
    require(
        manifest.get("source_profile") == profile.key, "Patch manifest profile differs"
    )
    growth = manifest.get("zero_fill_growth")
    require(isinstance(growth, dict), "Missing zero-fill allocation provenance")
    original_segments = {
        bytes(source.data[offset + 8 : offset + 24])
        .rstrip(b"\0")
        .decode(): struct.unpack_from("<QQQQ", source.data, offset + 24)
        for command, offset, _ in source.commands
        if command == 0x19
    }
    adapted_segments = {
        bytes(patched.data[offset + 8 : offset + 24])
        .rstrip(b"\0")
        .decode(): struct.unpack_from("<QQQQ", patched.data, offset + 24)
        for command, offset, _ in patched.commands
        if command == 0x19
    }
    require(
        original_segments.keys() == adapted_segments.keys(), "Segment inventory changed"
    )
    for name, (address, size, file_offset, file_size) in original_segments.items():
        adapted_address, adapted_size, adapted_offset, adapted_file_size = (
            adapted_segments[name]
        )
        require(adapted_offset == file_offset, f"Original file offsets moved in {name}")
        if name == "__DATA":
            require(
                growth["data_vm_size_before"] == size
                and growth["data_vm_size_after"] == adapted_size,
                "Incorrect zero-fill allocation provenance",
            )
            require(
                adapted_address == address
                and adapted_size >= size
                and adapted_file_size == file_size,
                "Data extension moved original bytes",
            )
        elif name == "__LINKEDIT":
            require(
                growth["linkedit_vm_before"] == address
                and growth["linkedit_vm_after"] == adapted_address,
                "Incorrect LINKEDIT mapping provenance",
            )
            require(
                adapted_address >= sum(adapted_segments["__DATA"][:2]),
                "LINKEDIT overlaps data",
            )
        else:
            require(
                (adapted_address, adapted_size, adapted_file_size)
                == (address, size, file_size),
                f"Original segment layout changed in {name}",
            )
    restored = bytearray(patched.data)
    seen: set[int] = set()
    for entry in manifest["sdl_redirects"] + manifest["platform_patches"]:
        offset = entry["offset"]
        before = bytes.fromhex(entry["original_bytes"])
        after = bytes.fromhex(entry["patched_bytes"])
        require(len(before) == len(after), "Instruction patch changed length")
        covered = set(range(offset, offset + len(before)))
        require(not seen & covered, "Overlapping instruction patches")
        seen.update(covered)
        require(
            source.data[offset : offset + len(before)] == before,
            "Incorrect original instruction in manifest",
        )
        require(
            patched.data[offset : offset + len(after)] == after,
            "Patched instruction differs from manifest",
        )
        restored[offset : offset + len(before)] = before
    for section in source.sections:
        if section["offset"] and section["size"]:
            start, end = section["offset"], section["offset"] + section["size"]
            require(
                restored[start:end] == source.data[start:end],
                f"Undocumented changes in {section['name']}",
            )
    modules = [app / "FactorioProbe", *list((app / "Frameworks").glob("*.dylib"))]
    sdk_root = sdk_path(sdk)
    for module in modules:
        macho = MachO(module)
        platforms = [
            struct.unpack_from("<I", macho.data, offset + 8)[0]
            for command, offset, _ in macho.commands
            if command == 0x32
        ]
        require(
            platforms == [platform], f"Wrong platform in {module.name}: {platforms}"
        )
        for library in macho.libraries:
            if "/Versions/" in library:
                # iOS IOKit deliberately retains a versioned install name.
                stub = sdk_root / (mobile_path(library).lstrip("/") + ".tbd")
                require(stub.is_file(), f"Non-iOS versioned library: {library}")
                documents = list(yaml.load_all(stub.read_text(), Loader=TBDLoader))
                require(
                    any(item.get("install-name") == library for item in documents),
                    f"Library not declared by iOS SDK: {library}",
                )
    require(
        (app / f"Frameworks/libSDL{profile.sdl_major}.dylib").is_file(),
        "Wrong SDL ABI bundled",
    )
    if sdk == "iphoneos":
        require(
            not any(
                "SIMULATOR ONLY" in item["name"]
                for item in manifest["platform_patches"]
            ),
            "Simulator bypass in device build",
        )
    verify_assets(app, profile)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    report: dict[str, object] = {
        "source_sha256": profile.sha256,
        "source_profile": profile.key,
        sdk: {
            "modules_verified": len(modules),
            "sdl_redirects": len(manifest["sdl_redirects"]),
            "platform_patches": manifest["platform_patches"],
            "zero_fill_growth": growth,
            "undocumented_section_changes": 0,
            "assets_verified": [mod for mod, _ in profile.mods],
            "signature": "ad-hoc; device provisioning still required",
        },
    }
    if args.benchmark_log:
        log = args.benchmark_log.read_text()
        checksum = benchmark_checksum(log)
        if args.reference_benchmark_log:
            reference = args.reference_benchmark_log.read_text()
            require(
                f"Factorio {profile.version} " in log
                and f"Factorio {profile.version} " in reference,
                "Native and ported benchmark versions differ",
            )
            require(
                checksum == benchmark_checksum(reference),
                "Ported and native simulation checksums differ",
            )
        else:
            require(
                profile == BASE_2077 and checksum == "2892897386",
                "This build requires a native reference benchmark",
            )
        report["simulation"] = {
            "ticks": 120,
            "checksum": checksum,
            "scope": "supplied probe save and mod set only",
        }
    elif args.reference_benchmark_log:
        parser.error("--reference-benchmark-log requires --benchmark-log")
    if args.signed_app:
        signed_app = args.signed_app
        require(
            (signed_app / "embedded.mobileprovision").is_file(),
            "Missing development provisioning profile",
        )
        subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", str(signed_app)], check=True
        )
        info = plistlib.loads((signed_app / "Info.plist").read_bytes())
        identifier = info["CFBundleIdentifier"]
        if args.bundle_id:
            require(
                identifier == args.bundle_id, "Xcode product bundle identifier differs"
            )
        require(
            info.get("FactorioSourceProfile") == profile.key,
            "Xcode product source profile differs",
        )
        signed_macho = MachO(signed_app / "FactorioProbe")
        for section in patched.sections:
            if section["offset"] and section["size"]:
                start, end = section["offset"], section["offset"] + section["size"]
                require(
                    signed_macho.data[start:end] == patched.data[start:end],
                    f"Xcode product differs in {section['name']}",
                )
        verify_assets(signed_app, profile)
        report["development_signed_app"] = {
            "path": str(signed_app),
            "bundle_id": identifier,
        }
    (ROOT / "reports/verification.json").write_text(json.dumps(report, indent=2) + "\n")
    logger.info("%s", json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
