from config import Config
from semantic.llm import LlmError
from semantic.stage import _clean_title, run_semantic_stage


def make_cfg(**kw):
    cfg = Config()
    for key, value in kw.items():
        setattr(cfg, key, value)
    return cfg


def test_skips_when_no_llm_key(tmp_path):
    result = run_semantic_stage(make_cfg(llm_api_key=""), tmp_path / "cache",
                                "标题", "up", "BV1", "ai_subtitle", 300,
                                "转写全文", tmp_path / "md")
    assert result is None


def test_produces_md_from_llm_body(tmp_path):
    cfg = make_cfg(llm_api_key="sk-1")

    def fake_structure(text, video_title, base_url, api_key, model, request=None):
        return "### 1. 缓存击穿 [00:00:00-00:01:30]\n\n- 大量请求打到过期键"

    md_dir = tmp_path / "md"
    result = run_semantic_stage(cfg, tmp_path / "cache", "120分钟Redis", "up",
                                "BV123", "ai_subtitle", 300, "转写全文", md_dir,
                                structure=fake_structure)
    assert result == md_dir / "120分钟Redis-BV123.md"
    md = result.read_text(encoding="utf-8")
    assert "### 1. 缓存击穿" in md
    assert (tmp_path / "cache" / "structured.md").read_text(encoding="utf-8") == \
        "### 1. 缓存击穿 [00:00:00-00:01:30]\n\n- 大量请求打到过期键"


def test_prints_semantic_missing_on_error(tmp_path, capsys):
    cfg = make_cfg(llm_api_key="sk-1")

    def failing_structure(text, video_title, base_url, api_key, model, request=None):
        raise LlmError("请求失败：超时")

    result = run_semantic_stage(cfg, tmp_path / "cache", "标题", "up", "BV1",
                                "ai_subtitle", 300, "转写全文", tmp_path / "md",
                                structure=failing_structure)
    assert result is None
    assert "语义缺失" in capsys.readouterr().out
    assert not (tmp_path / "md").exists()


def test_reuses_cached_body_without_llm_calls(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "structured.md").write_text("### 1. 哨兵模式 [00:00:00-00:01:00]",
                                         encoding="utf-8")

    def explode_structure(text, video_title, base_url, api_key, model, request=None):
        raise AssertionError("缓存命中时不应调用 LLM")

    result = run_semantic_stage(make_cfg(llm_api_key="sk-1"), cache, "标题", "up",
                                "BV1", "ai_subtitle", 300, "转写全文", tmp_path / "md",
                                structure=explode_structure)
    assert "### 1. 哨兵模式" in result.read_text(encoding="utf-8")


def test_long_transcript_split_into_two_calls(tmp_path):
    cfg = make_cfg(llm_api_key="sk-1")
    calls = []
    transcript = ("[00:00:00.000] " + "内容" * 600 + "\n") * 200  # 超阈值且含换行

    def recording_structure(text, video_title, base_url, api_key, model, request=None):
        calls.append(text)
        return "### 第" + str(len(calls)) + "部分"

    result = run_semantic_stage(cfg, tmp_path / "cache", "标题", "up", "BV1",
                                "ai_subtitle", 300, transcript, tmp_path / "md",
                                structure=recording_structure)
    assert len(calls) == 2
    assert all(len(c) < len(transcript) for c in calls)
    assert "### 第1部分" in result.read_text(encoding="utf-8")
    assert "### 第2部分" in result.read_text(encoding="utf-8")


def test_clean_title_strips_illegal_chars_and_collapses_spaces():
    assert _clean_title("彻底搞懂 K8s Pod | 12分钟") == "彻底搞懂 K8s Pod 12分钟"
    assert _clean_title("a/b\\c:d*e?f\"g<h>i") == "abcdefghi"
