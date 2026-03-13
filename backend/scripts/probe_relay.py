from __future__ import annotations

import argparse
import json
import ssl
import sys
from pathlib import Path
from urllib import request
from urllib.parse import urlparse

import certifi


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.relay_profile import resolve_api_key, resolve_base_url  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the configured OpenAI-compatible relay")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--base-url-file", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-file", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--expect-model", default="")
    parser.add_argument("--show-first", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = resolve_base_url(cli_value=args.base_url, base_url_file=args.base_url_file)
    api_key = resolve_api_key(api_key=args.api_key, api_key_file=args.api_key_file)
    if not base_url:
        raise SystemExit("[error] missing base URL")
    if not api_key:
        raise SystemExit("[error] missing API key")

    endpoint = base_url.rstrip("/") + "/models"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    req = request.Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "vertex-poems-relay-probe/0.1",
        },
        method="GET",
    )
    with request.urlopen(req, timeout=float(args.timeout), context=ssl_context) as response:
        payload = json.loads(response.read().decode("utf-8"))

    models = payload.get("data") if isinstance(payload, dict) else []
    model_ids = [str(item.get("id") or "").strip() for item in models if isinstance(item, dict) and str(item.get("id") or "").strip()]
    if args.expect_model and str(args.expect_model).strip() not in model_ids:
        raise SystemExit(f"[error] expected model not found: {args.expect_model}")
    parsed = urlparse(base_url)
    summary = {
        "base_url": f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}" if parsed.netloc else base_url,
        "models_count": len(model_ids),
        "first_models": model_ids[: max(int(args.show_first), 0)],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
