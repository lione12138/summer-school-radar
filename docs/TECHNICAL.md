# Summa Technical Notes

Technical notes for Summa, an open-source scanner for funded research training opportunities across many academic fields: environmental & earth science, computing & data science, social sciences, and humanities. It covers seasonal schools and short courses such as summer schools, winter schools, spring/autumn schools, training schools, field schools, doctoral schools, research schools, and short/advanced courses. Generic conference workshops are not included.

The project is inspired by curated vertical opportunity platforms such as Josh's Water Jobs, but it is aimed at research training rather than jobs. The goal is not to crawl the whole web. The goal is to maintain a trusted source registry, scan it regularly, extract structured evidence, apply strict filters, and publish a transparent public report.

## Three-Minute Start

```powershell
git clone https://github.com/lione12138/summer-school-radar.git
cd summer-school-radar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m research_school_radar.cli scan --offline-sample
```

Then open:

- `reports/YYYY-MM-DD.md` for the Markdown report
- `site/index.html` for the static website
- `site/candidates.json` for schema-v2 homepage copies (`opportunities`) and isolated deterministic RSS records (`scanner_opportunities`)
- `site/curated.json` for maintainer-reviewed records

Run a real fixed-source scan with:

```powershell
python -m research_school_radar.cli scan
```

Plain HTTP source pages are cached under ignored `data/http_cache/` with their
`ETag` and `Last-Modified` validators. Later scans send conditional request
headers and reuse the cached body on `304 Not Modified`, which reduces repeated
downloads for pages that change only every few weeks. Pass
`--refresh-http-cache` to bypass validators and overwrite the cache.

## Why Not Another Research-Training List?

Most opportunity lists are plain link collections. Summa is different:

- it targets research training opportunities, not generic study-abroad marketing
- it stores source evidence for high-risk fields such as deadline and funding
- it separates fully qualified opportunities from near-matches
- it makes failed hard conditions visible instead of hiding uncertainty
- it has a curated layer for maintainer-reviewed records
- it publishes a static website, Markdown reports, and JSON data
- it can publish daily to GitHub Pages, while limiting full source fetches to scheduled local scan days

## Current Status

This repository now contains the current Summa pipeline:

- fixed-source scanner for trusted academic and research organizations
- second-level candidate link following from source pages
- rule-based extraction for title, type, organizer, location, dates, duration, deadline, funding, topics, eligibility, fee, normalized EUR fee, and mode, with per-field source evidence and a transparent extraction-confidence score (the fraction of the four high-risk fields that were resolved)
- schema.org JSON-LD parsing and extraction adapters: domain adapters (ICIMOD) and structural adapters keyed by markup rather than site, e.g. WordPress "The Events Calendar" (used by ESA EO4Society, IEEE GRSS, and many academic event sites), which yields reliable dates, venue, and the official external application URL
- hard filtering that separates fully qualified opportunities from near-matches
- interpretable ranking
- Markdown report generation
- static website generation with browser-side filters
- JSON state file tracking seen opportunities
- conditional requests plus a bounded stale-if-error fallback for source-friendly collection
- a non-empty-source and 70% combined page/direct-collector coverage gate before a full scan may replace the public snapshot
- a schema-v2/non-empty/35%-retention candidate snapshot gate before last-known-good replacement
- local Monday/Wednesday/Friday DeepSeek-assisted collection and daily snapshot-based status refreshes
- single-writer GitHub Pages deployment through GitHub Actions
- GitHub issue template for external submissions
- optional analytics injection for Cloudflare Web Analytics or GoatCounter
- curated opportunity records generated from `data/opportunities.yml`
- test coverage split by module (`test_extract.py`, `test_site.py`, `test_rank.py`, `test_collect.py`, `test_report.py`, `test_review.py`, `test_storage.py`, etc.)

## What It Looks For

The default profile targets MSc, PhD, postdoc, and early-career research training across multiple fields: environmental & earth science, computing & data science, social sciences, and humanities methods. The `preferred_topics` list in `config/profile.yaml` is the relevance gate; widening or narrowing the domain is a matter of editing that list, but the focused source registry keeps the gate tractable.

An opportunity is treated as fully qualified only when all hard conditions are satisfied:

- application is open or the deadline has not passed
- duration is at least 5 days
- scholarship, travel grant, tuition waiver, stipend, accommodation support, or other funding is explicit; or the confirmed total fee is no more than approximately EUR 400
- in-person or substantially on-site, not online-only
- topic is relevant to the configured research profile

If no opportunity fully qualifies, the system says so clearly and lists only still-open near-matches. An opportunity is treated as past — and excluded from the still-open list — when its deadline has passed, or, when no deadline could be extracted, when the event itself has already started. Near-matches are never presented as qualified opportunities. Their failed hard conditions remain available in `site/candidates.json` for maintainers rather than occupying a public table column.

The scanner includes `training school` because research organizations commonly use that label for short, intensive summer-school-style programmes. Generic conference workshops are excluded entirely, since they are rarely funded multi-day schools; the remaining hard filters then apply to the school and course types that are kept.

## Architecture

