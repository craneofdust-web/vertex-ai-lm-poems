# TODO：跨項目共享上下文（待續）

建立日期：2026-03-06
來源窗口：Cowork 審計窗口

---

## 問題

所有在 `代碼庫與projects/` 的項目共用一個問題：

1. **術語孤島**：代碼項目的 Codex/Claude 窗口不知道 vault 裡定義的術語（如 `vault-projects` = `Obsidian for Living & Projects`）
2. **規範漂移**：規範在 Obsidian vault 更新，但代碼項目裡的 AI 用舊的或自己編的理解
3. **靜默失敗**：AI 不說「我不知道」，直接猜，而且猜得很自信

## 預期方案方向

在 `代碼庫與projects/` 根目錄放一個 `CLAUDE.md`，內容包含：

- 跨項目術語表（術語 → 實際意義 + 路徑對照）
- vault 路徑映射（Mac vs PC）
- 「不要自己猜」的行為規範
- 常見的指涉對象清單

Claude Code / Codex 會自動讀取父目錄的 CLAUDE.md，所以每個子項目都會自動繼承。

## 狀態

⬜ 未完成——因 Obsidian vault 未成功掛載到 Cowork 而中斷。
下一個窗口需要掛載 `Obsidian for Living & Projects` vault 才能建立完整的術語表和規範摘要。

## 所需存取

- `Obsidian for Living & Projects` vault（讀取術語、規範、項目定義）
- `代碼庫與projects/` 根目錄（寫入 CLAUDE.md）
