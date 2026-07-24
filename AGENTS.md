# AGENTS.md

AI agents working on this repository should read this file first. It is the operational brief for Summa.

## Product identity

- Product name: **Summa**.
- Python package/import path: `research_school_radar`.
- Distribution/repository name: `summer-school-radar`.
- Do not rename real package paths, CLI module paths, repository URLs, or generated GitHub Pages URLs just to make them match the product name.
- Avoid reintroducing the old public name "Summer School Radar" in user-facing copy. Historical package/repo names may still appear where they are technically required.

## What Summa does

Summa scans trusted official sources for funded, in-person or substantially on-site research training opportunities across multiple disciplines. It publishes a static site, Markdown reports, JSON data, and RSS.

It targets short research-training formats such as:

- summer/winter/spring/autumn schools
- training schools
- field schools
- doctoral/research schools
- short or advanced courses

It does **not** target:

- ordinary conference workshops
- PhD admissions
- PhD positions
- full degree programmes
- generic study-abroad marketing pages

Precision is more important than recall. Near-matches must not be presented as fully qualified opportunities.

## Current architecture

Main deterministic pipeline:

```text
sources -> collect -> parse -> extract -> filter -> rank -> report/site
```

Key modules:

- `src/research_school_radar/cli.py` — CLI entry point.
- `src/research_school_radar/collect.py` — fetches source and linked pages.
- `src/research_school_radar/http_cache.py` — conditional HTTP cache using `ETag` / `Last-Modified`, with a 14-day stale-if-error fallback for transient upstream failures.
- `src/research_school_radar/parse.py` — finds likely candidate links.
- `src/research_school_radar/extract.py` — rule-based candidate extraction.
- `src/research_school_radar/date_extraction.py` — date ranges, deadlines, and JSON-LD event dates.
- `src/research_school_radar/fee_extraction.py` — participant fee parsing and EUR normalization.
- `src/research_school_radar/location_extraction.py` — labelled HTML/text location extraction and cleanup.
- `src/research_school_radar/filter.py` — hard filters and near-match classification.
- `src/research_school_radar/rank.py` — scoring and deduplication.
- `src/research_school_radar/report.py` — Markdown report output.
- `src/research_school_radar/site.py` — coordinates static site generation.
- `src/research_school_radar/site_assets.py` — configures the autoescaped Jinja environment and copies versioned static assets into generated sites.
- `src/research_school_radar/site_home_page.py` — homepage data preparation and document rendering.
- `src/research_school_radar/site_home.py` — homepage methodology, about, and FAQ sections.
- `src/research_school_radar/site_detail.py` — opportunity detail-page rendering.
- `src/research_school_radar/site_sources_page.py` — source-registry page rendering.
- `src/research_school_radar/site_components.py` — shared bilingual, duration, deadline, and evidence components.
- `src/research_school_radar/site_calendar.py` — Google, Outlook, and ICS deadline links.
- `src/research_school_radar/site_filters.py` — opportunity filter and pagination markup.
- `src/research_school_radar/site_layout.py` — shared navigation and footer layout.
- `src/research_school_radar/site_paths.py` — stable detail-page paths.
- `src/research_school_radar/web/templates/` — tracked Jinja page shells and component templates; page-renderer Python modules must not embed frontend markup.
- `src/research_school_radar/web/static/css/` — shared and page-specific browser stylesheets.
- `src/research_school_radar/web/static/js/` — bilingual UI, language bootstrap, filtering, responsive sidebar, and 15-item pagination.
- `src/research_school_radar/site_seo.py` — sitemap, robots, JSON-LD, canary, watermark helpers.
- `src/research_school_radar/site_feed.py` — RSS rendering.
- `src/research_school_radar/api_sources.py` — direct collectors for structured source APIs/listings.
- `src/research_school_radar/collector_ihe.py` — IHE Delft structured-course collector.
- `src/research_school_radar/collector_ellis.py` — ELLIS listing, follow-up, deadline, and fee collector.
- `src/research_school_radar/collector_sib.py` — SIB Bioschemas Course/CourseInstance collector.
- `src/research_school_radar/collector_sicss.py` — SICSS official locations catalogue collector; keeps each institute's dates and location separate.
- `src/research_school_radar/ai_pipeline.py` — semantic ranking, DeepSeek extraction configuration, and advisory-output orchestration used by the CLI.
- `src/research_school_radar/search.py` — optional two-stage search clients: explicit broad Serper discovery and Brave same-domain refinement.
- `src/research_school_radar/discovery_filter.py` — pre-fetch Serper result gates for social/aggregator domains, excluded programme types, past years, and official/programme signals.
- `src/research_school_radar/ai_page_filter.py` — deterministic page-quality gate before DeepSeek; rejects listing/generic, past, and weak-signal pages.
- `src/research_school_radar/scan_health.py` — rejects zero-source real scans, enforces 70% success across configured page/direct-collector attempts, and writes scan manifests.
- Full-scan manifests retain per-source last-attempt, last-success, and consecutive-failure state; status refreshes point directly to the latest full scan instead of recursively nesting refresh manifests.
- `src/research_school_radar/snapshot_validation.py` — validates candidate schema v2, non-empty display/scanner records, and suspicious retention below 35% before snapshot replacement.
- `src/research_school_radar/ai_output_validation.py` — rejects unusable semantic, DeepSeek extraction, or build-time Chinese translation output before an AI snapshot can replace the last known-good snapshot.
- `src/research_school_radar/audit_report.py` — summarizes source coverage, Serper discovery, Brave refinement, semantic/DeepSeek output, translation, and candidate retention for non-publishing audit runs.
- `src/research_school_radar/storage.py` — seen-state JSON handling.
- `src/research_school_radar/publication.py` — shared public/high-quality/found display classification.
- `src/research_school_radar/candidate_io.py` — shared `Candidate` JSON serialization/deserialization.
- `src/research_school_radar/session_extraction.py` — conservative, source-independent extraction of explicitly labelled multi-session schedules and per-session deadlines.
- `src/research_school_radar/programme_sessions.py` — shared multi-session duration/date labels for reports, RSS, and the site.
- `src/research_school_radar/urls.py` — validates public external URLs before rendering links.
- `src/research_school_radar/atomic_io.py` — atomically writes generated text artifacts with transient lock retries.

