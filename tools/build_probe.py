"""Build the local iPadOS port from an exact, analyzed macOS game executable."""

import argparse
import json
import logging
import plistlib
import shutil
import subprocess
from pathlib import Path

from audit import audit as generate_audit
from audit import sdk_path
from bundle_assets import sync_assets
from config import DEFAULT_APP, DEFAULT_BUNDLE_ID, ROOT, source_profile
from entrypoint import inject_entry
from macho import MachO
from prepare_sdl import SDL_RELEASES, sdl_build_path
from source_profiles import SourceProfile

logger = logging.getLogger(__name__)


def defined_objc_classes(path: Path) -> set[str]:
    """Read class definitions that may collide between static and adapted SDL."""
    prefix = "_OBJC_CLASS_$_"
    return {
        symbol["name"][len(prefix) :]
        for symbol in MachO(path).symbols()
        if symbol["name"].startswith(prefix) and "library" not in symbol
    }


def rename_objc_classes(path: Path, replacements: dict[str, str]) -> None:
    """Rename runtime metadata without moving bytes in a signed Mach-O copy."""
    if not replacements:
        return
    macho = MachO(path)
    section = next(
        item for item in macho.sections if item["name"] == "__objc_classname"
    )
    start, end = section["offset"], section["offset"] + section["size"]
    for old, new in replacements.items():
        if len(old) != len(new):
            raise ValueError("Objective-C class renaming must preserve byte length")
        offset = macho.data.find(old.encode() + b"\0", start, end)
        if offset < 0:
            raise ValueError("Missing Objective-C metadata name: " + old)
        macho.data[offset : offset + len(old)] = new.encode()
    path.write_bytes(macho.data)


