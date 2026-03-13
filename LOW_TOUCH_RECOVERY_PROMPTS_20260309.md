# Low-Touch Recovery Prompts

Updated: 2026-03-09

Use these after closing all old `P02~P10` windows.
This pack minimizes operator effort: only 4 worker windows.

## Why this is safe

- `run_responses_wave.py` is resumable per `target_id`.
- Partial batches can be rerun safely.
- Already-completed targets inside a batch are skipped automatically.
- The recent parser / stance fixes are already patched into the repo.

## Shared Facts

- Repo: `C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
- `run_id`: `run_full_20260222_192855`
- `session_id`: `salon_leishen_full_20260309_01`
- relay base URL: `https://www.leishen-ai.cn/openai`
- model: `gpt-5.4`
- provider label: `中轉站_leishen_gpt`
- `gpt-5.4` is live-verified even though `/models` may not list it
- If you are using an already-live old Mac window with working relay access, you may skip bootstrap

## M01

```text
你現在是 Vertex ai LM POEMS 的 recovery 窗口 M01。
直接執行，不要分析，不要規劃，不要問問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 任務：只補完 `craft_pass batch_010`

執行規則
1. 進入專案根目錄。
2. 若是 fresh shell / 新窗口，先執行：
   `python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若 `python3` 不存在，就改用 `python`。
3. 然後只執行：
   `python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id craft_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_010`
4. 完成後只回報：`completed_batches`、`failed_batches`、是否還有人工處理。
```

## M02

```text
你現在是 Vertex ai LM POEMS 的 recovery 窗口 M02。
直接執行，不要分析，不要規劃，不要問問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 任務：補完整個 `theme_pass`

執行規則
1. 進入專案根目錄。
2. 若是 fresh shell / 新窗口，先執行：
   `python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若 `python3` 不存在，就改用 `python`。
3. 然後只執行：
   `python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_001 batch_002 batch_003 batch_004 batch_005 batch_006 batch_007 batch_008 batch_009 batch_010 batch_011`
4. 完成後只回報：`completed_batches`、`failed_batches`、是否還有人工處理。
```

## M03

```text
你現在是 Vertex ai LM POEMS 的 recovery 窗口 M03。
直接執行，不要分析，不要規劃，不要問問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 任務：補完整個 `counter_reading_pass`

執行規則
1. 進入專案根目錄。
2. 若是 fresh shell / 新窗口，先執行：
   `python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若 `python3` 不存在，就改用 `python`。
3. 然後只執行：
   `python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id counter_reading_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_001 batch_002 batch_003 batch_004 batch_005 batch_006 batch_007 batch_008 batch_009 batch_010 batch_011`
4. 完成後只回報：`completed_batches`、`failed_batches`、是否還有人工處理。
```

## M04

```text
你現在是 Vertex ai LM POEMS 的 recovery 窗口 M04。
直接執行，不要分析，不要規劃，不要問問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 任務：補完整個 `revision_synthesis_pass`

執行規則
1. 進入專案根目錄。
2. 若是 fresh shell / 新窗口，先執行：
   `python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若 `python3` 不存在，就改用 `python`。
3. 然後只執行：
   `python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id revision_synthesis_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_001 batch_002 batch_003 batch_004 batch_005 batch_006 batch_007 batch_008 batch_009 batch_010 batch_011`
4. 完成後只回報：`completed_batches`、`failed_batches`、是否還有人工處理。
```

## Finalizer

Use this only after `M01~M04` are all done.

```text
你現在是 Vertex ai LM POEMS 的收尾窗口。
直接執行，不要分析，不要規劃，不要問問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`

執行規則
1. 進入專案根目錄。
2. 若 `python3` 不存在，就改用 `python`。
3. 依序執行：
   `python3 backend/scripts/review_session_status.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01`
   `python3 backend/scripts/merge_review_waves.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01`
   `python3 backend/scripts/review_session_status.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01`
4. 完成後只回報：
   - 每個 wave 的 full / partial / missing 狀態
   - consensus_report 是否 ready
   - 是否仍有 failed_batches 需要補跑
```
