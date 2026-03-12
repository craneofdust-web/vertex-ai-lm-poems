# HANDOFF（v0.3.1）

更新日期：2026-02-23

## 0) 現況快照（已驗證）

- 目前主版本：`v0.3.1`
- 目前主 run：`run_full_20260222_192855`
- 語料掃描數（markdown）：`532`
- run 內 poems 總數：`522`
- 圖譜 citations：`141`
- 圖譜被引用 source 數：`99`
- seed 掛載匹配總數：`141`
- full 掛載匹配總數：`1286`
- fill_assignments 匹配總數（只含 seed 未命中部分）：`1145`
- 對照關係：`141 + 1145 = 1286`（已核對）

QA（抽樣驗收）
- 命令：`python3 scripts/sample_fill_quality.py --run-id run_full_20260222_192855 --sample-size 40 --seed 42 --out-prefix logs/fill_quality_192855`
- 結果：`quote_in_source_rate_percent = 98.95%`（`1133/1145`）
- 無效 `12` 筆主要是 heuristic fallback（空 quote / tags 行），不是主體詩句匹配。

## 1) 對你 6 點問題的結論（可直接沿用）

1. 「本地腳本是否只是叫 Gemini 隨便做？」
- 這批 run 的 `pipeline_request` 是 `iterations=6, sample_size=30`，屬於低覆蓋設定。
- 低覆蓋主要影響「seed 初始引用覆蓋」，不是代表完全沒掃到 500+。
- 你現在看到 500+ 有掃到、但 citations 低，核心原因是 seed 低覆蓋 + fill 尚未升格成 citations 表。

2. 「句子/段落不能脫離全詩背景」
- 已列為硬規則：句/段證據必須保存 parent poem 關聯與可回溯全文上下文。

3. 「角色互動敘述合理」
- 已採納，見下方角色分工。

4. 「先抽樣確認可用，再談升格」
- 已完成第一輪抽樣與統計。
- 仍需第二輪人工抽樣（重點看你在意的詩群）後，才進入升格實作。

5. 「先確認任務清單」
- 見第 4 節，已拆成控制窗與執行窗。

6. 「token 快滿，開雙窗交接」
- 可行；建議 4 回合交接流程，見第 5 節。

## 2) 角色分工（非技術術語版）

1. 本地腳本（跑一次的）
- 功能：做「大批次生產」：抽樣、請模型給片段、合併技能樹、做 fill。
- 產物：`runtime_workspaces/<run_id>/...` 的 JSON 檔。

2. 每次開站腳本（start_local）
- 功能：把 API + 網頁服務開起來，讀現有 DB/run 給你看。
- 不負責重建技能樹本體。

3. 顯示網頁（前端 + backend API）
- 功能：渲染、搜尋、hover/pin、節點細節、右欄 citations。
- 你每次互動是它在即時回應。

4. Gemini API
- 功能：在「生樹 + 初次對詩句做判斷」時提供模型輸出。
- 它不是開站後每次滑鼠移動都會重新判斷。

5. 未來學會成員（Claude/Codex/Web-GPT/人工）
- 功能：不是覆蓋前人，而是新增「支持/反對/修訂」意見。
- 最終由共識規則決定哪些證據進入樹。

## 3) 不可跳過的閘門（Gate）

Gate A（資料真實性）
- 必須先通過 `audit_run`：確認 corpus、seed、fill、full 的關係一致。

Gate B（引用可用性）
- `sample_fill_quality` 抽樣後，`quote_in_source_rate_percent` 建議 >= `97%`。
- 無效樣本要可解釋，且不能集中在你關心題材。

Gate C（語境完整性）
- 句/段證據設計前，先定義 parent-poem 關聯欄位與全文快照策略。
- 未達成前，不做「句級證據直接取代全詩視角」。

Gate D（升格前人工驗收）
- 你抽查「你最在意的作品清單」是否被合理映射。
- 過關才做 fill -> citations 升格。

## 4) 下一步任務清單（控制窗 / 執行窗）

控制窗（主控）
- [ ] 先鎖定本輪目標 run_id（目前建議 `run_full_20260222_192855`）
- [ ] 定義人工抽樣清單（你最在意作品至少 30 首）
- [ ] 決定是否先重跑高覆蓋 full（建議是）

執行窗（實作）
- [ ] 重跑 full（高覆蓋設定）
- [ ] `init_db.py` 匯入
- [ ] `audit_run.py` 生成審計報告
- [ ] `sample_fill_quality.py` 生成 QA 報告
- [ ] 根據 Gate 結果決定是否進入 fill->citations 升格

## 5) 建議的 4 回合交接流程

回合 1（控制窗）
- 確認 run_id、目標、這輪是否要重跑 full。

