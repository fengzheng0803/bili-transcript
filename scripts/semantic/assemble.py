"""文档组装：脚本模板表头 + LLM 产出的 markdown 正文。"""


def render_markdown(video_title: str, up_name: str, source: str, duration: int,
                    bvid: str, body: str) -> str:
    """把 LLM 产出的正文嵌进固定表头，生成最终 markdown 文档。"""
    lines = [
        f"# {video_title}", "",
        "## 视频信息", "",
        "| 项目 | 内容 |", "|---|---|",
        f"| BV号 | {bvid} |",
        f"| up主 | {up_name} |",
        f"| 时长 | {_fmt_duration(duration)} |",
        f"| 字幕来源 | {source} |", "",
        "## 正文", "",
        body.strip(), "",
        "---", "",
        "*本文档由 bili-transcript 技能生成：字幕来源与转写路线如上表，"
        "章节划分与内容过滤由 LLM 自动完成。*", "",
    ]
    return "\n".join(lines)


def _fmt_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
