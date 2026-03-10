# Relay Bootstrap

Updated: 2026-03-09

## Verified Base URL

- `https://www.leishen-ai.cn/openai`

## Home Files To Keep In Sync

- `~/.config/opencode/opencode.json`
- `~/.config/opencode/relay_api_key`
- `~/.config/opencode/relay_base_url`

`run_responses_wave.py` now resolves relay settings in this order:

1. CLI args
2. env vars
3. `~/.config/opencode/relay_base_url` / `~/.config/opencode/relay_api_key`
4. `~/.config/opencode/opencode.json`

## PC Status

- `bootstrap_relay_home.py` has been run successfully on the PC.
- `probe_relay.py` reached `/models` successfully.
- Live `/responses` smoke call succeeded with `gpt-5.3-codex`.
- Live `/responses` smoke call also succeeded with `gpt-5.4`, even though `/models` does not currently list it.
- `run_responses_wave.py` completed a 1-job smoke import on session `relay_smoke_20260308_01`.

## Mac Bootstrap

If you are using a fresh Mac shell or a new Mac window, run from the repo root:

```bash
python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai
python3 backend/scripts/probe_relay.py --base-url https://www.leishen-ai.cn/openai
opencode models openai
```

If you are using an already-live old Mac window that still has a working relay session, you can skip this preflight and let that window assist directly for the remaining experience-card window.

If the Mac still has old provider values in `~/.config/opencode/opencode.json`, update that file first, or pass the current relay values explicitly to `bootstrap_relay_home.py`.

## Project Smoke Test

From the repo root:

```bash
python3 backend/scripts/run_responses_wave.py   --run-id run_full_20260222_192855   --session-id relay_smoke_20260308_01   --wave-id craft_pass   --batch-id batch_001   --model gpt-5.3-codex   --reasoning-effort xhigh   --max-jobs 1   --sleep-seconds 0
```

## Notes

- Temporary assist note: existing Mac old windows appear to retain usable relay access for roughly another 24h, so they can temporarily join the parallel run pool.
- `opencode models openai` is a provider-level connectivity check.
- In this CLI version, `opencode run` may still require an existing session; a `Session not found` error is not the same as relay auth failure.
- Do not store the API key inside the repo or any synced note.
