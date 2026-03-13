# Parallel Window Prompts

Updated: 2026-03-09

Use these prompts by opening separate OpenCode windows and pasting one full block into each window.

## Shared Facts

- Repo: `C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
- `run_id`: `run_full_20260222_192855`
- `session_id`: `salon_leishen_full_20260309_01`
- relay base URL: `https://www.leishen-ai.cn/openai`
- model: `gpt-5.4`
- provider label: `中轉站_leishen_gpt`
- `gpt-5.4` is live-verified even though `/models` may not list it
- Existing old Mac windows seem to keep usable relay access for about another 24h; those windows can assist immediately
- Do not paste the same prompt into two windows
- Do not run final merge/status steps inside these worker windows

## Python Note

- Inside each prompt, `<PY>` means: use `python3` if available, otherwise use `python`.

## P01

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P01。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：finish the last missing craft batch
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id craft_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_011`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P02

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P02。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run theme_pass batches 001-004
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_001 batch_002 batch_003 batch_004`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P03

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P03。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run theme_pass batches 005-008
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_005 batch_006 batch_007 batch_008`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P04

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P04。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run theme_pass batches 009-011
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_009 batch_010 batch_011`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P05

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P05。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run counter_reading_pass batches 001-004
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id counter_reading_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_001 batch_002 batch_003 batch_004`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P06

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P06。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run counter_reading_pass batches 005-008
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id counter_reading_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_005 batch_006 batch_007 batch_008`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P07

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P07。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run counter_reading_pass batches 009-011
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id counter_reading_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_009 batch_010 batch_011`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P08

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P08。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run revision_synthesis_pass batches 001-004
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id revision_synthesis_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_001 batch_002 batch_003 batch_004`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P09

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P09。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run revision_synthesis_pass batches 005-008
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id revision_synthesis_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_005 batch_006 batch_007 batch_008`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## P10

```text
你現在是 Vertex ai LM POEMS 的並發執行窗口 P10。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- relay base URL：`https://www.leishen-ai.cn/openai`
- model：`gpt-5.4`
- provider_label：`中轉站_leishen_gpt`
- 重要：`gpt-5.4` 雖然可能沒列在 `/models`，但已 live 驗證可用
- 你的唯一任務：run revision_synthesis_pass batches 009-011
- 不要執行和其他窗口重疊的 batch
- 不要在本窗口執行 `merge_review_waves.py` 或最後的 `review_session_status.py`

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 若你是 fresh shell / 新窗口，且這台機器尚未完成 relay bootstrap，先執行：
   `<PY> backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
   若你是已在跑且 relay 正常的舊 Mac 窗口，可直接跳到下一步
4. 然後只執行這條主命令：
   `<PY> backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id revision_synthesis_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai batch_009 batch_010 batch_011`
5. 如果命令顯示某些 batch 已完成或 `job_count=0`，把它視為正常，不要重跑其他未分配批次。
6. 完成後只回報三件事：
   - `completed_batches`
   - `failed_batches`
   - 是否需要人工處理

```

## Finalizer

Use this only after all worker windows are done.

```text
你現在是 Vertex ai LM POEMS 的收尾窗口。
直接執行，不要先問我問題。

固定事實
- 專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`（如果你在 Mac，改用對應的 OneDrive 同步路徑）
- run_id：`run_full_20260222_192855`
- session_id：`salon_leishen_full_20260309_01`
- 這個窗口只做收尾，不跑新的 review batch

執行規則
1. 進入專案根目錄。
2. 決定可用的 Python 指令：優先 `python3`，否則 `python`；以下用 `<PY>` 指代。
3. 依序執行：
   - `<PY> backend/scripts/review_session_status.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01`
   - `<PY> backend/scripts/merge_review_waves.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01`
   - `<PY> backend/scripts/review_session_status.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01`
4. 完成後只回報：
   - 每個 wave 的 completed_batches / expected_batches
   - consensus_report 是否 ready
   - 是否還有失敗批次需要補跑
```
