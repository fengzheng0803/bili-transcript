from pathlib import Path

import pytest

import transcribe.cloud as cloud_mod
from bili_api import BiliApiError
from subtitle import Segment
from transcribe.cloud import CloudTranscriber


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_missing_api_key_raises():
    t = CloudTranscriber("https://api.siliconflow.cn/v1", "", "m")
    with pytest.raises(BiliApiError, match="API key"):
        t.transcribe(Path("a.m4a"), Path("/tmp/w"), Path("/tmp/dep"))


def test_transcribe_with_offsets_and_cache(tmp_path, monkeypatch):
    def fake_slice(cmd, dep):
        (tmp_path / "chunk_000.mp3").write_bytes(b"a")
        (tmp_path / "chunk_001.mp3").write_bytes(b"b")

    monkeypatch.setattr(cloud_mod, "run_ffmpeg", fake_slice)
    payloads = [
        {"segments": [{"start": 1.0, "end": 2.0, "text": "第一句"}]},
        {"segments": [{"start": 0.5, "end": 1.0, "text": "第二句"}]},
    ]

    def fake_request(method, url, **kw):
        assert url == "https://api.siliconflow.cn/v1/audio/transcriptions"
        assert kw["data"]["model"] == "m"
        assert kw["data"]["response_format"] == "verbose_json"
        assert kw["headers"]["Authorization"] == "Bearer k"
        assert kw["data"]["language"] == "zh"
        assert kw["files"]["file"][0] in ("chunk_000.mp3", "chunk_001.mp3")
        assert kw["files"]["file"][2] == "audio/mpeg"
        return FakeResp(payloads.pop(0))

    t = CloudTranscriber("https://api.siliconflow.cn/v1", "k", "m",
                         chunk_seconds=600, request=fake_request)
    segs = t.transcribe(Path("a.m4a"), tmp_path, Path("/tmp/dep"))
    assert segs == [Segment(1.0, 2.0, "第一句"), Segment(600.5, 601.0, "第二句")]
    # 缓存：重跑不再请求
    segs2 = t.transcribe(Path("a.m4a"), tmp_path, Path("/tmp/dep"))
    assert segs2 == segs
    assert payloads == []


def test_plain_text_fallback_uses_probe_duration(tmp_path, monkeypatch):
    calls = {"n": 0}

    class ProbeResult:
        stdout = "45.0\n"

    def router(cmd, dep):
        calls["n"] += 1
        if calls["n"] == 1:
            (tmp_path / "chunk_000.mp3").write_bytes(b"a")
        return ProbeResult()

    monkeypatch.setattr(cloud_mod, "run_ffmpeg", router)
    t = CloudTranscriber("https://api.siliconflow.cn/v1", "k", "m",
                         request=lambda m, u, **kw: FakeResp({"text": "整段文本"}))
    segs = t.transcribe(Path("a.m4a"), tmp_path, Path("/tmp/dep"))
    assert segs == [Segment(0.0, 45.0, "整段文本")]


def test_401_hints_invalid_key(tmp_path, monkeypatch):
    def fake_slice(cmd, dep):
        (tmp_path / "chunk_000.mp3").write_bytes(b"a")

    monkeypatch.setattr(cloud_mod, "run_ffmpeg", fake_slice)
    t = CloudTranscriber("https://api.siliconflow.cn/v1", "bad", "m",
                         request=lambda m, u, **kw: FakeResp({}, status=401))
    with pytest.raises(BiliApiError, match="API key"):
        t.transcribe(Path("a.m4a"), tmp_path, Path("/tmp/dep"))


def test_empty_text_returns_empty(tmp_path, monkeypatch):
    def fake_slice(cmd, dep):
        (tmp_path / "chunk_000.mp3").write_bytes(b"a")

    monkeypatch.setattr(cloud_mod, "run_ffmpeg", fake_slice)
    t = CloudTranscriber("https://api.siliconflow.cn/v1", "k", "m",
                         request=lambda m, u, **kw: FakeResp({"text": "  "}))
    assert t.transcribe(Path("a.m4a"), tmp_path, Path("/tmp/dep")) == []


def test_403_with_provider_message_maps_to_chinese_error(tmp_path, monkeypatch):
    def fake_slice(cmd, dep):
        (tmp_path / "chunk_000.mp3").write_bytes(b"a")

    monkeypatch.setattr(cloud_mod, "run_ffmpeg", fake_slice)

    class FakeResp403:
        status_code = 403
        _payload = {"message": "Access denied: please complete identity verification"}

        def json(self):
            return self._payload

        def raise_for_status(self):
            raise RuntimeError("HTTP 403")

    t = CloudTranscriber("https://api.siliconflow.cn/v1", "k", "m",
                         request=lambda m, u, **kw: FakeResp403())
    with pytest.raises(BiliApiError, match="转写服务请求失败"):
        t.transcribe(Path("a.m4a"), tmp_path, Path("/tmp/dep"))
