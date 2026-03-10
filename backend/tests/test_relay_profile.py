from __future__ import annotations

import json
from pathlib import Path

from app import relay_profile


def test_load_opencode_openai_options_reads_base_url_and_api_key(tmp_path: Path) -> None:
    config_path = tmp_path / "opencode.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": {
                    "openai": {
                        "options": {
                            "baseURL": "https://relay.example/openai/v1",
                            "apiKey": "secret-value",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    payload = relay_profile.load_opencode_openai_options(config_path)
    assert payload["base_url"] == "https://relay.example/openai/v1"
    assert payload["api_key"] == "secret-value"


def test_resolve_prefers_explicit_files_over_opencode_defaults(tmp_path: Path, monkeypatch) -> None:
    relay_dir = tmp_path / ".config" / "opencode"
    relay_dir.mkdir(parents=True)
    key_path = relay_dir / "relay_api_key"
    key_path.write_text("file-key\n", encoding="utf-8")
    base_url_path = relay_dir / "relay_base_url"
    base_url_path.write_text("https://file.example/openai/v1\n", encoding="utf-8")
    monkeypatch.setattr(relay_profile, "DEFAULT_RELAY_KEY_PATH", key_path)
    monkeypatch.setattr(relay_profile, "DEFAULT_RELAY_BASE_URL_PATH", base_url_path)
    monkeypatch.setattr(
        relay_profile,
        "load_opencode_openai_options",
        lambda config_path=relay_profile.DEFAULT_OPENCODE_CONFIG_PATH: {
            "base_url": "https://config.example/openai/v1",
            "api_key": "config-key",
        },
    )
    assert relay_profile.resolve_base_url() == "https://file.example/openai/v1"
    assert relay_profile.resolve_api_key() == "file-key"
