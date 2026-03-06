# Improvement Roadmap (v0.3.x)

This file tracks follow-up improvements discovered during the latest frontend/backend audit.

## Current Baseline

- Tooltip no longer follows mouse movement and is fixed beside citation cards.
- Left panel is collapsible.
- Edge rendering now supports show/hide and weak/far edge toggles.
- Layout spacing improved to reduce overlap in dense lanes.

## Priority A (no product decision required)

### A1. Split oversized backend modules

- Problem:
  - `backend/app/main.py` is very large and mixes route definitions, runtime discovery, and response shaping.
  - `backend/app/ingest.py` and `backend/app/pipeline.py` each hold multi-responsibility orchestration logic.
- Goal:
  - Extract route groups into separate modules (`routes_graph.py`, `routes_runs.py`, `routes_visualization.py`).
  - Move reusable query logic into service layer (`services/runs.py`, `services/graph.py`).
- Acceptance:
  - Functionality unchanged for `/graph`, `/node`, `/runs`, `/visualization/*`.
  - Existing behavior preserved with equivalent responses.

### A2. Persist run stats at ingest time

- Problem:
  - `/runs` currently recomputes stats from multiple tables and may re-scan corpus folders.
- Goal:
  - Persist computed stats JSON during ingest and read directly in `/runs`.
- Acceptance:
  - `/runs` response time remains stable as run history grows.
  - No corpus-wide filesystem scan on every `/runs` call.

### A3. Add async run job model for `/run/full`

- Problem:
  - `/run/full` is synchronous and blocks request lifecycle for long tasks.
- Goal:
  - Introduce async job endpoints (`POST /run/full` returns job_id, `GET /jobs/{job_id}` for status/progress/result).
- Acceptance:
  - Frontend can poll progress without blocking browser request timeout.
  - Failed jobs expose concise error summaries with log path references.

### A4. Add tests and CI baseline

- Problem:
  - No automated checks currently enforce runtime/API behavior.
- Goal:
  - Add API tests for core endpoints and one frontend smoke test.
  - Add GitHub Actions workflow for offline checks.
- Acceptance:
  - CI runs compile + test on PR.
  - Merge is blocked when checks fail.

## Priority B (frontend decision required)

### B1. Edge visual style preset (includes v0.2-like option)

- Why:
  - Users want stronger "skill tree" feel and better hierarchy legibility.
- Options:
  1. `Classic v0.2` (recommended):
     - thicker primary lines, visible arrowheads, weak lines thinner/dashed, selected-path highlight.
  2. `Minimal`:
     - thin neutral lines, low visual weight, focus on cards.
  3. `Adaptive`:
     - minimal by default, highlight only around selected node neighborhood.
- Decision needed:
  - Pick one preset as default.

### B2. Left panel interaction model

- Why:
  - Current panel is collapsible, but information density can still compete with graph area.
- Options:
  1. `Collapsible + resizable` (recommended):
     - keep current behavior and add drag resize handle.
  2. `Tabbed side panel`:
     - split into `Nodes` and `Notes` tabs.
  3. `Drawer mode`:
     - overlay panel opened on demand, maximizes graph width.
- Decision needed:
  - Pick desktop default and mobile fallback.

### B3. Node card art direction

- Why:
  - Need stronger visual distinction between tiers/lanes and reduced text crowding.
- Options:
  1. `Badge-first` (recommended):
     - stage badge + lane icon + short title + support chip.
  2. `Data-dense`:
     - keep more metadata visible directly on card.
  3. `Cinematic`:
     - larger cards, richer typography, stronger thematic color blocks.
- Decision needed:
  - Pick preferred visual language.

### B4. Detail panel citation reading mode

- Why:
  - Citation readability varies for long source text.
- Options:
  1. `Inline excerpt + expand` (recommended):
     - 6-10 line preview with one-click expand.
  2. `Pinned-only`:
     - no hover preview, only pinned reader pane.
  3. `Split viewer`:
     - dedicated right-bottom source reader with synchronized citation selection.
