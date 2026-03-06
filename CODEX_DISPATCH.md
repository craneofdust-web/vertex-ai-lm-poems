# CODEX_DISPATCH（v0.3.1 修正批次）

更新日期：2026-03-05
發出者：外部審計（Claude Opus via Cowork）
目標窗口：**Codex 新執行窗**

---

## 0) 當前狀態摘要（你需要知道的）

- 主版本：`v0.3.1`
- 唯一有效 run：`run_full_20260222_192855`（40 nodes, 42 edges, 141 citations, 522 poems mounted）
- 最近一次 run（`run_full_20260223_101648`）**失敗**：`ModuleNotFoundError: No module named 'vertexai'`，只留下空殼。
- DB：`data/skill_web.db`（2.2MB），結構正常，數據只有 192855 那一批。
- `.env` 的 `PROJECT_ID` 目前是佔位值 `your-gcp-project-id`，無法跑 pipeline。
- **零測試檔**，零 CI。
- `main.py` 890 行，嚴重需要拆分。
- 前端 `app.js` 18K 單檔，功能完整但不可維護。

---

## 1) 任務清單（嚴格按順序執行）

### Phase 1：拆分 main.py（Priority A1）

**目標**：把 `backend/app/main.py`（890 行）拆成模組化結構。

**步驟**：
1. 建立 `backend/app/routes/` 目錄
2. 抽出以下路由模組：
   - `routes/graph.py`：`/graph`, `/node/{node_id}`, `/node/{node_id}/lineage`, `/search`
   - `routes/runs.py`：`/runs`, `/runs/{run_id}/audit`, `/run/smoke`, `/run/full`
   - `routes/visualization.py`：`/visualizations`, `/visualization/{run_id}/...`, `/visualization/latest`
   - `routes/health.py`：`/health`, `/`（首頁）
3. 建立 `backend/app/services/` 目錄，抽出可複用查詢邏輯：
   - `services/graph_service.py`：圖譜查詢、lineage 計算
   - `services/run_service.py`：run 列表、stats 計算、run_id 解析
4. `main.py` 只留 FastAPI app 初始化、middleware、mount、router include
5. **驗收**：所有現有端點行為不變。跑 `python -m compileall -q backend/app` 無錯。

**禁止事項**：
- 不要改任何端點的 URL 或回傳格式
- 不要改 schema.sql
- 不要動前端

---

### Phase 2：補基礎測試（Priority A4）

**目標**：建立最低限度的自動測試。

**步驟**：
1. 在 `backend/` 下建立 `tests/` 目錄
2. 加入 `conftest.py`：建立 in-memory SQLite 測試 DB，fixture 提供 test client
3. 寫以下測試（`tests/test_api.py`）：
   - `test_health`：GET `/health` → 200
   - `test_graph_empty`：空 DB 下 GET `/graph` → 回傳空結構（不 500）
   - `test_runs_empty`：空 DB 下 GET `/runs` → 回傳空列表
   - `test_ingest_and_graph`：匯入一個最小 mock run，然後驗證 `/graph`、`/runs`、`/node/{id}` 回傳正確
   - `test_search`：匯入後搜尋，驗證結果
   - `test_visualization_routes`：驗證 `/visualizations` 不 crash
4. 加入 `pytest` 和 `httpx` 到 `requirements.txt`（或 `requirements-dev.txt`）
5. **驗收**：`cd backend && python -m pytest tests/ -v` 全過。

**禁止事項**：
- 不要碰功能代碼（Phase 1 的結果不動）
- 不要加 CI workflow（那是後續）
- 測試不需要真 GCP 連線

---

### Phase 3：清理失敗 run 與環境修復

**目標**：清除無效產物，修復啟動流程。

**步驟**：
1. 把 `runtime_workspaces/run_full_20260223_101648/` 移到 `recycle_bin/`（這是失敗的空 run）
2. 確認 `backend/scripts/start_local.py` 在 `.venv` 缺 `vertexai` 時：
   - 仍能啟動 UI/讀取端點
   - 在觸發 `/run/*` 時給出清楚錯誤（不是 import crash）
