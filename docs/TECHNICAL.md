# Technical README

Technical notes for Research Seasonal School Radar, an open-source radar for research seasonal training opportunities: summer schools, winter schools, training schools, field schools, doctoral schools, short courses, advanced courses, and structured research workshops.

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

The scanner retains `training school` because research organizations commonly use that label for short, intensive summer-school-style programmes. The generic word `workshop` is not sufficient by itself: workshop pages must also contain a training signal such as hands-on, field, practical, training, or capacity building. Duration and the remaining hard filters still apply.

## Architecture

The pipeline is intentionally simple Python rather than a multi-agent framework.

```text
config/sources.yaml
        |
        v
collect.py  ->  fixed source pages
        |
        v
parse.py    ->  candidate opportunity links
        |
        v
collect.py  ->  linked opportunity pages
        |
        v
extract.py  ->  structured Candidate records
        |
        v
filter.py   ->  hard filters and failed conditions
        |
        v
rank.py     ->  interpretable scoring and deduplication
        |
        +--> report.py  -> reports/YYYY-MM-DD.md
        |
        +--> site.py    -> site/index.html + site/candidates.json
        |
        +--> storage.py -> data/seen.json
```

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

## Configuration

- `config/profile.yaml` controls preferred topics, hard filters, financial-access thresholds and reference exchange rates, priority regions, supplementary regions, and excluded programme types.
- `config/sources.yaml` lists trusted sources. Each source can be enabled or disabled, and can block problematic linked domains.
- `config/queries.yaml` stores optional controlled discovery queries.
- `config/site.yaml` controls optional analytics.
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



