# Summa

[![Tests](https://github.com/lione12138/summer-school-radar/actions/workflows/tests.yml/badge.svg)](https://github.com/lione12138/summer-school-radar/actions/workflows/tests.yml)
[![License: AGPL v3](https://img.shields.io/badge/Code-AGPL--3.0-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-green.svg)](#license--reuse)

An open-source scanner for funded research training opportunities — summer schools, winter schools, training schools, field schools, and short courses — **across many academic fields**: environmental & earth science, computing & data science, the social sciences, and the humanities.

It is a fixed trusted-source scanner with rule-based extraction and transparent per-field evidence — not a fully automatic all-web radar. It scans a curated registry of trusted academic sources, extracts deadline / funding / fee / duration evidence together with the supporting text, separates fully qualified opportunities from near-matches, and publishes a static website that updates daily for free on GitHub Pages.

**Live site:** <https://lione12138.github.io/summer-school-radar/>

[Technical README](docs/TECHNICAL.md) | [中文技术说明](docs/TECHNICAL.zh-CN.md) | [License & reuse](#license--reuse)

## Latest Scan Results

This section is refreshed automatically by the daily local scan.

<!-- radar:results:start -->
_Last scan: 2026-06-17 · 0 fully qualified · 5 high-quality opportunities shown_

**No fully qualified opportunities in the latest scan.** The high-quality opportunities below are open and in scope, but missing a fully confirmed condition.

**High-Quality Opportunities**

| title | type | organizer | location | duration | deadline | funding / fee | topic |
|---|---|---|---|---|---|---|---|
| [River Basin Modelling](https://www.un-ihe.org/short-courses) | short course | IHE Delft | Delft, Netherlands | 11 Jan – 29 Jan 2027 · 19 days | 2026-12-11 | Fee about EUR 2600 · Apply on official page | groundwater, water resources, water quality, GIS |
| [ICOS Summer/Winter School January 2027, application is now open](https://www.icos-cp.eu/about/opportunities/summer-school) | summer school | ICOS | Europe | 18 Jan – 28 Jan 2027 · 11 days | 2026-07-31 | financial support · amount not stated · Apply on official page | climate, climate change, remote sensing, statistics |
| [Summer School Science Communication](https://www.universiteitleiden.nl/en/education/study-programmes/summer-schools/summer-school-science-communication) | summer school | Leiden Linguistics Summer School | Leiden | 6 Jul – 10 Jul 2026 · 5 days | uncertain | Fee about EUR 575 · Apply on official page | statistics, law, education research, design |
| [Karthaus summerschool](https://www.projects.science.uu.nl/iceclimate/karthaus/) | summer school | Karthaus Summer School | Europe | 18 May – 27 May 2027 · 10 days | uncertain | Funding or fee not stated | climate, meteorology, glaciology, cryosphere |
| [Machine Learning Summer School on Reliability & Safety](https://ellis.eu/events/machine-learning-summer-school-on-reliability-safety-mlss-rs) | summer school | ELLIS | Kraków | 29 Jun – 3 Jul 2026 · 5 days | uncertain | Funding or fee not stated | AI, machine learning |

<!-- radar:results:end -->

## Upcoming Research Training Opportunities

The generated website lists fully qualified scanner results first, then high-quality near-matches.

- **Fully Qualified Opportunities**: scanner results that satisfy every hard condition.
- **High-Quality Opportunities**: still-open, in-domain opportunities that are relevant but missing a fully confirmed hard condition.
- **Sources & Coverage**: the configured trusted source registry, including disabled sources and notes.

The site includes filters for keyword, status, topic, financial access, and deadline status. Rows with a known application deadline include an **Add to calendar** menu (Google Calendar, Outlook, or a downloadable `.ics` file).

```text
site/index.html
site/candidates.json
site/sources.html
site/sources.json
site/feed.xml
site/sitemap.xml
reports/YYYY-MM-DD.md
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