Optional AI branch:

```text
pages -> semantic chunks -> evidence snippets -> DeepSeek extraction -> validation -> homepage candidate copies
```

AI output is advisory. It may fill missing fields in copied candidates for homepage generation, then the normal hard filters run again. It must not mutate scanner `Candidate` objects, curated records, RSS source records, or Markdown report source records.

`Candidate.identity_key` is the stable identity for structured collector records and takes precedence over URL/title similarity during deduplication. Preserve it in JSON serialization, RSS GUIDs, detail-page names, and seen-state handling.

Candidate snapshot schema v2 stores AI/translation-ready homepage copies in `opportunities` and deterministic RSS/source records in `scanner_opportunities`. Never reconstruct RSS from the display list when scanner records are present.

Multi-session programmes use `Candidate.sessions` / `ProgrammeSession`. `start_date` and `end_date` describe the outer programme window only; `duration_days` must describe a real selectable session (normally the longest), never the number of calendar days between the first and last optional session. Preserve per-session dates and deadlines and render them in a collapsed schedule.

Multi-session extraction accepts explicitly labelled prose, table rows, and schema.org `subEvent` records. It may accept clearly named periods without numbers, but it must continue rejecting unlabelled event calendars.

## LLM and translation policy

- The only supported LLM provider is currently **DeepSeek**.
- Do not reintroduce Ollama, LM Studio, Qwen local-provider code, provider comparison scripts, or local-model setup instructions unless the user explicitly asks.
- API keys must come from environment variables or local ignored files. Never commit real keys.
- `DEEPSEEK_API_KEY` is used for optional LLM extraction and build-time Chinese translation.
- The model receives selected evidence snippets, not whole webpages and not browser control.
- Non-unknown model fields must cite valid evidence IDs and pass deterministic validation before being used in homepage copies.
- Search is not performed by DeepSeek. `SERPER_API_KEY` may power explicitly requested broad discovery in non-publishing manual audits only; `BRAVE_SEARCH_API_KEY` may power same-domain follow-up refinement. Missing search keys must degrade safely.

## Important configuration files

- `config/profile.yaml` — relevance topics, hard filters, financial-access rules, exchange-rate references.
- `config/sources.yaml` — trusted source registry. The optional `collector` field is the single switch for enabling a direct collector; do not hard-code collectors outside this registry.
- `config/queries.yaml` — optional controlled discovery queries.
- `config/site.yaml` — optional analytics settings.
- `config/ai.yaml` — semantic ranking, DeepSeek extraction, translation, cache, and budget settings.
- `data/opportunities.yml` — manually curated opportunity records.

Generated or local files should generally not be committed unless the task explicitly requires it:

