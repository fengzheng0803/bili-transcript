#!/usr/bin/env bash
# 一键初始化：venv、Python 依赖、静态 ffmpeg、可选预下载 whisper 模型（规格 §2）
set -euo pipefail

DEP_DIR="${BILI_DEP_DIR:-$HOME/bilibili-dep}"
VENV="$DEP_DIR/venv-bilibili"
BIN_DIR="$DEP_DIR/bin"
MODEL_DIR="$DEP_DIR/models"

echo "==> 创建 venv: $VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip

echo "==> 安装 Python 依赖"
"$VENV/bin/pip" install "requests==2.32.3" "faster-whisper==1.2.1" "pytest==8.3.4"

mkdir -p "$BIN_DIR" "$MODEL_DIR"

if [ ! -x "$BIN_DIR/ffmpeg" ] || [ ! -x "$BIN_DIR/ffprobe" ]; then
  echo "==> 下载静态 ffmpeg（johnvansickle amd64 static）"
  FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
  TMP_TAR="$(mktemp --suffix=.tar.xz)"
  trap 'rm -f "$TMP_TAR"' EXIT
  curl -fsSL "$FFMPEG_URL" -o "$TMP_TAR"
  tar -xJf "$TMP_TAR" -C "$BIN_DIR" --strip-components=1 --wildcards "*/ffmpeg" "*/ffprobe"
  rm -f "$TMP_TAR"
  trap - EXIT
fi

echo "==> ffmpeg 版本: $("$BIN_DIR/ffmpeg" -version | head -1)"

read -r -p "预下载本地转写模型 medium（约 1.5GB）？[y/N] " answer || answer=N
if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
  "$VENV/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('medium', download_root='$MODEL_DIR'); print('模型已下载到 $MODEL_DIR')"
fi

echo "==> 完成。使用方式："
echo "  $VENV/bin/python $(cd "$(dirname "$0")" && pwd)/main.py <bvid>"