The pipeline is intentionally simple Python rather than a multi-agent framework.

```text
Default branch:
sources -> collect -> parse -> extract rules -> filter -> rank -> report/site

Optional AI branch:
pages -> semantic chunks -> evidence snippets -> DeepSeek extraction -> evidence-ID validation -> homepage candidate copies + sidecar JSON
```

`config/sources.yaml` is also the authority for structured sources: a source's
optional `collector` value selects the matching direct collector in
`api_sources.py`. Page sources and direct collectors therefore share one
enabled/disabled registry rather than following separate hard-coded schedules.

The optional branch never overwrites scanner `Candidate` records. For the
generated homepage only, it may fill unresolved fields in deep-copied candidates
and then reruns the same hard filters and ranking. Markdown reports, RSS, state,
and curated data continue to use rule-based candidates.

For product-level reasoning, successful experiments, failed experiments, and
workflow tradeoffs, see `docs/DEVELOPMENT_LOG.md`.

## Optional semantic ranking

The default scan remains the rule-based pipeline above. It is lightweight,
API-key-free, and does not require semantic dependencies:

```powershell
pip install -e ".[dev]"
python -m research_school_radar.cli scan --offline-sample
python -m research_school_radar.cli scan
```

The optional semantic layer is advisory only. It ranks chunks from scanned pages
with `BAAI/bge-m3` via `sentence-transformers`, and writes sidecar
JSON for maintainers. It does not change `Candidate` records, hard filters,
`fully_qualified` status, ranking, Markdown report tables, RSS, or public site
tables. The source of truth for public qualification remains the rule-based
extractor and hard filters. Semantic ranking is cached under `data/ai_cache/`
using page URL, page text hash, embedding model, query hash, and chunking
config. Pages are ranked before the `max_pages_for_ai` limit is applied, and a
per-source cap keeps one large site from filling the whole review sidecar.

```powershell
pip install -e ".[dev,semantic]"
python -m research_school_radar.cli scan --enable-semantic
```

It writes:

- `site/semantic_chunks.json`
- `reports/YYYY-MM-DD.semantic.json`

### Semantic model notes

The first semantic implementation used `BAAI/bge-small-en-v1.5` because it is
fast and easy to run locally. In a June 2026 comparison on the optimized
semantic pipeline, `BAAI/bge-m3` produced stronger recall for already-known
opportunity pages and surfaced useful pages such as Leiden Science
Communication, Essex application pages, ICVSS application pages, and Tinbergen
summer-school pages. The same run used 212 considered pages and the same query,
chunking, per-page, and per-source limits:

| Model | Ranking time | Selected chunks | Matched existing candidates | Unmatched chunks | Notes |
|---|---:|---:|---:|---:|---|
| `BAAI/bge-small-en-v1.5` | 53.19s | 51 | 17 | 34 | Faster, lighter, but lower recall on known opportunities. |
| `BAAI/bge-m3` | 212.33s | 55 | 24 | 31 | Better recall, acceptable runtime for manual or scheduled semantic review. |

The project therefore defaults to `BAAI/bge-m3` for semantic review. Semantic
ranking alone does not change any opportunity data; it only selects evidence for
the optional LLM stage.

LLM extraction is also optional. It turns semantic chunks into
short numbered evidence snippets, sends those snippets to DeepSeek, and writes
structured sidecar JSON. Evidence-validated fields may enrich homepage
candidate copies, but cannot bypass hard filters. It does not change stored
`Candidate` records, Markdown report tables, RSS, or curated data.

The only supported LLM provider in the current codebase is DeepSeek:
OpenAI-compatible `/chat/completions`, default model `deepseek-v4-flash`,
`response_format: {"type": "json_object"}`, and
`thinking: {"type": "disabled"}`.

```powershell
pip install -e ".[dev,semantic,llm]"
$env:DEEPSEEK_API_KEY = "sk-..."
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction
```

DeepSeek requires a user-supplied API key. This project does not create API keys
or store real API keys in configuration files. If the configured provider is
unavailable, LLM extraction records a warning and the scan continues with the
existing rule-based outputs. The code strips thinking traces from model
responses as a fallback, and records `llm_json_parse_failed` instead of
crashing when output is not clean JSON.

That tolerant behavior is useful for ad hoc scans. Production snapshotting is
stricter: the local scheduler runs `ai_healthcheck --strict` before scanning and
`ai_output_validation.py` afterwards, so an unusable AI run cannot replace the
previous snapshot.

LLM extraction sends only selected semantic chunks, never full webpages. The
default resource limits are:

- `max_pages_for_ai: 150`
- `max_pages_per_source: 8`
- `max_pages_for_llm: 150`
- `max_chunks_per_page: 3`
- `max_chars_per_chunk: 2200`
- `max_total_chars_per_request: 7000`

The 150-page values are exploratory upper bounds for measuring real scheduled-run
sizes. Actual LLM calls are often fewer because pages must first pass source
collection, semantic similarity, and the per-source page cap. Once real run
sizes are known, lower these caps to the smallest values that preserve useful
recall.

The extraction schema is evidence-first. Each extractable field uses:

```json
{"value": "...", "evidence_ids": ["E1"], "resolved_evidence_texts": ["..."]}
```

The model receives numbered snippets and should return only `evidence_ids`.
`llm_extract.py` resolves IDs back to short snippet previews after the model
responds. `llm_validate.py` warns when a non-unknown value has no evidence ID,
an ID does not exist, or the cited snippet lacks field-specific context such as
deadline, fee, funding, location, or eligibility wording. Public sidecars keep
short snippet previews and do not dump full raw page text.

#### Using DeepSeek API

DeepSeek is the first recommended remote API provider to test. Its API uses an
OpenAI-compatible base URL, supports `deepseek-v4-flash`, supports JSON output,
and supports switching thinking mode off. The scanner sends only selected
`BAAI/bge-m3` semantic snippets to DeepSeek, not full webpages.

Configuration:

```powershell
$env:LLM_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "sk-..."
```

Optional explicit settings:

```powershell
$env:LLM_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
```

Then run:

```powershell
python -m research_school_radar.ai_healthcheck --provider deepseek
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
```

The DeepSeek request body is intentionally non-thinking:

```json
{
  "response_format": {"type": "json_object"},
  "thinking": {"type": "disabled"}
}
```

DeepSeek results remain fully auditable in sidecar data. Trusted fields can fill
homepage gaps and the normal hard filters are then recomputed; warned fields are
ignored for this merge. RSS and Markdown reports remain rule-based.

#### Bounded follow-up retrieval

After the first extraction, `ai_followup.py` selects only non-index,
non-expired items that still lack critical fields. The follow-up stage:

1. scores same-domain links for application, registration, deadline, fee,
   tuition, rates, funding, scholarship, grant, date, and practical-information
   signals;
2. follows links for at most the configured number of rounds and pages;
3. optionally submits title-aware `site:domain` queries through the existing
   Brave Search client when `BRAVE_SEARCH_API_KEY` is configured;
4. rejects search results outside the original official domain;
5. ranks fetched pages with the configured semantic model;
6. combines original and related evidence into a second LLM extraction;
7. retains the first extraction if the revised result resolves fewer critical
   fields or fails.

Default resource limits in `config/ai.yaml`:

```yaml
follow_up:
  enabled: true
  max_rounds: 2
  max_opportunities: 20
  max_queries_per_opportunity: 2
  max_results_per_query: 3
  max_pages_per_opportunity: 4
  max_total_followup_pages: 60
  max_followup_chunks_per_opportunity: 8
  max_total_chars_per_followup_request: 12000
  official_domains_only: true
  external_search_enabled: true
```

DeepSeek does not receive unrestricted browser control. The scanner performs
the HTTP requests and search calls, enforces budgets and domains, and passes
only selected evidence snippets to the model. Search failure, missing Brave
credentials, semantic failure, or follow-up extraction failure cannot abort the
rule-based scan or remove the initial AI extraction. Broad discovery is a
separate, explicit Serper stage and never replaces this same-domain refinement.

The extraction prompt now labels page type and registration status, separates
the primary application/registration deadline from other deadlines, rejects
cross-edition evidence, and requests complete fee tiers. Validation remains
deterministic and checks evidence IDs, context, date and fee support, explicit
closed language, past dates, index-page risk, and payment-deadline confusion.
It does not constitute independent factual certification. Homepage inclusion
still requires the evidence-gated merge and the normal rule pipeline; curated
publication still requires human review.

LLM extraction is cached under `data/ai_cache/` using page URL, selected chunk
text hash, model name, and `AI_EXTRACTION_SCHEMA_VERSION`. Use
`--refresh-ai-cache` to ignore cached semantic and LLM entries:

```powershell
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
```

LLM sidecar output goes to:

- `site/ai_extractions.json`
- `reports/YYYY-MM-DD.ai.json`

The DeepSeek endpoint can be checked separately without running a scan:

```powershell
python -m research_school_radar.ai_healthcheck
```

Tests do not download `BAAI/bge-m3`, require API keys, or require
model files. Semantic and LLM tests use stubs and empty offline page pools to
keep CI deterministic.

### AI-assisted homepage workflow

Semantic ranking is meant to surface pages that the rule-based
`looks_like_opportunity` gate may miss. LLM extraction creates advisory
structured drafts from numbered snippets, and `llm_validate.py` checks whether
non-unknown fields cite existing evidence IDs with suitable context.

AI output is integrated through `ai_home.py`:

- `data/review_queue.json` and `site/review_queue.json` include an
  `ai_advisory` block for candidates whose source or application URL exactly
  matches an AI extraction page URL.
- `site/ai_extractions.json` remains the advisory sidecar. Items include
  `evidence_snippets`, field-level `evidence_ids`, resolved short evidence
  previews, validation warnings, and confidence.
- Exact URL matches fill only missing or uncertain fields, and field-specific
  validation warnings block the affected field.
- Unmatched pages can become candidates only when `page_type` is explicitly
  `opportunity` or `application`; legacy unclassified outputs, fee pages,
  funding pages, and indexes cannot create standalone opportunities.
