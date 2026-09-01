"""转写器协议与工厂（规格 §3）：两条路线统一输出 [{start,end,text}]。"""
from pathlib import Path
from typing import Optional, Protocol

from config import Config
from subtitle import Segment


class Transcriber(Protocol):
    """转写器协议：输入音频文件，输出带时间戳的分段列表。"""

    def transcribe(self, audio: Path, work_dir: Path, dep_dir: Path) -> list[Segment]:
        """work_dir 用于中间产物（切片/缓存），dep_dir 用于定位依赖。"""
        ...


def create_transcriber(cfg: Config, choice: Optional[str] = None) -> Transcriber:
    kind = choice or cfg.asr_default
    if kind == "cloud":
        from transcribe.cloud import CloudTranscriber
        return CloudTranscriber(cfg.cloud_base_url, cfg.cloud_api_key, cfg.cloud_model)
    if kind == "local":
        from transcribe.local import LocalTranscriber
        return LocalTranscriber(cfg.local_model_size, cfg.local_device,
                                cfg.local_compute_type, cfg.dep_dir / "models")
    raise ValueError(f"未知的转写路线：{kind}（应为 local 或 cloud）")
