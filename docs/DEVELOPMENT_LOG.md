# Development Log / 开发日志

This file records product and technical decisions that came from real scan
experiments. It is intentionally more reflective than `TECHNICAL.md`.

## 2026-06-26: Reframing the Workflow

### Question

If ChatGPT Agent can be asked to scan a fixed source list every day and produce
a table, why maintain this project at all?

### Current Answer

This project should not try to beat a general-purpose agent at one-off research.
For a private, occasional search, ChatGPT Agent plus manual checking may be
enough.

The project is useful when the goal is a public, repeatable, auditable radar:

- stable source list and scan configuration
- deterministic collection and report generation
- preserved reports and review queues
- evidence-aware extraction rather than a one-time answer
- public README/site/RSS outputs
- human review before promotion into curated/public records

The project should therefore be treated as a publishing and verification system,
not as a fully autonomous research agent.

### Recommended Workflow

Use a hybrid workflow:

```text
fixed sources and controlled discovery
-> collect source pages and linked pages
-> deterministic follow-up fetch for application/registration/fees/funding pages
-> bge-m3 semantic ranking
-> DeepSeek advisory extraction from selected snippets
-> evidence validation and review queue
-> human confirmation
-> curated records and public tables
```

AI output remains advisory. It should not directly change `fully_qualified`,
hard filters, ranking, RSS, or public table status.

### What Worked

- `BAAI/bge-m3` improved semantic recall compared with
  `BAAI/bge-small-en-v1.5`, at acceptable runtime for weekly/manual use.
- DeepSeek API integration works through an OpenAI-compatible chat endpoint.
- DeepSeek with `deepseek-v4-flash`, JSON object mode, and disabled thinking can
  produce structured advisory extraction.
- Expanding the exploratory caps to 150 pages showed the actual current pool is
  smaller than the cap:
  - 212 pages considered by semantic ranking
  - 129 semantic chunks selected
  - 81 unique pages sent to LLM extraction
  - 81 AI extraction items produced
- The API found useful evidence that the rule extractor either missed or did
  not surface cleanly, including some deadline, fee, and funding snippets.

### What Failed Or Remains Weak

- Legacy local-model provider trials were not reliable enough for daily
  extraction. They were useful for validating the architecture, but produced
  too many omissions or malformed/weak outputs on real pages; that code has
  since been removed from the production branch.
- DeepSeek is not browsing. It only reads chunks the scanner has already
  collected and selected. It does not click links, open registration pages, or
  decide to visit fee pages by itself.
- The current page selection is too broad. In the 2026-06-26 run, many AI items
  were listing/index/testimonial pages rather than high-value detail pages.
- Raising caps alone is not the right long-term fix. It increases recall, but it
  also sends more weak pages to the LLM.
- API extraction can help review, but it does not make public qualification
  trustworthy without deterministic evidence and human checking.

### Next Engineering Priority

The next useful improvement is deterministic follow-up page expansion before
LLM extraction:

- detect and fetch links whose anchor text or URL contains application,
  registration, apply, fee, fees, tuition, cost, funding, scholarship, deadline,
  dates, or practical information
- deduplicate repeated pages
- deprioritize testimonials, generic archive pages, broad event listings, and
  pages with weak evidence
- group related pages from the same opportunity so the LLM sees overview,
  application, fee, and funding evidence together
- keep AI results in sidecars until a maintainer verifies the official source

This is closer to how a human or ChatGPT Agent searches: start with an overview,
then intentionally open the application/fees/deadline pages. The difference is
that the project keeps this process reproducible and inspectable.

### Cost Position

DeepSeek API costs appear low enough for weekly advisory runs because the model
only receives selected snippets, not all raw pages. The practical control should
be page and chunk selection quality, not simply minimizing the cap too early.

Current exploratory defaults:

