# Development and local checks

## 2.1.24の処理を検証する

最新版の検証は、起動済みのシミュレーターに対応するアプリを入れてから実行します。

```sh
uv run python tools/prepare_sdl.py --sdk iphonesimulator
uv run python tools/build_probe.py --sdk iphonesimulator --uikit --bundle-data
xcrun simctl install booted build/FactorioProbe.app
uv run python tools/check_simulation.py --mode space-age --simulator booted
uv run python tools/check_simulation.py --mode base --simulator booted
```

Mac版で作ったセーブをシミュレーターにコピーし、同じ構成で120回更新します。
Space Ageでは `tests/scenarios/space-age/control.lua` を使い、5惑星、品質、
宇宙プラットフォームも確認します。検証のために通常のセーブを開く処理はありません。
結果は `reports/simulation-*.json`、実行の記録は同じ名前の `.log` に残ります。

2.1.24でベンチマークのログを `tools/verify.py` に渡す場合は、同じ版とMOD構成の
Mac版のログも `--reference-benchmark-log` で指定します。以下にある固定の
チェックサム `2892897386` を使う手順は、2.0.77の通常版向けです。

ビルド前の検査、署名、生成したアプリの場所は
[日本語の準備手順](IPAD_SETUP.ja.md) を参照してください。

First complete setup and a device build as described in the [README](../README.md).
Run all commands here from the repository root.

## Check a build without Xcode signing

```sh
.venv/bin/python tools/prepare_sdl.py --sdk iphoneos
.venv/bin/python tools/build_probe.py --sdk iphoneos --uikit --bundle-data
.venv/bin/python tools/verify.py
```

`build_probe.py` generates its own audit from the selected original executable
and the installed SDK. No pre-generated reports are required. The resulting app
bundle is ad hoc signed and intended for local analysis. Installing it on an
iPad still requires Xcode development signing.

`verify.py` checks the original hash, the recorded original bytes of all
instruction patches, unchanged file-backed original sections after reversing
those patches, platforms, and signatures. Game simulation is checked only when
you explicitly provide your own benchmark log. These checks do not replace a
graphical device test.

## Small simulation probe on the iPad

Save your game before terminating a running app. Set `FACTORIO_DEVICE_ID` and
`FACTORIO_BUNDLE_ID` as described in the README; the development-signed app must
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
output includes `Performed 120 updates`, checksum `2892897386`, and `Goodbye`.
The probe does not overwrite normal saved games; running the first probe again
replaces `probe-map.zip`.

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

The helper uses fresh DerivedData for each run. This avoids an issue observed
in the original project where a reused test runner had inconsistent signatures.
To remove only this helper:

```sh
xcrun devicectl device uninstall app \
  --device "$FACTORIO_DEVICE_ID" local.factorio.probesnapshot.xctrunner
```

## Simulator CLI (optional)

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

## Check the repository before uploading

After a local `git init`, use `git status --short --ignored` to see which files
are excluded. Check `git diff --cached --stat` before committing. Generated
copies of the original executable, SDL downloads, game assets, diagnostic
reports, and local signing files do not belong in the source repository.
A fresh checkout must be able to generate them locally.

No automatic deployment, GitHub upload, release upload, or CI download of
Factorio is configured. The build reads only your existing local installation
and downloads only the specified SDL version as a build dependency.
