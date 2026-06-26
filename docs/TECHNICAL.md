# Technical README

Technical notes for Summer School Radar, an open-source radar for funded research seasonal schools and short courses: summer schools, winter schools, spring/autumn schools, training schools, field schools, doctoral schools, research schools, and short/advanced courses. Generic conference workshops are not included.

The project is inspired by curated vertical opportunity platforms such as Josh's Water Jobs, but it is aimed at research training rather than jobs. The goal is not to crawl the whole web. The goal is to maintain a trusted source registry, scan it regularly, extract structured evidence, apply strict filters, and publish a transparent public report.

## Three-Minute Start

```powershell
git clone <this-repository>
cd <this-repository>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m research_school_radar.cli scan --offline-sample
```

Then open:

- `reports/YYYY-MM-DD.md` for the Markdown report
- `site/index.html` for the static website
- `site/candidates.json` for scanner output
- `site/curated.json` for maintainer-reviewed records

Run a real fixed-source scan with:

```powershell
python -m research_school_radar.cli scan
```

## Why Not Another Summer School List?

Most summer school lists are plain link collections. This project is different:

- it targets research training opportunities, not generic study-abroad marketing
- it stores source evidence for high-risk fields such as deadline and funding
- it separates fully qualified opportunities from near-matches
- it makes failed hard conditions visible instead of hiding uncertainty
- it has a curated layer for maintainer-reviewed records
- it publishes a static website, Markdown reports, and JSON data
- it can run daily for free on GitHub Actions and GitHub Pages

## Current Status

This repository now contains a working MVP:

- fixed-source scanner for trusted academic and research organizations
- second-level candidate link following from source pages
- rule-based extraction for title, type, organizer, location, dates, duration, deadline, funding, topics, eligibility, fee, normalized EUR fee, and mode, with per-field source evidence and a transparent extraction-confidence score (the fraction of the four high-risk fields that were resolved)
- schema.org JSON-LD parsing and extraction adapters: domain adapters (ICIMOD) and structural adapters keyed by markup rather than site, e.g. WordPress "The Events Calendar" (used by ESA EO4Society, IEEE GRSS, and many academic event sites), which yields reliable dates, venue, and the official external application URL
- hard filtering that separates fully qualified opportunities from near-matches
- interpretable ranking
- Markdown report generation
- static website generation with browser-side filters
- JSON state file tracking seen opportunities (diff-friendly, auto-committed)
- GitHub Actions workflow for daily free scans
- GitHub Pages deployment
- GitHub issue template for external submissions
- optional analytics injection for Cloudflare Web Analytics or GoatCounter
- curated opportunity section generated from `data/opportunities.yml`
- test coverage for filtering, reporting, linked-page collection, location extraction, site generation, source disabling, and analytics injection

## What It Looks For

The default profile targets MSc, PhD, postdoc, and early-career research opportunities in the project's core domain: water and hydrology, climate and atmosphere, geoscience and earth observation, remote sensing, and scientific machine learning. The `preferred_topics` list in `config/profile.yaml` is the relevance gate; widening or narrowing the domain is a matter of editing that list, but the focused scope keeps the gate strong and the source registry tractable.

An opportunity is treated as fully qualified only when all hard conditions are satisfied:

- application is open or the deadline has not passed
- duration is at least 8 days
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

