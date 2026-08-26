# Security policy

## Supported version

Summa is maintained from the `main` branch. Security fixes are applied there;
older snapshots and forks are not maintained as separate release lines.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature on this repository
instead of opening a public issue. Include the affected file or URL, the impact,
and a minimal reproduction where possible. Do not include API keys, cookies,
private source data, or other credentials in a report.

Public data-quality problems are not security vulnerabilities. They can be
reported through the issue tracker or the opportunity-correction workflow.

## Secrets and generated output

API keys belong in environment variables or ignored local `.env` files. The
published site must not contain scanner snapshots, review queues, AI evidence,
translation status, scan manifests, or record-audit artifacts. CI validates the
deployment surface before it is pushed to GitHub Pages.
