# iPadで動かすための準備

Factorio 2.1.24、build 87808のSteam版Space Ageを、iPad用アプリとしてビルドできます。2026年11月13日に、起動中のメモリ不足を修正したアプリをiPadへ上書きし、ゲームの初期化が完了することをログで確認しました。

## 準備済みのアプリを使う

署名済みアプリは `build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app` にあります。Bundle Identifierは `org.lenhirata.factorioipad` です。Macとペアリング済みの13インチM5 iPad Proを署名対象に含めています。署名の有効期限は2026年11月20日12時46分です。時刻は日本時間です。

このiPadはiPadOS 27.3で、デベロッパモードが有効です。修正版はインストール済みです。再度更新するときは、iPadのロックを解除した状態で、リポジトリのフォルダーから次のコマンドを実行します。

```sh
xcrun devicectl device install app --device 'LenのiPad' \
  build/Xcode/Build/Products/Debug-iphoneos/FactorioProbe.app
xcrun devicectl device process launch --device 'LenのiPad' org.lenhirata.factorioipad
```

起動後にSteamを利用できないという案内が出た場合は、画面の案内に従って閉じます。Space Ageの有効状態は、ゲーム内のMOD設定で確認してください。通常版として遊ぶ場合は、同じ実行ファイルでSpace AgeなどのDLCを無効にできます。

署名の期限が切れた場合は、自分のTeamでビルドし直します。Xcodeで `FactorioProbe.xcodeproj` を開き、Signing & Capabilitiesで自分のTeamを選んでください。既存アプリを更新する場合は、Bundle Identifierを `org.lenhirata.factorioipad` にそろえます。

## 確認できた範囲

Mac版と移植版に同じセーブを読み込ませ、120回の更新後のチェックサムを比較しました。

| 実行する構成 | Mac版とシミュレーターのチェックサム |
|---|---|
| 2.1.24でSpace AgeなどのDLCを有効化 | `3668795911` で一致 |
| 2.1.24でDLCを無効化して通常版として実行 | `4181102737` で一致 |
| 旧版2.0.77の通常版 | `2892897386` で一致 |

2.1.24の通常版の検証には、Space Ageの実行ファイルでDLCを無効にした構成を使いました。

Space Ageの検証用シナリオは、Mac版と移植版の両方で通りました。Nauvis、Vulcanus、Fulgora、Gleba、Aquiloの地形を生成し、DLC固有の設備の定義、レジェンダリー品質の設備の作成、宇宙プラットフォームとハブの作成を確認しています。その状態で120回の更新も行いました。

iPad用アプリでは、29個の実行ファイルとライブラリ、1,269箇所のSDL呼び出しの転送、Space Age・Elevated Rails・Quality・Recyclerを含むデータ、開発用署名を検証しました。記録されていないセクションの変更はありません。

実機では、画像読み込み、テクスチャの転送を通過し、起動から29.6秒で `Factorio initialised` に到達しました。Steamを利用できないという案内の表示も、利用者が確認しました。画面撮影の自動テストは、iPad側の自動操作モードの有効化待ちで失敗しました。メニュー画面の確認は残っています。2.1.24での音声、タッチ操作、大規模な工場、長時間の動作は未検証です。

## 起動中に終了していた原因と修正

修正前のアプリは、Space Ageの画像を読み込む途中で終了していました。実機にデバッガを接続し、`EXC_RESOURCE` と5,120MiBのメモリ上限超過を確認しました。

`probe/FactorioProbe.entitlements` にIncreased Memory Limitを追加しました。署名済み実行ファイルとプロビジョニングの両方に許可が含まれることを、`tools/verify.py --signed-app` で検査します。Xcodeの署名では、この権限を外さず、自分のTeamでプロビジョニングを更新してください。

`probe/BitmapCompat.m` では、画像ごとに一時オブジェクトを解放し、ImageIOの画像キャッシュを無効にしました。画素の変換、並列読み込み、返した画像の寿命は、実際のImageIOを使うテストで確認しています。

更新前の設定とユーザーデータは、Macの `reports/ipad-user-backup-before-memory-fix/` に保存しました。同じBundle Identifierで上書きし、アプリの削除は行っていません。ログ、バックアップ、署名済みアプリはGitの管理対象外です。

## iPadの実解像度で描画する

13インチM5 iPad Proでは、`Documents/Factorio/config.ini` の `[graphics]` にある設定を次のように変更しました。画質のmediumは維持しています。

```ini
render-in-native-resolution=true
```

設定の変更後にゲームを再起動し、ログで `Native DPI: true` と `Drawable: 2752x2064` を確認しました。起動から31.0秒で初期化が完了しています。アプリ本体の変更や再インストールは不要でした。

ログの `Window: 1600x1200` は論理サイズです。描画先の画素数とは別の値なので、この値を2752×2064に書き換える処理は加えていません。実解像度での描画と画像素材の画質は別の設定です。mediumの画像素材も高精細にする場合は、別途画質を変更してメモリ使用量と動作を確認します。

再設定するときは、ゲームを保存して終了してから、Macへ取り出した設定のコピーを編集し、同じ場所へ戻します。

