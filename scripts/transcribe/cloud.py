"""云转写路线（规格 §3）：OpenAI 兼容接口 + ffmpeg 切片上传。"""
import json
import requests
from pathlib import Path

from audio import build_probe_cmd, build_slice_cmd, run_ffmpeg
from bili_api import BiliApiError
from http_util import request_with_retry
from subtitle import Segment

CHUNK_SECONDS = 600  # 切片时长（秒），25MB 上传限制内安全


class CloudTranscriber:
    """OpenAI 兼容 /audio/transcriptions 接口（硅基流动/Groq/OpenAI 通用）。"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 chunk_seconds: int = CHUNK_SECONDS, request=request_with_retry):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.chunk_seconds = chunk_seconds
        self.request = request

    def transcribe(self, audio: Path, work_dir: Path, dep_dir: Path) -> list[Segment]:
        if not self.api_key:
            raise BiliApiError("未配置 API key，编辑 config.json 或设置 BILI_ASR_API_KEY")
        chunks = self._ensure_chunks(audio, work_dir, dep_dir)
        segments: list[Segment] = []
        for i, chunk in enumerate(sorted(chunks)):
            offset = i * self.chunk_seconds
            cache = chunk.with_suffix(".txt")
            if cache.is_file():
                try:
                    segments.extend(json.loads(cache.read_text(encoding="utf-8"),
                                               object_hook=lambda d: Segment(**d)))
                    continue
                except (json.JSONDecodeError, KeyError, TypeError):
                    cache.unlink(missing_ok=True)  # 缓存损坏 → 删掉重新上传
            payload = self._upload(chunk)
            chunk_segs = self._parse_response(payload, offset, chunk, dep_dir)
            cache.write_text(json.dumps([s.__dict__ for s in chunk_segs],
                                        ensure_ascii=False), encoding="utf-8")
            segments.extend(chunk_segs)
        return segments

    def _ensure_chunks(self, audio: Path, work_dir: Path, dep_dir: Path) -> list[Path]:
        chunks = sorted(work_dir.glob("chunk_*.mp3"))
        if chunks:
            return chunks
        run_ffmpeg(build_slice_cmd(audio, work_dir / "chunk_%03d.mp3", self.chunk_seconds),
                   dep_dir)
        chunks = sorted(work_dir.glob("chunk_*.mp3"))
        if not chunks:
            raise BiliApiError("音频切片失败")
        return chunks

    def _upload(self, chunk: Path) -> dict:
        content = chunk.read_bytes()
        try:
            resp = self.request(
                "POST", f"{self.base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (chunk.name, content, "audio/mpeg")},
                data={"model": self.model, "language": "zh",
                      "response_format": "verbose_json"},
            )
        except requests.RequestException as exc:
            raise BiliApiError(f"转写服务请求失败：{exc}") from exc
        if resp.status_code == 401:
            raise BiliApiError("API key 无效（401），检查 BILI_ASR_API_KEY")
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("message", "")
            except Exception:
                detail = resp.text[:200]
            if not detail:
                detail = "（提供方无详情）"
            raise BiliApiError(f"转写服务请求失败（HTTP {resp.status_code}）：{detail}")
        return resp.json()

    def _parse_response(self, payload: dict, offset: float, chunk: Path,
                        dep_dir: Path) -> list[Segment]:
        raw_segs = payload.get("segments")
        if raw_segs:
            return [Segment(start=offset + float(s["start"]), end=offset + float(s["end"]),
                            text=s["text"].strip()) for s in raw_segs if s.get("text")]
        text = (payload.get("text") or "").strip()
        if not text:
            return []
        return [Segment(start=offset, end=offset + self._probe_duration(chunk, dep_dir),
                        text=text)]

    def _probe_duration(self, chunk: Path, dep_dir: Path) -> float:
        result = run_ffmpeg(build_probe_cmd(chunk), dep_dir)
        return float(result.stdout.strip())
