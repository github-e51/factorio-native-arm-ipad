# iPadで動かすための準備

この移植コードは、Steamの通常版Factorio 2.0.77、build 84539に対応しています。Space Age版や2.1.24は対象外です。実行ファイルのハッシュを確認してから変換するため、バージョン番号だけを合わせてもビルドできない場合があります。

## 今回の準備で完了したこと

2026年11月12日に、Steamの通常版2.0.77を取得し、指定のSHA-256との完全一致を確認しました。Xcode 27.0、iOS SDK 27.0でビルドし、開発用の署名まで完了しています。

署名済みアプリは `build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app` にあります。Bundle Identifierは `org.lenhirata.factorioipad` です。プロファイルには、Macとペアリング済みの13インチM5 iPad Proが含まれています。有効期限は2026年11月19日23時42分です。時刻は日本時間です。

このiPadのOSは27.3で、デベロッパモードは有効です。Mac側から状態を確認済みのため、同じ端末では有効化し直す必要はありません。

`tools/verify.py` で26個の実行ファイルとライブラリ、817箇所のSDL呼び出しの転送、記録したパッチとの一致を確認しました。記録されていないセクションの変更はありません。iPadへのインストールと起動はまだ行っていません。

Xcode 27のSDKに含まれる `arm64e-ios` と `arm64e.x1-ios` を確認処理が読み取れるよう修正しました。macOSやMac CatalystのAPIは対象から除外したままです。Pythonのテスト18件と、変更したPythonファイルのruff・tyによる検査が通っています。Objective-Cのビルドには、既存APIの非推奨警告が2件残っています。

GitHubのoriginには書き込み権限がないため、PRの作成は保留です。

## Steamから対応版を取得する

MacのSteamで、ライブラリのFactorioを右クリックし、プロパティのベータから2.0.77を選びます。DLCのSpace Ageも外して、更新が完了するまで待ってください。ゲームを起動する必要はありません。

旧バージョンの選択方法は[Factorio公式Wiki](https://wiki.factorio.com/Install_guide#Downloading_and_installing_old_versions)に説明されています。[公式サイトの2.0.77アーカイブ](https://factorio.com/download/archive/2.0.77)もありますが、配布元の違う実行ファイルは、この移植コードで使えるとは限りません。ここではSteamの通常版を使います。

このリポジトリのフォルダーで、次のコマンドを実行します。

```sh
uv sync --locked
uv run python tools/setup.py --preserve-source
```

セットアップは、実行ファイルとデータのバージョンを検査し、アプリを `build/source/factorio-2.0.77.app` に保存します。以後のビルドは、この保存したアプリを読みます。Steam側を更新しても保存したコピーは変わりません。パスはGitの管理対象外の `.local-config.json` に記録されます。

すでに保存したコピーがある場合は再検査して使います。壊れたコピーを自動で上書きすることはありません。`FACTORIO_APP` を設定している場合は、そのパスがローカル設定より優先されます。

保存する前に検査だけ行う場合は、次を使います。

```sh
uv run python tools/setup.py --check
```

## iPadに接続する前にビルドする

MacにXcodeとiOS SDK 26以降、CMakeが必要です。Apple Silicon上で実行してください。

```sh
uv run python tools/prepare_sdl.py --sdk iphoneos
uv run python tools/build_probe.py --sdk iphoneos --uikit --bundle-data
uv run python tools/verify.py --sdk iphoneos
```

出力は `build/iphoneos/FactorioProbe.app` です。この段階では開発用の署名とプロファイルが未設定のため、そのままiPadへインストールできません。検証は変換した実行ファイルの変更箇所、ライブラリの対象OS、署名を調べます。iPad上での描画や操作を確認するには実機が必要です。

Xcodeのビルド手順まで確認する場合は、署名を無効にして実行します。

```sh
xcodebuild -project FactorioProbe.xcodeproj -scheme FactorioProbe \
  -configuration Debug -sdk iphoneos -destination 'generic/platform=iOS' \
  -derivedDataPath build/Xcode CODE_SIGNING_ALLOWED=NO build
```

## iPadで操作を始めるとき

iPadOS 26以降のiPadをUSBでMacに接続します。iPadでMacを信頼し、設定のプライバシーとセキュリティからデベロッパモードを有効にします。

Macで `FactorioProbe.xcodeproj` を開き、FactorioProbeターゲットのSigning & Capabilitiesで自分のTeamを選びます。必要に応じてBundle Identifierを変更し、接続したiPadを実行先に選んでRunを実行します。詳細は [README](../README.md) の署名と起動の手順を参照してください。

今回の署名済みアプリを使う場合は、iPadの準備後に次のコマンドでインストールと起動ができます。デバイス名は `xcrun devicectl list devices` で確認してください。

```sh
xcrun devicectl device install app --device 'LenのiPad' \
  build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app
xcrun devicectl device process launch --device 'LenのiPad' org.lenhirata.factorioipad
```

Xcodeから再ビルドする場合もBundle Identifierを `org.lenhirata.factorioipad` にそろえてください。署名の期限が切れた場合は、自分のTeamでビルドし直します。

この準備では、iPadへのインストール、起動、既存セーブの変更は行いません。元の移植コードで描画が確認されているのはM1 iPad Proです。手元のiPadでの動作は、実機で確認するまで未検証です。

## 開発時の確認

```sh
uv run pytest
uv run ruff check tools/audit.py tools/config.py tools/setup.py tests/test_source.py tests/test_sdk_exports.py
uv run ty check tools/audit.py tools/config.py tools/setup.py tests/test_source.py tests/test_sdk_exports.py
```

テストはFactorio本体を使わずに、実行ファイルの不一致、データとアプリのバージョンの不一致、不完全なアプリの拒否を確認します。保存したコピーが元の更新から独立していることと、既存の保存先を上書きしないことも確認します。

SDKのテストでは、Xcode 27のARM64向け情報、ライブラリが再公開するAPIの読み取り、循環する参照の終了を確認します。macOSとMac Catalystなど、別の対象OSのAPIを除外できることも確認しています。
