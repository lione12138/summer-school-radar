from __future__ import annotations

from datetime import date
from pathlib import Path

from research_school_radar.cli import _load_curated_opportunities, _load_sources, collect_linked_opportunity_pages
from research_school_radar.models import Page, Source


PROFILE = {
    "preferred_topics": ["hydrology", "climate extremes", "water resources", "remote sensing"],
    "hard_filters": {
        "minimum_duration_days": 8,
        "require_funding_or_low_fee": True,
        "allow_online_only": False,
        "require_open_deadline": True,
    },
    "financial_access": {
        "maximum_unfunded_fee_eur": 400,
        "approximate_currency_to_eur": {
            "EUR": 1.0,
            "USD": 0.95,
            "GBP": 1.2,
        },
    },
    "priority_regions": ["continental Europe"],
    "supplementary_regions": ["North America"],
}


def _page(text: str, *, html: str = "", title: str = "Test School") -> Page:
    source = Source(
        name="Example Source",
        url="https://example.org/school",
        layer="1",
        region="continental Europe",
        source_type="research_institute",
    )
    return Page(
        url=source.url,
        title=title,
        text=text,
        html=html,
        source=source,
        fetched_at=date.today(),
    )


def test_collect_linked_pages_follows_only_opportunity_pages(monkeypatch) -> None:
    source = Source(
        name="Example Source",
        url="https://example.org/events",
        layer="1",
        region="continental Europe",
        source_type="research_network",
    )
    index_page = Page(
        url=source.url,
        title="Events",
        text="Events",
        html='<a href="/school">Hydrology summer school application deadline and travel grant</a>',
        source=source,
        fetched_at=date.today(),
    )

    def fake_fetch(linked_source: Source) -> Page:
        return Page(
            url=linked_source.url,
            title="Hydrology Summer School",
            text=(
                "Hydrology summer school. Application deadline: 15 October 2027. "
                "Travel grants are available. Dates: 1 July 2027 to 12 July 2027."
            ),
            html="",
            source=linked_source,
            fetched_at=date.today(),
        )

    monkeypatch.setattr("research_school_radar.cli.fetch_source", fake_fetch)
    pages, errors = collect_linked_opportunity_pages([index_page], max_links_per_source=3)
    assert not errors
    assert len(pages) == 1
    assert pages[0].url == "https://example.org/school"


def test_meta_refresh_landing_page_is_followed() -> None:
    import responses as responses_lib

    from research_school_radar.collect import fetch_source

    landing = (
        '<html><head><meta http-equiv="refresh" content="0; url=https://example.org/2026/">'
        "</head><body>redirecting</body></html>"
    )
    real = "<html><head><title>ML Summer School 2026</title></head><body>The school runs in July.</body></html>"
    source = Source(name="MetaSchool", url="https://example.org/", layer="2", region="global", source_type="x")

    @responses_lib.activate
    def run():
        responses_lib.add(responses_lib.GET, "https://example.org/", body=landing, status=200)
        responses_lib.add(responses_lib.GET, "https://example.org/2026/", body=real, status=200)
        return fetch_source(source)

    page = run()
    assert page.url == "https://example.org/2026/"
    assert "ML Summer School 2026" in page.title


def test_failing_source_does_not_abort_collection() -> None:
    from research_school_radar import collect as collect_module

    def boom(source):
        raise RuntimeError("render timeout")

    original = collect_module.fetch_source
    collect_module.fetch_source = boom
    try:
        source = Source(name="Flaky", url="https://example.org/x", layer="1", region="global", source_type="x")
        pages, errors = collect_module.collect_sources([source])
    finally:
        collect_module.fetch_source = original
    assert pages == []
    assert len(errors) == 1
    assert "Flaky" in errors[0] and "render timeout" in errors[0]


def test_render_flag_is_loaded_from_sources() -> None:
    sources = _load_sources(Path("config/sources.yaml"))
    cern = next((s for s in sources if s.name == "CERN Academic Training"), None)
    assert cern is not None
    assert cern.render is True
    # Sources without the flag default to plain requests.
    plain = next((s for s in sources if s.name == "EGU Training Schools"), None)
    assert plain is not None
    assert plain.render is False


def test_render_fetch_falls_back_when_playwright_missing(monkeypatch) -> None:
    import research_school_radar.collect as collect_module

    captured = {}

    class _Resp:
        url = "https://example.org/rendered"
        text = "<html><title>Plain</title><body>fallback</body></html>"

        def raise_for_status(self) -> None:
            pass

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr("research_school_radar.render.render_available", lambda: False)
    monkeypatch.setattr(collect_module.requests, "get", fake_get)
    source = Source(
        name="Rendered Source",
        url="https://example.org/rendered",
        layer="1",
        region="global",
        source_type="x",
        render=True,
    )
    page = collect_module.fetch_source(source)
    assert captured["url"] == "https://example.org/rendered"
    assert "fallback" in page.text