- The merged copies are run through `apply_hard_filters` and `rank_candidates`
  before rendering the existing three homepage tables.

AI output never mutates the scanner's original `Candidate` objects and does not
affect Markdown reports, RSS inclusion, scan state, or curated data. The public
homepage can reflect AI-filled evidence, but qualification remains a result of
the same deterministic hard filters. The manual curation path is:

```text
AI extraction -> maintainer checks official page -> maintainer edits data/opportunities.yml or data/overrides.yml
```

There is deliberately no automatic promotion into curated data.

Before production automation replaces a last-known-good snapshot,
`ai_output_validation.py` requires usable semantic chunks and at least one
usable evidence-validated DeepSeek extraction. This build-level check is in
addition to field-level validation in `llm_validate.py`.

### Real-world AI validation

Unit tests keep the optional AI branch safe and deterministic, but they do not
prove extraction quality on real organiser pages. Use this manual validation
sequence when checking the advisory branch:

```powershell
python -m research_school_radar.ai_healthcheck
$env:HF_HOME = Join-Path $env:TEMP "summer-school-radar-hf-cache"
python -m research_school_radar.cli scan --enable-semantic --refresh-ai-cache
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
python -m research_school_radar.ai_evaluate
```

`ai_evaluate.py` reads `site/ai_extractions.json` and writes:

```text
reports/YYYY-MM-DD.ai-evaluation-template.csv
```

If an annotated file exists at
`reports/YYYY-MM-DD.ai-evaluation-annotated.csv`, the command prints simple
yes/no rates for deadline, fee, funding, location, and summary usefulness. The
accepted human annotation values are `yes`, `no`, `unknown`, or empty. The tool
uses the standard library `csv` module and does not require pandas.

#### Comparing real AI extraction runs

Quality should be judged on real page sidecars. A typical workflow is:

```powershell
# Run DeepSeek extraction and keep a copy of the sidecar.
$env:LLM_PROVIDER = "deepseek"
$env:LLM_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
$env:DEEPSEEK_API_KEY = "sk-..."
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
Copy-Item reports/YYYY-MM-DD.ai.json reports/before.ai.json

# Change prompts, validation, or source configuration, then run again.
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
Copy-Item reports/YYYY-MM-DD.ai.json reports/after.ai.json

# Compare real outputs.
python -m research_school_radar.ai_compare_runs --left reports/before.ai.json --right reports/after.ai.json --left-name before --right-name after
```

The command writes:

```text
reports/YYYY-MM-DD.ai-run-comparison.md
```

It matches items by `page_url`, compares item counts, valid extraction counts,
confidence distributions, validation warning types, average warning count per
item, evidence-ID health, missing pages on each side, and disagreements for
title, event type, location, start/end dates, application deadline, fee,
funding, and eligibility.
It uses only the Python standard library and does not call any LLM provider.

Recommended operation:

- Manual deterministic scan: `python -m research_school_radar.cli scan`
- Manual semantic review: `python -m research_school_radar.cli scan --enable-semantic`
- Production-style AI scan: `python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --no-readme-update`
- Production AI-output gate: `python -m research_school_radar.ai_output_validation --site-dir site`

The local scheduler enables LLM extraction only on full-scan days. Health,
coverage, or AI-output validation failures preserve the previous snapshot;
maintainer review against official pages is still required for curation.

### Key Files

