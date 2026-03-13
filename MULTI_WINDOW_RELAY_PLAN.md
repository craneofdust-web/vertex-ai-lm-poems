# Multi-Window Relay Plan

Updated: 2026-03-09
Session: `salon_leishen_full_20260309_01`
Run: `run_full_20260222_192855`
Verified base URL: `https://www.leishen-ai.cn/openai`
Recommended model: `gpt-5.4` (verified live, though not listed in `/models`)

## Current Pending Snapshot

As checked on the PC:

- `craft_pass`: `10/11` complete, only `batch_011` still pending.
- `theme_pass`: `0/11` complete.
- `counter_reading_pass`: `0/11` complete.
- `revision_synthesis_pass`: `0/11` complete.


## Hidden Model Note

- `/models` currently lists up to `gpt-5`, `gpt-5-codex`, and `gpt-5.3-codex`, but a live `/responses` call with `gpt-5.4` has been verified on 2026-03-09.
- In other words: listing is stale; actual model acceptance is broader than the current announcement page.

## Temporary Mac Assist

- Existing old Mac windows appear to keep usable relay access for about another 24h.
- That means they can help as extra worker windows right now.
- Fresh Mac shells should still run `bootstrap_relay_home.py`, `probe_relay.py`, and `opencode models openai`; already-live old Mac windows can skip straight to their assigned worker command.

## Preflight

Run once on each machine before opening parallel windows, unless you are reusing an already-live old Mac window that already has working relay access:

```bash
python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai
python3 backend/scripts/probe_relay.py --base-url https://www.leishen-ai.cn/openai
opencode models openai
```

## Start Now: 4 Useful Windows

Window 1: finish the last missing craft batch

```bash
python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id craft_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_011
```

Window 2: run all `theme_pass` batches

```bash
python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --all-batches
```

Window 3: run all `counter_reading_pass` batches

```bash
python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id counter_reading_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --all-batches
```

Window 4: run all `revision_synthesis_pass` batches

```bash
python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id revision_synthesis_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --all-batches
```

## If You Want Even More Parallelism

Split one wave across several windows. Example for `theme_pass`:

Window A:

```bash
python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_001 batch_002 batch_003 batch_004
```

Window B:

```bash
python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_005 batch_006 batch_007 batch_008
```

Window C:

```bash
python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_009 batch_010 batch_011
```

You can apply the same `4 + 4 + 3` split to `counter_reading_pass` and `revision_synthesis_pass`.

## After All Windows Finish

Recompute status and consensus once to wash out concurrent summary-write noise:

```bash
python3 backend/scripts/review_session_status.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01
python3 backend/scripts/merge_review_waves.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01
python3 backend/scripts/review_session_status.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01
```

## Notes

- Do not run the exact same `wave_id + batch_id` pair in two windows.
- Concurrent writes mostly touch session summary files; the final rebuild above normalizes that.
- Wave outputs and batch outputs are file-separated, so this session is a good candidate for manual parallel windows.
