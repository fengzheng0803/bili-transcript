"""管线编排（规格 §3）：字幕优先 → 音频转写兜底，缓存与断点续传，尾接语义阶段。"""
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from audio import build_extract_audio_cmd, download_audio, pick_best_audio, run_ffmpeg
from bili_api import BiliApi, BiliApiError, PageInfo, VideoMeta, validate_bvid
from config import Config
from semantic.stage import run_semantic_stage
from subtitle import (Segment, choose_chinese_subtitle, download_subtitle,
                      format_transcript, parse_subtitle_json)
from transcribe.base import Transcriber, create_transcriber

SOURCE_OFFICIAL = "official_cc"
SOURCE_AI = "ai_subtitle"
SOURCE_LOCAL = "local_asr"
SOURCE_CLOUD = "cloud_asr"


@dataclass
class PipelineResult:
    bvid: str
    title: str
    up_name: str
    page: int
    part: str
    duration: int
    source: str
    transcript: str
    cache_dir: Path
    md_path: Optional[Path] = None


class Pipeline:
    def __init__(self, cfg: Config, api: Optional[BiliApi] = None,
                 transcriber: Optional[Transcriber] = None,
                 cache_root: Optional[Path] = None,
                 md_dir: Path = Path("transcripts")):
        self.cfg = cfg
        self.api = api or BiliApi(cookie=cfg.bili_cookie)
        self.transcriber = transcriber
        self.cache_root = cache_root or Path(".cache/bili-transcript")
        self.md_dir = md_dir
        self.asr_source = SOURCE_LOCAL if cfg.asr_default == "local" else SOURCE_CLOUD

    def run(self, bvid: str, page: int = 1, structure: bool = True) -> PipelineResult:
        validate_bvid(bvid)
        cache_dir = self.cache_root / f"{bvid}-p{page}"
        transcript_file = cache_dir / "transcript.txt"
        meta_file = cache_dir / "meta.json"
        saved = self._read_cache(meta_file, transcript_file, bvid, page)
        if saved is None:
            meta = self.api.get_video_meta(bvid)
            page_info = self._select_page(meta, page)
            cache_dir.mkdir(parents=True, exist_ok=True)
            source, segments = self._obtain_transcript(meta.bvid, page_info, cache_dir)
            transcript_file.write_text(format_transcript(segments), encoding="utf-8")
            saved = self._write_meta(meta_file, meta, page, page_info, source)
        transcript = transcript_file.read_text(encoding="utf-8")
        md_path = None
        if structure and self.cfg.llm_api_key:
            md_path = run_semantic_stage(self.cfg, cache_dir, saved["title"],
                                         saved["up_name"], saved["bvid"],
                                         saved["source"], saved["duration"],
                                         transcript, self.md_dir)
        return PipelineResult(bvid=saved["bvid"], title=saved["title"],
                              up_name=saved["up_name"], page=page, part=saved["part"],
                              duration=saved["duration"], source=saved["source"],
                              transcript=transcript, cache_dir=cache_dir,
                              md_path=md_path)

    def _read_cache(self, meta_file: Path, transcript_file: Path, bvid: str,
                    page: int) -> Optional[dict]:
        if not (transcript_file.is_file() and meta_file.is_file()):
            return None
        try:
            saved = json.loads(meta_file.read_text(encoding="utf-8"))
            if saved.get("bvid") == bvid and saved.get("page") == page:
                return saved
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # 缓存损坏 → 当作未命中，走重新获取
        return None

    def _write_meta(self, meta_file: Path, meta: VideoMeta, page: int,
                    page_info: PageInfo, source: str) -> dict:
        saved = {"bvid": meta.bvid, "title": meta.title, "up_name": meta.up_name,
                 "page": page, "part": page_info.part, "duration": page_info.duration,
                 "source": source}
        tmp_meta = meta_file.with_suffix(".json.tmp")
        tmp_meta.write_text(json.dumps(saved, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        os.replace(tmp_meta, meta_file)
        return saved

    def _select_page(self, meta: VideoMeta, page: int) -> PageInfo:
        for p in meta.pages:
            if p.page == page:
                return p
        pages = ", ".join(f"P{p.page} {p.part}" for p in meta.pages)
        raise BiliApiError(f"页码 {page} 不存在，可选：{pages}")

    def _obtain_transcript(self, bvid: str, page_info: PageInfo,
                           cache_dir: Path) -> tuple[str, list[Segment]]:
        entries = self.api.get_subtitles(bvid, page_info.cid)
        chosen = choose_chinese_subtitle(entries)
        if chosen is not None:
            subtitle_file = cache_dir / "subtitle.json"
            download_subtitle(chosen, subtitle_file, request=self.api.request,
                              headers=self.api.headers)
            segments = parse_subtitle_json(subtitle_file.read_text(encoding="utf-8"))
            source = SOURCE_OFFICIAL if chosen.ai_status == 0 else SOURCE_AI
            return source, segments

        transcriber = self.transcriber or create_transcriber(self.cfg)
        audio_file = cache_dir / "audio.m4a"
        if not audio_file.is_file():
            raw = cache_dir / "audio.raw"
            stream = pick_best_audio(self.api.get_audio_streams(bvid, page_info.cid))
            download_audio(stream.url, raw, request=self.api.request,
                           headers=self.api.headers)
            run_ffmpeg(build_extract_audio_cmd(raw, audio_file), self.cfg.dep_dir)
        segments = transcriber.transcribe(audio_file, cache_dir, self.cfg.dep_dir)
        return self.asr_source, segments
