# Development

This page is for working on the port itself. To just install the game, use the
[install guide](INSTALL.md). How the port works is described in
[Architecture](ARCHITECTURE.md). Run all commands from the repository root.

## Tools

| | |
|---|---|
| Mac | Apple Silicon, with Terminal running natively (not under Rosetta) |
| Xcode | iOS SDK 26 or newer; **Xcode 27.2 or later** for iPhone Duo |
| Python | 3.12 or newer (tested: 3.14) |
| CMake | In `PATH` when running setup; setup saves its absolute path for Xcode |

```sh
xcodebuild -version
xcrun --sdk iphoneos --show-sdk-version
python3 --version
cmake --version
brew install python cmake   # if missing
```

If `xcodebuild` points only to the Command Line Tools, select the full Xcode
under **Xcode → Settings → Locations → Command Line Tools**, or set
`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer` for the session.

The first build needs an internet connection to download PyYAML, SDL, and, if
necessary, Apple signing profiles. SDL 3.4.14 (for Factorio 2.1.23) or SDL 2.30.9
(for 2.0.77) comes from the official SDL repository and is checked against a
pinned SHA-256 hash.

## Supported game executables

The hash is of `factorio.app/Contents/MacOS/factorio`, the whole universal
executable, not the app folder or only its ARM64 slice. A matching version
number alone isn't enough: other distributions or re-signed executables differ.
No dSYM is needed; the required symbols are read from the verified executable.

| Version | SHA-256 | Status |
|---|---|---|
| **2.1.23**, build 87750, Steam | `42218e9676f36687282800e5b6336b049c0f0e45f0f71eb20f90c49ccdec4359` | iPhone Duo and iPad. SDL 3.4.14, 1,269 SDL redirects. 120-update Space Age probe: `4032494708` on Mac, Duo simulator and physical Duo |
| 2.0.77, build 84539 | `00b014d78df07e05ab1cee853904c8f7b3814ca652c043461a9d49fbad46cdf6` | Upstream-tested on iPad. SDL 2.30.9, 817 SDL redirects. Base-game probe: `2892897386` |
| 2.0.77, build 84539, Steam | `90e2ebfdb5fd8b3966915f704a0ae99177c2af64ed9267c634ced42bff36d820` | Experimental. Built with Xcode 27 and rendered the Space Age main menu on an M1 iPad Pro (iPadOS 27); Space Age probe: `2376201887` |

Setup checks the entry point, SDL version and unused Mach-O space before
patching a copy; the original game is never modified. The build records the
source hash, and verification rejects an app built from a different source.
Every other hash is rejected. **Do not remove the hash check:** the patches are
specific to these executables, and another version needs a new analysis.

```sh
python3 tools/setup.py                                  # standard Steam location
python3 tools/setup.py --app "/path/to/your/factorio.app"
```

Setup creates `.venv`, installs the pinned Python dependency, and writes local
paths to the ignored `.local-config.json` (see
[`local-config.example.json`](../local-config.example.json)). The installer adds
the chosen `device_id`, `team_id` and `bundle_id` to the same file.

## Building and installing

### With the installer

`Install Factorio.command` prepares Xcode, Python and CMake, runs setup, and then
runs `tools/install.py`, which picks the device, team and bundle ID, builds with
`xcodebuild`, installs, and launches. After setup you can run it directly:

```sh
.venv/bin/python tools/install.py                       # remembered settings
.venv/bin/python tools/install.py --bundle-id com.example.factorio --no-launch
```

The build log is `reports/install-build.log`.

### With Xcode

1. `open FactorioProbe.xcodeproj`
2. In the **FactorioProbe** target's **Signing & Capabilities**, enable
   **Automatically manage signing**, select your **Team**, and enter a unique
   **Bundle Identifier** such as `com.yourname.factorio`. The identifier is also
   applied to the generated app.
3. Select the **FactorioProbe** scheme and your connected **physical device**.
   For iPhone Duo, unfold it first.
4. **Product → Run** (⌘R).

The first build downloads and compiles SDL, generates the import audit, adapts a
copy of the original executable, and bundles the local game data, including
installed expansions. It takes time and several GB of disk. The build uses a
shell-script phase: Xcode compiles a small placeholder, which is then replaced by
the generated game executable (`tools/xcode_build.sh`). Edit files in `probe/`
directly; you don't need to add them to **Compile Sources**.

### From Terminal

