"""Compile the pinned SDL ABI required by the selected analyzed game build."""

import argparse
import hashlib
import logging
import subprocess
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from config import CMAKE, DEFAULT_APP, ROOT, source_profile
from source_profiles import SourceProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SDLRelease:
    """Pin source archive contents and the CMake shared-library target."""

    version: str
    sha256: str
    target: str
    library: str


SDL_RELEASES = {
    "3.4.14": SDLRelease(
        "3.4.14",
        "9d57b178fb297e121ef2605275937b7afaa7cd24d99ce1f95953e69e7a2535d6",
        "SDL3-shared",
        "libSDL3.0.dylib",
    ),
    "2.30.9": SDLRelease(
        "2.30.9",
        "682a055004081e37d81a7d4ce546c3ee3ef2e0e6a675ed2651e430ccd14eb407",
        "SDL2",
        "libSDL2-2.0.0.dylib",
    ),
}


def sdl_build_path(profile: SourceProfile, sdk: str) -> Path:
    """Keep SDL 2 and SDL 3 outputs separate for both Apple platforms."""
    platform = "simulator" if sdk == "iphonesimulator" else "iphoneos"
    prefix = "sdl" if profile.sdl_major == 2 else f"sdl{profile.sdl_major}"
    return ROOT / "build" / f"{prefix}-{platform}"


def prepare_sdl(profile: SourceProfile, sdk: str) -> Path:
    """Verify an upstream archive and compile the matching local input adapter."""
    release = SDL_RELEASES[profile.sdl_version]
    (ROOT / "reports").mkdir(exist_ok=True)
    vendor = ROOT / "build/vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    archive = vendor / f"SDL-{release.version}.tar.gz"
    if not archive.exists():
        url = f"https://github.com/libsdl-org/SDL/archive/refs/tags/release-{release.version}.tar.gz"
        urllib.request.urlretrieve(url, archive)
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != release.sha256:
            raise ValueError("SDL archive checksum mismatch")
    source = vendor / f"SDL-release-{release.version}"
    with tarfile.open(archive) as tar:
        if not source.exists():
            tar.extractall(vendor, filter="data")
        member = tar.extractfile(f"{source.name}/CMakeLists.txt")
        if member is None:
            raise ValueError("SDL archive has no CMakeLists.txt")
        upstream = member.read().decode()
    adapter = "SDLInputBridge.c" if profile.sdl_major == 2 else "SDLInputBridge3.c"
    cmake = upstream + "\n# Local iPad input adapter\n"
    cmake += f'target_sources({release.target} PRIVATE "{ROOT}/probe/{adapter}")\n'
    cmake += f'target_include_directories({release.target} PRIVATE "{source}/src")\n'
    cmake_file = source / "CMakeLists.txt"
    if cmake_file.read_text() != cmake:
        cmake_file.write_text(cmake)
    build = sdl_build_path(profile, sdk)
    stem = f"sdl{profile.sdl_major}-{sdk}"
    with (ROOT / f"reports/{stem}-configure.log").open("w") as log:
        subprocess.run(
            [
                CMAKE,
                "-S",
                str(source),
                "-B",
                str(build),
                "-DCMAKE_SYSTEM_NAME=iOS",
                "-DCMAKE_OSX_SYSROOT=" + sdk,
                "-DCMAKE_OSX_ARCHITECTURES=arm64",
                "-DCMAKE_OSX_DEPLOYMENT_TARGET=26.0",
                "-DSDL_SHARED=ON",
                "-DSDL_STATIC=OFF",
                "-DSDL_TEST=OFF",
                "-DSDL_TESTS=OFF",
                "-DCMAKE_BUILD_TYPE=Release",
            ],
            check=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    with (ROOT / f"reports/{stem}-build.log").open("w") as log:
        subprocess.run(
            [CMAKE, "--build", str(build), "-j", "8"],
            check=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    return build / release.library


def main() -> None:
    """Prepare the selected game's SDL without changing the original installation."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sdk", choices=["iphoneos", "iphonesimulator"], default="iphonesimulator"
    )
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    args = parser.parse_args()
    logger.info("%s", prepare_sdl(source_profile(args.app), args.sdk))


if __name__ == "__main__":
    main()
