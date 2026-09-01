from pathlib import Path
from types import SimpleNamespace

from config import Config, load_config


def test_defaults(monkeypatch):
    monkeypatch.setattr("config._json_config_paths", lambda: [])
    for env in ("BILI_COOKIE", "BILI_DEP_DIR", "BILI_ASR", "BILI_ASR_BASE_URL",
                "BILI_ASR_API_KEY", "BILI_ASR_MODEL", "BILI_ASR_LOCAL_MODEL_SIZE"):
        monkeypatch.delenv(env, raising=False)
    cfg = load_config()
    assert cfg.asr_default == "cloud"
    assert cfg.cloud_base_url == "https://api.siliconflow.cn/v1"
    assert cfg.cloud_model == "FunAudioLLM/SenseVoiceSmall"
    assert cfg.local_model_size == "medium"
    assert cfg.dep_dir == Path("~/bilibili-dep").expanduser()


def test_json_file_loaded(tmp_path, monkeypatch):
    proj = tmp_path / "config.json"
    proj.write_text('{"asr": {"default": "local"}}', encoding="utf-8")
    monkeypatch.setattr("config._json_config_paths", lambda: [proj])
    assert load_config().asr_default == "local"


def test_env_overrides_json(tmp_path, monkeypatch):
    proj = tmp_path / "config.json"
    proj.write_text('{"asr": {"cloud": {"model": "m-json"}}}', encoding="utf-8")
    monkeypatch.setattr("config._json_config_paths", lambda: [proj])
    monkeypatch.setenv("BILI_ASR_MODEL", "m-env")
    assert load_config().cloud_model == "m-env"


def test_cli_overrides_env(monkeypatch):
    monkeypatch.setattr("config._json_config_paths", lambda: [])
    for env in ("BILI_COOKIE", "BILI_DEP_DIR", "BILI_ASR", "BILI_ASR_BASE_URL",
                "BILI_ASR_API_KEY", "BILI_ASR_MODEL", "BILI_ASR_LOCAL_MODEL_SIZE"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("BILI_ASR", "local")
    cli = SimpleNamespace(asr="cloud")
    assert load_config(cli).asr_default == "cloud"


def test_dep_dir_expands_tilde(tmp_path, monkeypatch):
    proj = tmp_path / "config.json"
    proj.write_text('{"dep_dir": "~/custom-dep"}', encoding="utf-8")
    monkeypatch.setattr("config._json_config_paths", lambda: [proj])
    assert load_config().dep_dir == Path("~/custom-dep").expanduser()


def test_project_root_beats_user_config(tmp_path, monkeypatch):
    proj = tmp_path / "config.json"
    proj.write_text('{"asr": {"default": "local"}}', encoding="utf-8")
    user = tmp_path / "user.json"
    user.write_text('{"asr": {"default": "cloud"}}', encoding="utf-8")
    monkeypatch.setattr("config._json_config_paths", lambda: [proj, user])
    assert load_config().asr_default == "local"


def test_bilibili_cookie_and_nested_fields(tmp_path, monkeypatch):
    proj = tmp_path / "config.json"
    proj.write_text(
        '{"bilibili": {"cookie": "SESSDATA=abc"}, "asr": {"local": {"model_size": "large-v3", "compute_type": "float32"}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("config._json_config_paths", lambda: [proj])
    cfg = load_config()
    assert cfg.bili_cookie == "SESSDATA=abc"
    assert cfg.local_model_size == "large-v3"
    assert cfg.local_compute_type == "float32"


LLM_ENVS = ("BILI_LLM_BASE_URL", "BILI_LLM_API_KEY", "BILI_LLM_MODEL")


def test_llm_defaults(monkeypatch):
    monkeypatch.setattr("config._json_config_paths", lambda: [])
    for env in LLM_ENVS:
        monkeypatch.delenv(env, raising=False)
    cfg = load_config()
    assert cfg.llm_api_key == ""
    assert cfg.llm_base_url == "https://api.deepseek.com"
    assert cfg.llm_model == "deepseek-chat"


def test_llm_block_loaded(tmp_path, monkeypatch):
    proj = tmp_path / "config.json"
    proj.write_text(
        '{"llm": {"base_url": "https://api.deepseek.com", "api_key": "sk-1", "model": "deepseek-chat"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("config._json_config_paths", lambda: [proj])
    cfg = load_config()
    assert cfg.llm_api_key == "sk-1"
    assert cfg.llm_model == "deepseek-chat"
    assert cfg.llm_base_url == "https://api.deepseek.com"


def test_llm_env_overrides_json(tmp_path, monkeypatch):
    proj = tmp_path / "config.json"
    proj.write_text('{"llm": {"api_key": "sk-json"}}', encoding="utf-8")
    monkeypatch.setattr("config._json_config_paths", lambda: [proj])
    monkeypatch.setenv("BILI_LLM_API_KEY", "sk-env")
    assert load_config().llm_api_key == "sk-env"
