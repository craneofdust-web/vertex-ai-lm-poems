# Poetry Review Guardrails

Updated: 2026-03-08

## Purpose

This file tells future execution windows how to evaluate the poem corpus without flattening all works into one standard.

It is especially important for any `literary salon`, corpus-wide review, or multi-model evaluation pass.

## What is already readable from the current corpus / system

### 1. Folder-level stage signal is already part of the existing Gemini pipeline

In `brainstorm_skill_webs.py`, the current system instruction already distinguishes folder status:

- `未整理作品` or similar early archive -> treat as early / foundational talent layer
- `未完成長篇` / `未完成短篇` / `創作中` -> treat as experimental / in-progress work, not as fully realized poem
- other regular folders -> can be treated as more mature work

So this is not a new idea. The existing system already has a stage-aware reading habit at folder level.

### 2. Completion metadata exists, but not uniformly everywhere

The poems vault already defines a completion system:

- `0-純概念`
- `0-核心單句`
- `1-核心段落`
- `2-零散段落(2+完整段落)`
- `2-圈點框架(零星可相連)`
- `3-但缺關鍵轉折`
- `3-骨架齊全(完整可相連)`
- `4-邊幅修葺`
- `4-推敲用字`
- `5-詩評`

Sources:

- `文件/Obsidian for Literature & Poems/test/標籤分類備註for ai.md`
- `文件/Obsidian for Literature & Poems/others/Config/Attribute_Values.md`

Some individual works already expose `完成度` in frontmatter, but not all files do.

### 3. Creation-time signal exists, but is only partially normalized

Some works expose time clues through:

- timestamp-like filenames
- explicit date lines inside the file
- folder placement
- legacy archive grouping

But there is not yet one normalized corpus-wide `created_at` field for every poem.

So the system can read some time information now, but should not pretend it has a fully clean chronological database yet.

## Hard evaluation rules

### Rule 1 - Do not judge unfinished work as if it were a finished poem

If a work is marked or inferred as in-progress, draft, experimental, or low-completion:

- do not score it mainly on polish;
- do not compare it directly against fully matured late works;
- focus on what it is testing, assembling, or reaching toward;
- emphasize trajectory, structural promise, and live experiments.

### Rule 2 - Do not flatten early and late works into one contest

If a work is clearly early, archived, or from an older stage:

- read it as an earlier layer of talent, impulse, mimicry, or formative method;
- compare it primarily within its developmental era or function;
- do not punish it for not yet carrying the density of later work.

### Rule 3 - When time metadata is missing, downgrade comparison confidence

If the system cannot confidently determine the era of a poem:

- mark chronology confidence as `low` or `unknown`;
- avoid strong developmental claims;
- do not assert `regression` or `maturity drop` without evidence.

### Rule 4 - Separate at least three evaluation modes

Each reviewed work should be read under one of these modes:

1. `finished_work_mode`
2. `in_progress_mode`
3. `early_archive_mode`

Optional fourth mode when needed:

4. `experimental_transition_mode`

### Rule 5 - Output stage-aware verdicts, not one single universal score

The review system should prefer outputs like:

- `what already works`
- `what is being tested`
- `what feels structurally missing`
- `what should not yet be judged harshly`
- `what later work this might anticipate`

instead of one flat ranking.

## Metadata extraction policy for the salon run

Before or during review target export, try to extract these fields per poem:

- `source_id`
- `title`
- `folder_status`
- `completion_status` (if present)
- `creation_time_hint` (explicit / inferred / unknown)
- `maturity_bucket`
- `comparison_policy`

Recommended buckets:

- `early_archive`
- `in_progress`
- `maturing`
- `mature`
- `unknown`

Recommended comparison policies:

- `compare_with_same_stage_only`
- `compare_with_caution`
- `can_enter_general_pool`

## What the next window should assume right now

- Folder-level stage awareness is available now.
- Completion metadata is partially available now.
- Creation-time metadata is only partially available now.
- Therefore the next execution window should implement a stage-aware review, but must also record confidence about chronology instead of faking certainty.

## Important caution

Recent works may follow a more explicit and self-aware poetics described in `AUTHOR_POETIC_CONTEXT.md`.
Do not force that same interpretive frame onto much earlier work as if the entire corpus were written under one identical program.
