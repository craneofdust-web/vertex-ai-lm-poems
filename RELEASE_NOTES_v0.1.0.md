# Release Notes - v0.1.0 (Archived Baseline)

## Highlights
- Public repository baseline established.
- Configuration moved to environment variables.
- Personal machine path defaults removed from runtime config.
- Public docs, contribution guide, and security policy added.

## Included Components
- Skill fragment generation script.
- Merge and fill pipeline script.
- FastAPI + SQLite runtime with graph and lineage endpoints.

## Known Gaps
- CI workflow is not yet configured.
- API auth/rate limiting is not enabled by default.
- Public sample corpus is placeholder-only (`sample_poems/`).

## Upgrade Notes
- Set `PROJECT_ID` and `POEMS_SOURCE_FOLDER` before running smoke/full pipeline.
- Current runtime data scope for active API defaults is `v0.3.1`.
