"""本地转写路线（规格 §3）：faster-whisper，模型存 dep_dir/models。"""
from pathlib import Path

from bili_api import BiliApiError
from subtitle import Segment


class LocalTranscriber:
    """faster-whisper 整段转写（无需切片）。"""

    def __init__(self, model_size: str = "medium", device: str = "cpu",
                 compute_type: str = "int8",
                 download_root: Path = Path("~/bilibili-dep/models").expanduser()):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = Path(download_root)
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise BiliApiError("faster-whisper 未安装，运行 scripts/setup.sh")
            self._model = WhisperModel(self.model_size, device=self.device,
                                       compute_type=self.compute_type,
                                       download_root=str(self.download_root))
        return self._model

    def transcribe(self, audio: Path, work_dir: Path, dep_dir: Path) -> list[Segment]:
        del work_dir, dep_dir  # 本地路线无需切片与依赖目录
        segments, _info = self._load_model().transcribe(str(audio), language="zh")
        result = []
        for s in segments:
            text = s.text.strip()
            if text:
                result.append(Segment(start=float(s.start), end=float(s.end), text=text))
        return result
