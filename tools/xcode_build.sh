#!/bin/bash
set -euo pipefail
task_root="${SRCROOT}"
task_python="$task_root/.venv/bin/python"
task_sdk="${PLATFORM_NAME}"
if [[ ! -x "$task_python" ]]; then
    echo "Run python3 tools/setup.py from the repository folder first." >&2
    exit 1
fi
"$task_python" "$task_root/tools/prepare_sdl.py" --sdk "$task_sdk"
"$task_python" "$task_root/tools/build_probe.py" --sdk "$task_sdk" --uikit --bundle-data --bundle-id "$PRODUCT_BUNDLE_IDENTIFIER"
if [[ "$task_sdk" == "iphoneos" ]]; then
    task_app="$task_root/build/iphoneos/FactorioProbe.app"
else
    task_app="$task_root/build/FactorioProbe.app"
fi
task_product="${TARGET_BUILD_DIR}/${FULL_PRODUCT_NAME}"
if [[ -d "$task_product" ]]; then
    /usr/bin/find "$task_product" -mindepth 1 -maxdepth 1 ! -name embedded.mobileprovision -exec /bin/rm -rf {} +
fi
/usr/bin/ditto "$task_app" "$task_product"
if [[ "${CODE_SIGNING_ALLOWED:-NO}" == "YES" && -n "${EXPANDED_CODE_SIGN_IDENTITY:-}" ]]; then
    for task_library in "$task_product"/Frameworks/*.dylib; do
        /usr/bin/codesign --force --sign "$EXPANDED_CODE_SIGN_IDENTITY" --timestamp=none "$task_library"
    done
fi
