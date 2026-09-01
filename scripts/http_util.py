"""统一 HTTP 请求层：重试退避与连续请求限流（规格 §4）。"""
import time
from typing import Callable, Optional

import requests

BASE_INTERVAL = 0.5   # 连续请求基础间隔（秒）
MAX_INTERVAL = 2.0    # 连续请求间隔上限（秒）
MAX_RETRIES = 3       # 最多重试次数


class RiskControlError(RuntimeError):
    """B站风控响应（HTTP 412 或 JSON code=-412/-352）。"""


def backoff_sequence(scenario: str) -> list[float]:
    """重试等待序列：normal → [1,2,4]s；risk → [3,6,12]s。"""
    if scenario == "risk":
        return [3.0, 6.0, 12.0]
    return [1.0, 2.0, 4.0]


class RateLimiter:
    """连续请求间隔：失败翻倍至上限，成功后归位到基础间隔。"""

    def __init__(self, base: float = BASE_INTERVAL, max_: float = MAX_INTERVAL,
                 sleep: Callable[[float], None] = time.sleep):
        self._base = base
        self._max = max_
        self._sleep = sleep
        self._current = base

    def wait(self) -> None:
        self._sleep(self._current)

    def on_success(self) -> None:
        self._current = self._base

    def on_failure(self) -> None:
        self._current = min(self._current * 2, self._max)


_limiter = RateLimiter()


def request_with_retry(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    files: Optional[dict] = None,
    data: Optional[dict] = None,
    json: Optional[dict] = None,
    timeout: int = 30,
    sleep: Callable[[float], None] = time.sleep,
    limiter: Optional[RateLimiter] = None,
    risk_check: Optional[Callable] = None,
) -> requests.Response:
    """带退避重试的请求。普通失败 [1,2,4]s、风控 [3,6,12]s，3 次封顶。

    risk_check: 对响应做风控判定（如 JSON code=-412），命中则走 risk 退避。
    """
    limiter = limiter or _limiter
    for attempt in range(MAX_RETRIES + 1):
        limiter.wait()
        try:
            resp = requests.request(method, url, headers=headers, params=params,
                                    files=files, data=data, json=json, timeout=timeout)
        except requests.RequestException:
            if attempt == MAX_RETRIES:
                raise
            limiter.on_failure()
            sleep(backoff_sequence("normal")[attempt])
            continue
        risky = resp.status_code == 412 or (risk_check is not None and risk_check(resp))
        if risky or resp.status_code == 429 or resp.status_code >= 500:
            if attempt == MAX_RETRIES:
                if risky:
                    raise RiskControlError(f"风控拦截：{url}（状态 {resp.status_code}）")
                resp.raise_for_status()
            limiter.on_failure()
            sleep(backoff_sequence("risk" if risky else "normal")[attempt])
            continue
        limiter.on_success()
        return resp
    raise RuntimeError("unreachable")  # pragma: no cover
