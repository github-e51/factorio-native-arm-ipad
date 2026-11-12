# Factorio on iPad

## 日本語の準備手順

Factorio 2.1.24のSteam版Space Ageを、iPad用アプリとしてビルドできます。
2.0.77の通常版にも引き続き対応しています。
[iPadで動かすための準備](docs/IPAD_SETUP.ja.md) に、生成したアプリの場所、
インストール方法、検証結果、旧版へ戻す方法をまとめています。

Steamで最新版とSpace Ageを取得したあと、`uv sync --locked` と
`uv run python tools/setup.py --steam --preserve-source` を実行すると、検査したアプリを
`build/source/factorio-2.1.24-space-age.app` に保存してビルド元に設定します。
Steam側の更新後も、このコピーを使えます。対応する実行ファイルは
`tools/source_profiles.py` でSHA-256と版ごとのデータを固定しています。

Python環境の設定は `pyproject.toml` と `uv.lock` にあります。
`uv run pytest` で入力の検査とコピーの保存処理をテストできます。
Factorio本体と実機が必要な検証は、通常のテストには含みません。

2026年11月13日にXcode 27.0とiOS SDK 27.0で、2.1.24の開発用署名まで完了しました。
Mac版とシミュレーターで120回の更新後のチェックサムが一致し、5惑星の生成、
品質、宇宙プラットフォームの検証用シナリオも通っています。DLCを無効にした構成も
確認済みです。Pythonのテスト29件と変更したPythonファイルのruff・tyによる検査が
通っています。2.1.24での実機の描画、音声、タッチ操作は未検証です。

This repository builds a development-signed iPad app from your own macOS
installation of Factorio. Game simulation, graphics, audio, and saves then run
locally on the iPad. Playing requires no Mac or streaming connection; the Mac is
needed to build, install, and later renew the app's signing profile.

The repository includes porting code, touch controls, Xcode projects, and build
tools. Factorio itself, game assets, prebuilt apps, certificates, and saved games
are not included. This is not an official client from Wube Software.

## Requirements and tested configuration

| Component | Requirement / tested configuration |
|---|---|
| Mac | Apple Silicon; run Terminal natively as ARM64, not through Rosetta |
| Xcode | Full Xcode with iOS SDK 26 or newer; latest build verified: Xcode 27.0, SDK 27.0 |
| Python | 3.12 or newer; tested: 3.14 |
| CMake | Available in Terminal; setup saves its path for Xcode |
| iPad | iPadOS 26 or newer; graphics tested on an 11-inch iPad Pro M1, iPadOS 26.6.1 |
| Signing | Your own Apple Account in Xcode, a development team, and a paired iPad |
| Game | Factorio 2.0.77 base / build 84539, or 2.1.24 Space Age / build 87808; exact macOS Steam universal executables |

Other iPads and newer SDKs have not automatically been verified. The original
Metal renderer requires suitable BC texture support, among other capabilities.
The simulator cannot replace device testing: the tested simulator fails during
graphical startup on the BC3_RGBA pixel format. Small game simulation tests
already run there.

On the M1 iPad, testing covered the menu, tutorial, movement, inventory, mining
trees, text input, saving, and loading a saved game. Audio was confirmed on the
device. English on-screen controls and a visible touch cursor are included.
Physical keyboard and mouse support is connected through SDL but has not yet been
tested with real hardware. Large factories, the full range of building actions,
and long-term stability remain unverified. See [Architecture and limitations](docs/ARCHITECTURE.md).

## Prepare the repository and tools

Clone the repository, or download and extract its ZIP. In Terminal, change to the
folder containing this README and `FactorioProbe.xcodeproj`.
Run all commands below from that folder.

Open Xcode once, complete its setup, and install the iOS platform support.
Check your tools:

```sh
xcodebuild -version
xcrun --sdk iphoneos --show-sdk-version
python3 --version
cmake --version
```

If `xcodebuild` points only to Command Line Tools, select the full Xcode
installation under Xcode → Settings → Locations → Command Line Tools.
If you already use Homebrew, you can install uv and CMake with:

```sh
brew install uv cmake
```

The first build needs an internet connection to download PyYAML, SDL, and, if
necessary, Apple signing profiles. SDL 2.30.9 for 2.0.77 or SDL 3.4.14 for 2.1.24
is downloaded from the official SDL repository and checked against a pinned SHA-256 hash.

## Select your own Factorio app

You need a complete installation of an analyzed macOS game version.

| Executable | Exact SHA-256 |
|---|---|
| 2.0.77 base | `00b014d78df07e05ab1cee853904c8f7b3814ca652c043461a9d49fbad46cdf6` |
| 2.1.24 Space Age | `991c1182742f60cde97be2a412106670f73ba483fd1715a95e687b73c8b5250d` |

The hash applies to `factorio.app/Contents/MacOS/factorio`, not the app directory
or just its ARM64 slice. The version number alone is insufficient: other
distributions or executables that have been re-signed may differ.
A dSYM file is not required for this build; the necessary symbols are read from
the verified executable.