```sh
export FACTORIO_TEAM_ID="YOUR_TEAM_ID"
export FACTORIO_BUNDLE_ID="com.yourname.factorio"

xcodebuild \
  -project FactorioProbe.xcodeproj \
  -scheme FactorioProbe \
  -configuration Debug \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath build/Xcode \
  DEVELOPMENT_TEAM="$FACTORIO_TEAM_ID" \
  PRODUCT_BUNDLE_IDENTIFIER="$FACTORIO_BUNDLE_ID" \
  -allowProvisioningUpdates build

.venv/bin/python tools/verify.py \
  --signed-app build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app \
  --bundle-id "$FACTORIO_BUNDLE_ID"

xcrun devicectl list devices
export FACTORIO_DEVICE_ID="YOUR_DEVICE_IDENTIFIER"
xcrun devicectl device install app --device "$FACTORIO_DEVICE_ID" \
  build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app
xcrun devicectl device process launch --device "$FACTORIO_DEVICE_ID" "$FACTORIO_BUNDLE_ID"
```

The installable product is
`build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app`.
`build/iphoneos/FactorioProbe.app` is only ad hoc signed and can't be installed
on a physical device. Installing replaces an existing app with the same bundle
ID; keep the same ID so the app's saves are kept.

### App data

Saves are in the app container at `Documents/Factorio/user/saves`, and the
configuration at `Documents/Factorio/config.ini`; container-dependent paths are
adjusted at startup. Back up saves and copy the current log with:

```sh
xcrun devicectl device copy from --device "$FACTORIO_DEVICE_ID" \
  --domain-type appDataContainer --domain-identifier "$FACTORIO_BUNDLE_ID" \
  --source Documents/Factorio/user/saves --destination build/save-backup-01

xcrun devicectl device copy from --device "$FACTORIO_DEVICE_ID" \
  --domain-type appDataContainer --domain-identifier "$FACTORIO_BUNDLE_ID" \
  --source Documents/Factorio/user/factorio-current.log --destination reports/device-current.log
```

Logs contain local paths and device details; review them before sharing.

## Check a build without Xcode signing

```sh
.venv/bin/python tools/prepare_sdl.py --sdk iphoneos
.venv/bin/python tools/build_probe.py --sdk iphoneos --uikit --bundle-data
.venv/bin/python tools/verify.py
```

`build_probe.py` generates its own audit from the selected original executable
and the installed SDK. No pre-generated reports are required. The resulting app
bundle is ad hoc signed and intended for local analysis. Installing it on a
physical iPhone or iPad still requires Xcode development signing.

`verify.py` checks the original hash, the recorded original bytes of all
instruction patches, unchanged file-backed original sections after reversing
those patches, platforms, and signatures. Game simulation is checked only when
you explicitly provide your own benchmark log. These checks do not replace a
graphical device test.

## Small simulation probe on a device

