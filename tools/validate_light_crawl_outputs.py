from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_900_mini"

ROW_COLUMNS = [
    "pool_id",
    "volunteer_id",
    "college_name",
    "major_name",
    "crawl_status",
    "department_name",
    "department_url",
    "major_intro_url",
    "training_plan_url",
    "training_plan_year",
    "core_courses_summary",
    "ai_path_fit_notes",
    "math_foundation_notes",
    "cs_ai_foundation_notes",
    "research_resources_notes",
    "research_resources_source_ids",
    "recommendation_or_honors_notes",
    "postgraduate_path_notes",
    "recommendation_policy_notes",
    "recommendation_source_ids",
    "transfer_policy_notes",
    "learning_freedom_notes",
    "dorm_campus_notes",
    "dorm_campus_source_ids",
    "risk_tags",
    "uncertainty_tags",
    "nonofficial_signals",
    "source_ids",
    "next_deep_questions",
    "agent_confidence",
]

SOURCE_COLUMNS = [
    "source_id",
    "pool_id_or_school_key",
    "source_level",
    "source_type",
    "title",
    "publisher",
    "url",
    "publish_date",
    "access_date",
    "evidence_excerpt",
    "evidence_summary",
    "used_for_fields",
]

RISK_TAGS = {
    "major_diversion_risk",
    "off_target_courses",
    "sino_foreign",
    "mandatory_abroad",
    "tuition_unit_unclear",
    "very_high_tuition_possible",
    "small_plan",
    "new_no_history",
    "campus_move",
    "remote_or_weak_resource",
    "management_heavy_signal",
    "dorm_negative_signal",
    "source_conflict",
}

UNCERTAINTY_TAGS = {
    "training_plan_not_found",
    "recommendation_not_found",
    "transfer_policy_not_found",
    "department_unclear",
    "campus_unclear",
    "dorm_unclear",
    "forum_signal_sparse",
    "policy_year_unclear",
}

STATUS_VALUES = {"complete", "partial", "not_found"}
CONFIDENCE_VALUES = {"high", "medium", "low"}
SOURCE_LEVELS = {"official_hard", "official_soft", "nonofficial"}
SOURCE_TYPES = {"admission", "department", "training_plan", "policy", "research", "dorm", "forum", "other"}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def split_tags(value: object) -> list[str]:
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;；,，]+", text) if part.strip()]


def split_source_ids(value: object) -> list[str]:
    text = str(value).strip()
    if not text:
        return []
    ignored = {"not_found", "none", "nan", "na", "n/a", "-"}
    return [
        part.strip()
        for part in re.split(r"[;；,，\s]+", text)
        if part.strip() and part.strip().lower() not in ignored
    ]


def issue(issues: list[dict[str, str]], shard_id: str, severity: str, code: str, detail: str) -> None:
    issues.append({"shard_id": shard_id, "severity": severity, "code": code, "detail": detail})


