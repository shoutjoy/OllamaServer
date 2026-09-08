#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
BUILD="$ROOT/build"
APP_NAME="OllamaDesk"
APP="$DIST/$APP_NAME.app"
DMG="$DIST/$APP_NAME-macOS.dmg"

cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "이 스크립트는 macOS에서만 실행할 수 있습니다." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3가 필요합니다. Python 3.10 이상을 설치하세요." >&2
    exit 1
fi

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
    echo "PyInstaller가 필요합니다. 다음 명령으로 설치하세요:" >&2
    echo "  python3 -m pip install pyinstaller" >&2
    exit 1
fi

rm -rf "$APP" "$DMG"
python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "$APP_NAME" \
    --osx-bundle-identifier "com.shoutjoy.ollamadesk" \
    --add-data "Icon:Icon" \
    --add-data "CHAT/ollama-say.html:CHAT" \
    --add-data "CHAT/ollama_say_local_web_app.html:CHAT" \
    --distpath "$DIST" \
    --workpath "$BUILD" \
    --specpath "$BUILD" \
    app.py

# Ad Hoc signing makes the bundle internally consistent without requiring an
# Apple Developer certificate. It is not notarization and does not remove the
# first-run Gatekeeper warning for an app downloaded from the internet.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

STAGING="$(mktemp -d "${TMPDIR:-/tmp}/ollamadesk-dmg.XXXXXX")"
trap 'rm -rf "$STAGING"' EXIT
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    "$DMG"

echo "생성 완료:"
echo "  $APP"
echo "  $DMG"
echo "빌드 아키텍처: $(uname -m)"
