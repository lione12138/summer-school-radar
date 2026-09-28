import json
from pathlib import Path

from research_school_radar.benchmark import evaluate
from research_school_radar.utils import load_yaml


def test_fixed_date_gold_benchmark_does_not_regress():
    current = evaluate(Path("benchmarks/gold.json"), load_yaml(Path("config/profile.yaml")))
    baseline = json.loads(Path("benchmarks/baseline.json").read_text(encoding="utf-8"))
    assert current["cases"] >= 30
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