- `max_pages_for_ai: 150`
- `max_pages_per_source: 8`
- `max_pages_for_llm: 150`
- `max_chunks_per_page: 3`
- `max_chars_per_chunk: 2200`
- `max_total_chars_per_request: 7000`

These are measurement caps. After several real weekly runs, reduce them to the
smallest values that preserve useful recall.

## 2026-06-27: Bounded Follow-up Retrieval Implemented

The deterministic follow-up priority above is now implemented in the optional
AI advisory path. Missing high-value fields trigger limited official-domain
link following, optional Brave `site:` search, semantic re-ranking, and a second
evidence-grounded extraction. The model does not receive a general browser and
cannot exceed the configured opportunity, query, result, page, round, chunk, or
character budgets.

This iteration also tightened extraction semantics after reviewing the first
DeepSeek run:

- application/registration deadlines are separated from payment,
  accommodation, scholarship, travel-grant, and abstract deadlines
- explicit open, not-yet-open, and closed wording is requested
- complete fee tiers are requested instead of only the minimum amount
- evidence snippets preserve the exact related-page URL
- deterministic validation checks whether cited fee/date values are supported
  and warns about non-application deadline risk
- a second extraction replaces the first only when it resolves at least as many
  critical fields

The remaining evaluation question is empirical: run the same known-page test
set again and measure whether follow-up retrieval improves deadline, fee, and
funding accuracy without increasing cross-edition merges. AI results remain
sidecar-only until that comparison is complete.

## 2026-06-28: Evidence-Gated Homepage Integration

The separate public AI Review page made users compare two parallel products and
did not present the best available record in the main tables. The AI-enabled
build now merges validated extraction into deep copies of homepage candidates.

The safety boundary is field-level rather than page-level:

- exact URL matches fill only unresolved fields
- missing or invalid evidence IDs block the affected value
- deadline, fee, funding, location, and eligibility context warnings block only
  their corresponding fields
- unmatched pages require an explicit `opportunity` or `application` page type
- legacy outputs without page type can enrich exact matches but cannot create
  standalone opportunities
- merged records pass through the existing hard filters and ranking
- original scan candidates, Markdown reports, RSS, state, and curated data are
  unchanged

A local audit against the existing 81-item AI sidecar initially exposed three
false standalone leads from a scholarship page, a fee page, and an index page.
Requiring an explicit page type removed all three. The same audit correctly
filled ICOS's deadline and moved it from High-Quality to Fully Qualified through
the normal rule filters. The public `AI Review` page and navigation entry were
removed; `site/ai_extractions.json` remains the evidence and warning trail.

## 2026-07-14: Recoverable Scheduled Publishing

Two consecutive Windows scheduled runs stopped before generation because a
single `git pull --ff-only` attempt could not reach GitHub. The earlier generic
HTTP HEAD precheck was not a reliable predictor of Git transport availability.
The machine also had a reachable per-user Windows proxy that browsers used but
Git did not, explaining why interactive web access and scheduled Git behaved
differently.

The local automation now retries `pull`, `fetch`, and `push` with bounded delay.
When Git has no explicit proxy setting, it first reuses a reachable Windows user
proxy through process-scoped Git configuration without changing global config.
If GitHub is unavailable before an otherwise clean run, one local generation may
still complete. When its generated commit cannot be pushed, the script records
the commit hash, base revision, message, and allowed generated paths under
`.git/summa-pending-publish.json`, returns `main` and the working tree to their
pre-run state, and exits non-zero so monitoring still reports “not published.”
After connectivity returns, the next run validates the queued commit and pushes
it before starting new work. It discards queued output if newer `main` already
changed any of those generated paths.

Full local scans now also make one tiny Brave Search request before source work,
alongside the existing strict DeepSeek health check. Serper remains excluded
from scheduled scans and is still audit-only.

The live scheduler acceptance check exposed a second operational blocker: the
task remained queued while the laptop was on battery. The registered settings
now allow starting and continuing on battery while retaining the network and
three-hour execution constraints.
