from __future__ import annotations

import re


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower())
    return value.strip("_") or "unknown"


def resolve_review_source(provider: str, model: str) -> dict[str, str]:
    provider_raw = str(provider or "").strip()
    model_raw = str(model or "").strip()
    provider_key = provider_raw.lower()
    model_key = model_raw.lower()

    if (provider_key == "relay-openai-compatible" or "leishen" in provider_key) and model_key.startswith("gpt-5"):
        return {
            "source_label": "中轉站_leishen_gpt",
            "source_nickname": "雷神",
            "source_family": "relay_leishen_gpt",
            "source_status": "active",
            "source_quality_band": "unreviewed",
            "source_weight_bucket": "default",
        }

    if provider_key == "codex-local" and model_key == "deterministic-rubric-v1":
        return {
            "source_label": "本地_deterministic_rubric_v1",
            "source_nickname": "本地規則稿",
            "source_family": "local_deterministic_rubric",
            "source_status": "active",
            "source_quality_band": "unreviewed",
            "source_weight_bucket": "default",
        }

    return {
        "source_label": f"{_slug(provider_raw)}__{_slug(model_raw)}",
        "source_nickname": model_raw or provider_raw or "unknown",
        "source_family": _slug(provider_raw),
        "source_status": "active",
        "source_quality_band": "unreviewed",
        "source_weight_bucket": "default",
    }
