from __future__ import annotations

import json

import responses

from research_school_radar.collector_sib import _SIB_TRAINING_URL, _sib_training


PROFILE = {
    "preferred_topics": ["data science", "statistics", "machine learning", "bioinformatics"],
    "priority_regions": ["continental Europe"],
    "hard_filters": {"minimum_duration_days": 5},
    "financial_access": {"approximate_currency_to_eur": {"CHF": 1.04}},
}


@responses.activate
def test_sib_collector_reads_bioschemas_and_keeps_qualifying_course_instances() -> None:
    payload = {
        "@context": "https://schema.org",
        "@type": "Course",
        "name": "Research Data Science",
        "abstract": "Hands-on data science and statistics training for PhD researchers.",
        "educationalLevel": "Advanced",
        "hasCourseInstance": [
            {
                "@type": "CourseInstance",
                "name": "Research Data Science",
                "startDate": "2027-06-14",
                "endDate": "2027-06-18",
                "courseMode": ["onsite", "synchronous"],
                "location": {
                    "@type": "Place",
                    "address": {
                        "@type": "PostalAddress",
                        "addressLocality": "Lausanne",
                        "addressCountry": "Switzerland",
                    },
                },
                "url": "https://www.sib.swiss/training/course/20270614_RDS",
                "offers": [
                    {
                        "@type": "Offer",
                        "name": "Academic Price",
                        "price": 300,
                        "priceCurrency": "CHF",
                    }
                ],
            },
            {
                "@type": "CourseInstance",
                "name": "Short R introduction",
                "startDate": "2027-05-01",
                "endDate": "2027-05-03",
                "courseMode": ["onsite"],
                "url": "https://www.sib.swiss/training/course/20270501_R",
            },
        ],
    }
    responses.add(
        responses.GET,
        _SIB_TRAINING_URL,
        body=f'<html><script type="application/ld+json">{json.dumps(payload)}</script></html>',
        status=200,
    )

    candidates, errors = _sib_training(PROFILE)

    assert errors == []
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Research Data Science"
    assert candidate.duration_days == 5
    assert candidate.location == "Lausanne, Switzerland"
    assert candidate.mode == "in-person"
    assert candidate.fee_eur == 312
    assert candidate.identity_key.startswith("sib:https://www.sib.swiss/")