- `src/research_school_radar/cli.py` is the command entry point.
- `src/research_school_radar/collect.py` fetches source and linked pages with `requests` and `BeautifulSoup`, using conditional HTTP caching for normal requests.
- `src/research_school_radar/http_cache.py` stores page bodies plus `ETag` / `Last-Modified` validators under ignored `data/http_cache/`. A request exception, HTTP 429, or HTTP 5xx may reuse a cached body no older than 14 days; HTTP 404 and older entries do not use this fallback.
- `src/research_school_radar/parse.py` identifies likely opportunity links and skips unsuitable files or blocked domains.
- `src/research_school_radar/extract.py` performs rule-based structured extraction.
- `src/research_school_radar/filter.py` applies hard filters.
- `src/research_school_radar/rank.py` scores and deduplicates candidates. Stable collector identities take precedence; URL/title/date similarity is used only when no structured identity is available. Facts are merged before hard filters and scores are recomputed.
- `Candidate.identity_key` carries that structured identity through JSON, seen-state, RSS GUIDs, and stable detail-page names.
- `src/research_school_radar/report.py` writes Markdown reports.
- `src/research_school_radar/site.py` coordinates static website generation.
- `src/research_school_radar/site_assets.py` loads package-owned HTML shells and copies tracked CSS/JavaScript from `web/static/` into each generated site. `site_seo.py` and `site_feed.py` retain SEO/sitemap/robots/watermark helpers and RSS rendering.
- `src/research_school_radar/urls.py` validates external links before they enter HTML, JSON-LD, or RSS.
- `src/research_school_radar/atomic_io.py` atomically replaces generated text artifacts and retries transient Windows file locks.
- `src/research_school_radar/storage.py` updates the JSON seen-state file (data/seen.json).
- `src/research_school_radar/semantic.py` writes optional semantic chunk sidecars.
- `src/research_school_radar/evidence_snippets.py` selects short numbered snippets for evidence-first LLM prompting.
- `src/research_school_radar/ai_cache.py` implements the lightweight file cache for optional AI work.
- `src/research_school_radar/llm_client.py`, `llm_extract.py`, and `llm_validate.py` implement optional advisory LLM sidecars.
- `src/research_school_radar/ai_healthcheck.py` checks the configured LLM provider.
- `src/research_school_radar/scan_health.py` rejects zero-source real scans, enforces 70% success across page and direct-collector attempts, and writes scan manifests.
- `src/research_school_radar/snapshot_validation.py` requires schema-v2 display/scanner lists and rejects an unexplained scanner-record drop below 35% of a sufficiently large previous snapshot.
- `src/research_school_radar/session_extraction.py` conservatively detects explicitly labelled sessions and their deadlines on any source page; it requires at least two distinct labelled ranges so ordinary event calendars are not promoted.
- `src/research_school_radar/date_extraction.py`, `fee_extraction.py`, and `location_extraction.py` isolate deterministic date/deadline, fee, and location parsing from the candidate assembly performed by `extract.py`.
- `src/research_school_radar/collector_ihe.py`, `collector_ellis.py`, `collector_sib.py`, and `collector_sicss.py` contain source-specific direct-collector implementations. The SIB collector reads the official catalogue's embedded Bioschemas `Course` / `CourseInstance` records, while SICSS reads its official server-rendered location cards as separate institutes. `api_sources.py` only dispatches collector names configured in `config/sources.yaml` and records health outcomes.
- Full scans attach per-source health (`status`, `last_attempt`, `last_success`, and `consecutive_failures`) to the manifest and source-registry output. Status-refresh manifests collapse to one reference to the latest full scan, avoiding recursive growth.
- Multi-session extraction handles labelled prose, labelled table rows with optional deadline columns, and schema.org `subEvent` data. Clearly named periods such as “Foundation week” are accepted without numbering, while unlabelled calendars are still rejected.
- `src/research_school_radar/programme_sessions.py` formats structured session dates and per-session deadlines consistently across HTML, reports, and RSS.
- `src/research_school_radar/web/templates/` contains the tracked homepage, detail-page, and source-page HTML shells; `web/static/css/` and `web/static/js/` contain the browser assets. `site_detail.py`, `site_sources_page.py`, and `site_home_page.py` prepare escaped page fragments, while `site_components.py`, `site_calendar.py`, `site_filters.py`, `site_layout.py`, and `site_paths.py` provide reusable presentation primitives. `site.py` coordinates artifact generation.
- `src/research_school_radar/site_home.py` owns the homepage's static explanatory sections. HTML, CSS, and JavaScript are no longer stored in Python string constants.
- `src/research_school_radar/ai_pipeline.py` owns semantic ranking, DeepSeek configuration, follow-up orchestration, and AI sidecar generation so `cli.py` remains an entry-point coordinator.
- `src/research_school_radar/ai_output_validation.py` protects production snapshots from empty semantic/DeepSeek output or failed build-time Chinese translation.
- `src/research_school_radar/ai_evaluate.py` writes the human annotation CSV for real-world AI quality checks.

## Configuration

- `config/profile.yaml` controls preferred topics, hard filters, financial-access thresholds and reference exchange rates, priority regions, supplementary regions, and excluded programme types.
- `config/sources.yaml` lists trusted sources. Each source can be enabled or disabled, can block problematic linked domains, and can select a structured direct collector with `collector`.
- Sources explicitly registered as `research_training_provider` may expose subject-only course-card titles. The link parser follows cards whose nearby official metadata says `Course`; the detail extractor still requires a course overview and rejects conference pages deterministically.
- `config/queries.yaml` stores optional controlled discovery queries.
- `config/site.yaml` controls optional analytics.
- `config/ai.yaml` controls optional semantic ranking, DeepSeek advisory extraction, resource limits, and `data/ai_cache/` behavior.
- `data/opportunities.yml` is the manually curated high-confidence opportunity database.

Example source options:

```yaml
- name: ICIMOD
  url: https://www.icimod.org/events/
  layer: 1.5
  region: South Asia
  source_type: intergovernmental_research
  keywords: [Himalayan, climate, water, capacity building]
  blocked_link_domains: [servir.icimod.org]
  notes: Strong regional water and climate relevance.
```

Direct collectors use the same registry rather than a separate code-side
allowlist:

```yaml
- name: IHE Delft Institute for Water Education
  url: https://www.un-ihe.org/education/short-courses
  collector: ihe_delft
  enabled: true
```

Disabled sources stay documented without creating scan noise:

```yaml
- name: IIASA
  url: https://iiasa.ac.at/events
  enabled: false
  notes: Site currently returns Cloudflare 403 for scripted requests.
```

## Publishing Workflows

