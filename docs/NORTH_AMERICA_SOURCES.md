# North American source onboarding — 2026-09-22

Four official sources are enabled in `config/sources.yaml`. This adds one US-based organizer and three Canadian entries; an organizer's registry region is not the venue of every school it hosts.

| Source | Collection | Live deterministic records |
| --- | --- | --- |
| [SLMath Summer Graduate Schools](https://www.slmath.org/summer-schools) | Official current/upcoming JSON catalogue, with separate official nomination announcement | 10 |
| [CRM Schools](https://www.crmath.ca/en/activities/schools/) | Dedicated school catalogue, at most 20 same-domain activity routes; rendered `.event-details` only | 3 |
| [TRISEP](https://www.trisep.ca/) | Recurring programme homepage; scoped date adapter and current registration Indico link discovery | 1 |
| [Perimeter Undergraduate Summer School](https://perimeterinstitute.ca/training/undergraduate-summer-programs/undergraduate-summer-school) | Dedicated undergraduate school body, excluding internship and degree navigation | 1 |

Live replay returned no fetch/extraction errors: 15 raw records, 13 after deduplication. SLMath and CRM share the SMS and CRM–PIMS probability series. These named series share an identity only when both teaching dates also match; unrelated schools retain distinct catalogue IDs. Raw replay evidence is stored locally in `logs/north-america-onboarding-2026-09-22.json`.

SLMath's JSON endpoints require `Accept: application/json`; the site's default HTML Accept header caused a reproducible 406 on its page-content API. The collector reads exact per-school dates and separates the dated nomination-opening announcement from organizer-proposal deadlines. Before the stated opening day, matching editions are `not_open`; after that day, elapsed time alone does not establish that applications opened. The current listing contains schools in Canada and Japan as well as the US. Unknown per-school fees, funding and delivery mode remain unresolved.

CRM's rendered route must contain the expected event detail structure. A failed render is reported as a source error rather than a healthy empty result. It does not follow arbitrary microsites or conduct-policy links. Some details currently have only dates and a title; missing application/financial information remains unresolved. Conduct-policy boilerplate is not used as a school description.

TRISEP's year precedes its date range in the official sentence; the adapter joins those components only on the recurring root page. Perimeter's body selection excludes the header's unrelated “Get Updates” field and the site's masters/PhD/internship navigation. Shared undergraduate-programme funding and internship eligibility are not imported into the school without edition-specific evidence.

These are candidate counts, not new recommendations. SLMath 2027 nominations are not open at the replay date; TRISEP and Perimeter currently describe ended 2026 editions. Normal publication filters remain unchanged. This targeted onboarding does not replace the production full-scan snapshots or deploy the site; the next gated full scan incorporates the new sources.

Validation: 482 offline pytest tests passed; Ruff passed. No commit, push, production snapshot replacement or deployment was performed.


## Second US batch — 2026-09-22

Added four enabled official sources:

| Source | Entry and adaptation | Live candidates |
| --- | --- | --- |
| Berkeley Lab DL4SCI | https://dl4sci-school.lbl.gov/ — recurring programme and registered fee page; reconstruct split Google Sites inline text | 1 |
| ORNL National Neutron Scattering School | https://neutrons.ornl.gov/nns — dedicated current NNS page and scoped body/date adapter | 1 |
| Emory SISMID | https://sismid.sph.emory.edu/modules/index.html — dedicated in-person module tables | 16 |
| Georgia Tech SISG | https://sisg.biosciences.gatech.edu/courses-2/ — individual course tables under dated headings | 17 |

All four live checks passed without fetch errors. The 33 module records each span three calendar dates; all fail the unchanged four-day minimum. SISMID explicitly describes 2.5 teaching days, retained in duration evidence. No two-week outer window is advertised as a continuous course. These are deliberate audit candidates, not new recommendations. Both other schools currently describe ended 2026 editions.

The new `sismid` and `sisg` collectors are enabled only through the registry. Course links must remain on the registered domain; tables without their expected date headings fail rather than produce a misleading success. Per-course financial support remains unknown when only institute-wide information is available. SISG's separately hosted Auckland programme is not mixed into its Atlanta course tables.

DL4SCI's Google Sites headings split both “School” and “2026” across spans. Normalization joins inline text within individual paragraphs/headings, retaining programme content outside the misleading small `role=main` block. Explicit fee evidence preserves the USD 250 ceiling without turning it into an exact numeric fee. Limited student registration waivers retain their selection restriction.

Screened but not enabled: USPAS and UW INT returned HTTP 403; FRIB NS3 returned an Incapsula challenge even after rendering. The latter is now rejected by the content validator. Penn State astrostatistics is currently virtual; MBI/ICERM research internships and school-age outreach were not substituted for research schools. ORNL's older NXS entry still describes 2024, so the current recurring NNS school was chosen instead. EMSL was inspected but has not been added in this batch.

Local replay: `logs/us-expansion-2026-09-22.json`. No production snapshot replacement or deployment was performed.


Second-batch validation: 489 pytest tests passed; Ruff passed. The new registry entries are enabled locally; publication awaits a gated full scan.
