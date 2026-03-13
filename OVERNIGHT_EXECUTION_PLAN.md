# Overnight Execution Plan

Updated: 2026-03-08

## Goal

Deliver one high-output execution window that does three things in one pass:

1. build the first usable `literary salon` review workflow;
2. run one full corpus pass (or the strongest possible fallback if credentials block a fresh run);
3. inspect the current UI and ship concrete fixes instead of only writing notes.

This plan is designed for an unattended night run. It should prefer forward progress over waiting for new decisions.

## Fixed defaults for this run

Use these defaults unless a hard blocker appears:

- Edge preset default: `Classic v0.2`
- Left panel desktop default: `collapsible + resizable`
- Left panel mobile fallback: `drawer mode`
- Node card direction: `badge-first`
- Citation reading mode: `inline excerpt + expand`
- Full run target parameters: start from high-coverage settings equivalent to `iterations=30` and `sample_size=50`
- Literary salon execution mode: `artifact-first, resumable, batch-based`

## Non-negotiable rules

- Do not stall on missing user decisions; use the defaults above.
- Do not let docs-only work consume the window.
- Do not rewrite the whole architecture before shipping artifacts.
- Keep every long task resumable and leave machine-readable outputs.
- If a fresh full run is blocked by credentials or environment, continue with the strongest fallback path instead of ending the window empty-handed.
- Never judge unfinished work as if it were a finished poem.
- Never flatten early and late works into one ranking pool when chronology is uncertain.
- Use `AUTHOR_POETIC_CONTEXT.md` as a strong lens for recent work, not as a universal law for the entire corpus.

## Phase 0 - Preflight and environment check

Read first:

- `AGENTS.md`
- `HANDOFF.md`
- `IMPROVEMENT_ROADMAP.md`
- `POETRY_REVIEW_GUARDRAILS.md`
- `AUTHOR_POETIC_CONTEXT.md`
- this file

Then verify:

1. backend runtime can start;
2. `.env` is present or environment variables are available;
3. `PROJECT_ID` is not placeholder-only if fresh pipeline execution is required;
4. `POEMS_SOURCE_FOLDER` exists and contains the real corpus;
5. runtime Python has `requirements.txt` and `requirements-pipeline.txt` installed if `/run/full` is to be executed;
6. the current valid baseline run is still visible;
7. review-target export can read at least folder-level stage metadata, and preferably completion / time hints when present.

Minimum artifact output for this phase:

- a short `preflight_status.md` under a new run/work log folder;
- explicit pass/block notes for credentials, corpus path, and pipeline dependencies.
- a short note on metadata readability: `folder_status`, `completion_status`, `creation_time_hint`, and confidence level.

## Phase 1 - Baseline audit before changing anything

Audit the current best known run first (`run_full_20260222_192855` unless a newer valid run exists).

Required checks:

1. run coverage audit;
2. fill quality sample audit;
3. current mounted poem count;
4. cited-source coverage vs corpus size;
5. identify whether the next full run is improving on a real baseline.

Required outputs:

- `baseline_audit.json`
- `baseline_audit.md`
- `fill_quality_*.json`
- `fill_quality_*.md`

## Phase 2 - Build MVP literary salon (artifact-first)

Do not start with a heavy DB migration. Build the first version as local artifacts that can later be promoted into API/DB structures.

### Required MVP capabilities

1. Export review targets in batches from the corpus or active run.
2. Preserve full-poem context for every review target.
3. Allow multiple review waves per batch.
4. Record immutable provenance per review:
   - provider
   - model
   - prompt/policy version
   - batch id
   - timestamp
   - reviewer stance (`support`, `reject`, `revise`)
   - rationale
5. Merge multiple reviews into a consensus report without deleting disagreement.
6. Carry stage-aware metadata per target so unfinished / early works are not judged by mature-work standards.

### Recommended file outputs

Under a new folder such as:

- `runtime_workspaces/<run_id>/literary_salon/<session_id>/`

store:

- `review_targets.jsonl`
- `review_batches/`
- `review_waves/`
- `consensus_report.json`
- `consensus_report.md`
- `run_meta.json`

Each review target should include, when available:

- `folder_status`
- `completion_status`
- `creation_time_hint`
- `maturity_bucket`
- `comparison_policy`

### Recommended implementation shape

Add lightweight scripts first, then API/UI only if time remains:

