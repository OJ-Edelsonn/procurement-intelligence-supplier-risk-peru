"""Run the governed procurement pipeline with audit evidence and safe reuse."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from procurement_intelligence.settings import load_settings


class PipelineExecutionError(RuntimeError):
    """Raised when a configured pipeline step cannot be accepted."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _nested_value(payload: Mapping[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise KeyError(f"Missing JSON status path: {dotted_path}")
        value = value[part]
    return value


def _atomic_json(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def load_pipeline_config(path: Path) -> dict[str, Any]:
    """Load and validate the orchestration contract."""

    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("Pipeline config must be a YAML mapping.")
    pipeline = config.get("pipeline")
    steps = config.get("steps")
    if not isinstance(pipeline, dict) or not isinstance(steps, list) or not steps:
        raise ValueError("Pipeline config requires pipeline and non-empty steps sections.")
    if str(pipeline.get("schema_version")) != "1.0":
        raise ValueError("Unsupported pipeline schema_version; expected 1.0.")
    identifiers: set[str] = set()
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError(f"Pipeline step {index} must be a mapping.")
        missing = {"id", "stage", "module", "arguments"} - set(step)
        if missing:
            raise ValueError(f"Pipeline step {index} is missing {sorted(missing)}.")
        identifier = str(step["id"])
        if identifier in identifiers:
            raise ValueError(f"Duplicate pipeline step id: {identifier}")
        identifiers.add(identifier)
        if not isinstance(step["arguments"], list):
            raise ValueError(f"Step {identifier} arguments must be a list.")
        accepted = step.get("accepted_statuses", [])
        if accepted and not isinstance(accepted, list):
            raise ValueError(f"Step {identifier} accepted_statuses must be a list.")
        if step.get("status_path") and not step.get("artifact"):
            raise ValueError(f"Step {identifier} status_path requires an artifact.")
    return config


def _context(config: Mapping[str, Any], data_root: Path) -> dict[str, str]:
    pipeline = config["pipeline"]
    source = pipeline["source"]
    context = {
        "data_root": str(data_root),
        "source_period": str(source["source_period"]),
        "snapshot_date": str(source["snapshot_date"]),
        "year": str(source["year"]),
        "month": f"{int(source['month']):02d}",
    }
    for name, value in source.get("paths", {}).items():
        rendered = str(value).format_map(context)
        candidate = Path(rendered)
        if not candidate.is_absolute():
            candidate = data_root / candidate
        context[str(name)] = str(candidate)
    return context


def _render(value: Any, context: Mapping[str, str]) -> str:
    try:
        return str(value).format_map(context)
    except KeyError as error:
        raise ValueError(f"Unknown pipeline placeholder: {error.args[0]}") from error


def _artifact_assessment(
    step: Mapping[str, Any], root: Path, context: Mapping[str, str]
) -> dict[str, Any]:
    configured = step.get("artifact")
    if not configured:
        return {"exists": False, "accepted": False}
    rendered = _render(configured, context)
    artifact = Path(rendered)
    if not artifact.is_absolute():
        artifact = root / artifact
    result: dict[str, Any] = {
        "path": artifact,
        "display_path": _display_path(artifact, root, Path(context["data_root"])),
        "exists": artifact.is_file(),
        "accepted": False,
    }
    if not artifact.is_file():
        return result
    result["sha256"] = _sha256(artifact)
    status_path = step.get("status_path")
    if not status_path:
        result["accepted"] = True
        return result
    try:
        payload = _read_json(artifact)
        status = str(_nested_value(payload, str(status_path)))
        result["status"] = status
        result["accepted"] = status in {str(x) for x in step["accepted_statuses"]}
        allowed_rules = step.get("allowed_failed_rule_ids")
        if allowed_rules is not None:
            failed = {
                str(item["rule_id"])
                for item in payload.get("results", [])
                if item.get("status") != "PASS"
            }
            blocking = {
                str(item["rule_id"])
                for item in payload.get("results", [])
                if item.get("status") != "PASS" and item.get("severity") == "error"
            }
            permitted = {str(item) for item in allowed_rules}
            result["failed_rule_ids"] = sorted(failed)
            result["blocking_rule_ids"] = sorted(blocking)
            result["accepted"] = result["accepted"] and blocking <= permitted
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        result["error"] = str(error)
        result["accepted"] = False
    return result


def _display_path(path: Path, root: Path, data_root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        try:
            suffix = path.resolve().relative_to(data_root.resolve()).as_posix()
            return f"${{DATA_ROOT}}/{suffix}"
        except ValueError:
            return path.name


def _sanitize_argument(value: str, root: Path, data_root: Path) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        return _display_path(candidate, root, data_root)
    if ("/" in value or "\\" in value) and (root / candidate).exists():
        return candidate.as_posix()
    return value


def _sanitize_output(value: str, root: Path, data_root: Path) -> str:
    sanitized = value.replace(str(root.resolve()), "${PROJECT_ROOT}")
    sanitized = sanitized.replace(str(data_root.resolve()), "${DATA_ROOT}")
    return sanitized


def _selected_step_ids(
    steps: Sequence[Mapping[str, Any]], from_step: str | None, to_step: str | None
) -> set[str]:
    identifiers = [str(step["id"]) for step in steps]
    if from_step and from_step not in identifiers:
        raise ValueError(f"Unknown --from-step: {from_step}")
    if to_step and to_step not in identifiers:
        raise ValueError(f"Unknown --to-step: {to_step}")
    start = identifiers.index(from_step) if from_step else 0
    end = identifiers.index(to_step) if to_step else len(identifiers) - 1
    if start > end:
        raise ValueError("--from-step must not occur after --to-step.")
    return set(identifiers[start : end + 1])


def run_pipeline(
    config_path: Path,
    env_file: Path,
    report_path: Path | None = None,
    *,
    include_download: bool = False,
    include_powerbi: bool = False,
    force: bool = False,
    dry_run: bool = False,
    from_step: str | None = None,
    to_step: str | None = None,
    timeout_seconds: int | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Execute selected steps and always emit an auditable run report."""

    started_clock = time.perf_counter()
    started_at = datetime.now(timezone.utc)
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = load_pipeline_config(config_path)
    settings = load_settings(env_file)
    context = _context(config, settings.data_root)
    pipeline = config["pipeline"]
    steps = config["steps"]
    selected = _selected_step_ids(steps, from_step, to_step)
    report_target = report_path or root / str(pipeline["report"])
    if not report_target.is_absolute():
        report_target = root / report_target
    log_directory = root / str(pipeline.get("log_directory", "logs/pipeline"))
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")
    log_path = log_directory / f"{run_id}.log"
    results: list[dict[str, Any]] = []
    failure: str | None = None

    def append_log(message: str) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(message.rstrip() + "\n")

    for order, step in enumerate(steps, 1):
        identifier = str(step["id"])
        optional_group = step.get("optional_group")
        result: dict[str, Any] = {
            "order": order,
            "step_id": identifier,
            "stage": str(step["stage"]),
            "optional_group": optional_group,
        }
        if identifier not in selected:
            result["outcome"] = "NOT_SELECTED"
            results.append(result)
            continue
        if optional_group == "download" and not include_download:
            result["outcome"] = "SKIPPED_OPTIONAL"
            results.append(result)
            continue
        if optional_group == "powerbi" and not include_powerbi:
            result["outcome"] = "SKIPPED_OPTIONAL"
            results.append(result)
            continue

        assessment = _artifact_assessment(step, root, context)
        cacheable = bool(step.get("reuse_if_valid", False))
        if cacheable and assessment.get("accepted") and not force:
            result.update(
                {
                    "outcome": "REUSED_VALIDATED_ARTIFACT",
                    "artifact": assessment.get("display_path"),
                    "artifact_sha256": assessment.get("sha256"),
                    "artifact_status": assessment.get("status"),
                    "duration_seconds": 0.0,
                }
            )
            if assessment.get("failed_rule_ids"):
                result["accepted_failed_rule_ids"] = assessment["failed_rule_ids"]
            results.append(result)
            continue

        command = [
            sys.executable,
            "-m",
            str(step["module"]),
            *[_render(argument, context) for argument in step["arguments"]],
        ]
        result["command"] = [
            "python",
            "-m",
            str(step["module"]),
            *[_sanitize_argument(value, root, settings.data_root) for value in command[3:]],
        ]
        if dry_run:
            result["outcome"] = "DRY_RUN"
            result["duration_seconds"] = 0.0
            results.append(result)
            continue

        step_clock = time.perf_counter()
        append_log(f"START {identifier}")
        try:
            completed = runner(
                command,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds or int(pipeline.get("step_timeout_seconds", 900)),
                check=False,
            )
            duration = round(time.perf_counter() - step_clock, 4)
            result["duration_seconds"] = duration
            result["exit_code"] = int(completed.returncode)
            result["stdout_tail"] = _sanitize_output(
                completed.stdout.strip()[-2000:], root, settings.data_root
            )
            result["stderr_tail"] = _sanitize_output(
                completed.stderr.strip()[-2000:], root, settings.data_root
            )
            append_log(completed.stdout)
            append_log(completed.stderr)
            if completed.returncode != 0:
                raise PipelineExecutionError(
                    f"Step {identifier} exited with code {completed.returncode}."
                )
            assessment = _artifact_assessment(step, root, context)
            if step.get("artifact") and not assessment.get("accepted"):
                detail = assessment.get("status") or assessment.get("error") or "missing"
                raise PipelineExecutionError(
                    f"Step {identifier} produced an unacceptable artifact: {detail}."
                )
            result.update(
                {
                    "outcome": "PASS",
                    "artifact": assessment.get("display_path"),
                    "artifact_sha256": assessment.get("sha256"),
                    "artifact_status": assessment.get("status"),
                }
            )
            if assessment.get("failed_rule_ids"):
                result["accepted_failed_rule_ids"] = assessment["failed_rule_ids"]
            append_log(f"PASS {identifier} {duration:.4f}s")
        except (OSError, subprocess.SubprocessError, PipelineExecutionError) as error:
            result["outcome"] = "FAIL"
            result["error"] = str(error)
            failure = str(error)
            results.append(result)
            append_log(f"FAIL {identifier}: {error}")
            break
        results.append(result)

    completed_at = datetime.now(timezone.utc)
    executed = [item for item in results if item["outcome"] == "PASS"]
    reused = [
        item for item in results if item["outcome"] == "REUSED_VALIDATED_ARTIFACT"
    ]
    warning_steps = [
        item
        for item in results
        if item.get("artifact_status") in {"BLOCKED", "PASS_WITH_WARNINGS", "PASS_LIMITED"}
    ]
    if dry_run:
        status = "DRY_RUN"
    elif failure:
        status = "FAIL"
    elif warning_steps:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "pipeline": {
            "pipeline_id": pipeline["pipeline_id"],
            "source_id": pipeline["source"]["source_id"],
            "source_period": context["source_period"],
            "snapshot_date": context["snapshot_date"],
            "config": config_path.relative_to(root).as_posix(),
            "config_sha256": _sha256(config_path),
        },
        "run": {
            "run_id": run_id,
            "started_at_utc": started_at.isoformat(),
            "completed_at_utc": completed_at.isoformat(),
            "include_download": include_download,
            "include_powerbi": include_powerbi,
            "force": force,
            "dry_run": dry_run,
            "from_step": from_step,
            "to_step": to_step,
            "log": log_path.relative_to(root).as_posix(),
        },
        "summary": {
            "status": status,
            "steps_configured": len(steps),
            "steps_selected": sum(item["outcome"] != "NOT_SELECTED" for item in results),
            "steps_executed": len(executed),
            "steps_reused": len(reused),
            "steps_optional_skipped": sum(
                item["outcome"] == "SKIPPED_OPTIONAL" for item in results
            ),
            "steps_failed": sum(item["outcome"] == "FAIL" for item in results),
            "warning_steps": len(warning_steps),
            "duration_seconds": round(time.perf_counter() - started_clock, 4),
            "failure": failure,
        },
        "steps": results,
    }
    _atomic_json(report, report_target)
    if failure:
        raise PipelineExecutionError(failure)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/pipeline.yml"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--include-download", action="store_true")
    parser.add_argument("--include-powerbi", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--from-step")
    parser.add_argument("--to-step")
    parser.add_argument("--timeout-seconds", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        report = run_pipeline(
            args.config,
            args.env_file,
            args.report,
            include_download=args.include_download,
            include_powerbi=args.include_powerbi,
            force=args.force,
            dry_run=args.dry_run,
            from_step=args.from_step,
            to_step=args.to_step,
            timeout_seconds=args.timeout_seconds,
        )
    except PipelineExecutionError as error:
        print(f"Pipeline FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    summary = report["summary"]
    print(
        f"Pipeline {summary['status']}: {summary['steps_executed']} executed, "
        f"{summary['steps_reused']} reused, {summary['steps_failed']} failed; "
        f"{summary['duration_seconds']:.2f}s."
    )


if __name__ == "__main__":
    main()
