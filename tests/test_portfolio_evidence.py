from __future__ import annotations

import json
from pathlib import Path


def test_public_portfolio_metrics_match_governed_evidence() -> None:
    benchmark = json.loads(
        Path("reports/benchmark/phase16_benchmark.json").read_text(encoding="utf-8")
    )
    metrics = {item["metric_id"]: item["value"] for item in benchmark["outcome_metrics"]}
    assert metrics["raw_rows"] == 231123
    assert metrics["raw_tables"] == 22
    assert metrics["modeled_objects"] == 16
    assert metrics["published_kpis"] == 21
    assert metrics["tender_amount_pen"] == 6924924015.38
    assert metrics["markets_analyzed"] == 772
    assert metrics["eligible_markets"] == 87
    assert metrics["suppliers_scored"] == 179
    assert benchmark["summary"]["time_savings_claimed"] is False