Collection and publication are deliberately separated. The maintainer's Windows
machine runs `scripts/scan_and_publish.ps1` daily because its residential
connection reaches more official sites than a GitHub-hosted runner. On Monday,
Wednesday, and Friday the script performs a semantic + DeepSeek-assisted full
scan. It requires strict DeepSeek and Brave Search health checks, the combined
source-coverage gate from `scan_health.py`, `ai_output_validation.py`, and the
schema/retention gate in `snapshot_validation.py` before replacing the
last-known-good publish snapshot.

Scheduled Git synchronization reuses a reachable Windows user proxy when Git
has no explicit proxy configuration, then applies bounded retries. The proxy is
process-scoped and does not change global Git settings. If GitHub remains
unreachable, a clean machine may still finish one local generation run. Any
generated commit is recorded under `.git/` and the working branch is returned to
its pre-automation revision. A later run verifies the queued commit contains
only the recorded generated paths and publishes it after the remote recovers;
stale queued output is discarded if newer `main` already changed those paths.
This keeps API work recoverable without leaving `main` ahead or touching user
edits.

The registered Windows task uses `StartWhenAvailable`, permits execution on
battery power, and does not stop when the laptop switches from AC to battery.
This avoids an indefinitely queued refresh on unplugged maintainer machines.

On other days the local script runs:

```powershell
python -m research_school_radar.cli refresh-status --candidates-json data/latest_candidates.json
```

That command recalculates deadline/open/closed status without fetching source
pages. It does not overwrite the source-scan snapshots; the daily GitHub Pages
job performs the same no-fetch rebuild for publication. The versioned inputs are:

- `data/latest_candidates.json`
- `data/latest_sources.json`
- `data/latest_scan_manifest.json`

After a full local scan, the same commit can also include its generated
`seen.json`, review queue, and dated Markdown report. Those files preserve scan
history and auditability; they are not alternate Pages publishers.

The local task never writes `gh-pages`. `.github/workflows/ai_scan.yml` is the
only Pages writer, protected by a single publisher concurrency group. Its daily
scheduled mode copies the committed source snapshot, runs `refresh-status` from
the candidate snapshot, and publishes the resulting `site/` directory to
`gh-pages`. This keeps date-sensitive presentation current while avoiding daily
source load and competing branch writers.

Cloud AI scanning is manual only. Selecting the workflow's `ai` mode installs
the semantic/LLM extras, reads `DEEPSEEK_API_KEY` from repository secrets, runs
the bounded scan, validates it with `ai_output_validation.py` and
`snapshot_validation.py`, persists the
accepted snapshots, and publishes through the same single-writer job. An
optional `BRAVE_SEARCH_API_KEY` enables controlled same-domain refinement,
`SERPER_API_KEY` enables explicitly requested broad discovery only in manual
non-publishing audits, and an optional `HF_TOKEN` raises Hugging Face download
limits. Secret values are never written to generated output or commits.

## Public Website

The scanner generates:

- `site/index.html`
- `site/candidates.json`
- `site/curated.json`
- `site/.nojekyll`

The website is static and can be served by GitHub Pages. It includes browser-side filters for:

- keyword search
- status
- topic
- financial access: explicit funding, low/no fee, or unresolved/high fee
- deadline status

The homepage paginates the combined matching result set at 15 records per page.
Desktop layouts keep search and filters in a sticky left sidebar. On mobile,
search remains visible while the other controls collapse behind a button. The
internal `found` classification remains available as a filter/data attribute,
but its cards do not display a warning-style status badge; the public label is
the neutral `Listed` tier.

Curated opportunities from `data/opportunities.yml` are rendered first as a separate section. Automatic scanner results appear below them as fully qualified opportunities or near-matches.

Rows with a known application deadline include an `Add to calendar` link in the deadline column. The link downloads a standard `.ics` all-day calendar event for the application deadline, so users can import it into Apple Calendar, Google Calendar, Outlook, or another calendar client.

The generator also writes `site/sources.html` and `site/sources.json` from `config/sources.yaml`. This Sources & Coverage page shows enabled and disabled sources, source layer, region, source type, keywords, blocked linked domains, and notes.

It also writes `site/feed.xml`, an RSS 2.0 feed of curated, fully qualified, and still-open near-match opportunities, advertised from the homepage for autodiscovery so users and aggregators can subscribe instead of visiting the page.

## Financial Access Rule

The financial hard condition passes when either:

- participant funding is explicit; or
- the extracted total fee converts to no more than `maximum_unfunded_fee_eur`, which defaults to EUR 400.

`extract.py` recognizes common currency codes and symbols, free participation, and fee ranges. For a range it uses the highest amount. Supported currencies are converted through the fixed `financial_access.approximate_currency_to_eur` map in `config/profile.yaml`.

This design keeps scheduled scans free and avoids an exchange-rate API key. The rates are conservative reference values rather than live market rates. If the currency or amount cannot be normalized confidently, the candidate remains a near-match.

No backend server is required. The filters operate on HTML `data-*` attributes generated for each table row.

The public table intentionally hides internal ranking fields such as region priority and failed hard conditions. Those fields remain in `site/candidates.json` for maintainers and debugging. Scanner titles link to an internal detail page; official-page actions are rendered only for validated HTTP(S) URLs.