def test_disabled_sources_are_not_loaded() -> None:
    sources = _load_sources(Path("config/sources.yaml"))
    names = {source.name for source in sources}
    assert "IIASA" not in names


def test_dedicated_collectors_use_the_same_enabled_source_registry() -> None:
    sources = _load_sources(Path("config/sources.yaml"))
    collectors = {source.name: source.collector for source in sources if source.collector}

    assert collectors == {
        "ELLIS": "ellis",
        "IHE Delft": "ihe_delft",
        "SICSS": "sicss",
        "SIB Training": "sib_training",
    }


def test_computing_and_ai_source_expansion_is_enabled() -> None:
    sources = _load_sources(Path("config/sources.yaml"))
    by_name = {source.name: source for source in sources}
    expected = {
        "IEEE RAS Technical Education Programs",
        "IEEE RAS Cognitive Robotics Summer School",
        "EurAI ESSAI",
        "ESSIR",
        "NLDL Winter School",
        "Prob_AI Hub Winter School",
        "Exeter Machine Learning Summer School",
        "UNICRI AI Ethics Winter School",
    }

    assert expected <= by_name.keys()
    assert all(by_name[name].url.startswith("https://") for name in expected)


def test_social_science_and_linguistics_source_expansion_is_enabled() -> None:
    sources = _load_sources(Path("config/sources.yaml"))
    by_name = {source.name: source for source in sources}
    expected = {
        "SICSS",
        "Summer School in Social Sciences Methods",
        "Oxford Spring School",
        "CoLang",
        "CreteLing",
        "Advanced Language Processing Winter School",
        "Charles University Summer School of Linguistics",
        "Methods in Language Sciences",
        "Edinburgh Theoretical Historical Linguistics",
    }

    assert expected <= by_name.keys()
    assert all(by_name[name].url.startswith("https://") for name in expected)


def test_curated_opportunities_loader_reads_yaml(tmp_path) -> None:
    path = tmp_path / "opportunities.yml"
    path.write_text(
        "opportunities:\n"
        "  - title: Curated Hydrology School\n"
        "    organizer: Trusted Institute\n",
        encoding="utf-8",
    )
    opportunities = _load_curated_opportunities(path)
    assert opportunities == [{"title": "Curated Hydrology School", "organizer": "Trusted Institute"}]


def test_collect_sources_keeps_order_and_reports_errors(monkeypatch) -> None:
    from research_school_radar import collect

    sources = [
        Source(name="One", url="https://example.org/one", layer="1", region="global", source_type="test"),
        Source(name="Two", url="https://example.org/two", layer="1", region="global", source_type="test"),
        Source(name="Bad", url="https://example.org/bad", layer="1", region="global", source_type="test"),
    ]

    def fake_fetch(source: Source) -> Page:
        if source.name == "Bad":
            raise RuntimeError("boom")
        return Page(
            url=source.url,
            title=source.name,
            text="Summer school. Application deadline: 1 March 2027.",
            html="",
            source=source,
            fetched_at=date.today(),
        )

    monkeypatch.setattr(collect, "fetch_source", fake_fetch)
    pages, errors = collect.collect_sources(sources, max_workers=3)
    assert [page.title for page in pages] == ["One", "Two"]
    assert errors == ["Bad: boom"]


def test_collect_linked_opportunity_pages_keeps_order_and_filters(monkeypatch) -> None:
    import research_school_radar.cli as cli

    source = Source(name="Listing", url="https://example.org", layer="1", region="global", source_type="test")
    listing = Page(
        url="https://example.org",
        title="Listing",
        text="Summer schools. Application information.",
        html=(
            '<a href="/a">Hydrology summer school apply</a>'
            '<a href="/b">Climate training school application</a>'
            '<a href="/c">Archive</a>'
        ),
        source=source,
        fetched_at=date.today(),
    )

    def fake_fetch(linked_source: Source) -> Page:
        text = {
            "https://example.org/a": "Hydrology summer school. Application deadline: 1 March 2027.",
            "https://example.org/b": "Plain event listing without apply signal.",
        }[linked_source.url]
        return Page(
            url=linked_source.url,
            title=linked_source.url.rsplit("/", 1)[-1],
            text=text,
            html="",
            source=linked_source,
            fetched_at=date.today(),
        )

    monkeypatch.setattr(cli, "fetch_source", fake_fetch)
    pages, errors = cli.collect_linked_opportunity_pages([listing], max_links_per_source=5, max_workers=2)
    assert errors == []
    assert [page.url for page in pages] == ["https://example.org/a"]


