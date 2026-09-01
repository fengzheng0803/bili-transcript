import json

import pytest

from bili_api import BiliApiError, SubtitleEntry
from subtitle import Segment, choose_chinese_subtitle, download_subtitle, format_transcript, parse_subtitle_json

SUBTITLE_JSON = json.dumps({"body": [
    {"from": 0.0, "to": 1.5, "content": "大家好"},
    {"from": 1.5, "to": 3.0, "content": "欢迎观看"},
]}, ensure_ascii=False)


def test_parse_subtitle_json():
    segs = parse_subtitle_json(SUBTITLE_JSON)
    assert segs == [Segment(0.0, 1.5, "大家好"), Segment(1.5, 3.0, "欢迎观看")]


def test_parse_empty_body():
    assert parse_subtitle_json('{"body": []}') == []


def test_format_transcript():
    segs = parse_subtitle_json(SUBTITLE_JSON)
    assert format_transcript(segs) == "[00:00:00.000] 大家好\n[00:00:01.500] 欢迎观看\n"


def test_format_transcript_long_duration():
    assert format_transcript([Segment(3661.25, 3662.0, "一小时后")]) == "[01:01:01.250] 一小时后\n"


def test_format_transcript_empty():
    assert format_transcript([]) == ""


def test_choose_prefers_official_zh_cn():
    entries = [
        SubtitleEntry(lan="ai-zh", lan_doc="中文（自动生成）", url="u1", ai_status=1),
        SubtitleEntry(lan="zh-CN", lan_doc="中文（中国）", url="u2", ai_status=0),
        SubtitleEntry(lan="en-US", lan_doc="English", url="u3", ai_status=0),
    ]
    assert choose_chinese_subtitle(entries).url == "u2"


def test_choose_falls_back_to_ai_zh():
    entries = [
        SubtitleEntry(lan="ai-zh", lan_doc="中文（自动生成）", url="u1", ai_status=1),
        SubtitleEntry(lan="en-US", lan_doc="English", url="u3", ai_status=0),
    ]
    assert choose_chinese_subtitle(entries).url == "u1"


def test_choose_none_when_no_chinese():
    entries = [SubtitleEntry(lan="en-US", lan_doc="English", url="u3", ai_status=0)]
    assert choose_chinese_subtitle(entries) is None


def test_choose_empty_list():
    assert choose_chinese_subtitle([]) is None


def test_download_subtitle_writes_bytes(tmp_path):
    class RespOK:
        status_code = 200
        content = b'{"body": []}'

        def raise_for_status(self):
            pass

    dest = download_subtitle(
        SubtitleEntry("zh-CN", "中文", "https://s/a.json", 0), tmp_path / "sub.json",
        request=lambda m, u, **kw: RespOK())
    assert dest.read_bytes() == b'{"body": []}'


def test_download_subtitle_403_hints_cookie(tmp_path):
    class Resp403:
        status_code = 403

        def raise_for_status(self):
            raise RuntimeError()

    with pytest.raises(BiliApiError, match="cookie"):
        download_subtitle(
            SubtitleEntry("zh-CN", "中文", "https://s/a.json", 0), tmp_path / "sub.json",
            request=lambda m, u, **kw: Resp403())
