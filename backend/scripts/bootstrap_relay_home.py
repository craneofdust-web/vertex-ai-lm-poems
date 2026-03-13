from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.relay_profile import (  # noqa: E402
    DEFAULT_OPENCODE_CONFIG_PATH,
    DEFAULT_RELAY_BASE_URL_PATH,
    DEFAULT_RELAY_KEY_PATH,
    resolve_api_key,
    resolve_base_url,
    sync_opencode_openai_provider,
    write_relay_home_files,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap relay config files under ~/.config/opencode")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--base-url-file", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-file", default="")
    parser.add_argument("--model", default="openai/gpt-5.4")
    parser.add_argument("--skip-opencode-json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _mask_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc or parsed.path
    if not host:
        return ""
    scheme = parsed.scheme or "https"
    suffix = parsed.path.rstrip("/") if parsed.path and parsed.path != host else ""
    return f"{scheme}://{host}{suffix}"


def main() -> int:
    args = parse_args()
    base_url = resolve_base_url(cli_value=args.base_url, base_url_file=args.base_url_file)
    api_key = resolve_api_key(api_key=args.api_key, api_key_file=args.api_key_file)
    if not base_url:
        raise SystemExit("[error] missing base URL; pass --base-url / --base-url-file, set OPENAI_BASE_URL, create ~/.config/opencode/relay_base_url, or configure ~/.config/opencode/opencode.json")
    if not api_key:
        raise SystemExit("[error] missing API key; pass --api-key / --api-key-file, set OPENAI_API_KEY, create ~/.config/opencode/relay_api_key, or configure ~/.config/opencode/opencode.json")

    summary = {
        "base_url": _mask_base_url(base_url),
        "relay_api_key_path": str(DEFAULT_RELAY_KEY_PATH),
        "relay_base_url_path": str(DEFAULT_RELAY_BASE_URL_PATH),
        "opencode_config_path": str(DEFAULT_OPENCODE_CONFIG_PATH),
        "opencode_json_sync": not args.skip_opencode_json,
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    write_relay_home_files(base_url=base_url, api_key=api_key)
    if not args.skip_opencode_json:
        sync_opencode_openai_provider(base_url=base_url, api_key=api_key, model=str(args.model).strip())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
