# Summa

[![Tests](https://github.com/lione12138/summer-school-radar/actions/workflows/tests.yml/badge.svg)](https://github.com/lione12138/summer-school-radar/actions/workflows/tests.yml)
[![License: AGPL v3](https://img.shields.io/badge/Code-AGPL--3.0-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-green.svg)](#license--reuse)

An open-source scanner for funded research training opportunities — summer schools, winter schools, training schools, field schools, and short courses — **across many academic fields**: environmental & earth science, computing & data science, the social sciences, and the humanities.

It is a fixed trusted-source scanner with rule-based extraction and transparent per-field evidence — not a fully automatic all-web radar. It scans a curated registry of trusted academic sources, extracts deadline / funding / fee / duration evidence together with the supporting text, separates fully qualified, high-quality, and found opportunities, and publishes a static website that updates daily for free on GitHub Pages.

**Live site:** <https://lione12138.github.io/summer-school-radar/>

[Technical README](docs/TECHNICAL.md) | [中文技术说明](docs/TECHNICAL.zh-CN.md) | [License & reuse](#license--reuse)

## Latest Scan Results

This section is refreshed automatically by the daily local scan.

<!-- radar:results:start -->
_Last scan: 2026-06-19 · 1 fully qualified · 2 high-quality · 3 found shown_

**Fully Qualified Opportunities**

| # | title | type | organizer | location | duration | deadline | funding / fee | topic | eligibility | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | [Social Science Data Analysis](https://essexsummerschool.com/new-application/) | summer school | Essex Summer School | Colchester, UK | 29 Jun – 14 Aug 2026 · 47 days | 2026-07-17 | scholarship · amount not stated · Apply on official page | satellite, geospatial, AI, machine learning | Masters PhD Not Currently a Student Discipline Country of University / Employer * Afghanistan Albania Algeria Andorra Angola Anguilla Antigua and Barbuda Argentina Ar | topic match: satellite, geospatial, AI, machine learning; funding evidence: scholarship; deadline appears open; 47 days |

**High-Quality Opportunities**

| title | type | organizer | location | duration | deadline | funding / fee | topic |
|---|---|---|---|---|---|---|---|
| [ICOS Summer/Winter School January 2027, application is now open](https://www.icos-cp.eu/about/opportunities/summer-school) | summer school | ICOS | Europe | 18 Jan – 28 Jan 2027 · 11 days | 2026-07-31 | financial support · amount not stated · Apply on official page | climate, climate change, remote sensing, statistics |
| [ELLIS Summer School at Unit Saarbrücken](https://ellis.eu/events/ellis-summer-school-at-unit-saarbruecken-2026) | summer school | ELLIS | Saarland University | 24 Aug – 28 Aug 2026 · 5 days | uncertain | Fee about EUR 250 · Apply on official page | AI |

**Found Opportunities**

| title | type | organizer | location | duration | deadline | funding / fee | topic |
|---|---|---|---|---|---|---|---|
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
`BAAI/bge-small-en-v1.5` via `sentence-transformers`. Semantic ranking is
cached under `data/ai_cache/` by page URL, page text hash, embedding model,
query, and chunking config.

```powershell
pip install -e ".[dev,semantic]"
python -m research_school_radar.cli scan --enable-semantic
```

Semantic sidecar output goes to `site/semantic_chunks.json` and
`reports/YYYY-MM-DD.semantic.json`.

Local LLM extraction is also optional and advisory only. It reads semantic
chunks, asks a local Ollama OpenAI-compatible endpoint running `qwen3.5:9b` for
structured evidence, and writes sidecar JSON without changing candidates,
filters, rankings, RSS, or the public tables. Ollama must be installed manually;
this project does not install Ollama or download models automatically. In the
Ollama CLI, `/set nothink` can disable thinking during manual interactive tests.

```powershell
pip install -e ".[dev,semantic,llm]"
ollama run qwen3.5:9b
python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction
```

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

## AI-assisted review workflow

Semantic ranking can surface pages that rule-based link and opportunity gates
missed. Local LLM extraction turns selected semantic chunks into advisory
structured drafts, and evidence validation checks whether extracted fields are
grounded in those chunks.

The AI review output is intentionally separate:

- `data/review_queue.json` and `site/review_queue.json` can include an
  `ai_advisory` block for matching scanner candidates.
- `site/ai-review.html` lists matched AI records and potential missed pages.
- `site/ai_extractions.json` keeps the raw advisory extraction sidecar.

AI output does not determine final qualification, ranking, RSS inclusion, or
recommendation status. Maintainers should use it as a review aid only:

```text
AI extraction -> maintainer checks official page -> maintainer edits data/opportunities.yml or data/overrides.yml
```

Final curated records must still be checked against the official source.

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
No paid search API key is required.

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

