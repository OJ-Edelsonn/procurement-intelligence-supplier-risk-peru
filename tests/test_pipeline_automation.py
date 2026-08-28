from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from procurement_intelligence.automation.run_pipeline import (
    PipelineExecutionError,
    _sanitize_argument,
    _sanitize_output,
    load_pipeline_config,
    run_pipeline,
)


def _config(tmp_path: Path, status: str = "PASS") -> Path:
    artifact = tmp_path / "artifact.json"
    artifact.write_text(
        json.dumps({"summary": {"status": status}}), encoding="utf-8"
    )
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATA_ROOT={tmp_path.as_posix()}\n", encoding="utf-8")
    config = {
        "pipeline": {
            "schema_version": "1.0",
            "pipeline_id": "test",
            "report": "reports/run.json",
            "source": {
                "source_id": "test_source",
                "source_period": "2026-07",
                "snapshot_date": "2026-08-19",
                "year": 2026,
                "month": 7,
                "paths": {},
            },
        },
        "steps": [
            {
                "id": "check",
                "stage": "test",
                "module": "example.module",
                "arguments": [],
                "artifact": artifact.as_posix(),
                "status_path": "summary.status",
                "accepted_statuses": ["PASS"],
                "reuse_if_valid": True,
            }
        ],
    }
    path = tmp_path / "config" / "pipeline.yml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def test_repository_pipeline_contract_is_valid() -> None:
    config = load_pipeline_config(Path("config/pipeline.yml"))
    assert len(config["steps"]) == 14
    assert config["steps"][-1]["optional_group"] == "powerbi"
    assert "--overwrite" in config["steps"][4]["arguments"]


def test_pipeline_reuses_accepted_artifact(tmp_path: Path) -> None:
    config = _config(tmp_path)
    report = run_pipeline(config, tmp_path / ".env")
    assert report["summary"]["status"] == "PASS"
    assert report["summary"]["steps_reused"] == 1
    assert report["steps"][0]["outcome"] == "REUSED_VALIDATED_ARTIFACT"


def test_force_executes_step_and_records_timing(tmp_path: Path) -> None:
    config = _config(tmp_path)

    def runner(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args[0], 0, "completed\n", "")

    report = run_pipeline(config, tmp_path / ".env", force=True, runner=runner)
    assert report["summary"]["steps_executed"] == 1
    assert report["steps"][0]["outcome"] == "PASS"
    assert report["steps"][0]["stdout_tail"] == "completed"


def test_unacceptable_artifact_blocks_pipeline(tmp_path: Path) -> None:
    config = _config(tmp_path, status="FAIL")

    def runner(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args[0], 0, "", "")

    with pytest.raises(PipelineExecutionError, match="unacceptable artifact"):
        run_pipeline(config, tmp_path / ".env", runner=runner)
    report = json.loads((tmp_path / "reports" / "run.json").read_text())
    assert report["summary"]["status"] == "FAIL"
    assert report["summary"]["steps_failed"] == 1


def test_pipeline_dry_run_never_calls_runner(tmp_path: Path) -> None:
    config = _config(tmp_path)

    def runner(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("runner must not be called")

    report = run_pipeline(
        config, tmp_path / ".env", force=True, dry_run=True, runner=runner
    )
    assert report["summary"]["status"] == "DRY_RUN"
    assert report["steps"][0]["outcome"] == "DRY_RUN"


def test_duplicate_step_ids_are_rejected(tmp_path: Path) -> None:
    path = _config(tmp_path)
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["steps"].append(dict(config["steps"][0]))
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate pipeline step id"):
        load_pipeline_config(path)


def test_local_paths_are_sanitized_even_when_target_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "project"
    data_root = tmp_path / "private-data"
    missing = data_root / "raw" / "missing.zip"
    assert _sanitize_argument(str(missing), root, data_root) == (
        "${DATA_ROOT}/raw/missing.zip"
    )
    output = f"failed reading {missing} from {root}"
    sanitized = _sanitize_output(output, root, data_root)
    assert str(tmp_path) not in sanitized
    assert "${DATA_ROOT}" in sanitized
    assert "${PROJECT_ROOT}" in sanitized
