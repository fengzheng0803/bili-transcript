import json

import pytest

import pipeline as pipeline_mod
from bili_api import BiliApi
from config import Config
from pipeline import Pipeline


class FakeResp:
    def __init__(self, payload, status=200, content=b"", url=""):
        self._payload = payload
        self.status_code = status
        self.content = content
        self.url = url

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError()


def make_api(*responses):
    queue = list(responses)

    def request(method, url, **kw):
        return queue.pop(0)

    return BiliApi(request=request)


def fake_transcriber(segments):
    class T:
        def transcribe(self, audio, work_dir, dep_dir):
            return segments

    return T()


NAV = FakeResp({"code": 0, "data": {"wbi_img": {
    "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
    "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"}}})
VIEW = FakeResp({"code": 0, "data": {
    "aid": 1, "bvid": "BV1xx411c7mD", "title": "标题", "owner": {"name": "up"},
    "desc": "", "pages": [{"cid": 100, "page": 1, "part": "P1", "duration": 600}]}})
SUB_JSON = json.dumps({"body": [{"from": 0, "to": 1, "content": "你好"}]},
                      ensure_ascii=False).encode()


def test_subtitle_route_official(tmp_path):
    player = FakeResp({"code": 0, "data": {"subtitle": {"subtitles": [
        {"lan": "zh-CN", "lan_doc": "中文", "subtitle_url": "https://s/a.json",
         "ai_status": 0}]}}})
    api = make_api(VIEW, NAV, player, FakeResp({}, content=SUB_JSON))
    result = Pipeline(Config(dep_dir=tmp_path / "dep"), api=api,
                      cache_root=tmp_path / "cache").run("BV1xx411c7mD")
    assert result.source == "official_cc"
    assert "你好" in result.transcript
    assert (tmp_path / "cache/BV1xx411c7mD-p1/transcript.txt").is_file()


def test_ai_subtitle_route(tmp_path):
    player = FakeResp({"code": 0, "data": {"subtitle": {"subtitles": [
        {"lan": "ai-zh", "lan_doc": "中文（自动生成）", "subtitle_url": "https://s/a.json",
         "ai_status": 1}]}}})
    api = make_api(VIEW, NAV, player, FakeResp({}, content=SUB_JSON))
    result = Pipeline(Config(dep_dir=tmp_path / "dep"), api=api,
                      cache_root=tmp_path / "cache").run("BV1xx411c7mD")
    assert result.source == "ai_subtitle"


def test_no_subtitle_audio_route(tmp_path, monkeypatch):
    player = FakeResp({"code": 0, "data": {"subtitle": {"subtitles": []}}})
    playurl = FakeResp({"code": 0, "data": {"dash": {"audio": [
        {"baseUrl": "https://u/a.m4s", "bandwidth": 128000}]}}})
    m4s = FakeResp({}, content=b"raw-audio")
    api = make_api(VIEW, NAV, player, NAV, playurl, m4s)
    monkeypatch.setattr(pipeline_mod, "run_ffmpeg", lambda cmd, dep: None)
    cfg = Config(dep_dir=tmp_path / "dep")  # asr_default 默认 cloud
    pipe = Pipeline(cfg, api=api, cache_root=tmp_path / "cache",
                    transcriber=fake_transcriber([pipeline_mod.Segment(0, 2, "转写内容")]))
    result = pipe.run("BV1xx411c7mD")
    assert result.source == "cloud_asr"
    assert "转写内容" in result.transcript
    assert (tmp_path / "cache/BV1xx411c7mD-p1/audio.raw").is_file()


def test_local_source_label(tmp_path, monkeypatch):
    player = FakeResp({"code": 0, "data": {"subtitle": {"subtitles": []}}})
    playurl = FakeResp({"code": 0, "data": {"dash": {"audio": [
        {"baseUrl": "https://u/a.m4s", "bandwidth": 128000}]}}})
    m4s = FakeResp({}, content=b"raw-audio")
    api = make_api(VIEW, NAV, player, NAV, playurl, m4s)
    monkeypatch.setattr(pipeline_mod, "run_ffmpeg", lambda cmd, dep: None)
    cfg = Config(dep_dir=tmp_path / "dep", asr_default="local")
    pipe = Pipeline(cfg, api=api, cache_root=tmp_path / "cache",
                    transcriber=fake_transcriber([pipeline_mod.Segment(0, 2, "本地转写")]))
    assert pipe.run("BV1xx411c7mD").source == "local_asr"


def test_resume_from_cache(tmp_path):
    cache = tmp_path / "cache" / "BV1xx411c7mD-p1"
    cache.mkdir(parents=True)
    (cache / "transcript.txt").write_text("[00:00:00.000] 已缓存", encoding="utf-8")
    (cache / "meta.json").write_text(
        json.dumps({"bvid": "BV1xx411c7mD", "title": "标题", "up_name": "up",
                    "page": 1, "part": "P1", "duration": 600,
                    "source": "ai_subtitle"}),
        encoding="utf-8")

    def fail(method, url, **kw):
        raise AssertionError("缓存命中时不应发起请求")

    pipe = Pipeline(Config(dep_dir=tmp_path / "dep"), api=BiliApi(request=fail),
                    cache_root=tmp_path / "cache")
    result = pipe.run("BV1xx411c7mD")
    assert result.transcript == "[00:00:00.000] 已缓存"
    assert result.source == "ai_subtitle"
    assert result.title == "标题"