```sh
xcrun devicectl device copy from --device 'LenのiPad' \
  --domain-type appDataContainer --domain-identifier org.lenhirata.factorioipad \
  --source Documents/Factorio/config.ini --destination reports/ipad-config-before.ini
cp reports/ipad-config-before.ini reports/ipad-config-edited.ini
# ipad-config-edited.iniの[graphics]にある設定を編集し、元のコピーは残します。
xcrun devicectl device copy to --device 'LenのiPad' \
  --domain-type appDataContainer --domain-identifier org.lenhirata.factorioipad \
  --source reports/ipad-config-edited.ini --destination Documents/Factorio/config.ini
xcrun devicectl device process launch --device 'LenのiPad' org.lenhirata.factorioipad
```

今回の変更前の設定とユーザーデータは `reports/ipad-backup-before-native-resolution/` に保存しています。この設定はiPadのアプリ内に保存され、通常の再起動でも維持されます。

## Steamから再取得する

SteamでFactorioのプロパティを開き、ベータを「なし」にして、DLCのSpace Ageを有効にします。更新が完了してから、次を実行してください。

```sh
uv sync --locked
uv run python tools/setup.py --steam --preserve-source
```

`--steam` は、保存済みの旧版が設定されていてもSteam側のアプリを読みます。セットアップは実行ファイルのSHA-256、アプリのバージョン、各DLCのデータを検査し、`build/source/factorio-2.1.24-space-age.app` に保存します。以後のビルドでは、このコピーを使います。Steamの更新では、このコピーは変更されません。

設定はGitの管理対象外の `.local-config.json` に記録されます。`FACTORIO_APP` を設定している場合は、その値が設定ファイルより優先されます。未解析の実行ファイルは、同じバージョン番号でも受け付けません。対応する実行ファイルの一覧は `tools/source_profiles.py` にあります。

旧バージョンの取得方法は[Factorio公式Wiki](https://wiki.factorio.com/Install_guide#Downloading_and_installing_old_versions)に説明されています。最新版の番号は[公式の配布情報](https://factorio.com/api/latest-releases)で確認できます。

## ビルドし直す

Apple SiliconのMac、XcodeとiOS SDK 26以降、CMake、uvが必要です。今回使ったのはXcode 27.0とiOS SDK 27.0です。

```sh
uv run python tools/prepare_sdl.py --sdk iphoneos
uv run python tools/build_probe.py --sdk iphoneos --uikit --bundle-data
uv run python tools/verify.py --sdk iphoneos
```

`build/iphoneos/FactorioProbe.app` は開発用の署名を付ける前の出力です。iPadへインストールするには、Xcodeから自分のTeamで署名した製品を使います。

2.0.77にはSDL 2.30.9、2.1.24にはSDL 3.4.14を使います。SDLは公式リポジトリから取得し、固定したSHA-256を検査します。ゲームのバージョンを切り替えると、ビルド先のデータも入れ替わります。

## 処理を再検証する

シミュレーター用アプリを作成し、Xcodeなどで起動済みのiPadシミュレーターへインストールします。

```sh
uv run python tools/prepare_sdl.py --sdk iphonesimulator
uv run python tools/build_probe.py --sdk iphonesimulator --uikit --bundle-data
xcrun simctl install booted build/FactorioProbe.app
uv run python tools/check_simulation.py --mode space-age --simulator booted
uv run python tools/check_simulation.py --mode base --simulator booted
```

検証用の設定とセーブは、Macでは `build/simulation/`、シミュレーターではアプリ内の `Documents/Factorio/validation/` に保存します。通常のセーブを使いません。ログは `reports/simulation-*.log` と `reports/simulation-*.json` に出力します。

検証用シナリオは `tests/scenarios/space-age/control.lua` にあります。2.1.24で追加された `--test-scenario` を使い、処理が完了したかを確認します。

## 旧版へ戻す

前の作業で用意した2.0.77の通常版は `build/source/factorio-2.0.77.app` に残っています。署名済みの旧版アプリも `build/preserved/2.0.77-base/FactorioProbe.app` に退避しています。

ビルド元を旧版に戻す場合は、次を実行します。

```sh
uv run python tools/setup.py --app build/source/factorio-2.0.77.app
```

[公式の2.1の案内](https://factorio.com/blog/post/fff-444)では、2.1で更新したセーブやブループリントは2.0へ戻せないと説明されています。旧版のセーブは別に保管してください。

## コードを検査する

```sh
uv run pytest
uv run ruff check tools/source_profiles.py tools/config.py tools/setup.py tools/audit.py tools/macho.py tools/entrypoint.py tools/build_probe.py tools/prepare_sdl.py tools/verify.py tools/bundle_assets.py tools/check_simulation.py tools/run_probe.py tests/test_*.py
uv run ty check tools/source_profiles.py tools/config.py tools/setup.py tools/audit.py tools/macho.py tools/entrypoint.py tools/build_probe.py tools/prepare_sdl.py tools/verify.py tools/bundle_assets.py tools/check_simulation.py tools/run_probe.py tests/test_*.py
```

テスト35件が通っています。対応していない実行ファイルや不完全なデータの拒否、保存したコピーの独立性、データの入れ替え、SDKの読み取り、パッチ前後の命令、データ領域の拡張、検証ログの判定、署名情報の読み取りを確認します。macOSではObjective-Cの画像処理テストもコンパイルして実行します。ゲーム本体はテストに含めません。

Objective-Cには、以前から使っているAPIの非推奨警告が2件残っています。