Optional AI advisory branch:
pages -> semantic chunks -> evidence snippets -> optional LLM extraction -> evidence-ID validation -> sidecar JSON -> AI review
```

The optional branch reads collected page text but never overwrites `Candidate`
records, hard-filter results, ranking, RSS inclusion, or public qualification
status.

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
| `BAAI/bge-m3` | 212.33s | 55 | 24 | 31 | Better recall, acceptable runtime for manual or weekly semantic review. |

The project therefore defaults to `BAAI/bge-m3` for semantic review. This does
not make semantic output authoritative. The review sidecar still needs human
checking, and the rule-based scanner remains the source of truth for public
qualification.

LLM extraction is also optional and advisory only. It turns semantic chunks into
short numbered evidence snippets, sends those snippets to a configured provider,
and writes structured sidecar JSON. It does not
change `Candidate` records, hard filters, ranking, Markdown report tables, RSS,
or public site tables.

Supported providers:

- `ollama`: native `/api/chat`, default model `qwen3.5:9b`, request includes
  `think: false` and `format: "json"`.
- `lmstudio`: OpenAI-compatible `/v1/chat/completions`, default model id
  `qwen2.5-7b-instruct`, request uses `response_format` JSON schema when
  supported and falls back to plain JSON prompting with a
  `lmstudio_structured_output_fallback` warning.
- `deepseek`: remote OpenAI-compatible `/chat/completions`, default model
  `deepseek-v4-flash`, request uses `response_format: {"type": "json_object"}`
  and `thinking: {"type": "disabled"}`.

```powershell
pip install -e ".[dev,semantic,llm]"
$env:DEEPSEEK_API_KEY = "sk-..."
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction
```

Ollama or LM Studio must be installed manually. Remote providers such as
DeepSeek require a user-supplied API key. This project does not install local
LLM software, download models automatically, create API keys, or store real API
keys in configuration files. In the Ollama CLI, `/set nothink` can disable
thinking during manual interactive tests. If the configured provider is
unavailable, LLM extraction records a warning and the scan continues with the
existing rule-based outputs. The code strips thinking traces from model
responses as a fallback, and records `llm_json_parse_failed` instead of
crashing when output is not clean JSON.

LLM extraction sends only selected semantic chunks, never full webpages. The
default resource limits are:

- `max_pages_for_ai: 150`
- `max_pages_per_source: 8`
- `max_pages_for_llm: 150`
- `max_chunks_per_page: 3`
- `max_chars_per_chunk: 2200`
- `max_total_chars_per_request: 7000`

The 150-page values are exploratory upper bounds for measuring real weekly run
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

### Local LLM trial notes

Local LLM extraction has been tested with small Qwen-family models through both
Ollama and LM Studio:

- Ollama native `/api/chat` with `qwen3.5:9b`, `think: false`, and JSON mode.
- LM Studio OpenAI-compatible `/v1/chat/completions` with
  `qwen2.5-7b-instruct`.

These trials were useful for validating the advisory architecture but were not
reliable enough to promote into the main pipeline. Early Ollama runs produced
truncated JSON until `num_predict` was increased; after that, extraction still
misread or omitted high-risk fields on real pages such as deadline, fee, and
funding. LM Studio runs depended on a manually started local server and did not
consistently improve extraction quality. The current recommendation is to keep
local LLM extraction disabled for daily use and rely on `BAAI/bge-m3` semantic
ranking plus rule-based extraction. Future work may revisit external AI APIs
only with strict evidence grounding, cost controls, and human-review gates.

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

DeepSeek results remain advisory sidecar data. They are useful for reviewing
missed deadline, fee, funding, location, and eligibility evidence, but they do
not change `fully_qualified`, hard filters, ranking, RSS, or public tables.

#### Using LM Studio

LM Studio must be installed manually. Download and load the model inside LM
Studio, then start Developer / Local Server. The current tested downloaded model
is:

```text
idasummer/Qwen2.5-7B-Instruct-Q5_K_M-GGUF
```

The API model identifier exposed by LM Studio is shorter:

```text
qwen2.5-7b-instruct
```

Use that API model id in `LLM_MODEL`, not the repository/download name. LM
Studio usually does not reuse Ollama model files, so installing the same family
of models in both tools can duplicate disk usage.

Check model ids:

```powershell
curl.exe http://localhost:1234/v1/models
```

Configuration:

```powershell
$env:LLM_PROVIDER = "lmstudio"
$env:LLM_BASE_URL = "http://localhost:1234/v1"
$env:LLM_MODEL = "qwen2.5-7b-instruct"
$env:LLM_API_KEY = "lm-studio"
```

Then run:

```powershell
python -m research_school_radar.ai_healthcheck --provider lmstudio
python -m research_school_radar.ai_compare_providers
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
```

LM Studio may be faster on AMD iGPU / Radeon 780M setups when partial GPU
offload is enabled. Structured output may improve JSON validity, but evidence
validation and manual review are still required.

LLM extraction is cached under `data/ai_cache/` using page URL, selected chunk
text hash, model name, and `AI_EXTRACTION_SCHEMA_VERSION`. Use
`--refresh-ai-cache` to ignore cached semantic and LLM entries:

```powershell
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
```

LLM sidecar output goes to:

- `site/ai_extractions.json`
- `reports/YYYY-MM-DD.ai.json`
- `site/ai-review.html` when AI extraction has run

The endpoint can be checked separately without running a scan:

```powershell
python -m research_school_radar.ai_healthcheck
```

If the internal disk is limited on Windows, Ollama model storage can be moved by
setting an external directory and restarting Ollama:

```powershell
$env:OLLAMA_MODELS = "E:\ollama-models"
```

Tests do not download `BAAI/bge-m3`, require API keys, or require
model files. Semantic and LLM tests use stubs and empty offline page pools to
keep CI deterministic.

### AI-assisted review workflow

Semantic ranking is meant to surface pages that the rule-based
`looks_like_opportunity` gate may miss. Local LLM extraction creates advisory
structured drafts from numbered snippets, and `llm_validate.py` checks whether
non-unknown fields cite existing evidence IDs with suitable context.

AI output is integrated only into review surfaces:

- `data/review_queue.json` and `site/review_queue.json` include an
  `ai_advisory` block for candidates whose source or application URL exactly
  matches an AI extraction page URL.
- `site/ai-review.html` lists matched AI records and a `Potential Missed Pages`
  section for unmatched semantic/AI pages that deserve manual checking.
- `site/ai_extractions.json` remains the advisory sidecar. Items include
  `evidence_snippets`, field-level `evidence_ids`, resolved short evidence
  previews, validation warnings, and confidence.

AI output never mutates `Candidate` fields and never affects hard filters,
`fully_qualified`, ranking, RSS inclusion, or public recommendation status.
The manual promotion path is:

```text
AI extraction -> maintainer checks official page -> maintainer edits data/opportunities.yml or data/overrides.yml
```

There is deliberately no automatic promotion from AI output into curated data.

### Real-world AI validation

Unit tests keep the optional AI branch safe and deterministic, but they do not
prove extraction quality on real organiser pages. Use this manual validation
sequence when checking the advisory branch:

```powershell
python -m research_school_radar.ai_healthcheck
python -m research_school_radar.ai_compare_providers
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

