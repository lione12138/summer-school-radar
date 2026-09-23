# Australian source onboarding — 2026-09-22

Five official sources are enabled across the 22–23 September batches; one is retained disabled pending reconciliation of conflicting official dates.

| Source | Official entry | Collection |
| --- | --- | --- |
| AMSI Winter School | https://ws.amsi.org.au/ | Recurring programme plus registered application/fee evidence; edition-scoped dates and conditional grants |
| ACAN Neuroscience | https://ans.org.au/acan | Dedicated Australasian Neuroscience Society course; explicit dates, UNSW venue and GST-qualified fee |
| ACSPRI | https://www.acspri.org.au/ | Registry-controlled `acspri` collector; current seasonal programmes, in-person course variations, and each variation's price page |
| AMSI Summer School — disabled | https://ss.amsi.org.au/ | Homepage says 6 February 2027; About and AMSI calendar say 5 February 2027 |

AMSI Summer School date evidence: [homepage](https://ss.amsi.org.au/), [About](https://ss.amsi.org.au/about/), [official calendar](https://amsi.org.au/events/event/amsi-summer-school-2027/). No date has been silently selected. Its disabled registry note records the reason and review date.

The enabled sources produced five records in live checks: AMSI Winter School 2026 (6–17 July), ACAN 2026 (10–30 May), and three ACSPRI Melbourne offerings in February 2027. The first two editions have ended. ACSPRI's two-day offerings fail the four-day minimum; its five-day qualitative research course has a general standard fee of AUD 4,255, with separate early-bird/member/student discounts. This onboarding does not imply five new recommendations.

`collector_acspri.py` discovers at most three seasonal programme links from the official root and twenty in-person course links per programme. It reads offering cards separately: the same subject's online and Melbourne editions are not merged. Teaching dates come from the offering's own structured schedule, excluding its early-bird date; only explicitly scheduled days count toward duration. The numeric pricing URL supplies stable offering identity. Standard fee extraction is mandatory: a missing price raises a collection error instead of silently turning a known paid course into a fee-unknown listing. The official [booking policy](https://www.acspri.org.au/online-winter-program-2026) denominates booking credits/payments in AUD. Student/member discounts are not treated as the general fee. Early-bird discount expiry is not an application closing date. No login or booking is performed.

`australia_adapters.py` attaches AMSI Winter School's edition year to its explicitly stated month/day interval, reads the extended application deadline, selects the general non-member fee, and retains the eligibility restrictions on travel/accommodation grants. The option of remote participation is labelled hybrid. Cross-links to other AMSI schools and research scholarships are blocked for this programme source. ACAN's institutional sponsors are not interpreted as student financial aid, and the fee remains explicitly “AUD 5250 + GST” without pretending the tax-inclusive total is known.

AMSI BioInfoSummer currently points to an old 2024 edition and was not enabled in this batch. ANU's 2027 Political Analysis school is explicitly online; research scholarships/internships were not substituted for schools.

Raw replay: local `logs/australia-onboarding-2026-09-22.json`. Production snapshots and deployment are unchanged by onboarding; the next gated full scan incorporates the enabled sources.

## Second batch — 2026-09-23

- [ANSTO-HZB-AONSA Neutron School](https://www.ansto.gov.au/whats-on/ansto-hzb-aonsa-neutron-school-2026): 16–20 November 2026, Lucas Heights, AUD 750 including GST. The adapter reads the EOI closing row (16 August), never the 11 October registration deadline for already accepted applicants. AINSE flight assistance retains the affiliated-university, outside-Greater-Sydney campus and capped-support restrictions. This is an edition-specific entry requiring annual URL review; `programme_key` preserves recurring identity.
- [UNSW Economics Summer School](https://www.unsw.edu.au/business/study-with-us/economics-summer-school): recurring graduate-training entry. The record explicitly covers the full programme, both courses, 8–12 February 2027, at the regular AUD 2,250 fee. It does not assign five days to an individual half-programme course or substitute a student/half-programme price. The visible registration link does not independently prove an open application window, so deadline status remains uncertain.

Both official pages fetched successfully and produced one candidate each in `logs/australia-expansion-2026-09-23.json`. Neither adds a recommendation: ANSTO applications have closed; UNSW application status is unconfirmed and its standard fee exceeds the recommendation threshold. These changes do not replace production snapshots or deploy the site. ACCESS-NRI workshop listings and pre-university/study-abroad programmes were not added as research schools.