def test_fetch_source_uses_etag_cache_on_not_modified(tmp_path) -> None:
    import responses as responses_lib

    from research_school_radar.collect import fetch_source
    from research_school_radar.http_cache import HttpCache

    source = Source(name="Cached", url="https://example.org/cached", layer="1", region="global", source_type="test")
    cache = HttpCache(tmp_path / "http_cache")

    @responses_lib.activate
    def first_fetch():
        responses_lib.add(
            responses_lib.GET,
            source.url,
            body="<html><head><title>Cached School</title></head><body>Summer school first body</body></html>",
            status=200,
            headers={"ETag": '"v1"', "Last-Modified": "Wed, 01 Jul 2026 10:00:00 GMT"},
            content_type="text/html",
        )
        return fetch_source(source, http_cache=cache)

    first = first_fetch()
    assert "first body" in first.text

    seen_headers: dict[str, str] = {}

    @responses_lib.activate
    def second_fetch():
        def callback(request):  # noqa: ANN001, ANN202 - responses callback.
            seen_headers.update(request.headers)
            return (304, {}, "")

        responses_lib.add_callback(responses_lib.GET, source.url, callback=callback)
        return fetch_source(source, http_cache=cache)

    second = second_fetch()
    assert "first body" in second.text
    assert second.title == "Cached School"
    assert seen_headers["If-None-Match"] == '"v1"'
    assert seen_headers["If-Modified-Since"] == "Wed, 01 Jul 2026 10:00:00 GMT"
    assert cache.stats == {"requests": 2, "hits_304": 1, "stale_fallbacks": 0, "stores": 1}


def test_http_cache_refresh_bypasses_conditional_headers(tmp_path) -> None:
    import responses as responses_lib

    from research_school_radar.collect import fetch_source
    from research_school_radar.http_cache import HttpCache

    source = Source(name="Cached", url="https://example.org/refresh", layer="1", region="global", source_type="test")
    cache_dir = tmp_path / "http_cache"

    @responses_lib.activate
    def seed_cache():
        responses_lib.add(
            responses_lib.GET,
            source.url,
            body="<html><title>Old</title><body>old body</body></html>",
            status=200,
            headers={"ETag": '"old"'},
        )
        fetch_source(source, http_cache=HttpCache(cache_dir))

    seed_cache()
    seen_headers: dict[str, str] = {}

    @responses_lib.activate
    def refresh_fetch():
        def callback(request):  # noqa: ANN001, ANN202 - responses callback.
            seen_headers.update(request.headers)
            return (200, {"ETag": '"new"'}, "<html><title>New</title><body>new body</body></html>")

        responses_lib.add_callback(responses_lib.GET, source.url, callback=callback)
        return fetch_source(source, http_cache=HttpCache(cache_dir, refresh=True))

    refreshed = refresh_fetch()
    assert "new body" in refreshed.text
    assert "If-None-Match" not in seen_headers



def test_http_cache_prune_removes_only_stale_entries(tmp_path) -> None:
    import os
    import time

    from research_school_radar.http_cache import HttpCache

    cache = HttpCache(tmp_path)
    cache.directory.mkdir(parents=True, exist_ok=True)
    fresh = cache._path("https://example.org/fresh")
    stale = cache._path("https://example.org/stale")
    fresh.write_text("{}", encoding="utf-8")
    stale.write_text("{}", encoding="utf-8")
    # Age the stale entry past the cutoff via mtime (prune keys off mtime, and
    # a 304 hit refreshes mtime through touch()).
    old = time.time() - 60 * 86400
    os.utime(stale, (old, old))

    removed = cache.prune(max_age_days=45)

    assert removed == 1
    assert fresh.exists()
    assert not stale.exists()

    # touch() rescues an entry from pruning.
    os.utime(fresh, (old, old))
    cache.touch("https://example.org/fresh")
    assert cache.prune(max_age_days=45) == 0
    assert fresh.exists()