Synthetic provider comparison checks wiring and latency, but provider quality
should be judged on real page sidecars. A typical workflow is:

```powershell
# Run Ollama extraction, then keep a copy of the sidecar.
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
Copy-Item reports/YYYY-MM-DD.ai.json reports/ollama.ai.json

# Run LM Studio extraction with LM Studio env vars, then keep a copy.
$env:LLM_PROVIDER = "lmstudio"
$env:LLM_BASE_URL = "http://localhost:1234/v1"
$env:LLM_MODEL = "qwen2.5-7b-instruct"
$env:LLM_API_KEY = "lm-studio"
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
Copy-Item reports/YYYY-MM-DD.ai.json reports/lmstudio.ai.json

# Run DeepSeek extraction with DeepSeek env vars, then keep a copy.
$env:LLM_PROVIDER = "deepseek"
$env:LLM_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
$env:DEEPSEEK_API_KEY = "sk-..."
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
Copy-Item reports/YYYY-MM-DD.ai.json reports/deepseek.ai.json

# Compare real outputs.
python -m research_school_radar.ai_compare_runs --left reports/ollama.ai.json --right reports/lmstudio.ai.json --left-name ollama --right-name lmstudio
python -m research_school_radar.ai_compare_runs --left reports/lmstudio.ai.json --right reports/deepseek.ai.json --left-name lmstudio --right-name deepseek
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

- Daily: `python -m research_school_radar.cli scan`
- Manual or weekly: `python -m research_school_radar.cli scan --enable-semantic`
- Manual review only: `python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction`

Do not enable LLM extraction in daily automation yet. It is slower, more
resource-intensive, can time out on long prompts, and still requires manual
validation against official pages.

### Key Files

- `src/research_school_radar/cli.py` is the command entry point.
- `src/research_school_radar/collect.py` fetches source and linked pages with `requests` and `BeautifulSoup`.
- `src/research_school_radar/parse.py` identifies likely opportunity links and skips unsuitable files or blocked domains.
- `src/research_school_radar/extract.py` performs rule-based structured extraction.
- `src/research_school_radar/filter.py` applies hard filters.
- `src/research_school_radar/rank.py` scores and deduplicates candidates. Deduplication runs on every scan: it canonicalizes URLs (dropping tracking parameters, fragments, and trailing slashes), then merges the same event reported under different titles or by different sources when a title-similarity match is confirmed by a shared date, while keeping distinct editions that have different start dates.
- `src/research_school_radar/report.py` writes Markdown reports.
- `src/research_school_radar/site.py` writes the static public website.
- `src/research_school_radar/storage.py` updates the JSON seen-state file (data/seen.json).
- `src/research_school_radar/semantic.py` writes optional semantic chunk sidecars.
- `src/research_school_radar/evidence_snippets.py` selects short numbered snippets for evidence-first LLM prompting.
- `src/research_school_radar/ai_cache.py` implements the lightweight file cache for optional AI work.
- `src/research_school_radar/llm_client.py`, `llm_extract.py`, and `llm_validate.py` implement optional advisory LLM sidecars.
- `src/research_school_radar/ai_healthcheck.py` checks the configured LLM provider.
- `src/research_school_radar/ai_evaluate.py` writes the human annotation CSV for real-world AI quality checks.
- `src/research_school_radar/ai_compare_providers.py` runs a tiny provider comparison without a full scan.

## Configuration

- `config/profile.yaml` controls preferred topics, hard filters, financial-access thresholds and reference exchange rates, priority regions, supplementary regions, and excluded programme types.
- `config/sources.yaml` lists trusted sources. Each source can be enabled or disabled, and can block problematic linked domains.
- `config/queries.yaml` stores optional controlled discovery queries.
- `config/site.yaml` controls optional analytics.
- `config/ai.yaml` controls optional semantic ranking, LLM advisory extraction, resource limits, and `data/ai_cache/` behavior.
- `data/opportunities.yml` is the manually curated high-confidence opportunity database.

Example source options:

```yaml
- name: ICIMOD
  url: https://www.icimod.org/events/
  layer: 1.5
  region: South Asia
  source_type: intergovernmental_research
  keywords: [Himalayan, climate, water, capacity building]
  scan_frequency: every_run
  blocked_link_domains: [servir.icimod.org]
  notes: Strong regional water and climate relevance.
