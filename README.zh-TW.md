# Vertex AI LM POEMS 中文說明（正式）

本檔為中文入口；英文主文件以 `README.md` 為準。
舊入口別名：`中文說明.md`（內容已導向本檔）。

## 版本語意

- API 服務版本：`0.1.x`（runtime 服務基線版本）。
- 目前預設資料範圍：`v0.3.1`（僅 `runtime_workspaces/` 且已寫入 SQLite 的 run）。
- 可視化頁面的 `V1~V6` 是樣式變體，不是 pipeline 版本。

## 穩定入口

- 主介面: `http://127.0.0.1:8010/`
- 技能樹索引: `http://127.0.0.1:8010/visualizations`
- 最新 full: `http://127.0.0.1:8010/visualization/latest?mode=full`
- 最新 smoke: `http://127.0.0.1:8010/visualization/latest?mode=smoke`

## 啟動（macOS）

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 scripts/start_local.py --reload
```

`requirements.txt` 只含 runtime 依賴；要執行 `/run/*` 再安裝 `requirements-pipeline.txt`。

日常啟動（已建好 `.venv`）：

```bash
cd "/Users/liujiugao/Library/CloudStorage/OneDrive-個人/代碼庫與projects/vertex ai LM POEMS"
git pull
cd backend
source .venv/bin/activate
python3 scripts/start_local.py --reload
```

若你在 `.venv` 內遇到 `No module named uvicorn`：

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/start_local.py --reload
```

若 `pip` 顯示 `pypi.org` 憑證主機名不匹配，這是本機網路/代理憑證問題，需先修正網路設定。

若執行 `/run/smoke` 或 `/run/full` 出現 `Missing dependency: vertexai`，代表目前啟動用的 Python 尚未裝齊依賴，請在同一環境執行：

```bash
cd backend
python3 -m pip install -r requirements-pipeline.txt
```

補充：專案根目錄的 `.env` 會在啟動時自動讀取（若 shell 尚未手動 export 同名變數）。

## 執行 Pipeline（重建引用覆蓋）

在 `backend/` 目錄下執行：

```bash
# smoke（快速檢查）
python3 scripts/trigger_api_run.py --mode smoke --iterations 2 --sample-size 20 --max-stage-jump 2 --out logs/last_smoke_result.json

# full（v0.3.1 建議覆蓋配置）
python3 scripts/trigger_api_run.py --mode full --max-stage-jump 2 --out logs/last_full_result.json
```

注意：
- 對 500+ 語料，不建議使用舊的 full 參數（例如 `--iterations 6 --sample-size 30`），通常會造成引用覆蓋過低。
- 若要手動指定 full 參數，建議從 `--iterations 30 --sample-size 50` 起步再調整。

## 目錄結構（整理後）

- `backend/`: backend API + static frontend
- `data/`: local SQLite data
- `runtime_workspaces/`: active API pipeline outputs
- `references/`: preserved reference materials
- `recycle_bin/`: recycle/quarantine before final delete
- `sample_poems/`: sample corpus placeholder

## 參考資料分層

- `references/v0.1_notebookLM/`: NotebookLM era (v0.1, tracked)
- `references/v0.2_api_results/runs/`: API era outputs (v0.2, local-only and gitignored)
- `references/legacy_handoff/`: previous-window handoff docs (local-only and gitignored)

## 回收策略

- 待刪檔案先移到 `recycle_bin/`，不直接硬刪。
- 確認不需回復後，再做一次性最終刪除。

## 公開前檢查

- 確認 `.github/ISSUE_TEMPLATE/config.yml` 的安全回報連結可用且符合專案政策。
- 確認未追蹤任何本地私有資料（語料、執行輸出、DB、logs、憑證）。
- 至少檢查 `/health`、`/runs`、`/graph`、`/visualizations` 可用。

## 後續改進目標

- 後續前後端優化目標與前端待決策項目，請見 `IMPROVEMENT_ROADMAP.md`。

## 覆蓋率審計（分辨 500+ 掃描與引用覆蓋）

在 `backend/` 目錄執行：

```bash
python3 scripts/audit_run.py --run-id run_full_20260222_192855 --out logs/run_audit.json
```

API 也可直接查：

- `GET /runs/{run_id}/audit`
- `GET /runs` 的 `stats` 在可用時也會包含掛載覆蓋欄位（`mounting_full_*`, `mounting_seed_*`）。

## Fill 抽樣驗收閘門（升格前必做）

在 `backend/` 目錄執行：

```bash
python3 scripts/sample_fill_quality.py --run-id run_full_20260222_192855 --sample-size 40 --seed 42 --out-prefix logs/fill_quality_192855
```

輸出：
- `logs/fill_quality_192855.json`
- `logs/fill_quality_192855.md`

欄位解讀：
- `full_matches_from_poem_mounting_full`：full 掛載總匹配數。
- `seed_matches_from_poem_mounting_seed`：seed 初始匹配數。
- `fill_matches_from_fill_assignments`：fill 補齊匹配數（通常等於 `full - seed`）。
- 建議通過抽樣驗收後，才把 fill 結果升格為 citations。
