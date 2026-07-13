# CLAUDE.md

This file is the Claude Code working guide for Summa. Read `AGENTS.md` first for the cross-agent project brief; this file adds Claude-specific execution rules and shortcuts.

## Identity and naming

- Product name: **Summa**.
- Python import package: `research_school_radar`.
- Python distribution / repository name: `summer-school-radar`.
- Keep those names separate. Do not rename imports, CLI module paths, package metadata, repository URLs, or generated GitHub Pages URLs just because product copy says Summa.
- Avoid the old public name "Summer School Radar" in user-facing copy, except when explicitly discussing legacy naming.

## First checks before editing

Use PowerShell in this workspace.

```powershell
git status --short
rg -n "TODO|FIXME|Ollama|LM Studio|qwen|<this-repository>|Summer School Radar|research-school-radar" README.md docs src tests config
```

Rules:

- Treat existing uncommitted changes as user work unless you created them in the current task.
- Do not run destructive git commands such as `git reset --hard`, `git checkout --`, or broad deletes without explicit permission.
- Do not print `.env`, `.env.local`, API keys, tokens, or local secret-bearing config.
- Prefer `rg` / `rg --files` for search.

## Project shape

Deterministic pipeline:

```text
config/sources.yaml
    -> collect.py + http_cache.py
    -> parse.py
    -> extract.py
    -> filter.py
    -> rank.py
    -> report.py / site.py
```

Optional AI branch:

```text
pages
    -> semantic.py
    -> evidence_snippets.py
    -> llm_extract.py via DeepSeek
    -> llm_validate.py
    -> ai_home.py homepage copies
```

AI branch constraints:

- DeepSeek is currently the only supported LLM provider.
- Do not reintroduce Ollama, LM Studio, Qwen local model setup, or provider comparison tools unless the user explicitly asks.
- AI output is advisory and evidence-gated.
- AI may fill homepage candidate copies, but must not mutate original scanner `Candidate` records, curated data, RSS source records, or Markdown report source records.
- Hard filters remain deterministic and must run after any AI-filled fields.

## Main files by responsibility

- `src/research_school_radar/cli.py` — CLI entry point and scan orchestration.
- `src/research_school_radar/collect.py` — HTTP collection and linked-page fetching.
- `src/research_school_radar/http_cache.py` — conditional request cache using `ETag` / `Last-Modified`, plus a 14-day stale-if-error fallback for transient failures.
- `src/research_school_radar/api_sources.py` — direct collectors for structured listings and JSON APIs, enabled only through each source's `collector` field in `config/sources.yaml`.
- `src/research_school_radar/ai_pipeline.py` — semantic/DeepSeek configuration and advisory-output orchestration, separated from the CLI entry point.
- `src/research_school_radar/parse.py` — candidate-link discovery.
- `src/research_school_radar/extract.py` — rule-based field extraction.
- `src/research_school_radar/filter.py` — hard conditions and near-match classification.
- `src/research_school_radar/rank.py` — scoring and deduplication.
- `src/research_school_radar/report.py` — Markdown reports.
- `src/research_school_radar/site.py` — static site coordinator.
- `src/research_school_radar/site_styles.py` — CSS.
- `src/research_school_radar/site_i18n.py` — bilingual UI dictionaries and language script.
- `src/research_school_radar/site_seo.py` — sitemap, robots, JSON-LD, canary, watermark.
- `src/research_school_radar/site_feed.py` — RSS feed.
- `src/research_school_radar/publication.py` — shared public/high-quality/found display classification.
- `src/research_school_radar/candidate_io.py` — shared `Candidate` JSON serialization/deserialization.
- `src/research_school_radar/session_extraction.py` — source-independent extraction of explicitly labelled multi-session schedules.
- `src/research_school_radar/date_extraction.py`, `fee_extraction.py`, and `location_extraction.py` — focused deterministic field extractors used by the candidate coordinator.
- `src/research_school_radar/collector_ihe.py` and `collector_ellis.py` — source-specific direct collectors registered by `api_sources.py` through `config/sources.yaml`.
- Source health tracks last attempt, last success, and consecutive failures per configured source; status-refresh manifests must not recursively nest older refresh manifests.
- Multi-session detection supports labelled prose, table rows, and JSON-LD `subEvent`; unlabelled event calendars remain excluded.
- `src/research_school_radar/programme_sessions.py` — multi-session duration/date presentation shared by reports, RSS, and HTML.
- `src/research_school_radar/site_components.py`, `site_calendar.py`, `site_filters.py`, `site_layout.py`, and `site_paths.py` — reusable site presentation primitives.
- `src/research_school_radar/site_detail.py` and `site_sources_page.py` — dedicated detail and source-page renderers; `site.py` remains the build coordinator.
- `src/research_school_radar/site_home_page.py`, `site_home.py`, and `site_home_styles.py` — homepage renderer, static sections, and homepage-only styles.
- `src/research_school_radar/urls.py` — validates public external URLs before rendering links.
- `src/research_school_radar/atomic_io.py` — atomically writes generated text artifacts with transient lock retries.
- `src/research_school_radar/scan_health.py` — non-empty-source and 70% combined page/direct-collector coverage gate plus scan manifests.
- `src/research_school_radar/snapshot_validation.py` — schema-v2/non-empty/35%-retention gate for last-known-good candidate snapshots.
- `src/research_school_radar/ai_output_validation.py` — validates semantic, DeepSeek extraction, and build-time Chinese translation artifacts before a snapshot is replaced.
- `src/research_school_radar/translation.py` — build-time Chinese translation support.
- `src/research_school_radar/localization_audit.py` — localization coverage checks.

