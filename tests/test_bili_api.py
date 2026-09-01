import pytest

from bili_api import BiliApi, BiliApiError


class FakeResp:
    def __init__(self, payload, status=200, url=""):
        self._payload = payload
        self.status_code = status
        self.url = url

    def json(self):
        return self._payload


def fake_requester(*responses):
    """按序返回预先构造的响应。"""
    queue = list(responses)

    def request(method, url, **kw):
        return queue.pop(0)

    return request


NAV_JSON = {"code": 0, "data": {"wbi_img": {
    "img_url": "https://i0.hdslb.com/bfs/wbi/0123456789abcdef0123456789abcdef.png",
    "sub_url": "https://i0.hdslb.com/bfs/wbi/fedcba9876543210fedcba9876543210.png",
}}}
VIEW_JSON = {"code": 0, "data": {
    "aid": 123, "bvid": "BV1xx411c7mD", "title": "测试视频",
    "owner": {"name": "up主"}, "desc": "描述",
    "pages": [{"cid": 100, "page": 1, "part": "P1", "duration": 600},
              {"cid": 101, "page": 2, "part": "P2", "duration": 300}]}}


def test_get_video_meta():
    api = BiliApi(request=fake_requester(FakeResp(VIEW_JSON)))
    meta = api.get_video_meta("BV1xx411c7mD")
    assert meta.title == "测试视频"
    assert meta.up_name == "up主"
    assert [p.cid for p in meta.pages] == [100, 101]


def test_video_not_found():
    api = BiliApi(request=fake_requester(FakeResp({"code": -404})))
    with pytest.raises(BiliApiError, match="不存在"):
        api.get_video_meta("BV1xx411c7mD")


def test_negative_412_hints_cookie():
    api = BiliApi(request=fake_requester(FakeResp({"code": -412})))
    with pytest.raises(BiliApiError, match="cookie"):
        api.get_video_meta("BV1xx411c7mD")


def test_get_subtitles_wbi_signed():
    captured = []
    player = {"code": 0, "data": {"subtitle": {"subtitles": [
        {"lan": "zh-CN", "lan_doc": "中文（中国）", "subtitle_url": "https://s/a.json", "ai_status": 0}]}}}

    def request(method, url, **kw):
        captured.append((url, kw["params"]))
        return FakeResp(NAV_JSON if url.endswith("/nav") else player)

    api = BiliApi(request=request)
    subs = api.get_subtitles("BV1xx411c7mD", 100)
    assert subs[0].lan == "zh-CN" and subs[0].ai_status == 0
    assert any("w_rid" in params for _, params in captured)


def test_get_audio_streams():
    playurl = {"code": 0, "data": {"dash": {"audio": [
        {"id": 30280, "baseUrl": "https://upos/a.m4s", "bandwidth": 64000},
        {"id": 30216, "baseUrl": "https://upos/b.m4s", "bandwidth": 128000}]}}}
    api = BiliApi(request=fake_requester(FakeResp(NAV_JSON), FakeResp(playurl)))
    streams = api.get_audio_streams("BV1xx411c7mD", 100)
    assert [s.bandwidth for s in streams] == [64000, 128000]


def test_search_strips_em_tags():
    search = {"code": 0, "data": {"result": [
        {"bvid": "BV1aa411c7mD", "title": "标题<em class=\"keyword\">关键词</em>部分",
         "author": "作者", "duration": "12:34", "play": 999, "videos": 2}]}}
    api = BiliApi(request=fake_requester(FakeResp(NAV_JSON), FakeResp(search)))
    results = api.search_videos("关键词")
    assert results[0].title == "标题关键词部分"
    assert results[0].page_count == 2
    assert results[0].bvid == "BV1aa411c7mD"


def test_search_limit():
    search = {"code": 0, "data": {"result": [
        {"bvid": f"BV1aa411c7m{i}", "title": f"t{i}", "author": "a", "duration": "00:01",
         "play": 1, "videos": 1} for i in range(6)]}}
    api = BiliApi(request=fake_requester(FakeResp(NAV_JSON), FakeResp(search)))
    assert len(api.search_videos("kw", limit=3)) == 3


def test_resolve_b23():
    api = BiliApi(request=lambda m, u, **kw: FakeResp(
        {}, url="https://www.bilibili.com/video/BV1xx411c7mD/"))
    assert api.resolve_b23("https://b23.tv/abcd") == "https://www.bilibili.com/video/BV1xx411c7mD/"


def test_resolve_b23_failure():
    api = BiliApi(request=lambda m, u, **kw: FakeResp({}, url="https://b23.tv/abcd"))
    with pytest.raises(BiliApiError, match="短链"):
        api.resolve_b23("https://b23.tv/abcd")


def test_cookie_attached():
    captured = []

    def request(method, url, **kw):
        captured.append(kw["headers"])
        return FakeResp(VIEW_JSON)

    BiliApi(cookie="SESSDATA=abc", request=request).get_video_meta("BV1xx411c7mD")
    assert captured[0]["Cookie"] == "SESSDATA=abc"


def test_wbi_keys_tolerates_anonymous_nav():
    """匿名时 nav 返回 -101 但 data.wbi_img 仍含密钥——_wbi_keys 必须照常取到密钥。"""
    nav_101 = {"code": -101, "data": {"wbi_img": {
        "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
        "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"}}}
    player = {"code": 0, "data": {"subtitle": {"subtitles": [
        {"lan": "zh-CN", "lan_doc": "中文（中国）", "subtitle_url": "https://s/a.json",
         "ai_status": 0}]}}}
    api = BiliApi(request=fake_requester(FakeResp(nav_101), FakeResp(player)))
    subs = api.get_subtitles("BV1xx411c7mD", 100)
    assert subs[0].lan == "zh-CN"


def test_negative_101_on_endpoint_hints_cookie():
    api = BiliApi(request=fake_requester(FakeResp({"code": -101})))
    with pytest.raises(BiliApiError, match="cookie"):
        api.get_video_meta("BV1xx411c7mD")
