# Emergency Recovery Prompts

Use these only for windows that stalled, errored, or stopped early.

Why restart is safe: `run_responses_wave.py` is resumable and skips already-completed `target_id`s inside each batch.

Recommended operator action: pause all currently-bad windows except any one that is visibly still writing fresh results right now. Then relaunch with the matching recovery prompt below.

## R02

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_001 batch_002 batch_003 batch_004`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R03

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_005 batch_006 batch_007 batch_008`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R04

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id theme_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_009 batch_010 batch_011`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R05

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id counter_reading_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_001 batch_002 batch_003 batch_004`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R06

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id counter_reading_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_005 batch_006 batch_007 batch_008`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R07

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id counter_reading_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_009 batch_010 batch_011`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R08

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id revision_synthesis_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_001 batch_002 batch_003 batch_004`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R09

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id revision_synthesis_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_005 batch_006 batch_007 batch_008`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R10

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id revision_synthesis_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_009 batch_010 batch_011`

完成後只回報：`completed_batches`、`failed_batches`。
```

## R11

```text
不要分析，不要規劃，不要問問題。直接執行。

專案根目錄：`C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS`
若是 fresh shell，先跑：
`python3 backend/scripts/bootstrap_relay_home.py --base-url https://www.leishen-ai.cn/openai`
若 `python3` 不存在，就改用 `python`。

然後只跑這條命令：
`python3 backend/scripts/run_responses_batch_group.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01 --wave-id craft_pass --model gpt-5.4 --reasoning-effort xhigh --provider-label 中轉站_leishen_gpt --base-url https://www.leishen-ai.cn/openai --continue-on-error batch_010`

完成後只回報：`completed_batches`、`failed_batches`。
```