Save your game before terminating a running app. Set `FACTORIO_DEVICE_ID` and
`FACTORIO_BUNDLE_ID` as in [From Terminal](#from-terminal); the development-signed app must
already be installed.

```sh
mkdir -p reports
xcrun devicectl device process launch \
  --device "$FACTORIO_DEVICE_ID" --terminate-existing --console --timeout 120 \
  "$FACTORIO_BUNDLE_ID" --probe-core > reports/core-ipad.log 2>&1

xcrun devicectl device process launch \
  --device "$FACTORIO_DEVICE_ID" --terminate-existing --console --timeout 120 \
  "$FACTORIO_BUNDLE_ID" --probe-benchmark > reports/benchmark-ipad.log 2>&1

.venv/bin/python tools/verify.py --benchmark-log reports/benchmark-ipad.log
```

The first probe creates `Documents/Factorio/user/probe-map.zip` in the app
container; the second simulates that exact small map for 120 updates. Expected
output includes `Performed 120 updates`, a checksum, and `Goodbye`. For the
Factorio 2.1.23 Space Age installation tested on the iPhone Duo, the checksum
is `4032494708`; this matched the original Mac game and the simulator.
The probe does not overwrite normal saved games; running the first probe again
replaces `probe-map.zip`.

This local build retains the owned Space Age, Quality, and Elevated Rails assets
when present in the source installation. With all three expansion mods enabled,
the original macOS 2.0.77 executable produced checksum `2376201887` on the same
64 × 64, seed 12345, 120-update probe on October 7, 2026. For an iPad probe with
the same mods, explicitly compare against that native baseline:

```sh
.venv/bin/python tools/verify.py --benchmark-log reports/benchmark-ipad.log \
  --benchmark-checksum 2376201887
```

For 2.1.23 Space Age, use `--benchmark-checksum 4032494708` instead. The default
checksum remains the upstream 2.0.77 base-game value. A matching small
simulation does not establish graphical or full Space Age gameplay compatibility.
The local iPad run on October 7, 2026 matched `2376201887`, and a separate
graphical run reached the Space Age main menu after about 72 seconds. This does
not test large saves, progression through the expansion planets, or multiplayer.

Launching without arguments starts the normal game again. If you run these
probes through an Xcode scheme instead of the CLI, remove the launch arguments
afterward.

## Device screenshots / UIKit test helper

`tools/device_ui.py` builds and installs a separate XCTest helper. It is optional
and is not required for playing. Here, `--device` expects the **UDID from Xcode's
device view**, which may differ from the CoreDevice identifier used by
`devicectl`. Substitute your own values:

```sh
.venv/bin/python tools/device_ui.py \
  --device "YOUR_IPAD_UDID" \
  --team "$FACTORIO_TEAM_ID" \
  --bundle-id "$FACTORIO_BUNDLE_ID"
```

This command activates the installed app and exports screenshots to
`reports/DeviceUI-…/`. Use `--button 'Inventory'`, `--key Tab`, and
`--tap 0.5 0.4` for targeted actions. To run multiple actions in a specified
order, pass a JSON array to `--actions`; example entries include
`{"button":"Menu"}` and `{"x":0.5,"y":0.4}`. These actions affect the running
game. Screenshot tests check only that the app is in the foreground; assess the
actual game response by inspecting the images.

On the iPhone Duo, XCTest may capture its primary/outer display instead of the
active inner game display. For Duo graphics checks, use the
[inner-display screenshot procedure](IPHONE_DUO.md#checking-the-display-developers).

The helper uses fresh DerivedData for each run. This avoids an issue observed
in the original project where a reused test runner had inconsistent signatures.
To remove only this helper:

```sh
xcrun devicectl device uninstall app \
  --device "$FACTORIO_DEVICE_ID" local.factorio.probesnapshot.xctrunner
```

## Simulator checks

### iPhone Duo simulator checks

The iPhone Duo simulator profile needs **Xcode 27.2 or later**, even though the
Duo shipped with iOS 27.1; an iOS 27.0 runtime cannot boot it. If multiple Xcode versions are
installed, set `DEVELOPER_DIR` to the desired app's `Contents/Developer` directory.
Use `xcrun simctl list devices available` to obtain the simulator UDID.

Build the universal simulator app with the same source game and expansion assets:

```sh
.venv/bin/python tools/prepare_sdl.py --sdk iphonesimulator
.venv/bin/python tools/build_probe.py --sdk iphonesimulator --uikit --bundle-data \
  --bundle-id "$FACTORIO_BUNDLE_ID"
.venv/bin/python tools/verify.py --sdk iphonesimulator
xcrun simctl install "$FACTORIO_SIMULATOR_ID" build/FactorioProbe.app
xcrun simctl launch --console "$FACTORIO_SIMULATOR_ID" "$FACTORIO_BUNDLE_ID" --probe-core
xcrun simctl launch --console "$FACTORIO_SIMULATOR_ID" "$FACTORIO_BUNDLE_ID" --probe-benchmark
```

The separate UIKit control harness exercises the production `TouchControls.m`
without loading the game renderer. It checks safe-area bounds, control overlaps,
keyboard bounds/visibility, the portrait control deck and the game-view space it
reserves, cursor coordinates after resizing, hardware-cursor drawing, release of
held input, and that a mouse button remains down until touch-up.
SDL input endpoints are recording sinks in this harness; it does not
prove in-game input integration or graphical gameplay.

```sh
.venv/bin/python tools/test_touch_controls.py --device "$FACTORIO_SIMULATOR_ID"
```

Results and rendered control screenshots are copied to `reports/touch-controls/`.
Nine cases pass on the iPhone Duo / iOS 27.1 simulator: eight representative
window sizes, including the inner display in landscape and portrait, and the
simulator's actual window/safe area.
The 2.0.77 Space Age map creation and 120-update probe also passed, matching the
Mac and physical iPad checksum **2376201887**. A 2.1.23 Space Age probe matched
the Mac and physical iPhone checksum **4032494708**. Simulator timing is not a
phone performance measurement: the simulator uses the Mac's resources.

Normal graphical startup currently fails: the simulated Metal device reports
no Mac1/Apple7 GPU-family support and no BC texture compression, and the game's
OpenGL fallback cannot create its context. Physical iPhone graphics, complete
gameplay and live fold/unfold transitions remain unverified. The physical Duo
rendered both the Space Age main menu and an early tutorial scene on its
2853 × 2007 inner display, with the bottom HUD visible. SDL must use the active
window scene's orientation during later frame updates; the global status-bar
orientation can be unknown and crop the view to 669 points wide. Capture the
inner display with `xcrun devicectl device capture screenshot` and run
`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift tests/check_duo_viewport.swift <screenshot.png>`
to detect the black right-edge regression. The existing
`--simulator-metal` option is diagnostic only and is forbidden for device builds.
That diagnostic reached Metal initialization on the Duo simulator, then failed
texture validation for pixel format 134 (`BC3_RGBA`), confirming the simulator's
graphics limitation. The standard build does not include this diagnostic bypass.

On the physical Duo, the inset build leaves the UIWindow at 951 × 669 points.
The game view uses the larger of the system safe area and 16 points at the top
and sides, with a fixed 16-point bottom margin matching the Duo's top margin.
The tested landscape game view is 919 × 637 points / 2757 × 1911 pixels.
Capture a game screen and run
`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift tests/check_duo_safe_viewport.swift <screenshot.png>`
to check that game pixels no longer reach the unsafe side and bottom edges.

### Other simulator CLI probes

Start an iPad simulator in Xcode. If several simulators are running, use the
appropriate identifier from `xcrun simctl list devices` instead of `booted`.
These instructions use the default bundle identifier `local.factorio.loaderprobe`:

```sh
.venv/bin/python tools/prepare_sdl.py --sdk iphonesimulator
.venv/bin/python tools/build_probe.py --sdk iphonesimulator --uikit --bundle-data
xcrun simctl install booted build/FactorioProbe.app
.venv/bin/python tools/run_probe.py create --device booted
.venv/bin/python tools/run_probe.py benchmark --device booted
.venv/bin/python tools/verify.py --sdk iphonesimulator \
  --benchmark-log reports/benchmark-simulator.log
```

The runner script creates its own diagnostic configuration and `probe-map.zip`
in the simulator; it is not intended to manage a normal simulator game session.
For a custom identifier, pass `--bundle-id` to both `build_probe.py` and
`run_probe.py`. See [Architecture](ARCHITECTURE.md) for the known simulator
graphics limitation.

## Local source compatibility tests

The Python tests do not contain or download game files. To check the experimental
variant against your own installation, including rejecting altered patch layouts:

```sh
FACTORIO_TEST_APP="$HOME/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app" \
  .venv/bin/python -m unittest discover -s tests -v
```

Without `FACTORIO_TEST_APP`, checks requiring the game are explicitly skipped.
These checks do not replace `tools/verify.py`, simulation, or physical iPad tests.
Builds made before source hashes were added to patch manifests must be rebuilt
before using the updated verifier.

The SDK audit accepts Xcode 27's `arm64e-ios` and `arm64e.x1-ios` system-library
exports as well as the earlier `arm64-ios` exports. Catalyst and macOS exports
remain excluded. Small standalone TBD fixtures test that discovery and library
reexports without requiring an installed SDK.

## Troubleshooting

| Problem | Next step |
|---|---|
| Original hash doesn't match | Provide your own exact supported game version; don't bypass the check |
| `.venv/bin/python` is missing | Run `python3 tools/setup.py` |
| `cmake` is missing only in Xcode | Rerun setup in Terminal; it saves the absolute CMake path |
| Download or SDL hash check fails | Check the connection; remove only the downloaded SDL archive under `build/vendor/` and rebuild; keep hash verification on |
| `Signing requires a development team` | Select your team, automatic signing, and your own bundle ID |
| Device is unavailable | Unlocked, USB trust granted, Developer Mode on, and Xcode finished preparing it |
| App reported as untrusted | Check the signature with `codesign --verify --deep --strict`; use fresh DerivedData for a broken build; otherwise trust the developer on the device |
| Menus respond incorrectly | Switch to Tap mode; hide the controls if buttons are in the way |
| Duo simulator fails on BC3 / pixel format 134 | Known simulator graphics limitation; use a physical device |
| `FACTORIO_PROBE_UNIMPLEMENTED` / crash | An unimplemented platform call was reached; save the log. The port doesn't cover every macOS function |

Build details are in Xcode's build log, `reports/install-build.log`, and
`reports/sdl-configure-iphoneos.log` / `reports/sdl-build-iphoneos.log`.

## Before committing

`build/`, `reports/`, `.venv/`, `.local-config.json`, signed apps, game files,
certificates and Xcode user settings are ignored. Use
`git status --short --ignored` to see what is excluded and check
`git diff --cached --stat` before committing. Don't add those files through
GitHub's web upload either; `.gitignore` doesn't protect files you select there.
A fresh checkout must be able to generate everything locally.

No CI, release upload, or download of Factorio is configured. The build reads
only your local installation and downloads only the pinned SDL release.