def validate_shard(
    shard_id: str,
    input_path: Path,
    rows_path: Path,
    sources_path: Path,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, list[dict[str, str]], dict[str, object]]:
    issues: list[dict[str, str]] = []
    expected = read_csv(input_path)

    rows = None
    sources = None
    if not rows_path.exists():
        issue(issues, shard_id, "error", "missing_rows_file", str(rows_path))
    else:
        rows = read_csv(rows_path)
        if list(rows.columns) != ROW_COLUMNS:
            issue(issues, shard_id, "error", "bad_row_columns", json.dumps(list(rows.columns), ensure_ascii=False))
    if not sources_path.exists():
        issue(issues, shard_id, "error", "missing_sources_file", str(sources_path))
    else:
        sources = read_csv(sources_path)
        if list(sources.columns) != SOURCE_COLUMNS:
            issue(issues, shard_id, "error", "bad_source_columns", json.dumps(list(sources.columns), ensure_ascii=False))

    if rows is not None:
        if len(rows) != len(expected):
            issue(issues, shard_id, "error", "row_count_mismatch", f"expected={len(expected)} actual={len(rows)}")
        if "pool_id" in rows.columns:
            duplicated = rows["pool_id"][rows["pool_id"].duplicated()].unique().tolist()
            if duplicated:
                issue(issues, shard_id, "error", "duplicate_pool_id", ";".join(map(str, duplicated[:20])))

        if set(["pool_id", "volunteer_id", "college_name", "major_name"]).issubset(rows.columns):
            merged = expected[["pool_id", "volunteer_id", "college_name", "major_name"]].merge(
                rows[["pool_id", "volunteer_id", "college_name", "major_name"]],
                on="pool_id",
                how="outer",
                suffixes=("_expected", "_actual"),
                indicator=True,
            )
            for _, item in merged.iterrows():
                if item["_merge"] != "both":
                    issue(issues, shard_id, "error", "pool_id_set_mismatch", str(item.to_dict()))
                    continue
                for field in ["volunteer_id", "college_name", "major_name"]:
                    if str(item[f"{field}_expected"]) != str(item[f"{field}_actual"]):
                        issue(
                            issues,
                            shard_id,
                            "error",
                            "identity_field_changed",
                            f"pool_id={item['pool_id']} field={field} expected={item[f'{field}_expected']} actual={item[f'{field}_actual']}",
                        )

        if "crawl_status" in rows.columns:
            bad_status = sorted(set(rows["crawl_status"]) - STATUS_VALUES)
            if bad_status:
                issue(issues, shard_id, "error", "invalid_crawl_status", ";".join(bad_status))
        if "agent_confidence" in rows.columns:
            bad_confidence = sorted(set(rows["agent_confidence"]) - CONFIDENCE_VALUES)
            if bad_confidence:
                issue(issues, shard_id, "error", "invalid_agent_confidence", ";".join(bad_confidence))

        if "risk_tags" in rows.columns:
            bad_risk_tags = sorted({tag for value in rows["risk_tags"] for tag in split_tags(value)} - RISK_TAGS)
            if bad_risk_tags:
                issue(issues, shard_id, "error", "invalid_risk_tags", ";".join(bad_risk_tags))
        if "uncertainty_tags" in rows.columns:
            bad_uncertainty_tags = sorted({tag for value in rows["uncertainty_tags"] for tag in split_tags(value)} - UNCERTAINTY_TAGS)
            if bad_uncertainty_tags:
                issue(issues, shard_id, "error", "invalid_uncertainty_tags", ";".join(bad_uncertainty_tags))

    if sources is not None:
        if "source_id" in sources.columns:
            duplicated_sources = sources["source_id"][sources["source_id"].duplicated()].unique().tolist()
            if duplicated_sources:
                issue(issues, shard_id, "error", "duplicate_source_id", ";".join(map(str, duplicated_sources[:20])))
        if "source_level" in sources.columns:
            bad_levels = sorted(set(sources["source_level"]) - SOURCE_LEVELS)
            if bad_levels:
                issue(issues, shard_id, "error", "invalid_source_level", ";".join(bad_levels))
        if "source_type" in sources.columns:
            bad_types = sorted(set(sources["source_type"]) - SOURCE_TYPES)
            if bad_types:
                issue(issues, shard_id, "error", "invalid_source_type", ";".join(bad_types))

    if rows is not None and sources is not None and "source_id" in sources.columns:
        valid_source_ids = set(sources["source_id"].astype(str))
        source_fields = [
            "research_resources_source_ids",
            "recommendation_source_ids",
            "dorm_campus_source_ids",
            "source_ids",
        ]
        missing_refs: list[str] = []
        for _, row in rows.iterrows():
            for field in source_fields:
                if field not in rows.columns:
                    continue
                for source_id in split_source_ids(row[field]):
                    if source_id not in valid_source_ids:
                        missing_refs.append(f"pool_id={row.get('pool_id', '')} field={field} source_id={source_id}")
        if missing_refs:
            issue(issues, shard_id, "error", "missing_source_refs", " | ".join(missing_refs[:40]))

    summary = {
        "shard_id": shard_id,
        "expected_rows": int(len(expected)),
        "actual_rows": 0 if rows is None else int(len(rows)),
        "source_rows": 0 if sources is None else int(len(sources)),
        "issue_count": len(issues),
        "error_count": sum(1 for item in issues if item["severity"] == "error"),
    }
    return rows, sources, issues, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate light-crawl output files.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    input_dir = run_dir / "input_shards"
    output_dir = run_dir / "outputs"
    qa_dir = run_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    retry_manifest_path = run_dir / "retry_manifest.json"
    retry_manifest = json.loads(retry_manifest_path.read_text(encoding="utf-8-sig")) if retry_manifest_path.exists() else {"retries": []}
    all_rows: list[pd.DataFrame] = []
    all_sources: list[pd.DataFrame] = []
    all_issues: list[dict[str, str]] = []
    summaries: list[dict[str, object]] = []

    for shard in manifest["shards"]:
        shard_id = shard["shard_id"]
        rows, sources, issues, summary = validate_shard(
            shard_id,
            input_path=Path(shard.get("input_csv", input_dir / f"{shard_id}_input.csv")),
            rows_path=Path(shard.get("rows_csv", output_dir / f"{shard_id}_light_crawl_rows.csv")),
            sources_path=Path(shard.get("sources_csv", output_dir / f"{shard_id}_sources.csv")),
        )
        if rows is not None:
            rows.insert(0, "shard_id", shard_id)
            all_rows.append(rows)
        if sources is not None:
            sources.insert(0, "shard_id", shard_id)
            all_sources.append(sources)
        all_issues.extend(issues)
        summaries.append(summary)

    retry_summaries: list[dict[str, object]] = []
    retry_issues: list[dict[str, str]] = []
    retry_rows: list[pd.DataFrame] = []
    retry_sources: list[pd.DataFrame] = []
    for retry in retry_manifest["retries"]:
        retry_id = retry["retry_id"]
        rows, sources, issues, summary = validate_shard(
            retry_id,
            input_path=Path(retry["input_csv"]),
            rows_path=Path(retry["rows_csv"]),
            sources_path=Path(retry["sources_csv"]),
        )
        summary["parent_shard_id"] = retry["parent_shard_id"]
        retry_summaries.append(summary)
        retry_issues.extend(issues)
        if rows is not None and not issues:
            rows.insert(0, "retry_id", retry_id)
            rows.insert(0, "parent_shard_id", retry["parent_shard_id"])
            retry_rows.append(rows)
        if sources is not None and not issues:
            sources.insert(0, "retry_id", retry_id)
            sources.insert(0, "parent_shard_id", retry["parent_shard_id"])
            retry_sources.append(sources)

    summary_df = pd.DataFrame(summaries)
    issues_df = pd.DataFrame(all_issues, columns=["shard_id", "severity", "code", "detail"])
    retry_summary_df = pd.DataFrame(retry_summaries)
    retry_issues_df = pd.DataFrame(retry_issues, columns=["shard_id", "severity", "code", "detail"])
    summary_df.to_csv(qa_dir / "validation_summary.csv", index=False, encoding="utf-8-sig")
    issues_df.to_csv(qa_dir / "validation_issues.csv", index=False, encoding="utf-8-sig")
    retry_summary_df.to_csv(qa_dir / "retry_validation_summary.csv", index=False, encoding="utf-8-sig")
    retry_issues_df.to_csv(qa_dir / "retry_validation_issues.csv", index=False, encoding="utf-8-sig")
    if all_rows:
        pd.concat(all_rows, ignore_index=True).to_csv(qa_dir / "light_crawl_900_rows_merged.csv", index=False, encoding="utf-8-sig")
    if all_sources:
        pd.concat(all_sources, ignore_index=True).to_csv(qa_dir / "light_crawl_900_sources_merged.csv", index=False, encoding="utf-8-sig")
    if retry_rows:
        pd.concat(retry_rows, ignore_index=True).to_csv(qa_dir / "retry_rows_valid.csv", index=False, encoding="utf-8-sig")
    if retry_sources:
        pd.concat(retry_sources, ignore_index=True).to_csv(qa_dir / "retry_sources_valid.csv", index=False, encoding="utf-8-sig")

    result = {
        "run_dir": str(run_dir),
        "shards": len(summaries),
        "completed_row_files": int(summary_df["actual_rows"].gt(0).sum()) if not summary_df.empty else 0,
        "actual_rows": int(summary_df["actual_rows"].sum()) if not summary_df.empty else 0,
        "source_rows": int(summary_df["source_rows"].sum()) if not summary_df.empty else 0,
        "issues": len(all_issues),
        "errors": int(summary_df["error_count"].sum()) if not summary_df.empty else 0,
        "retry_completed_row_files": int(retry_summary_df["actual_rows"].gt(0).sum()) if not retry_summary_df.empty else 0,
        "retry_actual_rows": int(retry_summary_df["actual_rows"].sum()) if not retry_summary_df.empty else 0,
        "retry_errors": int(retry_summary_df["error_count"].sum()) if not retry_summary_df.empty else 0,
        "qa_dir": str(qa_dir),
    }
    (qa_dir / "validation_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
