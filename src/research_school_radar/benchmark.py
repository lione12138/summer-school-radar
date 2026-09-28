"""Offline, fixed-date extraction/publication benchmark; no search or LLM calls."""
import argparse
from contextlib import ExitStack
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from .extract import extract_candidate
from .filter import apply_hard_filters
from .models import Page, Source
from .publication import is_display_candidate
from .utils import load_yaml


def evaluate(gold_path: Path, profile: dict) -> dict:
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    reference = date.fromisoformat(gold["as_of"])

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return reference

    results = []
    with ExitStack() as stack:
        for module in ("extract", "filter", "models", "date_extraction"):
            stack.enter_context(patch(f"research_school_radar.{module}.date", FrozenDate))
        for case in gold["cases"]:
            html = (gold_path.parent / case["html"]).read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            for node in soup(["script", "style", "noscript"]):
                node.decompose()
            source = Source(case["title"], case["url"], case["source_layer"], "global", "research_training_provider")
            page = Page(case["url"], soup.title.get_text(" ", strip=True) if soup.title else case["title"],
                        soup.get_text(" ", strip=True), html, source, reference)
            c = extract_candidate(page, profile, as_of=reference)
            published = is_display_candidate(apply_hard_filters(c, profile)) if c else False
            results.append({"id": case["id"], "found": c is not None, "published": published,
                            "expected_found": case["expected_found"], "expected_publish": case["expected_publish"],
                            "kind": case["kind"]})
    expected = sum(r["expected_publish"] for r in results)
    tp = sum(r["published"] and r["expected_publish"] for r in results)
    fp = sum(r["published"] and not r["expected_publish"] for r in results)
    known = sum(r["expected_found"] for r in results)
    found = sum(r["found"] and r["expected_found"] for r in results)
    return {"as_of": gold["as_of"], "cases": len(results), "known_pages": known,
            "found": found, "extraction_recall": found / known if known else 0,
            "eligible": expected, "correctly_published": tp, "false_positives": fp,
            "publication_precision": tp / (tp + fp) if tp + fp else None,
            "publication_recall": tp / expected if expected else None,
            "misses": [r["id"] for r in results if r["expected_publish"] and not r["published"]],
            "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=Path("benchmarks/gold.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.gold, load_yaml(Path("config/profile.yaml")))
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
