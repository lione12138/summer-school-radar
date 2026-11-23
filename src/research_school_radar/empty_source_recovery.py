"""Bounded same-host search for repeatedly empty official sources."""
from datetime import date
from urllib.parse import urlsplit
from .site_freshness import source_health_by_name

def recovery_queries(sources, manifest, *, today=None, limit=4):
    year = (today or date.today()).year + 1
    health = source_health_by_name(manifest)
    eligible = [s for s in sources if s.enabled and str(s.layer) in {"1", "1.5", "2"}
                and int(health.get(s.name, {}).get("consecutive_empty_scans", 0)) >= 3]
    eligible.sort(key=lambda s: (-int(health[s.name].get("consecutive_empty_scans", 0)), s.name))
    # Rotate the bounded batch daily so a long empty list does not starve sources.
    if eligible:
        offset = (today or date.today()).toordinal() % len(eligible)
        eligible = eligible[offset:] + eligible[:offset]
    return [(s, f'site:{urlsplit(s.url).hostname} {year} ("summer school" OR "summer training" OR "summer research programme")')
            for s in eligible[:limit] if urlsplit(s.url).hostname]

def same_host_results(source, results):
    host = (urlsplit(source.url).hostname or "").removeprefix("www.")
    return [r for r in results if (urlsplit(r.url).hostname or "").removeprefix("www.") == host]
