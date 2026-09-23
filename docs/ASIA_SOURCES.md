# Asian source onboarding — 2026-09-23

Four sources are enabled across two batches; NUS IMS is retained disabled pending access repair.

| Source | Official entry | Result |
| --- | --- | --- |
| ICTS Schools, India | https://www.icts.res.in/programs/upcoming | New registry-controlled `icts_schools` collector; two school records |
| AstroAI Asian Network | https://cd3.ipmu.jp/a3n_Aug2026/ | Official Kavli IPMU edition page; one school in Taipei |
| NUS IMS Schools, Singapore — disabled | https://ims.nus.edu.sg/events/ | Rendered catalogue works, tested detail page returns an Incapsula challenge |

The ICTS collector follows at most twenty same-host `/program/` links from programme cards whose titles explicitly say school. Generic meetings, organizer proposal calls and admissions links are not selected. Missing catalogue structure raises an error, while a valid catalogue without school cards may legitimately produce zero records. Detail extraction uses only `article.programs`: the global admissions navigation otherwise caused the generic exclusion check to reject real schools. Each detail failure is reported through collector health. Dates, deadlines and eligibility remain programme-specific; limited travel support for participants from India retains that restriction. No broader opportunity vocabulary was introduced.

Live results: the Second ICTS-ICTP Advanced School and Conference on Quantum Matter runs 7–18 December 2026, with a 1 September deadline; Winter School on Biological Physics runs 21 December 2026–1 January 2027, with a 31 August deadline. Both are already closed to applications. AstroAI runs 24–28 August 2026 in Taipei, with a 1 June deadline, and has ended. Its limited support prioritizes junior researchers from Asian institutes. The AstroAI page uses the research centre's generic document title, so an edition-scoped adapter supplies the actual school identity and labelled venue. The edition URL requires annual review; its explicit programme key preserves recurring identity.

NUS ordinary HTTP returned empty content. Browser rendering recovered three school links, but the tested 2027 spring-school detail returned an access challenge. This source is disabled rather than counted as working coverage. ASIAA's broad catalogue was not enabled because it also contains old school links and internships; it supplied the official reference to the current AstroAI school. RIKEN's combined internship/lecture programme was deferred pending separate treatment of its five teaching days across a seven-day window. Existing OIST OCNC was not duplicated; its official unit page says the 2026 course is cancelled for venue renovation.

Live replay: local `logs/asia-onboarding-2026-09-23.json`, three candidates and no collection errors for the enabled entries. No new recommendations are implied. Production snapshots and deployment were not changed by onboarding.

## Second batch

- [VIASM-IAMP Probability and Mathematical Physics School](https://www.viasm.edu.vn/en/hdkh/VIASM-IAMP-PMP-27), Hanoi: 23–28 July 2027; general registration deadline 1 July 2027; explicitly free registration. Free registration is not a claim that travel or accommodation is funded. Extraction is scoped to `.box-about` to remove PhD navigation, and the labelled venue is kept separate from subsequent prose. The edition-specific URL requires annual review.
- [J-PARC Neutron and Muon School 2026](https://conference-indico.kek.jp/event/378/), Tokai: 9–13 November 2026. Registry-controlled `neutron_japan` joins the official About and Application pages. The extended deadline is 30 September, with possible early closure at capacity; the old 31 August date remains on the page and must not win. Fee JPY 40,000; meals and accommodation require no extra payment. The school is taught in Japanese in 2026. Radiation-worker registration and associated medical/training conditions are preserved in eligibility. Domestic travel assistance is conditional and restricted to the named student/academic categories; international flights are not promised. Required evidence changes fail collection rather than silently using obsolete values. Review the edition URLs and collector each year.

Both candidates pass current deterministic hard filters in local replay (`logs/asia-expansion-2026-09-23.json`). This is not a production publication: a gated full scan and final audit still precede snapshot replacement. VIASM's GAB2026 winter-school detail was investigated but not added because its date field is empty; ISSP and APCTP search results did not provide a comparably verified additional school in this batch.
