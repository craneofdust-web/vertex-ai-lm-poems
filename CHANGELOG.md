# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- Documentation consistency pass across `README.md`, `中文說明.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `PUBLIC_SCOPE.md`.
- Clarified version semantics: API release baseline (`0.1.x`) vs runtime data scope (`v0.3.1`) vs visualization style labels (`V1~V6`).
- Clarified public publishing checklist and required pre-publish validations.
- Added `CODE_OF_CONDUCT.md` and linked it from project docs.
- Migrated runtime path naming from the legacy nested backend location to `backend` and updated active config/docs accordingly.
- Added `backend/scripts/start_local.py` with interpreter auto-fallback to reduce startup failure under broken virtualenv setups.
- Added `HEAD` support for read endpoints to improve browser/proxy compatibility (including Safari preflight-style requests).
- Removed optional-chaining syntax from frontend runtime code to avoid parse failures on older Safari engines.
- Refreshed UI theme to daylight-first colors and enabled automatic light/dark follow-system behavior via `prefers-color-scheme`.
- Promoted active runtime scope/version naming to `v0.3.1` across API responses and docs.
- Updated citation hover/pin behavior to prefer original source poem text over explanation snippets.
- Added project-root `.env` auto-loading for runtime defaults when shell variables are not pre-exported.

### Security
- Security reporting guidance now explicitly prioritizes GitHub private vulnerability reporting.

## [0.1.0] - 2026-02-22

### Added
- Public migration baseline files: `.gitignore`, `.env.example`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`.
- Community templates: issue templates for bug reports and feature requests.
- Public docs refresh for repository root and backend runtime.

### Changed
- Removed personal machine path defaults from runtime config and pipeline defaults.
- Switched source corpus defaults to `./sample_poems` and env-based configuration.

### Security
- Added explicit guidance to keep secrets and local credentials out of the repository.
