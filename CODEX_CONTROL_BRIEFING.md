# CODEX 主控台窗口簡報

更新日期：2026-02-24
發出者：外部審計（Claude Opus via Cowork）

---

## 目前局面

你（主控台窗口）目前的執行窗口可以放棄了。原因：

1. **執行窗跑了很久但只做了文檔整理**——9 個 commit 全是 docs/fix/chore，沒有推進 ROADMAP 的任何 Priority A 任務。
2. **最近一次 pipeline run 失敗了**（`vertexai` 沒裝），產出為零。
3. 外部審計（本文件）已重新排定優先級，寫入 `CODEX_DISPATCH.md`。

---

## 你需要做的事

### 步驟 1：開新執行窗

在 Codex 開一個新窗口，給它以下指示：

```
讀取項目根目錄的 CODEX_DISPATCH.md，按照裡面的任務清單嚴格按順序執行。
每完成一個 Phase 就 commit 並更新 CODEX_DISPATCH.md 的狀態表。
不要跳過任何步驟，不要自己做架構決定。
```

### 步驟 2：舊執行窗

舊的執行窗口（就是跑了老半天那個）直接關掉或放著不管。它沒有未完成的有價值工作。

### 步驟 3：監控新窗口

新窗口應該依序產出以下 commit：

| 預期順序 | Commit prefix | 內容 | 怎麼驗證 |
|----------|--------------|------|----------|
| 1 | `refactor:` | main.py 拆分成 routes/ + services/ | `python -m compileall -q backend/app` 無錯 |
| 2 | `test:` | 加入 backend/tests/ | `cd backend && python -m pytest tests/ -v` 全過 |
| 3 | `chore:` | 清理失敗 run + 環境修復 | `runtime_workspaces/` 裡沒有空 run |
| 4 | `chore:` | requirements 分離 | `pip install -r requirements.txt` 能啟動 backend |
| 5 (可選) | `refactor:` | 前端 app.js 拆分 | 瀏覽器打開無報錯 |

### 步驟 4：完成後的下一步

當 Phase 1-4 都完成後，接下來的工作是：

1. **你自己**在本地填好 `.env` 的真正 `PROJECT_ID`
2. 用高覆蓋參數重跑 full run：`--iterations 30 --sample-size 50`
3. 跑 audit + fill quality QA
4. 通過 Gate D（人工驗收你的重點詩作）後，才進入 fill→citations 升格

這些需要 GCP 認證和你的本地環境，不適合丟給 Codex 盲跑。

---

## 風險提醒

- Codex 有傾向做大量文檔整理而不碰核心代碼。如果看到它又開始改 README / CHANGELOG / CONTRIBUTING 之類的，**立刻糾正**，叫它回到 CODEX_DISPATCH.md 的任務清單。
- Phase 1（拆分 main.py）是最有價值但也最容易搞砸的步驟。如果它拆完後端點行為有變，要求它 revert 重來。
- 不要讓它碰 pipeline 生成邏輯（`brainstorm_skill_webs.py` 等），那些腳本目前能跑就好。