For the standard Steam installation, run:

```sh
uv run python tools/setup.py --steam --preserve-source
```

For a different installation location:

```sh
uv run python tools/setup.py --app "/path/to/your/factorio.app"
```

Setup checks the original hash, matching base-data version and tools, uses
`uv sync --locked` to prepare `.venv`, and writes local paths to `.local-config.json`.
That file is excluded by `.gitignore`. See also
[`local-config.example.json`](local-config.example.json).

For 2.1.24, select the public Steam branch and enable the Space Age DLC.
For the 2.0.77 baseline, select 2.0.77 in Betas and disable Space Age.
Wait for the complete download. Setup preserves the selected executable and all
edition-specific assets outside Steam's update directory. An unrecognized hash
requires a new analysis; keep the hash check enabled.
This project does not modify the original app.

## Set up the iPad and signing

1. Connect the iPad to the Mac over USB, unlock it, and accept the trust prompt.
   Xcode must recognize the device and finish preparing it.
2. On the iPad, enable Developer Mode under
   Settings → Privacy & Security → Developer Mode and confirm the requested
   restart. If the option is missing, pair the device with Xcode first.
3. Sign in with your own Apple Account under
   Xcode → Settings → Apple Accounts.

Apple documents these steps in
[Enabling Developer Mode](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device)
and [Running apps on devices](https://developer.apple.com/documentation/xcode/running-your-app-on-simulated-or-physical-devices).

```sh
open FactorioProbe.xcodeproj
```

In Xcode, open the FactorioProbe target. Under Signing & Capabilities,
enable Automatically manage signing and select your own Team.
If necessary, enter your own unique Bundle Identifier, such as
`com.yourname.factorioipad`. This identifier is also applied to the generated app.
At the top, select the FactorioProbe scheme and your connected physical iPad.

Xcode can also create a Personal Team. Check whether signing works with your own
account configuration and how long its profile remains valid; no one else's
profiles are supplied with this repository.
[Apple: Signing workflow](https://help.apple.com/xcode/mac/current/en.lproj/dev60b6fbbc7.html)

## Build and launch

In Xcode, choose Product → Run / ⌘R. The first build downloads and compiles
SDL, generates the import audit, adapts a copy of the original executable, and
bundles the selected edition's local game assets, including owned DLC. This takes time and several GB of free disk
space. Xcode then signs the app and libraries and installs them.

The build intentionally uses a shell script phase: Xcode first compiles a small
placeholder, which is then replaced by the locally generated game executable.
Edit files in `probe/` directly; you do not need to add them separately to
“Compile Sources.”

The initial graphical startup took about 20–30 seconds on the tested device.
Dismiss the Steam unavailable message with Confirm; Steam login and Steam
features are unavailable. Close the changelog if it appears. Then start a
tutorial or a base-game session from the main menu.

Once installed, Factorio Probe can be opened directly on the iPad, and you can
disconnect the USB cable. Normal play does not require the XCTest helper.
Automatic crash-log uploading is disabled in the local build.

## Alternative: Build and install from Terminal

After setup, device pairing, and configuring your Xcode account, replace the
example values below with your own. The team ID must identify your signing team;
the bundle ID must match your intended app.

```sh
export FACTORIO_TEAM_ID="YOUR_TEAM_ID"
export FACTORIO_BUNDLE_ID="com.yourname.factorioipad"

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
```

The installable product is generated at
`build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app`.
`build/iphoneos/FactorioProbe.app` is only ad hoc signed and cannot be installed
directly on the iPad.

Verify the signature, game binary sections, and identifier:

```sh
.venv/bin/python tools/verify.py \
  --signed-app build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app \
  --bundle-id "$FACTORIO_BUNDLE_ID"
```

List devices and enter your iPad's identifier:

```sh
xcrun devicectl list devices
export FACTORIO_DEVICE_ID="YOUR_IPAD_IDENTIFIER"

xcrun devicectl device install app \
  --device "$FACTORIO_DEVICE_ID" \
  build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app

xcrun devicectl device process launch \
  --device "$FACTORIO_DEVICE_ID" "$FACTORIO_BUNDLE_ID"
```

This installation replaces an existing app with the same identifier. Save your
current game before updating. Keep the same bundle ID for future updates so that
the same app and its existing data are updated.

## Touch controls and hardware input

| Control | Function |
|---|---|
| Stick at the bottom left | WASD movement, including diagonals |
| Inventory / Rotate / Clear / pick | E / R / Q: inventory, rotate, clear cursor or pick an entity with the pipette |
| Map / Research / Tab | M / T / Tab; Tab also acknowledges the corresponding tutorial prompt |
| Pick up / Shoot / Menu | F / Space / Escape |
| + / − / Enter | Zoom through mouse-wheel events / confirm |
| Shift / Ctrl / Alt | Toggle modifiers on; tap again to release |
| Left click / Middle click / Right click | Grouped on the bottom row: left, middle, and right mouse buttons |
| Keyboard | Additional on-screen keyboard with letters, numbers, and special keys |
| Hide controls / Show controls | Hide or show the on-screen controls |

The mode button at the top cycles through:

- Tap: Touching the screen clicks directly. Use this for normal menu interaction.
- Mine: Holding a finger on a tree or ore acts as holding the right mouse
  button. Switch back to Tap for menus.
- Cursor: Touch positions a visible white arrow without clicking. Then press
  one of the three mouse buttons. The arrow tip marks the click position. To drag,
  hold a mouse button and slide a second finger across the game area. Building
  actions involving multiple fingers still need further device testing.

Left click is used for actions such as selecting and placing; Right click for
mining and other inventory actions; Middle click for actions such as setting
inventory filters. The exact effect depends on the game context and key bindings.
Separate mouse buttons are not needed for ordinary tapping.

Connect an external keyboard and mouse directly to the iPad and select
Hide controls. SDL includes hardware keyboard, mouse movement, mouse button,
and scrolling support, but the complete hardware workflow remains untested.
Controllers are currently disabled.

## Saves, updates, and renewing signing

Saves are stored inside the iPad app at `Documents/Factorio/user/saves`, and the
configuration is stored at `Documents/Factorio/config.ini`. After an update,
container-dependent data paths are adjusted at startup.

Using your device and bundle IDs set above, you can back up saves to the Mac
before an update. Choose a new destination folder for each backup:

```sh
xcrun devicectl device copy from \
  --device "$FACTORIO_DEVICE_ID" \
  --domain-type appDataContainer \
  --domain-identifier "$FACTORIO_BUNDLE_ID" \
  --source Documents/Factorio/user/saves \
  --destination build/save-backup-01
```

Signing validity depends on your own development profile. When it expires,
rebuild and reinstall using your own team. Do not delete the app for
troubleshooting before backing up saves: uninstalling removes its local data.
A Steam update does not affect the source preserved by setup. An unpreserved
Steam source may fail the next build's hash check after an update. An installed
iPad app contains its own copy of the assets. Keep separate backups before
migrating saves from 2.0 to 2.1; 2.1 saves cannot be downgraded to 2.0.

## Troubleshooting

| Problem | Next step |
|---|---|
| Original hash does not match | Provide your own exact supported game version; do not bypass the version check |
| `.venv/bin/python` is missing | Run `python3 tools/setup.py` in the repository |
| `cmake` is missing only in Xcode | Rerun setup in Terminal; it saves the absolute CMake path locally |
| Download or SDL hash check fails | Check the connection; remove only `build/vendor/SDL-2.30.9.tar.gz` and rebuild; keep hash verification enabled |
| `Signing requires a development team` | Select your team, automatic signing, and your own bundle ID in Signing & Capabilities |
| iPad is unavailable | Check that it is unlocked, USB trust is granted, Developer Mode is enabled, and Xcode has finished preparing it |
| App is reported as untrusted | First check the signature with `codesign --verify --deep --strict`; use fresh DerivedData for a broken build; if the signature is valid, follow the specific Xcode/iPad prompt |
| Menus respond incorrectly | Switch to Tap; temporarily use Hide controls if buttons are obscured |
| Simulator fails on BC3 / pixel format 134 | Known graphics limitation; test on a supported physical iPad |
| `FACTORIO_PROBE_UNIMPLEMENTED` / crash | An unimplemented platform call was reached; save the log. The port does not cover every macOS function |

Build details are available in Xcode's build log and locally in
`reports/sdl3-iphoneos-configure.log` and `reports/sdl3-iphoneos-build.log`.
Copy the current game log with:

```sh
xcrun devicectl device copy from \
  --device "$FACTORIO_DEVICE_ID" \
  --domain-type appDataContainer \
  --domain-identifier "$FACTORIO_BUNDLE_ID" \
  --source Documents/Factorio/user/factorio-current.log \
  --destination reports/ipad-current.log
```

Logs contain local paths and device details. Review relevant excerpts before
sharing them. More diagnostic commands: [Development and testing](docs/DEVELOPMENT.md).

## What belongs in the GitHub repository?

Upload this folder's contents, including `.gitignore`. Files under `probe/`,
`tools/`, `tests/`, and `docs/`, together with the shared Xcode projects, are the
required sources. A build does not generate any additional files that need to be
committed for another user.

`build/`, `reports/`, `.venv/`, `.local-config.json`, signed apps, game archives,
certificates, and Xcode user settings are excluded. Do not upload these manually
through GitHub's web interface either: `.gitignore` does not protect against
explicitly selecting files there. The other person runs their own setup with
their own game installation and signing configuration.

Porting code and documentation: [MIT License](LICENSE).
Factorio, SDL, and other components: [Scope and notices](THIRD_PARTY_NOTICES.md).
