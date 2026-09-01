"""字幕下载与解析（规格 §3 ⑤）：json → 带时间戳文本。"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from bili_api import BiliApiError, HEADERS, LOGIN_HINT, SubtitleEntry
from http_util import request_with_retry


@dataclass
class Segment:
    """统一的时间戳分段类型（全项目共用，含两条转写路线）。"""
    start: float
    end: float
    text: str


def choose_chinese_subtitle(entries: list[SubtitleEntry]) -> Optional[SubtitleEntry]:
    """中文字幕选择：优先 zh-CN 人工，其次 ai-zh AI（规格 §3 ④）。"""
    zh = [e for e in entries if "zh" in e.lan.lower() or "中文" in e.lan_doc]
    if not zh:
        return None

    def score(e: SubtitleEntry) -> tuple[int, int]:
        return (0 if e.ai_status == 0 else 1, 0 if e.lan == "zh-CN" else 1)

    return min(zh, key=score)


def parse_subtitle_json(raw: str) -> list[Segment]:
    body = json.loads(raw).get("body") or []
    return [Segment(start=float(b["from"]), end=float(b["to"]), text=b["content"])
            for b in body]


def _fmt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_transcript(segments: list[Segment]) -> str:
    """[HH:MM:SS.mmm] 文本 每行一条。"""
    lines = [f"[{_fmt_ts(seg.start)}] {seg.text}" for seg in segments]
    return "\n".join(lines) + ("\n" if lines else "")


def download_subtitle(entry: SubtitleEntry, dest: Path, request=request_with_retry,
                      headers=HEADERS) -> Path:
    resp = request("GET", entry.url, headers=headers)
    if resp.status_code == 403:
        raise BiliApiError(LOGIN_HINT)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest
