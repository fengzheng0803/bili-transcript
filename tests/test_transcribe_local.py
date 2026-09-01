import sys
import types

import pytest

from config import Config
from transcribe.base import create_transcriber


def _install_fake_provider(module_name, monkeypatch):
    """在 sys.modules 中安装假的 provider 模块（测试结束自动还原），记录构造参数。"""
    fake = types.ModuleType(module_name)

    class Fake:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def transcribe(self, audio, work_dir, dep_dir):
            return []

    fake.CloudTranscriber = Fake
    fake.LocalTranscriber = Fake
    monkeypatch.setitem(sys.modules, module_name, fake)
    return fake


def test_factory_default_is_cloud(monkeypatch):
    _install_fake_provider("transcribe.cloud", monkeypatch)
    cfg = Config()
    t = create_transcriber(cfg)
    assert t.args == (cfg.cloud_base_url, cfg.cloud_api_key, cfg.cloud_model)


def test_factory_choice_local(monkeypatch):
    _install_fake_provider("transcribe.local", monkeypatch)
    cfg = Config(asr_default="cloud")
    t = create_transcriber(cfg, choice="local")
    assert t.args == (cfg.local_model_size, cfg.local_device, cfg.local_compute_type,
                      cfg.dep_dir / "models")


def test_factory_unknown_choice_raises():
    with pytest.raises(ValueError):
        create_transcriber(Config(), choice="nope")


import sys
import types
from pathlib import Path

import pytest

from bili_api import BiliApiError
from subtitle import Segment
from transcribe.local import LocalTranscriber


def _install_fake_faster_whisper(monkeypatch):
    fake = types.ModuleType("faster_whisper")

    class FakeSeg:
        def __init__(self, start, end, text):
            self.start, self.end, self.text = start, end, text

    class FakeModel:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def transcribe(self, path, language="zh"):
            assert language == "zh"
            return [FakeSeg(1, 2, " 你好 "), FakeSeg(2, 3, "   ")], "info"

    fake.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)  # 测试结束自动还原（Ruling I）
    return fake


def test_local_transcriber_normalizes_segments(monkeypatch):
    _install_fake_faster_whisper(monkeypatch)
    t = LocalTranscriber("medium", "cpu", "int8", Path("/tmp/models"))
    segs = t.transcribe(Path("a.m4a"), Path("/tmp/w"), Path("/tmp/dep"))
    assert segs == [Segment(1.0, 2.0, "你好")]  # 空文本段被过滤、strip 生效
    assert t._model.kwargs["download_root"] == "/tmp/models"


def test_local_transcriber_missing_dependency(monkeypatch):
    # 本环境已真实安装 faster-whisper（Task 1），用无 WhisperModel 属性的空模块
    # 让 `from faster_whisper import WhisperModel` 触发 ImportError（Ruling I）
    monkeypatch.setitem(sys.modules, "faster_whisper", types.ModuleType("faster_whisper"))
    t = LocalTranscriber()
    with pytest.raises(BiliApiError, match="setup.sh"):
        t._load_model()
