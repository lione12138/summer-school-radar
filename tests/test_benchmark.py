import json
from pathlib import Path

from research_school_radar.benchmark import evaluate, evaluate_discovery
from research_school_radar.utils import load_yaml


def test_fixed_date_gold_benchmark_does_not_regress():
    current = evaluate(Path("benchmarks/gold.json"), load_yaml(Path("config/profile.yaml")))
    baseline = json.loads(Path("benchmarks/baseline.json").read_text(encoding="utf-8"))
    assert current["cases"] >= 30
    assert current['field_errors'] == 0, [r for r in current['results'] if r['field_errors']]
    assert current["false_positives"] <= baseline["false_positives"]
    assert current["found"] >= baseline["found"]
    assert current["correctly_published"] >= baseline["correctly_published"]
    prior = {item["id"]: item for item in baseline["results"]}
    for item in current["results"]:
        old = prior[item["id"]]
        if old["found"] and old["expected_found"]:
            assert item["found"], item["id"]
        if old["published"] and old["expected_publish"]:
            assert item["published"], item["id"]


def test_discovery_coverage_distinguishes_search_and_prefilter_losses(tmp_path):
    gold = tmp_path / "gold.json"
    captured = tmp_path / "capture.json"
    gold.write_text(json.dumps({"as_of": "2026-09-28", "cases": [
        {"kind": "official_capture", "expected_publish": True, "url": f"https://example.edu/{name}"}
        for name in ("a", "b", "c")]}))
    captured.write_text(json.dumps({"results": [{"url": "https://example.edu/a"}, {"url": "https://example.edu/b"}],
                                    "accepted_urls": ["https://example.edu/a"]}))
    result = evaluate_discovery(gold, captured)
    assert result["known_eligible_urls"] == 3
    assert result["search_found"] == 2 and result["prefilter_retained"] == 1
    assert result["missing_urls"] == ["https://example.edu/c"]