3. 確認 `trigger_api_run.py` 在 `vertexai` 不存在時 fail-fast 並顯示 install hint
4. **驗收**：
   - `recycle_bin/` 裡有 `run_full_20260223_101648/`
   - `runtime_workspaces/` 裡只剩有效 run
   - `python3 backend/scripts/start_local.py` 在無 vertexai 環境下能正常啟動讀取端點

---

### Phase 4：requirements 整理

**目標**：讓依賴可重現。

**步驟**：
1. 從 `backend/` 根目錄分出：
   - `requirements.txt`：runtime 必要（fastapi, uvicorn, pydantic, aiosqlite 或 sqlite 相關）
   - `requirements-dev.txt`：測試和開發（pytest, httpx, ruff/flake8）
   - `requirements-pipeline.txt`：pipeline/生成相關（google-cloud-aiplatform, vertexai）
2. 更新 README 和 `start_local.py` 相應說明
3. **驗收**：`pip install -r requirements.txt` 後能啟動 backend；不含 vertexai 也能跑 UI。

---

### Phase 5：前端最小拆分（Optional, if time permits）

**目標**：把 `app.js`（18K）至少拆成邏輯模組。

**步驟**：
1. 分出 `graph-renderer.js`、`panel-manager.js`、`api-client.js`
2. 用 ES module import 串接
3. `index.html` 改用 `<script type="module">`
4. **驗收**：前端功能不變，瀏覽器 console 無錯。

---

## 2) 通用規則

- **每個 Phase 完成後 commit 一次**，commit message 用 `refactor:` / `test:` / `chore:` prefix。
- **不碰 pipeline 生成邏輯**（brainstorm_skill_webs.py、build_master_and_fill_mounting.py）。
- **不跑任何 Gemini API 調用**。
- **不改 `.env` 的值**（佔位值留著，那是給用戶自己填的）。
- **不碰 references/ 目錄**。
- 如遇到不確定的架構決定，**停下來寫註解說明選項**，不要自己決定。

---

## 3) 完成後交付物

Phase 完成後，更新此文件的狀態：

| Phase | 狀態 | Commit hash | 備註 |
|-------|------|-------------|------|
| 1. 拆分 main.py | ✅ 已完成 | `4b3ff4b` | main.py 890→36 行；routes/ 4 模組 + services/ 2 模組，共 1089 行；`compileall` 通過 |
| 2. 補基礎測試 | ✅ 已完成 | `10efed3` | `backend/tests/` 含 conftest.py + test_api.py（6 tests），含 mock ingest fixture |
| 3. 清理 + 環境修復 | ✅ 已完成 | `fa35197` | 失敗 run 已移至 `recycle_bin/`；vertexai 缺失時 start_local 可啟動、trigger_api_run fail-fast |
| 4. requirements 整理 | ✅ 已完成 | `58752dd` | 新增 `requirements-dev.txt`、`requirements-pipeline.txt`；CODEX_DISPATCH.md 同步 commit |
| 5. 前端拆分 | ✅ 已完成 | `c0e5c2b` | `app.js` 拆為 `static/modules/` 下 3 個 ES module；`index.html` 改用 `<script type="module">` |

### 外部審計補充（2026-03-06 by Claude Opus via Cowork）

**已驗證通過項目**：
- `python -m compileall -q backend/app` → 無錯誤
- main.py 確實從 890 行降到 36 行，僅保留 app init + middleware + router include
- routes/ 和 services/ 結構合理，責任劃分清晰
- 測試結構正確，含 mock ingest fixture，不需要真實 GCP 連線
- 失敗 run `run_full_20260223_101648` 已確認從 `runtime_workspaces/` 移出
- 前端 JS 拆分位於 `static/modules/`（非 `static/` 根目錄）

**殘留未提交變更（非 Codex 產出，屬 v0.3.1 早期工作）**：
- Modified: `CHANGELOG.md`（補充 v0.3.1 changelog entries）、`backend/app/ingest.py`（mounting stats 函數）、`backend/static/styles.css`（panel 佈局改進）
- Untracked: `HANDOFF.md`、`IMPROVEMENT_ROADMAP.md`、`backend/app/audit.py`、`backend/scripts/audit_run.py`、`backend/scripts/sample_fill_quality.py`、`CODEX_CONTROL_BRIEFING.md`
- 這些是 Codex dispatch 之前就存在但從未 commit 的文件，建議一次性提交