After pushing to GitHub, configure Pages to serve the `gh-pages` branch. The
daily GitHub Actions refresh publishes the latest committed snapshot. Run the
workflow manually in `ai` mode only when a cloud-side advisory scan is
specifically needed; routine full collection remains local on
Monday/Wednesday/Friday.

The public site will be available at:

```text
https://<username>.github.io/<repository>/
```

## Curator Workflow

The project separates automatic discovery from curated publication.

```text
scanner output
    -> reports/YYYY-MM-DD.md
    -> site/candidates.json
    -> maintainer review
    -> data/opportunities.yml
    -> public curated layer
```

The intended workflow is:

1. The scanner finds candidates and near-matches.
2. Maintainers inspect the official source page.
3. Deadline, funding, duration, mode, and eligibility evidence are checked.
4. High-confidence records are added to `data/opportunities.yml`.
5. External contributors can submit opportunities through the GitHub issue template.

This mirrors the useful part of curated platforms: automatic discovery helps, but trust comes from review and clean structured records.

## External Submissions

The repository includes:

```text
.github/ISSUE_TEMPLATE/submit-opportunity.yml
```

Contributors can submit:

- title
- official URL
- organizer
- opportunity type
- location
- duration
- deadline
- mode
- funding evidence
- topic fit
- eligibility
- notes or risks

This gives the project a lightweight community submission path without building a custom backend.

## Doctoral Schools Scope

The scanner keeps `doctoral school` as an opportunity term because many European and research-network training events use labels such as doctoral school, PhD school, graduate training school, or doctoral training school for short seasonal research training.

The scanner should not collect PhD degree admissions, PhD positions, full-time doctoral programmes, or ordinary graduate school enrollment. `config/profile.yaml` documents this scope, and `parse.py` excludes common degree-recruitment phrases before treating a page as an opportunity.

## Analytics

GitHub Pages does not provide a long-term public analytics dashboard for the generated website. The project supports optional client-side analytics through `config/site.yaml`.

Default:

```yaml
analytics:
  provider: none
  cloudflare_token: ""
  goatcounter_code: ""
```

Cloudflare Web Analytics:

```yaml
analytics:
  provider: cloudflare
  cloudflare_token: "your-token"
```

GoatCounter:

```yaml
analytics:
  provider: goatcounter
  goatcounter_code: "your-dashboard-code"
```

When analytics is disabled, no tracking script is injected. When enabled, the dashboard lives in the analytics provider, not inside this repository.

## Optional Controlled Discovery Search

The default scan does not scrape Google or other search-result pages. Broad
discovery is optional and uses Serper only when `--include-discovery` is passed.
Before fetching, results from social/aggregator domains, excluded programme
types, explicit past years, missing programme signals, or missing official
signals are rejected. Accepted results remain labelled as discovery sources
and still pass normal extraction and hard filters. Serper discovery is separate
from Brave's same-domain field refinement in the AI follow-up stage.

```powershell
$env:SERPER_API_KEY = "..."
$env:BRAVE_SEARCH_API_KEY = "..."
python -m research_school_radar.cli scan --include-discovery --enable-semantic --enable-llm-extraction
```

This combined command runs broad Serper discovery first. Candidates and known
official-source pages then enter the normal semantic/evidence pipeline; Brave
may search only within an already known official domain when important fields
remain unresolved. Either stage can also be enabled independently. For example,
to use only precise Brave follow-up with the fixed source registry:

```powershell
$env:BRAVE_SEARCH_API_KEY = "..."
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction
```

Without either key, the project still runs normally using fixed sources and
links already present on official pages.

The GitHub Actions `discovery` checkbox applies only to manual `audit` mode and
reads `SERPER_API_KEY` from repository secrets. Publishing `ai` runs, scheduled
cloud refreshes, and local scheduled scans never enable Serper. The workflow
also accepts the compatibility secret name `SERPER_SEARCH_API_KEY`.

Semantic ranking may retain up to 150 pages for evidence analysis. Before the
DeepSeek request, a second deterministic gate rejects listing/generic pages,
pages with only explicit past years, already-past candidates, weak programme
signals, and weak detail signals. DeepSeek receives at most 80 surviving pages.
The filter counts are written to `ai_extractions.json` and the audit report.

For production evaluation, select manual `audit` mode. It executes the same
bounded AI scan and validation gates, writes `audit/search-audit.json` and
`audit/search-audit.md`, and uploads the audit plus generated evidence sidecars
as a 14-day workflow artifact. Audit mode never commits `data/latest_*` and
never writes `gh-pages`, even when every validation gate passes.

## Optional Headless Rendering

Most sources return their content in the served HTML and are fetched with `requests`. A minority render content client-side, so the served HTML is an empty shell. Such a source can set `render: true` in `config/sources.yaml`, and the scanner loads it in headless Chromium via Playwright instead.

Playwright is an optional dependency. Install it with:

```powershell
pip install -e ".[render]"
python -m playwright install chromium
```

When Playwright is not installed, a `render: true` source falls back to a plain request automatically, so the default workflow stays lightweight. The optional AI workflow can install and cache the browser so rendered sources work in CI when that path is enabled.

## Direct Collectors (JSON APIs and structured listings)

