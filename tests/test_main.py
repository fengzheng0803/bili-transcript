import pytest

import main as main_mod
from bili_api import BiliApiError, SearchResult


def test_transcribe_parser_accepts_bvid_and_options():
    args = main_mod.build_transcribe_parser().parse_args(
        ["BV1xx411c7mD", "--page", "2", "--asr", "local", "--out", "o"])
    assert args.input == "BV1xx411c7mD"
    assert args.page == 2
    assert args.asr == "local"
    assert str(args.out) == "o"


def test_transcribe_parser_defaults():
    args = main_mod.build_transcribe_parser().parse_args(["BV1xx411c7mD"])
    assert args.page == 1 and args.asr is None and args.out is None


def test_search_parser():
    args = main_mod.build_search_parser().parse_args(["关键词", "--limit", "3"])
    assert args.keyword == "关键词" and args.limit == 3


def test_main_transcribe_flow(tmp_path, monkeypatch, capsys):
    class FakePipe:
        def __init__(self, cfg, cache_root=None):
            self.cache_root = cache_root

        def run(self, bvid, page, structure=True):
            class R:
                pass

            r = R()
            r.title, r.bvid, r.page, r.source = "标题", bvid, page, "ai_subtitle"
            r.cache_dir = tmp_path / "c"
            r.cache_dir.mkdir(exist_ok=True)
            r.md_path = None
            return r

    monkeypatch.setattr(main_mod, "Pipeline", FakePipe)
    code = main_mod.main(["BV1xx411c7mD", "--out", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 0
    assert "标题" in out and "ai_subtitle" in out


def test_main_invalid_bvid(capsys):
    assert main_mod.main(["not-a-bvid"]) == 2
    assert "无效的 BV 号" in capsys.readouterr().err


def test_main_b23_shortlink_resolves(tmp_path, monkeypatch, capsys):
    ran = {}

    class FakeApi:
        def __init__(self, cookie=""):
            pass

        def resolve_b23(self, short_url):
            assert short_url == "https://b23.tv/abcd"
            return "https://www.bilibili.com/video/BV1xx411c7mD/"

    class FakePipe:
        def __init__(self, cfg, cache_root=None):
            pass

        def run(self, bvid, page, structure=True):
            ran["bvid"] = bvid
            class R:
                pass

            r = R()
            r.title, r.bvid, r.page, r.source = "标题", bvid, page, "ai_subtitle"
            r.cache_dir = tmp_path / "c"
            r.cache_dir.mkdir(exist_ok=True)
            r.md_path = None
            return r

    monkeypatch.setattr(main_mod, "BiliApi", FakeApi)
    monkeypatch.setattr(main_mod, "Pipeline", FakePipe)
    code = main_mod.main(["https://b23.tv/abcd"])
    assert code == 0
    assert ran["bvid"] == "BV1xx411c7mD"


def test_main_b23_resolve_failure(capsys, monkeypatch):
    class FakeApi:
        def __init__(self, cookie=""):
            pass

        def resolve_b23(self, short_url):
            raise BiliApiError("b23.tv 短链解析失败，请提供完整链接或 BV 号")

    monkeypatch.setattr(main_mod, "BiliApi", FakeApi)
    assert main_mod.main(["https://b23.tv/abcd"]) == 1
    assert "短链解析失败" in capsys.readouterr().err


def test_main_pipeline_error(capsys, monkeypatch):
    class BadPipe:
        def __init__(self, cfg, cache_root=None):
            pass

        def run(self, bvid, page, structure=True):
            raise BiliApiError("视频不存在（-404）")

    monkeypatch.setattr(main_mod, "Pipeline", BadPipe)
    assert main_mod.main(["BV1xx411c7mD"]) == 1
    assert "视频不存在" in capsys.readouterr().err


def test_main_search_no_result(capsys, monkeypatch):
    class Api:
        def __init__(self, cookie=""):
            pass

        def search_videos(self, kw, limit):
            return []

    monkeypatch.setattr(main_mod, "BiliApi", Api)
    assert main_mod.main(["search", "无结果关键词"]) == 2
    assert "无搜索结果" in capsys.readouterr().err


def test_main_search_lists_candidates(capsys, monkeypatch):
    class Api:
        def __init__(self, cookie=""):
            pass

        def search_videos(self, kw, limit):
            return [SearchResult("BV1xx411c7mD", "标题A", "up", "12:34", 999, 2)]

    monkeypatch.setattr(main_mod, "BiliApi", Api)
    assert main_mod.main(["search", "关键词"]) == 0
    out = capsys.readouterr().out
    assert "BV1xx411c7mD" in out and "标题A" in out


def test_transcribe_parser_no_structure_flag():
    args = main_mod.build_transcribe_parser().parse_args(
        ["BV1xx411c7mD", "--no-structure"])
    assert args.no_structure is True


def test_main_passes_structure_false(tmp_path, monkeypatch, capsys):
    calls = {}

    class FakePipe:
        def __init__(self, cfg, cache_root=None):
            pass

        def run(self, bvid, page, structure=True):
            calls["structure"] = structure
            class R:
                pass

            r = R()
            r.title, r.bvid, r.page, r.source = "标题", bvid, page, "ai_subtitle"
            r.cache_dir = tmp_path / "c"
            r.cache_dir.mkdir(exist_ok=True)
            r.md_path = None
            return r

    monkeypatch.setattr(main_mod, "Pipeline", FakePipe)
    assert main_mod.main(["BV1xx411c7mD", "--no-structure"]) == 0
    assert calls["structure"] is False


def test_main_prints_md_path(tmp_path, monkeypatch, capsys):
    class FakePipe:
        def __init__(self, cfg, cache_root=None):
            pass

        def run(self, bvid, page, structure=True):
            class R:
                pass

            r = R()
            r.title, r.bvid, r.page, r.source = "标题", bvid, page, "ai_subtitle"
            r.cache_dir = tmp_path / "c"
            r.cache_dir.mkdir(exist_ok=True)
            r.md_path = tmp_path / "标题.md"
            return r

    monkeypatch.setattr(main_mod, "Pipeline", FakePipe)
    assert main_mod.main(["BV1xx411c7mD"]) == 0
    assert str(tmp_path / "标题.md") in capsys.readouterr().out
