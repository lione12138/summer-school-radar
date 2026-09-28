# Summa pilot gold benchmark

Run `python -m research_school_radar.benchmark --output logs/benchmark.json`.
The pytest suite runs the same comparison against `baseline.json` offline.

The reference date is **2026-09-28**. There are 30 captured official-page cases
(29 distinct programmes; CERN includes its application and programme pages)
and 10 explicitly synthetic boundary cases. Official HTML comes from the local
HTTP cache; executable scripts, styles and SVGs are removed while JSON-LD is preserved. Each case records its source
URL, capture timestamp, expected extraction/publication and annotation rationale.
Initial annotations use the project eligibility policy and the captured edition
records, not the evaluator's current output. These are an initial agent-reviewed
gold set, not an independently human-adjudicated representative sample.

Cases cover open/closed calls, uncertain information, expensive fees, conditional
support, online training, conference workshops, degree admissions, short events,
and multi-session duration. The boundary cases are not real programmes.

Metrics distinguish extraction recall (known input pages producing records) from
publication recall and precision (eligible records correctly displayed). The
runner exercises the real extractor, hard filters and publication functions.
It does **not** simulate a successful LLM audit, use API keys or search the web.
Discovery evidence/audit/URL rejection is separately exercised in
`tests/test_discovery_publication.py`.

Initial baseline: 35/38 extractable pages found, 6/9 eligible cases published,
zero false positives. Three misses are ECMWF pages whose existing structured
collection/AI path is not reproduced by this single-page deterministic replay.
Keep these misses visible; do not relabel them as negatives to improve scores.

These numbers are **not whole-web search recall**, and 100% precision here does
not establish production precision. An end-to-end discovery recall estimate
requires frozen Serper result sets or a dated live run compared against a larger,
independently assembled set of known programmes. Add such captures as the next
evaluation layer. Do not lower the baseline automatically; explain intentional
label/policy changes in the development log.