A site that renders its listing client-side (a single-page app) returns an empty HTML shell to `requests`. This is ordinary client-side rendering, not anti-scraping. The page-by-page pipeline cannot read it, but two things often can:

- **its own JSON API** — when the app fetches data from a public endpoint, calling that endpoint directly returns clean structured records (exact dates, deadline, price) with no browser; or
- **its server-rendered listing** — when the listing page itself carries each event's dates and location inline (only the detail pages are empty), the listing is parsed directly.

`src/research_school_radar/api_sources.py` holds these collectors:

- **IHE Delft** — course catalogue from `https://www.un-ihe.org/api/v1/...`; each upcoming edition maps to a candidate at full confidence (exact dates, deadline, fee).
- **ELLIS** — the events listing is server-rendered with each card's date range and location, so the listing is parsed into candidates even though the detail pages are an empty shell.
- **SIB** — embedded Bioschemas `Course` / `CourseInstance` records provide exact course dates, modes, locations, fees, and stable detail URLs.
- **SICSS** — the official locations catalogue is split into independent institutes, preserving each site's dates, location, free-tuition evidence, and application URL.

A collector returns `(candidates, errors)` and never raises, so a single failing structured source does not abort collection. The `collector` field on an enabled `config/sources.yaml` record is the only activation path; disabling that record disables both its source entry and direct collector.

Not every JS-rendered site can be reached this way. Some expose no usable data endpoint and load content only after interaction (e.g. CUAHSI). A few sit behind active bot management such as Cloudflare's challenge (e.g. IIASA), which blocks even a real headless browser; these are left disabled rather than circumvented.

## Local Development

Install and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m research_school_radar.cli scan
```

Run tests:

```powershell
pytest
```

Run without network:

```powershell
python -m research_school_radar.cli scan --offline-sample
```

Useful outputs:

- `reports/YYYY-MM-DD.md`: Markdown report
- `site/index.html`: public static website
- `site/candidates.json`: structured candidate data
- `data/seen.json`: seen-opportunity JSON state

## Current Limitations

The current implementation is useful but still early.

- Extraction is rule-based, so unusual page layouts can produce uncertain fields.
- Dates and deadlines share one date parser, which understands ISO (`2026-03-08`), day-first (`8 March 2026`, `1st March 2026`), month-first (`March 8, 2026`), abbreviated months (`15 Jan 2026`), numeric (`8/3/2026`, `08.03.2026`), and compact ranges that share a month or year (`June 9-14, 2025`, `9-14 July 2027`). Deadlines tolerate filler words between the keyword and the date (e.g. "deadline was extended until 8 March 2026"). Month-only dates ("March 2026") are intentionally treated as uncertain.
- Funding detection covers grants, scholarships, bursaries, qualified fellowships, tuition and fee waivers, stipends, and covered accommodation/board/lodging/meals/travel, and suppresses negated statements (e.g. "no financial support is foreseen"). Ambiguous wording such as a bare "fellowship" (which can mean a membership grade) requires an availability cue, but unusual phrasing can still slip through.
- Fixed exchange rates require occasional maintenance and intentionally trade precision for a free, deterministic workflow.
- Listing, calendar, navigation, and landing pages are filtered out: a candidate must have either a deadline or exactly one event date range (several ranges without a deadline indicates a calendar) and a non-generic, non-section title; pure language courses (CEFR level transitions) and degree recruitment are also excluded. Genuine opportunities with no machine-readable date can therefore be missed until their details are published.
- No curator UI exists yet; `data/opportunities.yml` is edited manually.
- No email digest is generated yet.
- No automatic PR or issue creation exists for promising new candidates.
- Field-level evidence exists for many extracted fields, but a richer per-field confidence model and public evidence UI are still incomplete.
- JavaScript filtering works on the static page, but there is no persistent user preference state.

## Suggested Improvements

High-impact next steps:

1. Add richer field-level confidence scores and public evidence snippets for deadline, funding, duration, and mode.
2. Continue adding source-specific parsers or direct collectors for high-value sources.
3. Add a review command that promotes a candidate from `site/candidates.json` into `data/opportunities.yml`.
4. Add GitHub Action logic to open an issue or PR when a strong new candidate appears.
5. Add weekly email, Telegram, or newsletter digest support.
6. Improve date extraction with richer patterns and page-specific adapters.
7. Add an archive page so historical daily reports are browsable from the website.
8. Add custom domain support and optional Cloudflare Web Analytics setup notes.
9. Add screenshots or an example report section for the README.

Medium-term direction:

```text
trusted source scanner
    + contributor submissions
    + curator review
    + static public database
    + RSS/newsletter distribution
    + transparent evidence and risk labels
```

This would move the project from a daily scanner toward a credible vertical opportunity platform for research training.

## Design Principles

- Precision is more important than recall.
- Near-matches are never presented as fully qualified.
- Deadline and funding evidence should be preserved whenever possible.
- A simple reliable scanner is better than an opaque autonomous browsing system.
- LLMs may help with extraction later, but should not become uncontrolled web browsers.
- Curated quality matters more than raw volume.