```

Disabled sources stay documented without creating scan noise:

```yaml
- name: IIASA
  url: https://iiasa.ac.at/events
  enabled: false
  notes: Site currently returns Cloudflare 403 for scripted requests.
```

## Daily Free Workflow

The GitHub Actions workflow at `.github/workflows/scheduled_scan.yml` runs once per day:

```yaml
schedule:
  - cron: "17 6 * * *"
```

The workflow:

1. checks out the repository
2. installs the Python package
3. runs `python -m research_school_radar.cli scan`
4. commits `reports/`, `data/seen.json`, and `data/opportunities.yml`
5. uploads `site/` as a GitHub Pages artifact
6. deploys the public website with GitHub Pages

This default workflow is free for a public GitHub repository and does not require a search API key.

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

The public table intentionally hides internal ranking fields such as region priority and failed hard conditions. Those fields remain in `site/candidates.json` for maintainers and debugging. Titles link directly to the official opportunity page.

After pushing to GitHub:

1. Open repository settings.
2. Go to Pages.
3. Set build and deployment source to GitHub Actions.
4. Run the `Scheduled research school scan` workflow once, or wait for the daily schedule.

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

The default scan does not scrape Google or other search-result pages. Controlled discovery is optional and uses the Brave Search API if `BRAVE_SEARCH_API_KEY` is configured. (Bing Web Search was retired by Microsoft in 2025 and is no longer supported.)

```powershell
$env:BRAVE_SEARCH_API_KEY = "..."
python -m research_school_radar.cli scan --include-discovery
```

The Brave Search free plan is sufficient; the scanner spaces queries about one second apart to respect its rate limit.

Without the key, the project still runs normally using fixed sources.

## Optional Headless Rendering

Most sources return their content in the served HTML and are fetched with `requests`. A minority render content client-side, so the served HTML is an empty shell. Such a source can set `render: true` in `config/sources.yaml`, and the scanner loads it in headless Chromium via Playwright instead.

Playwright is an optional dependency. Install it with:

```powershell
pip install -e ".[render]"
python -m playwright install chromium
```

When Playwright is not installed, a `render: true` source falls back to a plain request automatically, so the default workflow stays lightweight. The daily GitHub Actions workflow installs the browser (cached between runs) so rendered sources work in CI.

## Direct Collectors (JSON APIs and structured listings)

A site that renders its listing client-side (a single-page app) returns an empty HTML shell to `requests`. This is ordinary client-side rendering, not anti-scraping. The page-by-page pipeline cannot read it, but two things often can:

- **its own JSON API** — when the app fetches data from a public endpoint, calling that endpoint directly returns clean structured records (exact dates, deadline, price) with no browser; or
- **its server-rendered listing** — when the listing page itself carries each event's dates and location inline (only the detail pages are empty), the listing is parsed directly.

`src/research_school_radar/api_sources.py` holds these collectors:

- **IHE Delft** — course catalogue from `https://www.un-ihe.org/api/v1/...`; each upcoming edition maps to a candidate at full confidence (exact dates, deadline, fee).
- **ELLIS** — the events listing is server-rendered with each card's date range and location, so the listing is parsed into candidates even though the detail pages are an empty shell.

A collector returns `(candidates, errors)` and never raises, so a failing source cannot abort the scan. The corresponding HTML sources are disabled in `config/sources.yaml` with notes pointing to the collector.

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
- No RSS feed or email digest is generated yet.
- No automatic PR creation exists for promising new candidates.
- No confidence score is stored per extracted field.
- JavaScript filtering works on the static page, but there is no persistent user preference state.

## Suggested Improvements

High-impact next steps:

1. Add field-level confidence scores and evidence snippets for deadline, funding, duration, and mode.
2. Add source-specific parsers for high-value sites such as EGU, ICIMOD, ELLIS, IHE Delft, and CUAHSI.
3. Generate an RSS feed for fully qualified and curated opportunities.
4. Add a review command that promotes a candidate from `site/candidates.json` into `data/opportunities.yml`.
5. Add GitHub Action logic to open an issue when a strong new candidate appears.
6. Add weekly email or Telegram digest support.
7. Improve date extraction with richer patterns and page-specific adapters.
8. Add an archive page so historical daily reports are browsable from the website.
9. Add custom domain support and optional Cloudflare Web Analytics setup notes.
10. Add screenshots or an example report section for the README.

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



