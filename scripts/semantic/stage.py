"""语义阶段编排：transcript 全文一次调用 LLM，产出结构化 markdown。"""
import re
from pathlib import Path
from typing import Optional

from config import Config
from semantic import llm
from semantic.assemble import render_markdown

LONG_TRANSCRIPT_CHARS = 50_000  # 超过此长度按两半切分，避免超模型上下文


def run_semantic_stage(cfg: Config, cache_dir: Path, video_title: str, up_name: str,
                       bvid: str, source: str, duration: int, transcript: str,
                       md_dir: Path, structure=None) -> Optional[Path]:
    """全文调用 LLM 整理，产出 markdown 文档并返回其路径。

    未配置 llm.api_key → 返回 None（行为同旧版）。
    LLM 调用失败 → 打印 [语义缺失] 并返回 None，不产 md。
    cache 中 structured.md 已存在 → 跳过 LLM 调用直接复用（免重复花费）。"""
    if not cfg.llm_api_key:
        return None
    if structure is None:
        structure = llm.structure_transcript
    body_file = cache_dir / "structured.md"
    if body_file.is_file():
        body = body_file.read_text(encoding="utf-8")
    else:
        try:
            body = _structure_long(transcript, video_title, cfg, structure)
        except llm.LlmError as exc:
            print(f"[语义缺失] 全文结构整理失败：{exc}")
            return None
        body_file.parent.mkdir(parents=True, exist_ok=True)
        body_file.write_text(body, encoding="utf-8")
    md = render_markdown(video_title, up_name, source, duration, bvid, body)
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{_clean_title(video_title)}-{bvid}.md"
    md_path.write_text(md, encoding="utf-8")
    return md_path


def _structure_long(transcript: str, video_title: str, cfg: Config, structure) -> str:
    if len(transcript) <= LONG_TRANSCRIPT_CHARS:
        return structure(transcript, video_title, cfg.llm_base_url,
                         cfg.llm_api_key, cfg.llm_model)
    mid = len(transcript) // 2
    newline = transcript.rfind("\n", mid - 2000, mid)
    if newline == -1:
        newline = mid
    bodies = [structure(part, video_title, cfg.llm_base_url, cfg.llm_api_key,
                        cfg.llm_model)
              for part in (transcript[:newline], transcript[newline:])]
    return "\n\n".join(bodies)


def _clean_title(title: str) -> str:
    cleaned = re.sub(r'[/\\:*?"<>|]', "", title)
    return re.sub(r"\s+", " ", cleaned).strip()
