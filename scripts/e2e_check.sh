#!/usr/bin/env bash
# 手工端到端验收（规格 §8）：一条带字幕样例 + 一条无字幕短样例。
# 用法：bash scripts/e2e_check.sh <有字幕的BV> <无字幕的BV> [cloud|local]
# 云路线需先配置 BILI_ASR_API_KEY。
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SKILL_DIR/.."
PY="$HOME/bilibili-dep/venv-bilibili/bin/python"
ASR="${3:-cloud}"

echo "== 样例1：字幕路线（预期 source 为 official_cc 或 ai_subtitle）"
"$PY" "$SKILL_DIR/scripts/main.py" "$1" --asr "$ASR"

echo "== 样例2：转写路线（预期 source 为 ${ASR}_asr）"
"$PY" "$SKILL_DIR/scripts/main.py" "$2" --asr "$ASR"

echo "== 缓存产物"
ls "$PWD/.cache/bili-transcript/"
