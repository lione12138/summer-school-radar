# Summer School Radar

[![Tests](https://github.com/lione12138/summer-school-radar/actions/workflows/tests.yml/badge.svg)](https://github.com/lione12138/summer-school-radar/actions/workflows/tests.yml)
[![Daily scan](https://github.com/lione12138/summer-school-radar/actions/workflows/scheduled_scan.yml/badge.svg)](https://github.com/lione12138/summer-school-radar/actions/workflows/scheduled_scan.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An open-source scanner for funded research training opportunities — summer schools, winter schools, training schools, field schools, and short courses — in **water, climate, geoscience, remote sensing, and scientific machine learning**.

It is a fixed trusted-source scanner with rule-based extraction, a maintainer-curated layer, and transparent per-field evidence — not a fully automatic all-web radar. It scans a curated registry of trusted academic sources, extracts deadline / funding / fee / duration evidence together with the supporting text, separates fully qualified opportunities from near-matches, and publishes a static website that updates daily for free on GitHub Pages.

**Live site:** <https://lione12138.github.io/summer-school-radar/>

[Technical README](docs/TECHNICAL.md) | [中文技术说明](docs/TECHNICAL.zh-CN.md) | [MIT License](LICENSE)

## Latest Scan Results

This section is refreshed automatically by the daily scan workflow.

<!-- radar:results:start -->
_Last scan: 2026-06-14 · 0 fully qualified · 5 high-quality opportunities shown_

**No fully qualified opportunities in the latest scan.** The high-quality opportunities below are open and in scope, but missing a fully confirmed condition.

**High-Quality Opportunities**

| title | type | organizer | location | duration | deadline | funding / fee | topic |
|---|---|---|---|---|---|---|---|
| [River Basin Modelling](https://www.un-ihe.org/short-courses) | short course | IHE Delft | Delft, Netherlands | 11 Jan – 29 Jan 2027 · 19 days | 2026-12-11 | Fee about EUR 2600 · Apply on official page | groundwater, water resources, water quality, GIS |
| [ICOS Summer/Winter School January 2027, application is now open](https://www.icos-cp.eu/about/opportunities/summer-school) | summer school | ICOS | Europe | 18 Jan – 28 Jan 2027 · 11 days | 2026-07-31 | Funding or fee not stated | climate, climate change, remote sensing |
| [Short Course: Structural Geology Must-Knows](https://eage.eventsair.com/short-course-structural-geology-must-knows/) | short course | EAGE | Venue Preview Webinar | 1 Sep – 3 Sep 2026 · 3 days | 2026-07-31 | Funding or fee not stated | geoscience, geology |
| [ELLIS Sites ICML Fest 2026: Celebrate, Connect, Collaborate](https://ellis.eu/events/ellis-sites-icml-fest-2026) | summer school | ELLIS | Multiple Locations | 16 Jun – 24 Jul 2026 · 39 days | uncertain | Funding or fee not stated | AI, machine learning |
| [IEEE GRSS Summer School on UAS-Based GNSS-R Remote Sensing](https://www.grss-ieee.org/event/ieee-grss-summer-school-on-uas-based-gnss-r-remote-sensing/) | summer school | IEEE GRSS | University of Michigan, Ann Arbor, USA | 14 Jul – 16 Jul 2026 · 3 days | uncertain | Funding or fee not stated | climate, geoscience, remote sensing, earth observation |

<!-- radar:results:end -->

## Upcoming Research Training Opportunities

The generated website shows maintainer-reviewed opportunities first, followed by scanner results.

- **Curated Opportunities**: high-confidence records reviewed by maintainers.
- **Fully Qualified Opportunities**: scanner results that satisfy every hard condition.
- **High-Quality Opportunities**: still-open, in-domain opportunities that are relevant but missing a fully confirmed hard condition.
- **Sources & Coverage**: the configured trusted source registry, including disabled sources and notes.

The site includes filters for keyword, status, topic, financial access, and deadline status. Rows with a known application deadline include an **Add to calendar** link that downloads a standard `.ics` event.

```text
site/index.html
site/candidates.json
site/curated.json
site/sources.html
site/sources.json
site/feed.xml
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
| Topic | Relevant to water, hydrology, climate, geoscience, remote sensing, environmental modelling, disaster risk, or scientific machine learning |

Near-matches are never presented as qualified results.

Foreign-currency fees are converted with configurable fixed reference rates so the default workflow remains free and API-key-free. The rates are deliberately conservative, not real-time. Unknown currencies or ambiguous fees remain near-matches.

The radar targets seasonal schools and short courses — summer schools, winter schools, spring/autumn schools, training schools, doctoral schools, field schools, research schools, and short/advanced courses. `Training school` is included because many research networks use it for the same kind of short, intensive programme as a summer school. Generic conference workshops are not included.

## Why Not Another Summer School List?

Most summer school lists are plain link collections. This project is different:

- trusted source registry instead of random web crawling
- structured extraction for deadline, funding, duration, mode, eligibility, and location
- hard filters with visible failed conditions
- maintainer-reviewed curated layer
- static public website plus Markdown and JSON outputs
- daily free automation with GitHub Actions and GitHub Pages
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

The included GitHub Actions workflow can:

1. run the scanner every day
2. commit the Markdown report and seen database
3. build `site/index.html`
4. deploy the static site to GitHub Pages

For a public repository, the default workflow does not require a paid search API key.

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

