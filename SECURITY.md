# Security Policy

## Reporting a Vulnerability

Do not open a public issue for sensitive vulnerabilities.

Preferred channel:
- Use GitHub Security Advisories private reporting in this repository (`Security` tab -> `Report a vulnerability`).

Fallback channel:
- Contact the maintainer through a private channel and include:
  - impact summary
  - reproduction steps
  - affected files or endpoints
  - suggested remediation

## Secret Handling

- Keep credentials in environment variables only.
- Never commit service account files.
- Rotate credentials immediately if accidental exposure is suspected.
- Verify `.env`, runtime logs, and local DB files are excluded before pushing.
