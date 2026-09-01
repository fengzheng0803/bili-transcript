"""配置加载：CLI > env > config.json > 默认值（规格 §5）。"""
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class Config:
    bili_cookie: str = ""
    dep_dir: Path = Path("~/bilibili-dep").expanduser()
    asr_default: str = "cloud"
    cloud_base_url: str = "https://api.siliconflow.cn/v1"
    cloud_api_key: str = ""
    cloud_model: str = "FunAudioLLM/SenseVoiceSmall"
    local_model_size: str = "medium"
    local_device: str = "cpu"
    local_compute_type: str = "int8"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"


ENV_KEYS = {
    "bili_cookie": "BILI_COOKIE",
    "dep_dir": "BILI_DEP_DIR",
    "asr_default": "BILI_ASR",
    "cloud_base_url": "BILI_ASR_BASE_URL",
    "cloud_api_key": "BILI_ASR_API_KEY",
    "cloud_model": "BILI_ASR_MODEL",
    "local_model_size": "BILI_ASR_LOCAL_MODEL_SIZE",
    "llm_base_url": "BILI_LLM_BASE_URL",
    "llm_api_key": "BILI_LLM_API_KEY",
    "llm_model": "BILI_LLM_MODEL",
}


def _json_config_paths() -> list[Path]:
    """查找顺序：项目根 config.json → ~/.config/bili-transcript/config.json（先找到者优先）。"""
    return [Path("config.json"), Path("~/.config/bili-transcript/config.json").expanduser()]


def _apply(cfg: Config, data: dict) -> None:
    bili = data.get("bilibili") or {}
    if bili.get("cookie"):
        cfg.bili_cookie = bili["cookie"]
    if "dep_dir" in data:
        cfg.dep_dir = data["dep_dir"]
    asr = data.get("asr") or {}
    if asr.get("default"):
        cfg.asr_default = asr["default"]
    cloud = asr.get("cloud") or {}
    if cloud.get("base_url"):
        cfg.cloud_base_url = cloud["base_url"]
    if cloud.get("api_key"):
        cfg.cloud_api_key = cloud["api_key"]
    if cloud.get("model"):
        cfg.cloud_model = cloud["model"]
    local = asr.get("local") or {}
    if local.get("model_size"):
        cfg.local_model_size = local["model_size"]
    if local.get("device"):
        cfg.local_device = local["device"]
    if local.get("compute_type"):
        cfg.local_compute_type = local["compute_type"]
    llm = data.get("llm") or {}
    if llm.get("base_url"):
        cfg.llm_base_url = llm["base_url"]
    if llm.get("api_key"):
        cfg.llm_api_key = llm["api_key"]
    if llm.get("model"):
        cfg.llm_model = llm["model"]


def load_config(cli: Optional[Any] = None) -> Config:
    cfg = Config()
    for path in _json_config_paths():
        if path.is_file():
            _apply(cfg, json.loads(path.read_text(encoding="utf-8")))
            break
    for field_name, env in ENV_KEYS.items():
        if os.environ.get(env):
            setattr(cfg, field_name, os.environ[env])
    if cli is not None and getattr(cli, "asr", None):
        cfg.asr_default = cli.asr
    if isinstance(cfg.dep_dir, str):
        cfg.dep_dir = Path(cfg.dep_dir).expanduser()
    return cfg
