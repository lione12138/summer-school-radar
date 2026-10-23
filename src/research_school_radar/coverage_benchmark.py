"""Replay real coverage captures at a fixed date, without HTTP or model calls."""
import argparse
from contextlib import ExitStack
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from .candidate_io import candidate_to_dict
from .cli import _load_sources
from .filter import apply_hard_filters
from .models import Page, Source
from .parse import candidate_links
from .programme_evidence import extract_with_programme_evidence
from .publication import is_display_candidate, is_verified_self_funded
from .utils import load_yaml


def evaluate(path=Path("benchmarks/coverage-2026-10.json")):
    gold = json.loads(path.read_text(encoding="utf-8"))
    captures = {row["id"]: row for row in json.loads((path.parent / gold["captures"]).read_text(encoding="utf-8"))}
    sources = {source.name: source for source in _load_sources(Path("config/sources.yaml"))}
    profile = load_yaml(Path("config/profile.yaml"))
    reference = date.fromisoformat(gold["as_of"])

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return reference

    def page(capture_id, source):
        capture = captures[capture_id]
        html = (path.parent / capture["html"]).read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else source.name
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        if capture["url"] != source.url:
            source = replace(source, url=capture["url"], notes="Linked from " + source.url)
        return Page(capture["url"], title, soup.get_text(" ", strip=True), html, source, reference)

    results = []
    with ExitStack() as stack:
        for module in ("extract", "filter", "models", "date_extraction"):
            stack.enter_context(patch(f"research_school_radar.{module}.date", FrozenDate))
        for case in gold["cases"]:
            source = sources[case["source"]]
            candidates = extract_with_programme_evidence([page(key, source) for key in case["pages"]], profile)
            candidate = apply_hard_filters(candidates[0], profile) if len(candidates) == 1 else None
            actual = candidate_to_dict(candidate) if candidate else {}
            field_errors = [key for key, value in case["fields"].items() if actual.get(key) != value]
            for key, value in case.get("contains", {}).items():
                if value not in str(actual.get(key, "")):
                    field_errors.append(key)
            published = bool(candidate and is_display_candidate(candidate))
            results.append({"id": case["id"], "found": candidate is not None,
                            "fields_correct": not field_errors, "field_errors": field_errors,
                            "published": published, "expected_publish": case["expected_publish"],
                            "self_funded": bool(candidate and is_verified_self_funded(candidate))})
        links = []
        for case in gold["links"]:
            capture = captures[case["capture"]]
            source = Source(case["id"], capture["url"], "1", "global", "research_institute")
            found = candidate_links(page(case["capture"], source), limit=8)
            links.append({"id": case["id"], "found": case["target"] in found})
    return {"as_of": gold["as_of"], "cases": len(results), "found": sum(r["found"] for r in results),
            "fields_correct": sum(r["fields_correct"] for r in results),
            "correctly_published": sum(r["published"] and r["expected_publish"] for r in results),
            "false_positives": sum(r["published"] and not r["expected_publish"] for r in results),
            "results": results, "link_discovery": links,
            "limits": "Fixture extraction/publication only. Princeton requires live evidence audit; ICTP detail fetch not captured."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate()
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
