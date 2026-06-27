from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_FILES = [
    "result.json",
    "sources.csv",
    "student_search_log.csv",
    "rescue_queue.csv",
    "summary.md",
    "debug_notes.md",
]

OPTIONAL_PILOT_FILES = ["sop_debugger_report.md"]

RESULT_KEYS = [
    "school_key",
    "college_name",
    "crawl_status",
    "run_scope",
    "majors",
    "school_level_findings",
    "decision_snapshot",
    "row_findings",
    "evidence_gaps",
    "risk_tags",
    "uncertainty_tags",
    "protocol_issues",
    "agent_notes",
]

DECISION_KEYS = [
    "provisional_bucket",
    "can_learn_needed_foundations",
    "low_time_tax_likelihood",
    "postgraduate_path_strength",
    "best_keep_reason",
    "largest_risk",
    "manual_questions_that_change_decision",
]

ROW_KEYS = [
    "pool_id",
    "volunteer_id",
    "college_name",
    "major_name",
    "official_major_match",
    "risk_tags",
    "uncertainty_tags",
    "major_alignment",
    "goal_alignment",
    "training_plan",
    "math_foundation",
    "cs_ai_foundation",
    "research_access",
    "postgraduate_path",
    "learning_freedom",
    "campus_dorm",
    "tuition_abroad",
    "student_signals",
    "source_ids",
    "evidence_gaps",
]

GOAL_ALIGNMENT_KEYS = [
    "foundation_fit",
    "learning_freedom_fit",
    "research_postgrad_fit",
    "time_tax_risk",
]

SOURCE_COLUMNS = [
    "source_id",
    "source_level",
    "source_type",
    "title",
    "publisher",
    "url",
    "publish_date",
    "access_date",
    "applies_to",
    "evidence_excerpt",
    "evidence_summary",
    "used_for_fields",
    "access_method",
    "local_artifact_path",
    "extraction_method",
    "reliability_notes",
]

STUDENT_COLUMNS = [
    "query",
    "platform",
    "result_url",
    "result_title",
    "adoption_status",
    "reason",
    "related_fields",
]

RESCUE_COLUMNS = [
    "rescue_id",
    "school_key",
    "college_name",
    "major_name",
    "blocked_item_type",
    "title_or_field",
    "url",
    "source_id_if_any",
    "blocker_type",
    "attempted_methods",
    "error_or_symptom",
    "impact_on_decision",
    "priority",
    "suggested_rescue_method",
    "related_risk_tags",
    "related_uncertainty_tags",
]


def split_source_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        return [item.strip() for item in re.split(r"[;,，、\s]+", text) if item.strip()]
    return [str(value).strip()] if str(value).strip() else []


def missing_keys(obj: Any, keys: list[str]) -> list[str]:
    if not isinstance(obj, dict):
        return keys
    return [key for key in keys if key not in obj]