def build_shim(
    app: Path, source: Path, profile: SourceProfile, uikit: bool, sdk: str
) -> dict[str, str]:
    """Compile platform fallbacks and facades while preserving original library ordinals."""
    audit = json.loads((ROOT / f"reports/audit-{sdk}.json").read_text())
    if audit["sha256"] != profile.sha256:
        raise ValueError("Import audit belongs to a different executable")
    directory = ROOT / "build" / f"generated-{sdk}"
    directory.mkdir(parents=True, exist_ok=True)
    missing = {
        symbol["name"]
        for library in audit["libraries"]
        for symbol in library["missing"]
    }
    missing.difference_update(
        {
            "_nan",
            "_clGetPlatformIDs",
            "_SteamAPI_RestartAppIfNecessary",
            "_SteamAPI_Init",
            "_SteamInternal_SteamAPI_Init",
        }
    )
    classes = sorted(
        {symbol.split("$_")[1] for symbol in missing if symbol.startswith("_OBJC_")}
    )
    classes = [
        name for name in classes if name not in ("NSColorSpace", "NSBitmapImageRep")
    ]
    lines = [
        "#import <Foundation/Foundation.h>",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <execinfo.h>",
        "__attribute__((noreturn)) static void unavailable(const char *s) {",
        'fprintf(stderr, "FACTORIO_PROBE_UNIMPLEMENTED: %s\\n", s); void *bt[32]; int n=backtrace(bt,32); backtrace_symbols_fd(bt,n,2); fflush(stderr); abort(); }',
    ]
    for name in classes:
        lines += [
            f"@interface {name}: NSObject @end",
            f"@implementation {name}",
            "- (void)doesNotRecognizeSelector:(SEL)s { unavailable(sel_getName(s)); }",
            "+ (void)doesNotRecognizeSelector:(SEL)s { unavailable(sel_getName(s)); }",
            "@end",
        ]
    for index, symbol in enumerate(sorted(missing)):
        if symbol.startswith("_OBJC_"):
            continue
        if symbol == "_NSApp":
            lines.append("id NSApp = nil;")
        elif symbol == "_NSAppKitVersionNumber":
            lines.append("double NSAppKitVersionNumber = 0;")
        elif (symbol.startswith("_k") and symbol[2:3].isupper()) or (
            symbol.startswith("_NS") and symbol != "_NSRectFill"
        ):
            lines.append(f'NSString * const {symbol[1:]} = @"{symbol[1:]}";')
        else:
            lines += [
                f'void probe_trap_{index}(void) __asm__("{symbol}");',
                f'void probe_trap_{index}(void) {{ unavailable("{symbol}"); }}',
            ]
    shim_source = directory / "ProbeShim.m"
    shim_source.write_text("\n".join(lines) + "\n")
    frameworks = app / "Frameworks"
    if frameworks.exists():
        shutil.rmtree(frameworks)
    frameworks.mkdir()
    library = frameworks / "ProbeShim.dylib"
    triple = "arm64-apple-ios26.0" + ("-simulator" if sdk == "iphonesimulator" else "")
    sdk_root = str(sdk_path(sdk))
    command = [
        "xcrun",
        "--sdk",
        sdk,
        "clang",
        "-target",
        triple,
        "-Werror=property-attribute-mismatch",
        "-Werror=objc-property-synthesis",
        "-isysroot",
        sdk_root,
        "-dynamiclib",
        "-fobjc-arc",
        str(shim_source),
        str(ROOT / "probe/PlatformFallbacks.m"),
        str(ROOT / "probe/BitmapCompat.m"),
        "-framework",
        "ImageIO",
        "-o",
        str(library),
        "-install_name",
        "@executable_path/Frameworks/ProbeShim.dylib",
        "-Wl,-reexport-lSystem",
        "-Wl,-reexport-lobjc",
        "-Wl,-reexport-lresolv",
    ]
    if uikit:
        main_offset = (
            next(
                item["address"]
                for item in audit["entrypoints"]
                if item["name"] == "_main"
            )
            - 0x100000000
        )
        command += [
            str(ROOT / "probe/UIKitEntry.m"),
            str(ROOT / "probe/MetalCompat.m"),
            str(ROOT / "probe/TouchControls.m"),
            "-I"
            + str(ROOT / f"build/vendor/SDL-release-{profile.sdl_version}/include"),
            f"-DORIGINAL_MAIN_OFFSET={main_offset}",
            f"-DFACTORIO_SDL_MAJOR={profile.sdl_major}",
            "-framework",
            "UIKit",
        ]
        sdl = frameworks / f"libSDL{profile.sdl_major}.dylib"
        release = SDL_RELEASES[profile.sdl_version]
        shutil.copyfile(sdl_build_path(profile, sdk) / release.library, sdl)
        subprocess.run(
            [
                "install_name_tool",
                "-id",
                f"@executable_path/Frameworks/{sdl.name}",
                str(sdl),
            ],
            check=True,
        )
        collisions = defined_objc_classes(source) & defined_objc_classes(sdl)
        if any(not name.startswith("SDL") for name in collisions):
            raise ValueError(f"Unexpected Objective-C class collisions: {collisions}")
        rename_objc_classes(sdl, {name: "FPI" + name[3:] for name in collisions})
        subprocess.run(
            ["codesign", "--force", "--sign", "-", str(sdl)],
            check=True,
            capture_output=True,
        )
        command += ["-Wl,-reexport_library," + str(sdl)]
    for item in audit["libraries"]:
        if ".framework/" in item["mobile"] and item["sdk_has_exports"]:
            command += ["-Wl,-reexport_framework," + Path(item["mobile"]).name]
    subprocess.run(command, check=True)
    if "NSColor" in defined_objc_classes(library):
        rename_objc_classes(library, {"NSColor": "FPColor"})
    subprocess.run(["codesign", "--force", "--sign", "-", str(library)], check=True)
    # Separate facades preserve the original dyld library ordinals.
    empty = directory / "Facade.c"
    empty.write_text("/* Reexports only. */\n")
    replacements = {}
    for index, item in enumerate(audit["libraries"]):
        if (
            ".framework/" not in item["original"]
            and "libsteam_api" not in item["original"]
        ):
            continue
        target = frameworks / f"P{index:02}.dylib"
        install = "@executable_path/Frameworks/" + target.name
        subprocess.run(
            [
                "xcrun",
                "--sdk",
                sdk,
                "clang",
                "-target",
                triple,
                "-isysroot",
                sdk_root,
                "-dynamiclib",
                str(empty),
                "-o",
                str(target),
                "-install_name",
                install,
                "-Wl,-reexport_library," + str(library),
                "-L" + str(frameworks),
            ],
            check=True,
        )
        subprocess.run(
            ["codesign", "--force", "--sign", "-", str(target)],
            check=True,
            capture_output=True,
        )
        replacements[item["original"]] = install
    return replacements


