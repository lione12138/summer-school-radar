# October coverage regression

Reference date: 2026-10-21. Reviewed and implemented on 2026-10-22–23.
Transport success is not an estimate of programme recall.

## Reproducible comparison

Run `python -m research_school_radar.coverage_benchmark` or
`python -m pytest tests/test_coverage_regression.py`.
Captures, source URLs, original SHA-256 hashes and capture dates are recorded in
`benchmarks/coverage-captures-2026-10.json`. Scripts/styles were removed for
offline replay; headings, body text, links and relevant structure are retained.

| Same supplied official inputs | Before (fc88e038) | After |
| --- | ---: | ---: |
| Programme records extracted | 4/5 | 5/5 |
| Records passing every annotated field check | 0/5 | 5/5 |
| Eligible records correctly published | 1/3 | 3/3 |
| False-positive publications | 1 | 0 |
| ICTP/GFZ target links within eight-link budget | 0/2 | 2/2 |

These are small, agent-reviewed regression fixtures, not a population recall or
production precision estimate. Both versions receive the newly registered
sources, isolating extraction improvements from registry expansion. Princeton
is intentionally a negative publication case until its discovery audit passes.
ICTP's official listing is captured, but its detail endpoint timed out during
this investigation; a listing-link success is not counted as a published record.

## Findings and repairs

- **ICTP:** `Spring College` was absent from the programme vocabulary; chronological
  listing order also consumed the eight-link budget with closed calls. Recognize
  this short-course format and prioritize dated open applications in ICTP cards.
  The known Spring College detail URL is an explicit follow-up in the registry.
- **Princeton:** an Opportunities for Youth lead was titled `Featured`.
  Reject generic titles and aggregator publications; follow at most two explicit
  external programme links per lead, eight requests per scan, with no recursion.
  Recovered pages retain `discovery` trust and require the existing evidence audit.
  The independently hosted programme site remains at discovery trust even though
  it links to a matching Princeton Qualtrics application. No domain promotion.
- **MyClimate:** folded milestone text attached “Application Deadline” to the next
  announcement date. Date-first deadline parsing now returns 30 October 2026.
  The official `15 November 2027: Acceptance Announcements` contradiction remains
  explicit in the summary. Myanmar/Thailand eligibility and needs-based support
  remain visible; the notification year is not silently changed.
- **IMISCOE:** unrelated event dates in the Joomla page caused a calendar rejection.
  Extract only the article. Record the EUR 200–600 fee tiers conservatively at the
  unrestricted EUR 600 rate. Two scholarships and two fee waivers are competitive;
  this is a verified self-funded directory record, not a funded recommendation.
- **PoliTO/CoMaDe:** join registered application/fee evidence and remove navigation
  contamination from key fields. Travel/accommodation and BUP eligibility remain
  explicit; registration/participation charges do not imply all expenses are paid.
- **CoMaDe date conflict:** the body gives 31 January–6 February 2027, but the
  quick-information block gives 2026. Preserve both quotations in `source_conflicts`
  and block every public tier until the official source resolves the contradiction.
  This corrects one false positive in the prior implementation's fixture replay.
- **Audit reliability:** failed JSON/provider extraction caches are retried on later
  scans. Audit retries explicitly request schema-compliant JSON. Evidence windows
  include plural organizers and avoid heavily overlapping excerpts, retaining
  Princeton's team and eligibility evidence. Its targeted evidence audit passed on
  23 October; the offline benchmark still requires audit and therefore rejects it.
- **ALPS:** same title, organizer, full dates, location and sessions establish the
  same edition across URL/identity migrations. Prefer explicit programme IDs,
  retain prior editions and edition lookup aliases, and never merge distinct
  explicit programme keys solely by text similarity.

## Healthy sources with no extracted records

| Source | Captured evidence | Interpretation |
| --- | --- | --- |
| IAH | “No courses are currently listed” | No courses in this captured listing; does not prove whole-site coverage |
| UKCEH | “No results found” | No results in the captured response; monitor rather than assert parser failure |
| COST Action Events | Current items are surveys, webinars, workshops/conferences | No explicit target school identified in this sample; funding navigation is not a programme |
| GFZ | Potsdam Summer School 2026 card, detail anchor labelled only “read more” | Genuine link-discovery miss; fixed using the nearest card heading. The 31 March 2026 application deadline is past, so this does not add an open opportunity |

Existing manifests already separate `fetch_health`, `extraction_health`,
`extracted_records`, `public_open_records` and `consecutive_empty_scans`.
The Sources page explicitly says that extracted candidates do not guarantee
coverage and zero candidates leave coverage unverified. These observations and
the dated benchmark are the coverage evidence, rather than HTTP success rates.

## Follow-up records kept separate

- [GIG-ARTS School 2027](https://gig-arts.eu/2026/09/20/early-bird-registration-now-open-for-the-gig-arts-school-2027/):
  official announcement states EUR 680 early registration until 15 November 2026,
  EUR 800 regular, with travel/accommodation excluded. The reported Global Access
  awards require their own verified eligibility and award evidence; do not label
  all participants funded or infer a general application deadline from early-bird pricing.
- [Quantsol Winter School](https://www.helmholtz-berlin.de/events/quantsol-winterschool/index_en.html):
  retain as a review lead. The reported EUR 790 fee exceeds the EUR 400 recommendation
  threshold. It has not been promoted into the funded/low-fee selection.