def test_page_out_of_range(tmp_path):
    api = make_api(VIEW)
    with pytest.raises(pipeline_mod.BiliApiError, match="页码"):
        Pipeline(Config(dep_dir=tmp_path / "dep"), api=api,
                 cache_root=tmp_path / "c").run("BV1xx411c7mD", page=3)


def test_download_403_hints_cookie(tmp_path):
    player = FakeResp({"code": 0, "data": {"subtitle": {"subtitles": []}}})
    playurl = FakeResp({"code": 0, "data": {"dash": {"audio": [
        {"baseUrl": "https://u/a.m4s", "bandwidth": 1}]}}})
    api = make_api(VIEW, NAV, player, NAV, playurl, FakeResp({}, status=403))
    with pytest.raises(pipeline_mod.BiliApiError, match="cookie"):
        Pipeline(Config(dep_dir=tmp_path / "dep"), api=api,
                 cache_root=tmp_path / "c").run("BV1xx411c7mD")


def test_no_llm_key_skips_semantic(tmp_path):
    player = FakeResp({"code": 0, "data": {"subtitle": {"subtitles": [
        {"lan": "zh-CN", "lan_doc": "中文", "subtitle_url": "https://s/a.json",
         "ai_status": 0}]}}})
    api = make_api(VIEW, NAV, player, FakeResp({}, content=SUB_JSON))
    pipe = Pipeline(Config(dep_dir=tmp_path / "dep"), api=api,
                    cache_root=tmp_path / "cache", md_dir=tmp_path / "md")
    result = pipe.run("BV1xx411c7mD")
    assert result.md_path is None
    assert not (tmp_path / "cache" / "BV1xx411c7mD-p1" / "structure.json").exists()


def test_semantic_stage_runs_when_llm_configured(tmp_path, monkeypatch):
    player = FakeResp({"code": 0, "data": {"subtitle": {"subtitles": [
        {"lan": "zh-CN", "lan_doc": "中文", "subtitle_url": "https://s/a.json",
         "ai_status": 0}]}}})
    api = make_api(VIEW, NAV, player, FakeResp({}, content=SUB_JSON))
    monkeypatch.setattr("semantic.llm.structure_transcript",
                        lambda text, title, base_url, api_key, model, request=None:
                        "### 1. 你好 [00:00:00-00:00:01]")
    pipe = Pipeline(Config(dep_dir=tmp_path / "dep", llm_api_key="sk-1"), api=api,
                    cache_root=tmp_path / "cache", md_dir=tmp_path / "md")
    result = pipe.run("BV1xx411c7mD")
    assert result.md_path == tmp_path / "md" / "标题-BV1xx411c7mD.md"
    assert "### 1. 你好" in result.md_path.read_text(encoding="utf-8")
    assert (tmp_path / "cache" / "BV1xx411c7mD-p1" / "structured.md").is_file()


def test_structure_false_skips_semantic(tmp_path):
    player = FakeResp({"code": 0, "data": {"subtitle": {"subtitles": [
        {"lan": "zh-CN", "lan_doc": "中文", "subtitle_url": "https://s/a.json",
         "ai_status": 0}]}}})
    api = make_api(VIEW, NAV, player, FakeResp({}, content=SUB_JSON))
    pipe = Pipeline(Config(dep_dir=tmp_path / "dep", llm_api_key="sk-1"), api=api,
                    cache_root=tmp_path / "cache", md_dir=tmp_path / "md")
    result = pipe.run("BV1xx411c7mD", structure=False)
    assert result.md_path is None
    assert not (tmp_path / "cache" / "BV1xx411c7mD-p1" / "structured.md").exists()


def test_semantic_runs_on_cache_hit(tmp_path, monkeypatch):
    cache = tmp_path / "cache" / "BV1xx411c7mD-p1"
    cache.mkdir(parents=True)
    (cache / "transcript.txt").write_text(
        "[00:00:30.000] 缓存内容\n[00:01:00.000] 继续讲解", encoding="utf-8")
    (cache / "meta.json").write_text(
        json.dumps({"bvid": "BV1xx411c7mD", "title": "标题", "up_name": "up",
                    "page": 1, "part": "P1", "duration": 600,
                    "source": "ai_subtitle"}),
        encoding="utf-8")
    monkeypatch.setattr("semantic.llm.structure_transcript",
                        lambda text, title, base_url, api_key, model, request=None:
                        "### 1. 缓存 [00:00:30-00:01:05]")

    def fail(method, url, **kw):
        raise AssertionError("缓存命中时不应发起请求")

    pipe = Pipeline(Config(dep_dir=tmp_path / "dep", llm_api_key="sk-1"),
                    api=BiliApi(request=fail), cache_root=tmp_path / "cache",
                    md_dir=tmp_path / "md")
    result = pipe.run("BV1xx411c7mD")
    assert result.md_path == tmp_path / "md" / "标题-BV1xx411c7mD.md"
    assert "### 1. 缓存" in result.md_path.read_text(encoding="utf-8")
