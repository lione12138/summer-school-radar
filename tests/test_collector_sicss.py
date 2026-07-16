from datetime import date

from research_school_radar.collector_sicss import _candidates_from_html


PROFILE = {
    "preferred_topics": [
        "computational social science",
        "social science methods",
        "data analysis",
    ],
    "region_priority": ["global"],
}


def test_sicss_listing_creates_separate_upcoming_location_records() -> None:
    html = """
    <div class="card">
      <h5 class="card-title">Past</h5>
      <h6 class="card-subtitle">Past City</h6>
      <p class="card-text">June 1 to June 5, 2026</p>
      <a href="/2026/past">Learn More</a><a href="/2026/past/apply">Apply</a>
    </div>
    <div class="card">
      <h5 class="card-title">Stanford</h5>
      <h6 class="card-subtitle">Stanford University</h6>
      <p class="card-text">August 10 to August 21, 2026</p>
      <a href="/2026/stanford">Learn More</a><a href="/2026/stanford/apply">Apply</a>
    </div>
    <div class="card">
      <h5 class="card-title">WITS-StAndrews</h5>
      <h6 class="card-subtitle">Johannesburg, South Africa</h6>
      <p class="card-text">17–21 August, 2026</p>
      <a href="/2026/wits-standrews">Learn More</a>
      <a href="/2026/wits-standrews/apply">Apply</a>
    </div>
    """

    candidates = _candidates_from_html(html, PROFILE, as_of=date(2026, 7, 16))

    assert [candidate.title for candidate in candidates] == [
        "SICSS-Stanford",
        "SICSS-WITS-StAndrews",
    ]
    assert candidates[0].application_link == "https://new.sicss.io/2026/stanford/apply"
    assert candidates[0].fee_eur == 0.0
    assert candidates[0].funding_available is True
    assert candidates[0].identity_key == "sicss:2026:stanford"
    assert candidates[1].start_date == date(2026, 8, 17)
    assert candidates[1].end_date == date(2026, 8, 21)
    assert candidates[1].duration_days == 5