回合 2（執行窗）
- 跑 full + 匯入 + 兩份報告（audit / fill_quality）。

回合 3（控制窗）
- 對照你的 30 首重點詩作抽樣結果，標記可接受/不可接受。

回合 4（執行窗）
- 若過 Gate，開始設計 fill->citations 升格草案；否則回去調整生成參數再跑。

## 6) 命名與舊路徑（next_window_stack）

- 程式碼路徑與 API 主流程已使用 `v0.3.1`。
- `next_window_stack` 目前只殘留在歷史產物 JSON（例如舊 run 的 `run_meta.json` / `master_skill_web.json` 字串欄位）。
- 已在 `GET /runs/{run_id}/audit` 端做 legacy path 清理，避免在審計結果中暴露舊命名作為主路徑。
- 後續若重跑 full，新的產物會自然改成當前路徑命名。

## OpenCode Handoff 2026-03-12 18:33
Branch: C Vertex POEM 庫
Workdir: C:\Users\user\OneDrive\代碼庫與projects\vertex ai LM POEMS
Objective: 以評審會共識+多視角並行產生新技能樹節點，合併生成新版 master skill web，重新掛載並輸出視覺化。
Done: 完成四波評審（522/522）並生成共識報告；修復 responses wave 的 target_id mismatch；新增 run_logs 回報；產出 `review_dossier.json`（同一詩所有評審意見）；`brainstorm_skill_webs.py` 支援評審會摘要注入與 relay backend；`build_master_and_fill_mounting.py` 支援 `EXTRA_FRAGMENT_PATHS`。
In Progress: A/B/C/E 視角 fragments 未完整產出（僅 D 完整，E 部分）；等待補齊後合併新版 master + 重新掛載 + 視覺化。
Next: 1) 以 relay 重新跑 A/B/C/E 直到各 10 份 fragment；2) 執行 `build_master_and_fill_mounting.py` 產生新 run 的 `master_skill_web.json` 與掛載；3) 執行 `generate_skill_tree_visualizations.py` 輸出新版視覺化。
Blockers: A/B/C/E fragment 仍缺；relay 需可用的 base_url/api_key（勿寫入手動 secrets）。
Running Processes: None（外部 A~E 視窗已由使用者關閉）。
Key Files: runtime_workspaces/run_full_20260222_192855/literary_salon/salon_leishen_full_20260309_01/consensus_report.json; runtime_workspaces/run_full_20260222_192855/literary_salon/salon_leishen_full_20260309_01/review_dossier.json; runtime_workspaces/run_full_20260222_192855/runs/run_full_20260222_192855/master_skill_web.json; runtime_workspaces/run_full_20260222_192855/runs/run_full_20260222_192855/poem_mounting_full.json; brainstorm_skill_webs.py; build_master_and_fill_mounting.py; backend/scripts/build_review_dossier.py
Commands Run: python backend/scripts/merge_review_waves.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01; python backend/scripts/review_session_status.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01; python backend/scripts/build_review_dossier.py --run-id run_full_20260222_192855 --session-id salon_leishen_full_20260309_01; python backend/scripts/run_responses_batch_group.py ... (theme/counter reruns); python backend/scripts/run_responses_wave.py ... (target_id fix tests)
Tests/Checks: review_session_status（全波完成）；merge_review_waves（consensus_report_ready=true）。
Risks/Notes: `brainstorm_skill_webs.py` 需設定 LLM_BACKEND=relay 才不會走 GCP；`build_master_and_fill_mounting.py` fill 階段仍走 Vertex（若無 GCP 可先 `--skip-fill` 或後續再改 relay）；遵守 DISPATCH/JP 先詢號規則。
Resume Command: cd "/Users/liujiugao/Library/CloudStorage/OneDrive-個人/代碼庫與projects/vertex ai LM POEMS" && python3 -c "from pathlib import Path; print('craft', len(list(Path('archives/skill_web_fragments_craft').glob('skill_web_fragment_*.json')))); print('theme', len(list(Path('archives/skill_web_fragments_theme').glob('skill_web_fragment_*.json')))); print('counter', len(list(Path('archives/skill_web_fragments_counter').glob('skill_web_fragment_*.json')))); print('revision', len(list(Path('archives/skill_web_fragments_revision').glob('skill_web_fragment_*.json')))); print('experimental', len(list(Path('archives/skill_web_fragments_experimental').glob('skill_web_fragment_*.json'))))"
Git Status: ## codex/recovery-vertex-20260310...origin/codex/recovery-vertex-20260310 | M backend/app/responses_relay.py | M backend/scripts/run_responses_batch_group.py | M backend/scripts/run_responses_wave.py | M brainstorm_skill_webs.py | M build_master_and_fill_mounting.py | ? archives/ | ? backend/scripts/build_review_dossier.py
