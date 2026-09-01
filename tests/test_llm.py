import pytest
import requests

from semantic.llm import LlmError, structure_transcript


def _resp(content, status=200):
    class Resp:
        status_code = status
        text = content

        def json(self):
            if status == 200:
                return {"choices": [{"message": {"content": content}}]}
            return {"message": "bad key"}

    return Resp()


def test_structure_transcript_returns_content_stripped():
    def fake_request(method, url, **kw):
        return _resp("\n## 正文\n\n### 1. 标题 [00:00:00-00:01:30]\n\n- 内容\n\n")

    body = structure_transcript("全文", "视频标题", "https://api.example.com",
                                "sk-test", "m1", request=fake_request)
    assert body == "## 正文\n\n### 1. 标题 [00:00:00-00:01:30]\n\n- 内容"


def test_structure_transcript_sends_full_text():
    captured = {}

    def fake_request(method, url, **kw):
        captured["method"], captured["url"], captured["kw"] = method, url, kw
        return _resp("正文")

    structure_transcript("全部转写文字", "视频标题", "https://api.example.com",
                         "sk-test", "m1", request=fake_request)
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.example.com/chat/completions"
    assert captured["kw"]["headers"] == {"Authorization": "Bearer sk-test"}
    body = captured["kw"]["json"]
    assert body["model"] == "m1"
    assert "视频标题" in body["messages"][1]["content"]
    assert "全部转写文字" in body["messages"][1]["content"]


def test_structure_transcript_raises_on_401():
    def fake_request(method, url, **kw):
        return _resp("", status=401)

    with pytest.raises(LlmError, match="401"):
        structure_transcript("x", "y", "u", "k", "m", request=fake_request)


def test_structure_transcript_wraps_network_error():
    def fake_request(method, url, **kw):
        raise requests.ConnectionError("网络不可达")

    with pytest.raises(LlmError, match="请求失败"):
        structure_transcript("x", "y", "u", "k", "m", request=fake_request)