If a change adds more HTML/CSS/JS/SEO/feed/i18n responsibility to `site.py`, consider splitting it into the relevant `site_*` module instead.

## Configuration and generated data

Configuration:

- `config/profile.yaml` — topics, hard filters, financial access, reference FX rates.
- `config/sources.yaml` — trusted source registry; the optional `collector` field is the sole activation switch for a structured direct collector.
- `config/queries.yaml` — optional controlled discovery queries.
- `config/site.yaml` — analytics settings.
- `config/ai.yaml` — semantic ranking, DeepSeek extraction, translation, cache, budgets.

Human-maintained data:

- `data/opportunities.yml` — curated records. Do not auto-promote candidates here.
- `data/overrides.yml`, if present — manual corrections. Preserve user edits.

Versioned publishing snapshots (automation-owned):

- `data/latest_candidates.json`
- `data/latest_sources.json`
- `data/latest_scan_manifest.json`

Generated/local outputs:

- `site/`
- `reports/*.ai.json`
- `reports/*.semantic.json`
- `data/http_cache/`
- `data/ai_cache/`
- `data/translation_cache/`
- `logs/`

Only commit generated files when the user explicitly asks for generated output or deployment artifacts.

## Common commands

Install dev dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Offline smoke scan:

```powershell
python -m research_school_radar.cli scan --offline-sample
```

Normal scan:

```powershell
python -m research_school_radar.cli scan
```

No-network status refresh from the latest generated candidates:

```powershell
python -m research_school_radar.cli refresh-status --candidates-json data/latest_candidates.json
```

Refresh HTTP cache:

```powershell
python -m research_school_radar.cli scan --refresh-http-cache
```

DeepSeek health check and optional AI scan:

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
python -m research_school_radar.ai_healthcheck --provider deepseek
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction
```

Do not assume the API key exists. If missing, keep work on deterministic code/tests unless the user asks to run live AI.

## Testing map

Run focused tests for changed areas:

- Collection/cache: `python -m pytest tests/test_collect.py -q`
- Extraction: `python -m pytest tests/test_extract.py -q`
- Filtering/ranking: `python -m pytest tests/test_rank.py -q`
- Site/RSS/SEO/i18n rendering: `python -m pytest tests/test_site.py tests/test_translation.py tests/test_localization_audit.py -q`
- DeepSeek/client flags: `python -m pytest tests/test_cli_llm_flags.py tests/test_deepseek_client.py tests/test_llm_validate.py -q`
- AI homepage merge: `python -m pytest tests/test_ai_home.py tests/test_ai_outputs.py -q`
- Search/follow-up: `python -m pytest tests/test_search.py tests/test_ai_followup.py -q`

For larger refactors:

```powershell
python -m pytest -q
```

If a full test run has unrelated existing failures, report the exact test names. Do not imply the suite passed.

## UI and localization rules

- Chinese UI must not fall back to English for newly added visible labels.
- When adding headings, buttons, filters, table headers, card labels, or status text, update the i18n dictionaries/contracts.
- Run localization or translation tests after touching visible UI copy.
- Keep desktop and mobile information density high. Avoid large single-opportunity cards unless there is a deliberate reason.

## Data quality rules

Fully qualified opportunities must satisfy all hard conditions:

- application is open or deadline has not passed;
- duration is at least 8 days;
- explicit participant funding exists, or confirmed total fee is within the configured low-fee threshold;
- in-person or substantially on-site;
- topic matches the configured profile.

When evidence is missing or ambiguous, classify as near-match rather than fully qualified.

Do not let model-generated translations, summaries, or inferred values become factual fields unless they are backed by official-source evidence and deterministic validation.

Structured collectors should set `Candidate.identity_key`. It takes precedence
over URL/title similarity for deduplication and must survive candidate JSON,
seen-state, RSS GUID, and detail-page serialization.

Candidate snapshot schema v2 keeps homepage/display copies in `opportunities`
and deterministic RSS records in `scanner_opportunities`; status refreshes must
preserve both collections separately.

For `Candidate.sessions`, the candidate start/end dates are only the outer
programme window. Keep each `ProgrammeSession` date/deadline, calculate
`duration_days` from a real selectable session, and render the schedule folded.

## Documentation maintenance

Keep these aligned:

- `README.md` — user-facing product overview.
- `docs/TECHNICAL.md` — English technical detail.
- `docs/TECHNICAL.zh-CN.md` — Chinese technical detail.
- `docs/DEVELOPMENT_LOG.md` — decisions, experiments, failures, and rationale.
- `AGENTS.md` — cross-agent operating brief.
- `CLAUDE.md` — Claude Code operating brief.

No placeholders such as `git clone <this-repository>`.

## Publishing schedule

- `scripts/scan_and_publish.ps1` runs daily through Windows Task Scheduler.
- In `Auto` mode it runs a residential-network, DeepSeek-assisted full source scan on Monday/Wednesday/Friday. The scan must pass the combined source-coverage gate, `ai_output_validation.py`, and `snapshot_validation.py` before replacing the last known-good snapshot.
- On other days it runs `python -m research_school_radar.cli refresh-status --candidates-json data/latest_candidates.json`, updating date-sensitive state without fetching source pages.
- Only full scans replace the three source snapshots; status refreshes rebuild presentation without overwriting them. The local task may commit generated seen/review/report state and never writes `gh-pages`.
- `.github/workflows/ai_scan.yml` is the only `gh-pages` writer. Its scheduled daily mode rebuilds from snapshots with no source fetch; cloud DeepSeek scanning is manual only.

## Handoff format

When finishing a task, report:

1. files changed;
2. what behavior changed;
3. tests run and exact result;
4. known failures or skipped checks;
5. any files intentionally not touched.