def test_http_cache_uses_recent_body_after_connection_error(tmp_path) -> None:
    import requests
    import responses as responses_lib

    from research_school_radar.collect import fetch_source
    from research_school_radar.http_cache import HttpCache

    source = Source(name="Cached", url="https://example.org/flaky", layer="1", region="global", source_type="test")
    cache = HttpCache(tmp_path / "http_cache", stale_if_error_max_age_days=14)

    @responses_lib.activate
    def seed_cache() -> None:
        responses_lib.add(
            responses_lib.GET,
            source.url,
            body="<html><title>Resilient</title><body>last known good body</body></html>",
            status=200,
            headers={"ETag": '"good"'},
        )
        fetch_source(source, http_cache=cache)

    seed_cache()
    cache_mtime = cache._path(source.url).stat().st_mtime

    @responses_lib.activate
    def fetch_during_outage():
        responses_lib.add(responses_lib.GET, source.url, body=requests.ConnectionError("offline"))
        return fetch_source(source, http_cache=cache)

    page = fetch_during_outage()

    assert "last known good body" in page.text
    assert cache.warning_records[-1]["event"] == "http_cache_stale_if_error"
    assert cache.warning_records[-1]["reason"] == "exception:ConnectionError"
    assert cache.warning_records[-1]["url"] == source.url
    assert cache.stats["stale_fallbacks"] == 1
    assert cache._path(source.url).stat().st_mtime == cache_mtime


def test_http_cache_uses_recent_body_for_429_and_5xx(tmp_path) -> None:
    import responses as responses_lib

    from research_school_radar.collect import fetch_source
    from research_school_radar.http_cache import HttpCache

    for status in (429, 503):
        source = Source(
            name=f"Cached {status}",
            url=f"https://example.org/flaky-{status}",
            layer="1",
            region="global",
            source_type="test",
        )
        cache = HttpCache(tmp_path / f"http_cache_{status}")

        @responses_lib.activate
        def seed_cache() -> None:
            responses_lib.add(
                responses_lib.GET,
                source.url,
                body=f"<html><title>Cached {status}</title><body>good {status}</body></html>",
                status=200,
            )
            fetch_source(source, http_cache=cache)

        seed_cache()

        @responses_lib.activate
        def fetch_transient_failure():
            responses_lib.add(responses_lib.GET, source.url, body="temporary failure", status=status)
            return fetch_source(source, http_cache=cache)

        page = fetch_transient_failure()

        assert f"good {status}" in page.text
        assert cache.warning_records[-1]["reason"] == f"http:{status}"


def test_http_cache_does_not_hide_explicit_client_error(tmp_path) -> None:
    import requests
    import responses as responses_lib

    from research_school_radar.collect import fetch_source
    from research_school_radar.http_cache import HttpCache

    source = Source(name="Removed", url="https://example.org/removed", layer="1", region="global", source_type="test")
    cache = HttpCache(tmp_path / "http_cache")

    @responses_lib.activate
    def seed_cache() -> None:
        responses_lib.add(responses_lib.GET, source.url, body="<html><body>old body</body></html>", status=200)
        fetch_source(source, http_cache=cache)

    seed_cache()

    @responses_lib.activate
    def fetch_removed() -> None:
        responses_lib.add(responses_lib.GET, source.url, body="not found", status=404)
        fetch_source(source, http_cache=cache)

    try:
        fetch_removed()
    except requests.HTTPError as exc:
        assert exc.response is not None
        assert exc.response.status_code == 404
    else:
        raise AssertionError("404 must not fall back to cached content")
    assert cache.warning_records == []


def test_http_cache_rejects_body_older_than_stale_if_error_window(tmp_path) -> None:
    import os
    import time

    import requests
    import responses as responses_lib

    from research_school_radar.collect import fetch_source
    from research_school_radar.http_cache import HttpCache

    source = Source(name="Expired", url="https://example.org/expired", layer="1", region="global", source_type="test")
    cache = HttpCache(tmp_path / "http_cache", stale_if_error_max_age_days=7)

    @responses_lib.activate
    def seed_cache() -> None:
        responses_lib.add(responses_lib.GET, source.url, body="<html><body>expired body</body></html>", status=200)
        fetch_source(source, http_cache=cache)

    seed_cache()
    expired = time.time() - 8 * 86400
    os.utime(cache._path(source.url), (expired, expired))

    @responses_lib.activate
    def fetch_during_outage() -> None:
        responses_lib.add(responses_lib.GET, source.url, body=requests.Timeout("timeout"))
        fetch_source(source, http_cache=cache)

    try:
        fetch_during_outage()
    except requests.Timeout:
        pass
    else:
        raise AssertionError("expired cache entry must not hide the request failure")
    assert cache.warning_records[-1]["event"] == "http_cache_stale_rejected"
    assert cache.warning_records[-1]["age_seconds"] > cache.warning_records[-1]["max_age_seconds"]