def validate_school(run_dir: Path, school_key: str, expected_rows: int | None, require_pilot_report: bool) -> dict[str, Any]:
    out_dir = run_dir / "school_outputs" / school_key
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {
        "school_key": school_key,
        "output_dir": str(out_dir.as_posix()),
        "exists": out_dir.exists(),
        "crawl_status": "",
        "row_findings": 0,
        "sources": 0,
        "official_hard_sources": 0,
        "student_searches": 0,
        "rescue_items": 0,
        "high_priority_rescue_items": 0,
        "protocol_issues": 0,
    }

    files = REQUIRED_FILES + (OPTIONAL_PILOT_FILES if require_pilot_report else [])
    for filename in files:
        path = out_dir / filename
        if not path.exists():
            errors.append(f"missing_file:{filename}")
        elif path.stat().st_size == 0:
            errors.append(f"empty_file:{filename}")

    result_path = out_dir / "result.json"
    result: dict[str, Any] = {}
    if result_path.exists() and result_path.stat().st_size:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"result_json_parse_error:{exc}")

    if result:
        metrics["crawl_status"] = result.get("crawl_status", "")
        metrics["row_findings"] = len(result.get("row_findings", []))
        metrics["protocol_issues"] = len(result.get("protocol_issues", []) or [])
        for key in missing_keys(result, RESULT_KEYS):
            errors.append(f"missing_result_key:{key}")

        decision = result.get("decision_snapshot", {})
        for key in missing_keys(decision, DECISION_KEYS):
            errors.append(f"missing_decision_key:{key}")

        if expected_rows is not None and metrics["row_findings"] != expected_rows:
            errors.append(f"row_count_mismatch:expected_{expected_rows}:got_{metrics['row_findings']}")

        for idx, row in enumerate(result.get("row_findings", []), start=1):
            for key in missing_keys(row, ROW_KEYS):
                errors.append(f"row_{idx}_missing_key:{key}")
            goal_alignment = row.get("goal_alignment", {})
            if isinstance(goal_alignment, dict):
                for key in GOAL_ALIGNMENT_KEYS:
                    if key not in goal_alignment:
                        errors.append(f"row_{idx}_missing_goal_alignment:{key}")
            else:
                warnings.append(f"row_{idx}_goal_alignment_not_object")

    sources_path = out_dir / "sources.csv"
    source_ids: set[str] = set()
    if sources_path.exists() and sources_path.stat().st_size:
        try:
            sources = pd.read_csv(sources_path, dtype=str, encoding="utf-8-sig").fillna("")
            metrics["sources"] = len(sources)
            if "source_level" in sources.columns:
                metrics["official_hard_sources"] = int((sources["source_level"] == "official_hard").sum())
            for col in SOURCE_COLUMNS:
                if col not in sources.columns:
                    errors.append(f"sources_missing_column:{col}")
            if "source_id" in sources.columns:
                source_ids = set(sources["source_id"].astype(str))
                duplicates = sources["source_id"][sources["source_id"].duplicated()].astype(str).tolist()
                for duplicate in sorted(set(duplicates)):
                    errors.append(f"duplicate_source_id:{duplicate}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"sources_csv_parse_error:{exc}")

    if result and source_ids:
        referenced: set[str] = set()
        for row in result.get("row_findings", []):
            referenced.update(split_source_ids(row.get("source_ids")))
        for missing in sorted(referenced - source_ids):
            errors.append(f"missing_source_ref:{missing}")
        if not referenced:
            errors.append("no_row_source_refs")

    student_path = out_dir / "student_search_log.csv"
    if student_path.exists() and student_path.stat().st_size:
        try:
            student = pd.read_csv(student_path, dtype=str, encoding="utf-8-sig").fillna("")
            metrics["student_searches"] = len(student)
            for col in STUDENT_COLUMNS:
                if col not in student.columns:
                    errors.append(f"student_log_missing_column:{col}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"student_csv_parse_error:{exc}")

    rescue_path = out_dir / "rescue_queue.csv"
    if rescue_path.exists() and rescue_path.stat().st_size:
        try:
            rescue = pd.read_csv(rescue_path, dtype=str, encoding="utf-8-sig").fillna("")
            metrics["rescue_items"] = len(rescue)
            for col in RESCUE_COLUMNS:
                if col not in rescue.columns:
                    errors.append(f"rescue_queue_missing_column:{col}")
            if "rescue_id" in rescue.columns:
                duplicates = rescue["rescue_id"][rescue["rescue_id"].duplicated()].astype(str).tolist()
                for duplicate in sorted(set(duplicates)):
                    errors.append(f"duplicate_rescue_id:{duplicate}")
            if "priority" in rescue.columns:
                metrics["high_priority_rescue_items"] = int((rescue["priority"] == "high").sum())
                invalid_priorities = sorted(set(rescue.loc[~rescue["priority"].isin(["high", "medium", "low"]), "priority"]))
                for priority in invalid_priorities:
                    errors.append(f"invalid_rescue_priority:{priority}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"rescue_queue_csv_parse_error:{exc}")

    metrics["errors"] = ";".join(errors)
    metrics["warnings"] = ";".join(warnings)
    metrics["valid"] = not errors
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--require-pilot-report", action="store_true")
    args = parser.parse_args()

    selected_path = args.run_dir / "selected_schools.csv"
    if not selected_path.exists():
        raise SystemExit(f"Missing selected_schools.csv: {selected_path}")

    selected = pd.read_csv(selected_path, dtype=str, encoding="utf-8-sig").fillna("")
    rows: list[dict[str, Any]] = []
    for _, school in selected.iterrows():
        school_key = school["school_key"]
        expected_rows = int(school["row_count"]) if school["row_count"] else None
        row = validate_school(args.run_dir, school_key, expected_rows, args.require_pilot_report)
        row["college_name"] = school["college_name"]
        rows.append(row)

    qa_dir = args.run_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)
    out.to_csv(qa_dir / "deep_crawl_validation.csv", index=False, encoding="utf-8-sig")
    summary = {
        "run_dir": str(args.run_dir.as_posix()),
        "schools": len(out),
        "valid_schools": int(out["valid"].sum()),
        "invalid_schools": int((~out["valid"]).sum()),
        "total_sources": int(out["sources"].sum()),
        "total_official_hard_sources": int(out["official_hard_sources"].sum()),
        "total_student_searches": int(out["student_searches"].sum()),
        "total_rescue_items": int(out["rescue_items"].sum()),
        "total_high_priority_rescue_items": int(out["high_priority_rescue_items"].sum()),
    }
    (qa_dir / "deep_crawl_validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["invalid_schools"]:
        invalid = out.loc[~out["valid"], ["school_key", "college_name", "errors"]]
        print(invalid.to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
