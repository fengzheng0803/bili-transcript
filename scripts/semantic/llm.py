"""语义阶段 LLM 调用：全文一次输入，输出结构化 markdown 正文。"""
import requests

from http_util import request_with_retry

SYSTEM_PROMPT = (
    "你是视频内容整理助手。给定视频标题和带时间戳的文字稿，请输出结构化 markdown 正文：\n"
    "1. 按主题划分章节，每节标题用「### 序号. 章节标题 [HH:MM:SS-HH:MM:SS]」形式，"
    "标题归纳该节主题\n"
    "2. 剔除广告、卖课卖书、求三连关注、片头片尾寒暄等与标题无关的内容\n"
    "3. 保留原文时间戳信息，正文忠实于原文字，不要编造或补充原文没有的内容\n"
    "只输出 markdown 正文，不要输出任何解释。"
)


class LlmError(Exception):
    """LLM 调用失败。"""


def structure_transcript(text: str, video_title: str, base_url: str, api_key: str,
                         model: str, request=request_with_retry) -> str:
    """全文一次调用：返回整理后的 markdown 正文。失败抛 LlmError。"""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"视频标题：{video_title}\n\n文字稿：\n{text}"},
        ],
        "temperature": 0,
    }
    try:
        resp = request("POST", f"{base_url.rstrip('/')}/chat/completions",
                       headers={"Authorization": f"Bearer {api_key}"},
                       json=payload, timeout=120)
    except requests.RequestException as exc:
        raise LlmError(f"请求失败：{exc}") from exc
    if resp.status_code == 401:
        raise LlmError("API key 无效（401）")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("message", "")
        except Exception:
            detail = resp.text[:200]
        raise LlmError(f"HTTP {resp.status_code}：{detail or '（无详情）'}")
    return resp.json()["choices"][0]["message"]["content"].strip()
