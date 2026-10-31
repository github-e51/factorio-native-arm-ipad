# Scope and third-party notices

The MIT License of this repository covers the porting code, build tools and
documentation it contains. It grants no rights to Factorio, its executables,
graphics, audio, game data or trademarks.

Factorio and its data are not part of this repository. The build reads your own
local macOS installation and produces local build products only. The original
licence files are kept when the game data is copied. The generated apps and game
archives are not among the files meant for upload.

SDL 2.30.9 or SDL 3.4.14, matching the Factorio version, is downloaded from the
official SDL repository during the first build. SDL is under the zlib licence;
its LICENSE.txt stays in the locally unpacked source under
`build/vendor/SDL-release-2.30.9` or `build/vendor/SDL-release-3.4.14`. The
project adds `probe/SDLInputBridge.c` to the SDL CMake target. For SDL 3.4.14 the
build also adjusts the UIKit window setup so that the iPhone Duo's active inner
display sets the window size, orientation and input focus, insets the game view
on phones, and reserves space below it for the portrait control deck. These local
changes are applied by `tools/prepare_sdl.py` and are not part of the official
SDL release.

Python/PyYAML, CMake, Homebrew and the Apple SDKs are used locally and are not
shipped with this repository. Their own licence terms apply.

This project is an independent, experimental port and not an official iPhone or
iPad client from Wube Software.