- Decision needed:
  - Pick default reading behavior.

## Priority C (later)

### C1. Frontend state persistence

- Persist UI preferences (`show edges`, `include weak/far`, panel collapse state, selected run) to `localStorage`.

### C2. Graph navigation usability

- Add mini-map, zoom controls, keyboard jump-to-node, and selected path emphasis.

### C3. Public hardening pass

- Optional write-endpoint auth toggle.
- Optional CORS allowlist mode.
- Rate limiting for `/run/*`.

## Priority D (vision track: consensus and fine-tunable architecture)

### D1. Atomic judgment unit = sentence/paragraph evidence

- Problem:
  - Current model output is effectively one-pass judgment per quote block, with limited revision history.
- Goal:
  - Store atomic evidence units (sentence/paragraph) as first-class records, not only final node-level citation bundles.
  - Enforce poem-context anchoring: sentence/paragraph evidence must always keep a link to full-poem context; no detached sentence-only interpretation.
- Acceptance:
  - Every evidence unit has a stable id and source span metadata.
  - Every evidence unit stores parent poem id + retrievable full-poem text snapshot/hash for context reconstruction.
  - Downstream node mappings can reference one or multiple atomic evidence units.

### D2. Multi-agent review ledger (not single-model authority)

- Problem:
  - Current flow is close to "single model decides, system accepts".
- Goal:
  - Add a review ledger where different agents/models can propose, support, or reject prior judgments.
  - Designed for mixed contributors: Gemini, Claude, Codex, Web-GPT, and human reviewer.
- Acceptance:
  - Each judgment keeps immutable provenance:
    - provider/model/version
    - prompt/policy version
    - timestamp
    - reviewer stance (`support`, `reject`, `revise`)
    - rationale text
  - Contradictory reviews can coexist until consensus policy resolves them.

### D3. Consensus policy engine

- Problem:
  - No explicit rule for turning conflicting reviews into "accepted knowledge".
- Goal:
  - Implement policy-based consensus scoring (weighted votes + confidence + recency + human override).
  - Treat the skill tree as "long-term scholarly consensus", not one-shot intuition.
- Acceptance:
  - Node/citation inclusion is explainable by policy trace.
  - UI can show why an edge/citation is accepted and what dissent exists.

### D4. Cost-aware, pluggable reviewer orchestration

- Problem:
  - Token budget and provider availability vary over time.
- Goal:
  - Allow review batches to route across providers based on budget/cap limits.
  - Example: when Claude/Codex quota is constrained, route selected batches to another provider, then merge by consensus policy.
- Acceptance:
  - Reviewer routing config supports provider fallback and per-batch limits.
  - Runs can be resumed and merged across multiple review waves.

### D5. Fine-tuning dataset export

- Problem:
  - Current outputs are not structured for robust future fine-tuning.
- Goal:
  - Export supervised preference data from the review ledger:
    - accepted vs rejected interpretations
    - revision chains
    - consensus outcomes
- Acceptance:
  - One command can export train/eval splits with provenance filters.
  - Exports include disagreement samples for robustness tuning.

### D6. Creative learning planner (product vision)

- Vision:
  - Systematically plan creative learning direction and desired breakthrough angles.
  - During practice-oriented writing, classify work by intended breakthrough objective, not only by vague inspiration cues.
- Goal:
  - Add "breakthrough intent" metadata and recommendation loop:
    - target capability to train
    - suggested exercises from underdeveloped nodes
    - post-work reflection mapped back to consensus graph
- Acceptance:
  - User can choose a target breakthrough before drafting.
  - System can show which nodes moved after the draft and why.

## Next checkpoint

- User validates current delivered UI changes first.
- After validation, execute Priority A in order (`A1 -> A2 -> A4 -> A3`) unless user reprioritizes.
- Start Priority B after user selects defaults for `B1` to `B4`.
- Keep Priority D as the long-term architecture track; start with `D1 -> D2 -> D3` before orchestration and tuning export.
