from semantic.assemble import render_markdown


def test_render_markdown_composes_header_and_body():
    body = "### 1. 认识Pod：K8s最小调度单位 [00:00:00-00:01:34]\n\n- 内容行"
    md = render_markdown("120分钟吃透Redis缓存架构", "某up", "cloud_asr", 7200,
                         "BV12345678901", body)
    assert md.startswith("# 120分钟吃透Redis缓存架构\n")
    assert "| BV号 | BV12345678901 |" in md
    assert "| up主 | 某up |" in md
    assert "| 时长 | 02:00:00 |" in md
    assert "| 字幕来源 | cloud_asr |" in md
    assert "## 正文" in md
    assert body in md


def test_render_short_duration_mm_ss():
    md = render_markdown("标题", "up", "ai_subtitle", 593, "BV1", "")
    assert "| 时长 | 09:53 |" in md


def test_render_trims_body():
    md = render_markdown("标题", "up", "ai_subtitle", 300, "BV1", "  正文\n\n")
    assert "- 内容" not in md
    assert "正文" in md
