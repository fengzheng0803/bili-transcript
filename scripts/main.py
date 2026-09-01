"""CLI 入口（规格 §5/§7）：main.py <bvid> [选项] 或 main.py search <关键词>。"""
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests

from bili_api import BiliApi, BiliApiError, extract_bvid_from_url, validate_bvid
from config import load_config
from http_util import RiskControlError
from pipeline import Pipeline


def build_transcribe_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bili-transcript", description="读取 B站视频字幕/转写为带时间戳文本")
    p.add_argument("input", help="BV 号或视频链接")
    p.add_argument("--page", type=int, default=1, help="分P页码，默认 1")
    p.add_argument("--asr", choices=["local", "cloud"], default=None,
                   help="转写路线（无字幕时），默认取配置 asr.default")
    p.add_argument("--out", type=Path, default=None,
                   help="输出/缓存根目录，默认 .cache/bili-transcript")
    p.add_argument("--no-structure", action="store_true",
                   help="跳过语义阶段（切段/过滤/LLM 判相关），只产出原始文字稿")
    return p


def build_search_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bili-transcript search", description="按关键词搜索 B站视频")
    p.add_argument("keyword", help="搜索关键词（视频名）")
    p.add_argument("--limit", type=int, default=5, help="候选数量，默认 5")
    return p


def _cmd_search(argv: list[str]) -> int:
    args = build_search_parser().parse_args(argv)
    cfg = load_config(args)
    results = BiliApi(cookie=cfg.bili_cookie).search_videos(args.keyword, args.limit)
    if not results:
        print("无搜索结果，请换关键词", file=sys.stderr)
        return 2
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r.title} | {r.up_name} | {r.duration} | "
              f"播放 {r.play} | {r.page_count}P | {r.bvid}")
    return 0


def _cmd_transcribe(argv: list[str]) -> int:
    args = build_transcribe_parser().parse_args(argv)
    cfg = load_config(args)
    bvid = extract_bvid_from_url(args.input)
    if bvid is None and args.input.startswith("http"):
        # b23.tv 等短链：跟随重定向解析出真实链接后再提取（规格 §7）
        try:
            bvid = extract_bvid_from_url(
                BiliApi(cookie=cfg.bili_cookie).resolve_b23(args.input))
        except BiliApiError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if bvid is None:
        try:
            bvid = validate_bvid(args.input)
        except BiliApiError:
            print("无效的 BV 号，应为 BV 开头 12 位", file=sys.stderr)
            return 2
    result = Pipeline(cfg, cache_root=args.out).run(bvid, args.page,
                                                   structure=not args.no_structure)
    print(f"视频：{result.title}（{result.bvid} P{result.page}）")
    print(f"字幕来源：{result.source}")
    if result.md_path is not None:
        print(f"结构化文档：{result.md_path}")
    print(f"文字稿：{result.cache_dir.resolve() / 'transcript.txt'}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and argv[0] == "search":
            return _cmd_search(argv[1:])
        return _cmd_transcribe(argv)
    except BiliApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RiskControlError:
        print("触发 B站风控，请在 config.json 填 bilibili.cookie（F12 → 网络请求 → 复制 Cookie 头）",
              file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ffmpeg 执行失败：{exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"网络请求失败：{exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"系统错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
