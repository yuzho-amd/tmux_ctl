#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN="$ROOT/bin/ttyd"

mkdir -p "$ROOT/bin"

if [[ -x "$BIN" ]]; then
  echo "ttyd already installed: $BIN"
  "$BIN" --version
  exit 0
fi

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)  ASSET="ttyd.x86_64" ;;
  aarch64|arm64) ASSET="ttyd.aarch64" ;;
  *)
    echo "Unsupported arch: $ARCH — install ttyd manually"
    exit 1
    ;;
esac

URL="https://github.com/tsl0922/ttyd/releases/download/1.7.7/${ASSET}"
echo "Downloading $URL ..."
curl -fsSL "$URL" -o "$BIN"
chmod +x "$BIN"
"$BIN" --version
echo "Done. Run: TTYD_BIN=$BIN python app.py"
