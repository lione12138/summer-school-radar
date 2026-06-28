# Summa

[![Tests](https://github.com/lione12138/summer-school-radar/actions/workflows/tests.yml/badge.svg)](https://github.com/lione12138/summer-school-radar/actions/workflows/tests.yml)
[![License: AGPL v3](https://img.shields.io/badge/Code-AGPL--3.0-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-green.svg)](#license--reuse)

An open-source scanner for funded research training opportunities — summer schools, winter schools, training schools, field schools, and short courses — **across many academic fields**: environmental & earth science, computing & data science, the social sciences, and the humanities.

It is a fixed trusted-source scanner with rule-based extraction and transparent per-field evidence — not a fully automatic all-web radar. It scans a curated registry of trusted academic sources, extracts deadline / funding / fee / duration evidence together with the supporting text, separates fully qualified, high-quality, and found opportunities, and publishes a static website that updates daily for free on GitHub Pages.

**Live site:** <https://lione12138.github.io/summer-school-radar/>

[Technical README](docs/TECHNICAL.md) | [中文技术说明](docs/TECHNICAL.zh-CN.md) | [License & reuse](#license--reuse)

## Abstract

Summa combines a conservative fixed-source crawler, rule-based field extraction,
and transparent evidence preservation to track research training opportunities.
The public qualification logic remains deterministic: deadlines, duration,
funding, fee, mode, and topic fit are extracted and filtered by explicit rules.
To improve recall, the project now also includes an optional semantic analysis
layer using `BAAI/bge-m3` embeddings. This embedding layer ranks scanned page
chunks for human review and helps surface relevant application, fee, funding,
eligibility, and deadline context that string matching may miss.

The semantic layer is still being optimized and is not the source of truth for
qualification, ranking, RSS inclusion, or public recommendation status. Future
work may add field-specific research-training ontologies for specialized
domains and may connect external AI APIs for more accurate advisory analysis
after evidence, cost, and reliability controls are in place.

## Latest Scan Results

This section is refreshed automatically by the daily local scan.

<!-- radar:results:start -->
_Last scan: 2026-06-27 · 1 fully qualified · 2 high-quality · 4 found shown_

**Fully Qualified Opportunities**

| # | title | type | organizer | location | duration | deadline | funding / fee | topic |
|---|---|---|---|---|---|---|---|---|
| 1 | [Social Science Data Analysis](https://essexsummerschool.com/new-application/) | summer school | Essex Summer School | Colchester, UK | 29 Jun – 14 Aug 2026 · 47 days | 2026-07-17 | scholarship · amount not stated · Apply on official page | satellite, geospatial, AI, machine learning |

**High-Quality Opportunities**

| title | type | organizer | location | duration | deadline | funding / fee | topic |
|---|---|---|---|---|---|---|---|
| [ICOS Summer/Winter School January 2027, application is now open](https://www.icos-cp.eu/about/opportunities/summer-school) | summer school | ICOS | Europe | 18 Jan – 28 Jan 2027 · 11 days | 2026-07-31 | financial support · amount not stated · Apply on official page | climate, climate change, remote sensing, statistics |
| [ELLIS Summer School at Unit Saarbrücken](https://ellis.eu/events/ellis-summer-school-at-unit-saarbruecken-2026) | summer school | ELLIS | Saarland University | 24 Aug – 28 Aug 2026 · 5 days | uncertain | Fee about EUR 250 · Apply on official page | AI |

**Found Opportunities**

| title | type | organizer | location | duration | deadline | funding / fee | topic |
|---|---|---|---|---|---|---|---|
| [Get to know the Bernstein Network!](https://bernstein-network.de/en/) | advanced course | Bernstein Network | Europe | uncertain | 2026-08-27 | travel grant, stipend · amount not stated · Apply on official page | satellite, AI, machine learning, data analysis |
| [Travel Grants](https://bernstein-network.de/en/bernstein-conference/early-career-scientists/travel-grants/) | advanced course | Bernstein Network | Europe | uncertain | 2026-07-01 | travel grant · amount not stated · Apply on official page | satellite, data analysis, statistics, computational neuroscience |
| [River Basin Modelling](https://www.un-ihe.org/short-courses) | short course | IHE Delft | Delft, Netherlands | 11 Jan – 29 Jan 2027 · 19 days | 2026-12-11 | Fee about EUR 2600 · Apply on official page | groundwater, water resources, water quality, GIS |
| [ELLIS Summer School at Unit Munich](https://ellis.eu/events/ellis-summer-school-at-unit-munich-2026) | summer school | ELLIS | TUM Garching Campus | 14 Sep – 18 Sep 2026 · 5 days | uncertain | Funding or fee not stated | machine learning, computer vision |

<!-- radar:results:end -->

## Upcoming Research Training Opportunities

The generated website lists scanner results in three public tiers:

- **Fully Qualified Opportunities**: scanner results that satisfy every hard condition.
- **High-Quality Opportunities**: not closed, not online-only, at least 5 days long, and either funded or no more than about EUR 70 per day.
- **Found Opportunities**: relevant records that remain worth checking but are missing too much evidence, are more expensive, or otherwise do not meet the high-quality bar.
- **Sources & Coverage**: the configured trusted source registry, including disabled sources and notes.

The site includes filters for keyword, status, topic, financial access, and deadline status. Rows with a known application deadline include an **Add to calendar** menu (Google Calendar, Outlook, or a downloadable `.ics` file).

```text
site/index.html
site/candidates.json
site/sources.html
site/sources.json
site/feed.xml
site/sitemap.xml
site/semantic_chunks.json
site/ai_extractions.json
site/ai-review.html
reports/YYYY-MM-DD.md
reports/YYYY-MM-DD.semantic.json
reports/YYYY-MM-DD.ai.json
```

## What Counts As Fully Qualified?

An opportunity must satisfy all hard conditions:

| Condition | Requirement |
|---|---|
| Deadline | Application is still open or deadline has not passed |
| Duration | At least 8 days |
| Financial access | Explicit funding is available, or the confirmed total fee is no more than approximately EUR 400 |
| Mode | In-person or substantially on-site, not online-only |
| Topic | Relevant to one of the covered fields: environmental & earth science (water, climate, geoscience, remote sensing), computing & data science (machine learning, computer vision, software engineering, cybersecurity, computational neuroscience, linguistics), or the social sciences & humanities (social-science methods, economics, political science, history, digital humanities) |

Near-matches are never presented as qualified results.

Foreign-currency fees are converted with configurable fixed reference rates so the default workflow remains free and API-key-free. The rates are deliberately conservative, not real-time. Unknown currencies or ambiguous fees remain near-matches.

The radar targets seasonal schools and short courses — summer schools, winter schools, spring/autumn schools, training schools, doctoral schools, field schools, research schools, and short/advanced courses. `Training school` is included because many research networks use it for the same kind of short, intensive programme as a summer school. Generic conference workshops are not included.

## Why Not Another Summer School List?

Most summer school lists are plain link collections. This project is different:

- trusted source registry instead of random web crawling
- structured extraction for deadline, funding, duration, mode, eligibility, and location
- hard filters with visible failed conditions
- static public website plus Markdown and JSON outputs
- daily free automation that publishes to GitHub Pages
- source coverage transparency through a generated Sources & Coverage page

## Doctoral Schools Scope

The radar may include short-term doctoral schools or PhD schools when they are seasonal research training opportunities, such as a one-week or two-week thematic training school for doctoral researchers.

It does **not** target PhD admissions, PhD positions, full-time doctoral degree programmes, or ordinary graduate school enrollment.

## Quick Start

```powershell
git clone <this-repository>
cd <this-repository>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m research_school_radar.cli scan --offline-sample
```

Then open:

- `site/index.html`
- `reports/YYYY-MM-DD.md`

Run a real fixed-source scan:

```powershell
python -m research_school_radar.cli scan
```

## Optional semantic ranking

The default pipeline remains rule-based, lightweight, and API-key-free:

```powershell
pip install -e ".[dev]"
python -m research_school_radar.cli scan --offline-sample
python -m research_school_radar.cli scan
```

Optional semantic chunk ranking can write a sidecar with the most relevant text
snippets from scanned pages. It does not change extraction, hard filters,
ranking, report tables, RSS, or public qualification status. It uses
`BAAI/bge-m3` via `sentence-transformers`. Semantic ranking is
cached under `data/ai_cache/` by page URL, page text hash, embedding model,
query, and chunking config. Ranking is applied before the output page limit, and
a per-source cap keeps one large site from dominating the review sidecar.

```powershell
pip install -e ".[dev,semantic]"
python -m research_school_radar.cli scan --enable-semantic
```

Semantic sidecar output goes to `site/semantic_chunks.json` and
`reports/YYYY-MM-DD.semantic.json`.

LLM extraction is also optional and advisory only. It reads semantic chunks and
asks a configured provider for structured evidence. Supported providers are:

- Ollama: native `/api/chat`, default model `qwen3.5:9b`, with `think: false`
  and `format: "json"`.
- LM Studio: OpenAI-compatible `/v1/chat/completions`, default model id
  `qwen2.5-7b-instruct`, with structured JSON schema mode when supported.
- DeepSeek API: OpenAI-compatible `/chat/completions`, default model
  `deepseek-v4-flash`, with `thinking` disabled and JSON object mode.

It writes sidecar JSON without changing candidates, filters, rankings, RSS, or
the public tables. Local LLM software and models must be installed manually;
remote API keys must be supplied by the user. The project does not install
Ollama, LM Studio, model files, or create API keys automatically. In the Ollama
CLI, `/set nothink` can disable thinking during manual interactive tests.

The LLM prompt is evidence-first: the scanner converts semantic chunks into
short numbered snippets such as `E1`, `E2`, and `E3`. The model is asked to cite
only `evidence_ids`; it should not invent or return free-form `evidence_text`.
The sidecar resolves those IDs back to short snippet text for review. This keeps
AI output auditable while avoiding full raw page dumps in public files.

```powershell
pip install -e ".[dev,semantic,llm]"
$env:DEEPSEEK_API_KEY = "sk-..."
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction
```

### Using DeepSeek as remote LLM provider

DeepSeek is the recommended first remote API trial because `deepseek-v4-flash`
is low-cost, supports OpenAI-compatible chat completions, supports JSON output,
and supports disabling thinking mode. Create a DeepSeek API key manually, then
set it locally:

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

DeepSeek output remains advisory only. It writes `site/ai_extractions.json`,
`reports/YYYY-MM-DD.ai.json`, and `site/ai-review.html`; it does not update the
main opportunity tables or fully qualified status.

When LLM extraction is enabled, the advisory pipeline can perform a bounded
follow-up pass for otherwise promising pages with missing deadline, fee,
funding, application URL, date, or location fields. It first follows relevant
links on the same official domain, including application, registration, fees,
tuition, rates, funding, scholarship, deadline, and practical-information
pages. Related pages are ranked again with `BAAI/bge-m3` and extracted together
with the original page. Evidence snippets retain the exact page URL used.

If `BRAVE_SEARCH_API_KEY` is set, unresolved fields can also trigger controlled
`site:official-domain` searches. Search is optional: without the key, the scan
keeps the initial evidence-grounded DeepSeek output and records a warning. The
default limits are two link-following rounds, two queries per opportunity,
three results per query, four added pages per opportunity, and sixty added
pages per scan. Configure these under `follow_up` in `config/ai.yaml`.

The follow-up prompt distinguishes application/registration deadlines from
payment, accommodation, scholarship, travel-grant, and abstract deadlines. It
also requests explicit open/closed status and complete fee tiers rather than
only the cheapest amount. Deterministic validation checks cited evidence,
date/fee support, past dates, closed wording, and non-application deadline
risk. This is still evidence validation, not a guarantee of factual truth;
human confirmation remains required before public promotion.

The current exploratory advisory settings allow up to 150 semantic pages and up
to 150 LLM pages. This is a cap, not a guaranteed call count; most runs process
fewer pages because collection, semantic similarity, and per-source limits
narrow the pool first. After observing real weekly run sizes, lower these caps
to the smallest values that still preserve useful recall.

### Using LM Studio as local LLM provider

LM Studio must be installed manually. Download and load the model inside LM
Studio, then start the local server from Developer / Local Server. The current
tested downloaded model is:

```text
idasummer/Qwen2.5-7B-Instruct-Q5_K_M-GGUF
```

LM Studio exposes a shorter API model identifier. For the current setup use this
exact API model id:

```text
qwen2.5-7b-instruct
```

Use the API model id in `LLM_MODEL`, not the download repository name. LM Studio
usually does not reuse Ollama model files, so downloading the same model in both
tools can duplicate disk usage.

Check the local server model ids:

```powershell
curl.exe http://localhost:1234/v1/models
```

Configure LM Studio:

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

LM Studio may be faster on AMD iGPU / Radeon 780M setups when GPU offload is
enabled. Structured output can improve JSON validity, but it does not remove the
need for evidence validation. AI results remain advisory only.

LLM sidecar output goes to `site/ai_extractions.json` and
`reports/YYYY-MM-DD.ai.json`. The generated site also includes
`site/ai-review.html` when AI extraction has run. LLM extraction is cached under
`data/ai_cache/` by page URL, selected chunk text hash, model name, and
extraction schema version. To ignore existing AI cache entries:

```powershell
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
```

These files are not the source of truth for fully qualified opportunities; the
hard filters remain rule-based.

Check the local Ollama endpoint separately with:

```powershell
python -m research_school_radar.ai_healthcheck
```

If the internal disk is limited on Windows, Ollama model storage can be moved by
setting an external directory before restarting Ollama:

```powershell
$env:OLLAMA_MODELS = "E:\ollama-models"
```

## Real-world AI validation

Passing tests only proves the optional AI branch is wired safely; it does not
prove extraction quality on real organiser pages. Validate it manually before
trusting any advisory output:

```powershell
python -m research_school_radar.ai_healthcheck
python -m research_school_radar.ai_compare_providers
$env:HF_HOME = Join-Path $env:TEMP "summer-school-radar-hf-cache"
python -m research_school_radar.cli scan --enable-semantic --refresh-ai-cache
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --refresh-ai-cache
python -m research_school_radar.ai_evaluate
```

`ai_compare_providers.py` runs a small synthetic wiring check for Ollama, LM
Studio, and DeepSeek when configured. It is not a quality benchmark.

`ai_evaluate.py` reads `site/ai_extractions.json` and writes:

```text
reports/YYYY-MM-DD.ai-evaluation-template.csv
```

To compare two real provider runs, save each sidecar first and then run:

```powershell
python -m research_school_radar.ai_compare_runs --left reports/ollama.ai.json --right reports/lmstudio.ai.json --left-name ollama --right-name lmstudio
```

This writes:

```text
reports/YYYY-MM-DD.ai-run-comparison.md
```

The comparison matches items by `page_url`, summarizes confidence and validation
warnings, evidence-ID health, and lists field disagreements for deadline, fee,
funding, location, dates, eligibility, title, and event type.

The CSV has empty `human_*` columns for manual annotation. Maintainers should
open the official pages, mark whether deadline, fee, funding, location, and
summary are correct, and only then manually promote reliable records through
`data/opportunities.yml` or `data/overrides.yml`.

Recommended operation:

- Daily: `python -m research_school_radar.cli scan`
- Manual or weekly: `python -m research_school_radar.cli scan --enable-semantic`
- Manual review only: `python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction`

Do not enable LLM extraction in daily automation yet. It is slower, more
resource-intensive, and still needs human validation.

## AI-assisted review workflow

Semantic ranking can surface pages that rule-based link and opportunity gates
missed. Local LLM extraction turns selected semantic chunks into advisory
structured drafts, and evidence validation checks whether extracted fields are
grounded in those chunks.

The AI review output is intentionally separate:

- `data/review_queue.json` and `site/review_queue.json` can include an
  `ai_advisory` block for matching scanner candidates.
- `site/ai-review.html` lists matched AI records and potential missed pages.
- `site/ai_extractions.json` keeps the advisory extraction sidecar, including
  short `evidence_snippets`, field-level `evidence_ids`, and resolved snippet
  previews for manual review.

AI output does not determine final qualification, ranking, RSS inclusion, or
recommendation status. Maintainers should use it as a review aid only:

```text
AI extraction -> maintainer checks official page -> maintainer edits data/opportunities.yml or data/overrides.yml
```

Final curated records must still be checked against the official source.

The AI workflow is not meant to replace ChatGPT Agent or other one-off research
assistants. The project is a reproducible publishing and verification system:
AI helps find and draft evidence, while deterministic collection, validation,
history, and human review keep the public output inspectable. See
[`docs/DEVELOPMENT_LOG.md`](docs/DEVELOPMENT_LOG.md) for the current product
reasoning and experiment notes.

## Daily Free Publishing

The scan runs **locally**, from a residential machine, because Cloudflare blocks
the datacenter IP ranges that GitHub Actions (and other cloud hosts) run on — so
a cloud-hosted daily scan would be served bot-challenge pages for many sources.
Running from a home/mobile connection avoids that entirely.

`scripts/scan_and_publish.ps1`, scheduled once a day by Windows Task Scheduler:

1. runs the scanner
2. commits the Markdown report and seen database to `main`
3. builds `site/index.html`
4. deploys the static site to the `gh-pages` branch, which GitHub Pages serves

It includes a connectivity precheck so it skips cleanly when the machine is
offline or on a captive network, and writes a log under `logs/` each run. Set it
up with:

```powershell
# one-time: register the 10:00 daily task
powershell -ExecutionPolicy Bypass -File scripts/register_task.ps1
```

GitHub Actions still runs the test suite on every push (see `.github/workflows/tests.yml`).
The optional `.github/workflows/ai_scan.yml` workflow runs the bounded
`bge-m3` + DeepSeek advisory scan weekly, can be started manually, and deploys
the resulting AI review site to the same `gh-pages` branch. It requires the
repository secret `DEEPSEEK_API_KEY`. `BRAVE_SEARCH_API_KEY` and `HF_TOKEN` are
optional. The local daily rule scan remains the primary collector because it
has better access to official sites than a cloud runner.

## Development

```powershell
pip install -e ".[dev]"
pytest
```

Tests run automatically in CI on every push and pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Contributing Opportunities

Use the GitHub issue template:

```text
.github/ISSUE_TEMPLATE/submit-opportunity.yml
```

Maintainers can review submitted or scanned opportunities and add high-confidence records to:

```text
data/opportunities.yml
```

## Project Shape

```text
config/sources.yaml
        |
        v
collect -> parse -> extract -> filter -> rank
        |
        +--> reports/YYYY-MM-DD.md
        +--> site/index.html
        +--> site/candidates.json
        +--> data/seen.json
```

See [docs/TECHNICAL.md](docs/TECHNICAL.md) for implementation details, current limitations, and the improvement roadmap.

## License & Reuse

This project uses two licenses:

- **Code** — [GNU AGPL-3.0-or-later](LICENSE). You may use, modify, and redistribute the code, but any modified version you run as a network service must also offer its complete source under the AGPL. This keeps derivatives open.
- **Data & compiled listings** (the generated `candidates.json`, the site tables, and the RSS feed) — [Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). You may reuse the data, including commercially, **as long as you give credit and link back** to <https://lione12138.github.io/summer-school-radar/>.

The underlying opportunity details are public facts gathered from the organisers' own pages; always confirm dates, deadlines, and funding on the official page before applying. If you republish the listings, attribution and a link back are required under CC BY 4.0, and a visible canonical-source marker is embedded in the generated output.

