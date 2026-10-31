#!/bin/bash
# Double-click in Finder to build and install Factorio on a connected iPhone or iPad.
# Prepares Xcode, Python and CMake, checks your own Factorio copy, then runs
# tools/install.py. Run it again to update the app or renew its signing.
set -u
cd "$(dirname "$0")" || exit 1

finish() { echo; read -r -p "Press Return to close this window. " _; exit "${1:-0}"; }
fail() { echo; echo "$1"; finish 1; }

echo "Factorio for iPhone and iPad - installer"
echo "========================================"

if [[ "$(uname -m)" != arm64 ]]; then
    fail "This needs an Apple Silicon Mac (M1 or newer). If this Mac has one, Terminal is running
under Rosetta: quit Terminal, select it in Finder > Applications > Utilities, choose
File > Get Info, and turn off \"Open using Rosetta\"."
fi

# Use the newest Xcode in /Applications without changing the system-wide selection.
xcode=""; best=0
for app in /Applications/Xcode*.app; do
    [[ -d "$app" ]] || continue
    v=$(defaults read "$app/Contents/Info" CFBundleShortVersionString 2>/dev/null) || continue
    n=$(echo "$v" | awk -F. '{printf "%d%03d", $1, $2}')
    if (( n > best )); then best=$n; xcode=$app; fi
done
if [[ -z "$xcode" ]]; then
    echo "Xcode is not installed. Opening it in the App Store."
    echo "Install it (it is large and can take an hour), open it once, then run this again."
    open "macappstore://apps.apple.com/app/id497799835"
    finish 1
fi
export DEVELOPER_DIR="$xcode/Contents/Developer"
echo "Using $(basename "$xcode") $(defaults read "$xcode/Contents/Info" CFBundleShortVersionString)"
if ! xcodebuild -checkFirstLaunchStatus >/dev/null 2>&1; then
    echo "Xcode has not finished its first-launch setup. Opening Xcode now:"
    echo "agree to the licence and install the iOS platform when it asks."
    open "$xcode"
    read -r -p "Press Return when Xcode has finished setting up. " _
    xcodebuild -checkFirstLaunchStatus >/dev/null 2>&1 ||
        fail "Xcode still needs its first-launch setup. Finish it in Xcode, then run this again."
fi
xcrun --sdk iphoneos --show-sdk-version >/dev/null 2>&1 ||
    fail "Xcode's iOS platform is missing. In Xcode, open Settings > Components, install iOS, then run this again."

# Python 3.12+ and CMake, through Homebrew when missing.
export PATH="/opt/homebrew/bin:$PATH"
find_python() {
    for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
        command -v "$candidate" >/dev/null 2>&1 || continue
        if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
            command -v "$candidate"; return
        fi
    done
}
python=$(find_python)
if [[ -z "$python" ]] || ! command -v cmake >/dev/null 2>&1; then
    echo
    echo "Python 3.12 or newer and CMake are needed. They install through Homebrew."
    if [[ ! -x /opt/homebrew/bin/brew ]]; then
        read -r -p "Homebrew is not installed. Install it now? It asks for your Mac password. [y/N] " answer
        [[ "$answer" == [yY]* ]] || fail "Install Homebrew from https://brew.sh, then run this again."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" ||
            fail "Homebrew did not install. See https://brew.sh, then run this again."
    fi
    /opt/homebrew/bin/brew install python cmake || fail "Installing Python and CMake failed."
    python=$(find_python)
    [[ -n "$python" ]] || fail "Python 3.12 or newer is still missing."
fi

# Your own Factorio copy: remembered, the usual Steam location, or dragged in.
factorio=""
if [[ -f .local-config.json ]]; then
    factorio=$("$python" -c 'import json; print(json.load(open(".local-config.json")).get("factorio_app", ""))' 2>/dev/null)
fi
[[ -d "$factorio" ]] || factorio="$HOME/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app"
while [[ ! -d "$factorio" ]]; do
    echo
    echo "Factorio was not found in the usual Steam folder."
    echo "Drag factorio.app from Finder into this window, then press Return:"
    read -r factorio
    factorio="${factorio//\\ / }"; factorio="${factorio%"${factorio##*[! ]}"}"
    factorio="${factorio#\'}"; factorio="${factorio%\'}"
done

echo
echo "Checking your Factorio copy and preparing build tools..."
"$python" tools/setup.py --app "$factorio" || fail "Setup stopped; see the message above. docs/INSTALL.md has help."

.venv/bin/python tools/install.py "$@"
finish $?
