from __future__ import annotations

import json
import os
import stat
from pathlib import Path


RELAY_CONFIG_DIR = Path.home() / ".config" / "opencode"
DEFAULT_RELAY_KEY_PATH = RELAY_CONFIG_DIR / "relay_api_key"
DEFAULT_RELAY_BASE_URL_PATH = RELAY_CONFIG_DIR / "relay_base_url"
DEFAULT_OPENCODE_CONFIG_PATH = RELAY_CONFIG_DIR / "opencode.json"


def _read_text_if_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_opencode_openai_options(config_path: Path = DEFAULT_OPENCODE_CONFIG_PATH) -> dict[str, str]:
    if not config_path.is_file():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    provider_map = payload.get("provider")
    if not isinstance(provider_map, dict):
        return {}
    openai_provider = provider_map.get("openai")
    if not isinstance(openai_provider, dict):
        return {}
    options = openai_provider.get("options")
    if not isinstance(options, dict):
        return {}
    return {
        "base_url": str(options.get("baseURL") or "").strip(),
        "api_key": str(options.get("apiKey") or "").strip(),
    }


def resolve_base_url(cli_value: str = "", base_url_file: str = "", env: dict[str, str] | None = None) -> str:
    env_map = env or os.environ
    direct = str(cli_value or "").strip()
    if direct:
        return direct
    env_value = str(env_map.get("OPENAI_BASE_URL") or "").strip()
    if env_value:
        return env_value
    file_value = str(base_url_file or env_map.get("OPENAI_BASE_URL_FILE") or "").strip()
    if file_value:
        loaded = _read_text_if_file(Path(file_value).expanduser())
        if loaded:
            return loaded
    loaded = _read_text_if_file(DEFAULT_RELAY_BASE_URL_PATH)
    if loaded:
        return loaded
    return load_opencode_openai_options().get("base_url", "")


def resolve_api_key(api_key: str = "", api_key_file: str = "", env: dict[str, str] | None = None) -> str:
    env_map = env or os.environ
    direct = str(api_key or "").strip()
    if direct:
        return direct
    env_value = str(env_map.get("OPENAI_API_KEY") or "").strip()
    if env_value:
        return env_value
    file_value = str(api_key_file or env_map.get("OPENAI_API_KEY_FILE") or "").strip()
    if file_value:
        loaded = _read_text_if_file(Path(file_value).expanduser())
        if loaded:
            return loaded
    loaded = _read_text_if_file(DEFAULT_RELAY_KEY_PATH)
    if loaded:
        return loaded
    return load_opencode_openai_options().get("api_key", "")


def ensure_relay_config_dir(config_dir: Path = RELAY_CONFIG_DIR) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def write_secret_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value).strip() + chr(10), encoding="utf-8")
    if os.name != "nt":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def write_relay_home_files(
    base_url: str,
    api_key: str,
    key_path: Path = DEFAULT_RELAY_KEY_PATH,
    base_url_path: Path = DEFAULT_RELAY_BASE_URL_PATH,
) -> dict[str, str]:
    ensure_relay_config_dir(key_path.parent)
    write_secret_file(key_path, api_key)
    write_secret_file(base_url_path, base_url)
    return {
        "api_key_file": str(key_path),
        "base_url_file": str(base_url_path),
    }


def sync_opencode_openai_provider(
    base_url: str,
    api_key: str,
    model: str = "openai/gpt-5.4",
    config_path: Path = DEFAULT_OPENCODE_CONFIG_PATH,
) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object]
    if config_path.is_file():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        payload = existing if isinstance(existing, dict) else {}
    else:
        payload = {}
    payload.setdefault("$schema", "https://opencode.ai/config.json")
    enabled_providers = payload.get("enabled_providers")
    if not isinstance(enabled_providers, list):
        enabled_providers = []
    if "openai" not in enabled_providers:
        enabled_providers.append("openai")
    payload["enabled_providers"] = enabled_providers
    payload.setdefault("model", model)
    provider_map = payload.get("provider")
    if not isinstance(provider_map, dict):
        provider_map = {}
    openai_provider = provider_map.get("openai")
    if not isinstance(openai_provider, dict):
        openai_provider = {}
    options = openai_provider.get("options")
    if not isinstance(options, dict):
        options = {}
    options["baseURL"] = str(base_url).strip()
    options["apiKey"] = str(api_key).strip()
    openai_provider["options"] = options
    provider_map["openai"] = openai_provider
    payload["provider"] = provider_map
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    return config_path
