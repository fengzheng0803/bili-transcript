"""B站 API 封装（规格 §3）：bvid 处理、wbi 签名、视频信息、搜索、字幕、音频流。"""
import hashlib
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Optional

from http_util import request_with_retry

API_BASE = "https://api.bilibili.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}

BVID_RE = re.compile(r"^BV[0-9A-Za-z]{10}$")
URL_BVID_RE = re.compile(r"/(BV[0-9A-Za-z]{10})")


class BiliApiError(RuntimeError):
    """面向用户的 B站错误（中文提示，规格 §6）。"""


def validate_bvid(s: str) -> str:
    """校验并返回 bvid；非法时抛 BiliApiError。"""
    if not isinstance(s, str) or not BVID_RE.match(s):
        raise BiliApiError("无效的 BV 号，应为 BV 开头 12 位")
    return s


def extract_bvid_from_url(url: str) -> Optional[str]:
    """从视频链接中提取 bvid；非视频链接返回 None。"""
    m = URL_BVID_RE.search(url or "")
    return m.group(1) if m else None


MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]
CHR_FILTER = re.compile(r"[!'()*]")


def get_mixin_key(orig: str) -> str:
    return "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def enc_wbi(params: dict, img_key: str, sub_key: str, ts: int) -> dict:
    """对参数做 wbi 签名，返回含 wts/w_rid 的新字典。"""
    mixin_key = get_mixin_key(img_key + sub_key)
    signed = dict(sorted({**params, "wts": ts}.items()))
    query = CHR_FILTER.sub("", urllib.parse.urlencode(signed))
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return {**signed, "w_rid": w_rid}


@dataclass
class PageInfo:
    cid: int
    page: int
    part: str
    duration: int


@dataclass
class VideoMeta:
    bvid: str
    aid: int
    title: str
    up_name: str
    desc: str
    pages: list[PageInfo]


@dataclass
class SubtitleEntry:
    lan: str
    lan_doc: str
    url: str
    ai_status: int  # 0 人工，1 AI


@dataclass
class AudioStreamInfo:
    url: str
    bandwidth: int


@dataclass
class SearchResult:
    bvid: str
    title: str
    up_name: str
    duration: str  # "mm:ss"
    play: int
    page_count: int


CODE_MESSAGES = {
    -404: "视频不存在（-404）",
    62002: "视频不可见（62002）",
    -403: "无权限访问（-403）",
}
LOGIN_HINT = "该视频需要登录，请在 config.json 填 bilibili.cookie（F12 → 网络请求 → 复制 Cookie 头）"


def _json_code_is_risk(resp) -> bool:
    try:
        return resp.json().get("code") in (-412, -352)
    except Exception:
        return False


class BiliApi:
    """B站公开 API 客户端。request 可注入（测试用）；cookie 可填以访问受限内容。"""

    def __init__(self, cookie: str = "", request: Optional[Callable] = None):
        self._request = request or request_with_retry
        self._headers = {**HEADERS}
        if cookie:
            self._headers["Cookie"] = cookie

    @property
    def headers(self) -> dict:
        return self._headers

    @property
    def request(self):
        return self._request

    def _get_json(self, path: str, params: dict) -> dict:
        resp = self._request("GET", API_BASE + path, params=params, headers=self._headers,
                             risk_check=_json_code_is_risk)
        data = resp.json()
        if data.get("code") != 0:
            self._raise_code(data)
        return data.get("data") or {}

    def _get_json_wbi(self, path: str, params: dict) -> dict:
        img_key, sub_key = self._wbi_keys()
        return self._get_json(path, enc_wbi(params, img_key, sub_key, int(time.time())))

    def _wbi_keys(self) -> tuple[str, str]:
        resp = self._request("GET", API_BASE + "/x/web-interface/nav",
                             params={}, headers=self._headers)
        wbi_img = (resp.json().get("data") or {}).get("wbi_img") or {}
        img, sub = wbi_img.get("img_url", ""), wbi_img.get("sub_url", "")
        if not img or not sub:
            raise BiliApiError("获取 wbi 密钥失败")
        return (img.rsplit("/", 1)[-1].split(".")[0],
                sub.rsplit("/", 1)[-1].split(".")[0])

    def _raise_code(self, data: dict) -> None:
        code = data.get("code")
        if code in CODE_MESSAGES:
            raise BiliApiError(CODE_MESSAGES[code])
        if code in (-412, -352, -101):
            raise BiliApiError(LOGIN_HINT)
        raise BiliApiError(f"B站接口错误：code={code} message={data.get('message')}")

    def get_video_meta(self, bvid: str) -> VideoMeta:
        data = self._get_json("/x/web-interface/view", {"bvid": validate_bvid(bvid)})
        return VideoMeta(
            bvid=data["bvid"],
            aid=data["aid"],
            title=data["title"],
            up_name=data["owner"]["name"],
            desc=data.get("desc", ""),
            pages=[PageInfo(cid=p["cid"], page=p["page"], part=p["part"],
                            duration=p["duration"]) for p in data["pages"]],
        )

    def search_videos(self, keyword: str, limit: int = 5) -> list[SearchResult]:
        data = self._get_json_wbi("/x/web-interface/wbi/search/type",
                                  {"search_type": "video", "keyword": keyword})
        results = []
        for item in (data.get("result") or [])[:limit]:
            results.append(SearchResult(
                bvid=item["bvid"],
                title=re.sub(r"</?em[^>]*>", "", item["title"]),
                up_name=item.get("author", ""),
                duration=item.get("duration", ""),
                play=item.get("play", 0),
                page_count=item.get("videos", 1),
            ))
        return results

    def get_subtitles(self, bvid: str, cid: int) -> list[SubtitleEntry]:
        data = self._get_json_wbi("/x/player/wbi/v2",
                                  {"bvid": validate_bvid(bvid), "cid": cid})
        subs = (data.get("subtitle") or {}).get("subtitles") or []
        return [SubtitleEntry(lan=s["lan"], lan_doc=s.get("lan_doc", ""),
                              url=s["subtitle_url"], ai_status=s.get("ai_status", 0))
                for s in subs if s.get("subtitle_url")]

    def get_audio_streams(self, bvid: str, cid: int) -> list[AudioStreamInfo]:
        data = self._get_json_wbi("/x/player/wbi/playurl",
                                  {"bvid": validate_bvid(bvid), "cid": cid, "fnval": 16})
        dash = data.get("dash") or {}
        return [AudioStreamInfo(url=a["baseUrl"], bandwidth=a.get("bandwidth", 0))
                for a in dash.get("audio") or [] if a.get("baseUrl")]

    def resolve_b23(self, short_url: str) -> str:
        resp = self._request("GET", short_url, headers=self._headers)
        final = resp.url
        if "b23.tv" in final:
            raise BiliApiError("b23.tv 短链解析失败，请提供完整链接或 BV 号")
        return final