- `backend/scripts/export_review_batch.py`
- `backend/scripts/run_review_wave.py`
- `backend/scripts/merge_review_waves.py`
- `backend/scripts/review_session_status.py`

If API support is easy after that, add a minimal read-only route layer for browsing generated review sessions.

## Phase 3 - Reviewer strategy for the first night

Target a real multi-angle discussion, but do not block on multi-provider availability.

### Preferred mode

If multiple providers are available, run at least three reviewer profiles:

1. formal / craft critic
2. imagery / symbolism critic
3. adversarial or skeptical reader

### Fallback mode

If only Gemini/Vertex is truly available, still run multiple review waves with different explicit rubrics and record them honestly as distinct rubric passes, not fake providers.

Example fallback wave set:

1. `craft_pass`
2. `theme_pass`
3. `counter_reading_pass`
4. `revision_synthesis_pass`

The output must clearly distinguish:

- `multi-provider review`
- `single-provider multi-rubric fallback`

It should also clearly distinguish:

- `finished_work_mode`
- `in_progress_mode`
- `early_archive_mode`
- `experimental_transition_mode` (if needed)

## Phase 4 - Fresh full run, then salon review

### Preferred path

1. execute a fresh high-coverage full run;
2. ingest it into SQLite;
3. run audit;
4. run fill quality gate;
5. export literary salon targets from the fresh run;
6. execute review waves in resumable batches;
7. merge consensus outputs.

### Strong fallback path

If a fresh full run is blocked by credentials, dependency breakage, or source path issues:

1. do not end the window;
2. use the latest valid run as the review base;
3. still execute the full literary salon workflow on all available mounted works;
4. leave a precise blocker artifact for the fresh full run.

### Batch execution rule

Do not attempt one giant opaque batch for everything.

- Use resumable chunks.
- Persist status after every chunk.
- If one chunk fails, continue with the next safe chunk and mark the failed one.

## Phase 5 - UI inspection and repair in the same window

Do not leave UI work as theory only. Inspect the current app and ship fixes.

### Required UI targets for this run

1. apply the chosen edge preset direction (`Classic v0.2` feel);
2. add desktop panel resizing and mobile drawer fallback if not already present;
3. improve citation reading with inline excerpt + expand behavior;
4. reduce dense-view readability issues discovered during hands-on inspection;
5. verify no regression in `/graph`, `/runs`, `/visualizations`, and selected-node reading flow.

### Nice-to-have if time remains

1. persist UI preferences to `localStorage`;
2. strengthen selected-path emphasis;
3. add one frontend smoke check if the test harness allows it.

## Phase 6 - Validation and morning-ready outputs

Before ending the window, produce visible outputs, not just source changes.

Required validation:

- `python -m compileall -q backend/app`
- backend tests that already exist
- manual or scripted sanity check for `/health`, `/runs`, `/graph`, `/visualizations`
- confirm literary salon artifacts exist and are readable

Required deliverables by morning:

1. code changes for salon scaffolding and UI improvements;
2. one fresh full run plus review outputs, or a documented fallback run with full review outputs;
3. a concise execution summary;
4. a blocker list only for items that truly could not be completed.

## Success tiers

### Gold

- fresh high-coverage full run completed;
- literary salon executed across the corpus;
- consensus report produced;
- UI fixes shipped and validated.

### Silver

- fresh full run blocked, but the latest valid run was fully reviewed with the salon workflow;
- UI fixes shipped and validated;
- blocker artifact clearly explains why a fresh run did not happen.

### Bronze

- salon scaffolding implemented;
- pilot batches completed;
- UI fixes shipped;
- full-run blocker precisely recorded with next command to resume.

Anything below Bronze is not acceptable for an overnight execution window.

## Suggested next-window instruction

Use this directly in the next Codex window:

```text
Read `OVERNIGHT_EXECUTION_PLAN.md`, `HANDOFF.md`, and `IMPROVEMENT_ROADMAP.md`, then execute the whole plan without waiting for more product decisions.
Use the defaults already fixed in `OVERNIGHT_EXECUTION_PLAN.md`.
Goal: deliver the first usable literary salon workflow, run one full corpus pass or the strongest valid fallback, inspect the current UI hands-on, and ship concrete fixes.
Do not stop at planning. Keep work resumable, artifact-first, and progress-oriented.
```
