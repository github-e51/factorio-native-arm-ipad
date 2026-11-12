"""Pin each analyzed executable to its assets, SDL ABI, and instruction patches."""

from dataclasses import dataclass


@dataclass(frozen=True)
class InstructionPatch:
    """Describe an instruction change relative to one named function."""

    symbol: str
    offset: int
    original: bytes
    replacement: bytes


@dataclass(frozen=True)
class SourceProfile:
    """Identify one exact game build rather than accepting a version label alone."""

    key: str
    version: str
    edition: str
    sha256: str
    sdl_version: str
    mods: tuple[tuple[str, str | None], ...]
    display_patch: InstructionPatch | None
    simulator_metal_patch: InstructionPatch | None

    @property
    def sdl_major(self) -> int:
        """Return the SDL ABI major used by this game executable."""
        return int(self.sdl_version.split(".")[0])


BASE_2077 = SourceProfile(
    key="2.0.77-base",
    version="2.0.77",
    edition="base",
    sha256="00b014d78df07e05ab1cee853904c8f7b3814ca652c043461a9d49fbad46cdf6",
    sdl_version="2.30.9",
    mods=(("base", "2.0.77"), ("core", None)),
    display_patch=InstructionPatch(
        symbol="__ZN9SDLWindow18logDisplayAdaptersEv",
        offset=424,
        original=bytes.fromhex("e00314aa"),
        replacement=bytes.fromhex("daffff17"),
    ),
    simulator_metal_patch=InstructionPatch(
        symbol="__ZN22GraphicsInterfaceMetal15createMTLDeviceEb",
        offset=44,
        original=bytes.fromhex("e8630091"),
        replacement=bytes.fromhex("4f000014"),
    ),
)

SPACE_2124 = SourceProfile(
    key="2.1.24-space-age",
    version="2.1.24",
    edition="space-age",
    sha256="991c1182742f60cde97be2a412106670f73ba483fd1715a95e687b73c8b5250d",
    sdl_version="3.4.14",
    mods=(
        ("base", "2.1.24"),
        ("core", None),
        ("space-age", "2.1.24"),
        ("elevated-rails", "2.1.24"),
        ("quality", "2.1.24"),
        ("recycler", "2.1.24"),
    ),
    # SDLWindow::logDisplays uses public SDL 3 APIs; there is no raw macOS
    # display-driver suffix to skip in this build.
    display_patch=None,
    simulator_metal_patch=None,
)

SOURCE_PROFILES = {profile.sha256: profile for profile in (BASE_2077, SPACE_2124)}
