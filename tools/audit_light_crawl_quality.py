from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_900_mini"

TEXT_COLUMNS = [
    "department_name",
    "core_courses_summary",
    "ai_path_fit_notes",
    "math_foundation_notes",
    "cs_ai_foundation_notes",
    "research_resources_notes",
    "recommendation_or_honors_notes",
    "postgraduate_path_notes",
    "recommendation_policy_notes",
    "transfer_policy_notes",
    "learning_freedom_notes",
    "dorm_campus_notes",
    "nonofficial_signals",
    "next_deep_questions",
]

SOURCE_TEXT_COLUMNS = [
    "title",
    "publisher",
    "evidence_excerpt",
    "evidence_summary",
    "used_for_fields",
]

MOJIBAKE_MARKERS = [
    "锟斤拷",
    "�",
    "浣犳",
    "娴欐",
    "楂樿",
    "蹇呴",
    "杈撳",
    "鏂囦",
    "绾ф",
    "鐢熺",
    "銆",
]


def nonempty(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().ne("")


def contains_mojibake(value: object) -> bool:
    text = str(value)
    if text.count("?") >= 4:
        return True
    return any(marker in text for marker in MOJIBAKE_MARKERS)


def split_ids(value: object) -> list[str]:
    text = str(value).strip()
    if not text:
        return []
    ignored = {"not_found", "none", "nan", "na", "n/a", "-"}
    return [
        part
        for part in re.split(r"[;；,，\s]+", text)
        if part and part.lower() not in ignored
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit light-crawl content quality after structural validation.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    qa_dir = run_dir / "qa"
    rows_path = qa_dir / "light_crawl_900_rows_merged.csv"
    sources_path = qa_dir / "light_crawl_900_sources_merged.csv"

    if not rows_path.exists():
        raise FileNotFoundError(rows_path)
    rows = pd.read_csv(rows_path, dtype=str, encoding="utf-8-sig").fillna("")
    sources = pd.read_csv(sources_path, dtype=str, encoding="utf-8-sig").fillna("") if sources_path.exists() else pd.DataFrame()

    available_text_columns = [column for column in TEXT_COLUMNS if column in rows.columns]
    row_flags = rows[["shard_id", "pool_id", "volunteer_id", "college_name", "major_name"]].copy()
    row_flags["has_mojibake"] = rows[available_text_columns].apply(lambda item: any(contains_mojibake(value) for value in item), axis=1)
    row_flags["has_source"] = nonempty(rows["source_ids"]) if "source_ids" in rows.columns else False
    row_flags["has_training_plan_url"] = nonempty(rows["training_plan_url"]) if "training_plan_url" in rows.columns else False
    row_flags["has_recommendation_source"] = nonempty(rows["recommendation_source_ids"]) if "recommendation_source_ids" in rows.columns else False
    row_flags["has_dorm_source"] = nonempty(rows["dorm_campus_source_ids"]) if "dorm_campus_source_ids" in rows.columns else False
    row_flags["source_ref_count"] = rows["source_ids"].map(lambda value: len(split_ids(value))) if "source_ids" in rows.columns else 0
    row_flags["low_information"] = (
        rows["crawl_status"].eq("not_found")
        | (
            rows["crawl_status"].eq("partial")
            & ~row_flags["has_training_plan_url"]
            & ~row_flags["has_recommendation_source"]
            & ~row_flags["has_dorm_source"]
        )
    )

    source_by_shard = sources.groupby("shard_id").size().rename("source_rows") if not sources.empty else pd.Series(dtype=int)
    if not sources.empty:
        available_source_text_columns = [column for column in SOURCE_TEXT_COLUMNS if column in sources.columns]
        source_flags = sources[["shard_id", "source_id"]].copy()
        source_flags["has_mojibake"] = sources[available_source_text_columns].apply(
            lambda item: any(contains_mojibake(value) for value in item), axis=1
        )
        source_mojibake_by_shard = source_flags.groupby("shard_id")["has_mojibake"].sum().rename("source_mojibake_rows")
    else:
        source_flags = pd.DataFrame(columns=["shard_id", "source_id", "has_mojibake"])
        source_mojibake_by_shard = pd.Series(dtype=int)
    official_hard_by_shard = (
        sources[sources["source_level"].eq("official_hard")].groupby("shard_id").size().rename("official_hard_sources")
        if not sources.empty and "source_level" in sources.columns
        else pd.Series(dtype=int)
    )

    summary = (
        row_flags.groupby("shard_id")
        .agg(
            rows=("pool_id", "size"),
            mojibake_rows=("has_mojibake", "sum"),
            low_information_rows=("low_information", "sum"),
            rows_with_source=("has_source", "sum"),
            rows_with_training_plan=("has_training_plan_url", "sum"),
            rows_with_recommendation_source=("has_recommendation_source", "sum"),
            rows_with_dorm_source=("has_dorm_source", "sum"),
            avg_source_refs=("source_ref_count", "mean"),
        )
        .join(source_by_shard, how="left")
        .join(source_mojibake_by_shard, how="left")
        .join(official_hard_by_shard, how="left")
        .fillna(0)
        .reset_index()
    )

    status_counts = rows.groupby(["shard_id", "crawl_status"]).size().unstack(fill_value=0).reset_index()
    summary = summary.merge(status_counts, on="shard_id", how="left")

    def grade(item: pd.Series) -> str:
        if item["mojibake_rows"] > 0 or item["source_mojibake_rows"] > 0:
            return "needs_repair"
        if item["source_rows"] == 0 or item["rows_with_source"] == 0:
            return "needs_rerun"
        low_ratio = item["low_information_rows"] / item["rows"]
        if low_ratio >= 0.8 or item["rows_with_recommendation_source"] == 0:
            return "low_coverage"
        return "usable_as_light_crawl"

    summary["quality_grade"] = summary.apply(grade, axis=1)

    qa_dir.mkdir(parents=True, exist_ok=True)
    row_flags.to_csv(qa_dir / "light_crawl_quality_row_flags.csv", index=False, encoding="utf-8-sig")
    source_flags.to_csv(qa_dir / "light_crawl_quality_source_flags.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(qa_dir / "light_crawl_quality_by_shard.csv", index=False, encoding="utf-8-sig")
    result = {
        "run_dir": str(run_dir),
        "rows": int(len(rows)),
        "shards": int(rows["shard_id"].nunique()),
        "mojibake_rows": int(row_flags["has_mojibake"].sum()),
        "source_mojibake_rows": int(source_flags["has_mojibake"].sum()) if not source_flags.empty else 0,
        "low_information_rows": int(row_flags["low_information"].sum()),
        "grades": summary["quality_grade"].value_counts().to_dict(),
        "output_files": {
            "row_flags": str(qa_dir / "light_crawl_quality_row_flags.csv"),
            "source_flags": str(qa_dir / "light_crawl_quality_source_flags.csv"),
            "by_shard": str(qa_dir / "light_crawl_quality_by_shard.csv"),
        },
    }
    (qa_dir / "light_crawl_quality_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
