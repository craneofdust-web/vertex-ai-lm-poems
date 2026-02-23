# Starter Issues

Use these as initial public onboarding issues.

## 1. Add offline CI checks
- Label: `good first issue`
- Goal: run syntax/type hygiene checks that do not require Vertex credentials.
- Acceptance:
  - workflow runs on push and PR
  - runs `python -m compileall -q backend/app`
  - failures block merge

## 2. Add API authentication toggle
- Label: `enhancement`
- Goal: optional API key auth for write endpoints (`/run/*`).
- Acceptance:
  - env switch to enable auth
  - unauthorized requests return 401

## 3. Corpus adapter abstraction
- Label: `enhancement`
- Goal: support custom corpus loaders beyond local Markdown folders.
- Acceptance:
  - loader interface documented
  - default markdown loader unchanged
  - one extra sample loader added