- `site/`
- `data/http_cache/`
- `data/ai_cache/`
- `data/translation_cache/`
- `logs/`
- `.env`
- `.env.local`

The publishing automation is the explicit exception for the three versioned
last-known-good snapshots: `data/latest_candidates.json`,
`data/latest_sources.json`, and `data/latest_scan_manifest.json`.

Do not print `.env` or other secret-bearing files.

## Development setup

Use PowerShell commands on this Windows workspace.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run the offline sample:

```powershell
python -m research_school_radar.cli scan --offline-sample
```

Run a normal scan:

```powershell
python -m research_school_radar.cli scan
```

Rebuild the public site from the latest generated candidates without fetching source pages:

```powershell
python -m research_school_radar.cli refresh-status --candidates-json data/latest_candidates.json
```

Force source-page cache refresh:

```powershell
python -m research_school_radar.cli scan --refresh-http-cache
```

Optional AI scan:

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
python -m research_school_radar.ai_healthcheck --provider deepseek
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction
```

## Testing expectations

Run targeted tests for the area you changed. Prefer fast focused tests over an unrelated full suite during iterative work.

Common commands:

```powershell
python -m pytest tests/test_collect.py -q
python -m pytest tests/test_extract.py -q
python -m pytest tests/test_site.py -q
python -m pytest tests/test_translation.py -q
python -m pytest tests/test_cli_llm_flags.py tests/test_deepseek_client.py -q
```

Before handing off larger changes, run:

```powershell
python -m pytest -q
```

If full-suite failures are unrelated to the current change, state the exact failing tests and why they appear unrelated. Do not hide failing tests.

## Coding rules

- Keep generated public output auditable from official-source evidence.
- Keep hard filters deterministic.
- Do not let AI output bypass hard filters.
- Do not silently promote candidates into `data/opportunities.yml`.
- Do not add broad web crawling. Source expansion should happen through `config/sources.yaml`, direct collectors, or explicitly scoped discovery.
- Do not make network-heavy or API-key-dependent tests mandatory.
- Use fixture/stub tests for LLM, semantic, translation, and HTTP behavior.
- Prefer small modules over adding more responsibilities to `site.py`.
- When editing i18n-visible UI text, update Chinese translation contracts and run the relevant localization/translation tests.
- Do not display a multi-session outer date window as one continuous course duration.
- Preserve existing user changes in the working tree. Do not reset, checkout, or delete unrelated files without explicit approval.

## Documentation rules

- README is user-facing and should describe Summa at product level.
- `docs/TECHNICAL.md` and `docs/TECHNICAL.zh-CN.md` should stay aligned with current architecture.
- `docs/DEVELOPMENT_LOG.md` is for decisions, experiments, failures, and rationale.
- Do not leave placeholders such as `git clone <this-repository>`.
- Use "Summa" for product copy. Keep `research_school_radar` only for imports and commands.

## Publishing model

- `scripts/scan_and_publish.ps1` runs daily on the maintainer's Windows machine. On Monday/Wednesday/Friday it performs a residential-network, DeepSeek-assisted full scan; on other days it performs a no-network `refresh-status` rebuild from the latest snapshots.
- A full local scan must pass strict DeepSeek and Brave Search health checks, `scan_health.py`, `ai_output_validation.py`, and `snapshot_validation.py` before replacing snapshots.
- Only successful full scans update the three source snapshots on `main`; status refreshes rebuild presentation without overwriting source-scan snapshots. Full scans may also commit generated seen/review/report state. The local task never writes `gh-pages`.
- Scheduled Git operations may reuse a reachable Windows user proxy through process-scoped Git configuration and retry transient failures. If generation finishes while GitHub is unavailable, the automation records the generated commit under `.git/`, restores the clean pre-run branch, and retries that exact generated output after connectivity returns.
- The Windows task is allowed to start and continue on battery power; `StartWhenAvailable` handles missed wake times.
- `.github/workflows/ai_scan.yml` is the sole `gh-pages` writer. It runs a no-fetch `refresh-status` build from snapshots every day; its cloud AI scan modes are manual only. Manual `audit` runs upload evidence and metrics without committing snapshots or publishing, while manual `ai` runs may publish only after all gates pass.

## Current design priorities

1. Smaller, maintainable modules.
2. Higher information density on web and mobile pages.
3. Evidence-first extraction and translation.
4. Conditional caching and source-friendly fetching.
5. Clear separation between scanner output, AI advisory output, and curated records.