def main() -> None:
    """Generate a local app, its provenance manifest, and optional game assets."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--bundle-id", default=DEFAULT_BUNDLE_ID)
    parser.add_argument(
        "--shim", action="store_true", help="Add fail-fast diagnostic placeholders"
    )
    parser.add_argument(
        "--uikit",
        action="store_true",
        help="Use UIKit entry and the matching iOS SDL adapter",
    )
    parser.add_argument(
        "--simulator-metal",
        action="store_true",
        help="Simulator-only graphics diagnostic",
    )
    parser.add_argument(
        "--sdk", choices=["iphoneos", "iphonesimulator"], default="iphonesimulator"
    )
    parser.add_argument(
        "--bundle-data",
        action="store_true",
        help="Include the selected edition's game data",
    )
    args = parser.parse_args()
    if args.simulator_metal and args.sdk != "iphonesimulator":
        parser.error("--simulator-metal is forbidden in device builds")
    profile = source_profile(args.app)
    if args.shim or args.uikit:
        generate_audit(args.app, args.sdk)
    (ROOT / "reports").mkdir(exist_ok=True)
    app = ROOT / (
        "build/FactorioProbe.app"
        if args.sdk == "iphonesimulator"
        else "build/iphoneos/FactorioProbe.app"
    )
    app.mkdir(parents=True, exist_ok=True)
    binary = args.app / "Contents/MacOS/factorio"
    macho = MachO(binary)
    from audit import mobile_path

    replacements = {library: mobile_path(library) for library in macho.libraries}
    if args.shim or args.uikit:
        replacements.update(build_shim(app, binary, profile, args.uikit, args.sdk))
    macho.retarget(
        app / "FactorioProbe", 7 if args.sdk == "iphonesimulator" else 2, replacements
    )
    if args.uikit:
        entry = inject_entry(
            app / "FactorioProbe",
            app / f"Frameworks/libSDL{profile.sdl_major}.dylib",
            args.simulator_metal,
            profile,
        )
        (ROOT / f"reports/entrypoint-patch-{args.sdk}.json").write_text(
            json.dumps(entry, indent=2) + "\n"
        )
    info = {
        "CFBundleExecutable": "FactorioProbe",
        "CFBundleIdentifier": args.bundle_id,
        "CFBundleName": "Factorio Loader Probe",
        "CFBundleDisplayName": "Factorio Probe",
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
        "CFBundleShortVersionString": profile.version,
        "CFBundleSupportedPlatforms": [
            "iPhoneSimulator" if args.sdk == "iphonesimulator" else "iPhoneOS"
        ],
        "MinimumOSVersion": "26.0",
        "UIDeviceFamily": [2],
        "LSRequiresIPhoneOS": True,
        "UILaunchScreen": {},
        "FactorioSourceProfile": profile.key,
    }
    if args.uikit:
        info.update(
            {
                "UISupportedInterfaceOrientations": [
                    "UIInterfaceOrientationLandscapeLeft",
                    "UIInterfaceOrientationLandscapeRight",
                ],
                "UIApplicationSupportsIndirectInputEvents": True,
                "UIStatusBarHidden": True,
                "UIViewControllerBasedStatusBarAppearance": False,
                "UIRequiresFullScreen": True,
            }
        )
    (app / "Info.plist").write_bytes(plistlib.dumps(info))
    if args.bundle_data:
        sync_assets(args.app / "Contents/data", app / "data", profile.sha256)
    subprocess.run(["codesign", "--force", "--sign", "-", str(app)], check=True)
    logger.info("%s", app)


if __name__ == "__main__":
    main()
