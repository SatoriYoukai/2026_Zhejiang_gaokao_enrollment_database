from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_900_mini_v6_48shards_20260627"
DEFAULT_POOL = ROOT / "outputs" / "ai_path_candidates" / "wide_pool_900.csv"
DEFAULT_MASTER = ROOT / "outputs" / "clean_database" / "volunteer_master_2026_with_history.csv"
DEFAULT_OUT_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_triage_v1_20260627"

LOW_PRIORITY_RANK_BANDS = {"低优先保底", "远保底"}
STRONG_RANK_BANDS = {"超冲", "冲", "贴合", "稳", "保"}
CORE_MAJOR_CATEGORIES = {"core_math_stat", "core_cs_ai"}

OFFICIAL_COST_LIMIT_RMB = 50_000
BUCKET_ORDER = {
    "keep_for_deep_crawl": 0,
    "borderline_review": 1,
    "drop_by_light_crawl": 2,
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def to_float(value: Any) -> float | None:
    text = clean_text(value).replace(",", "")
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not match:
        return None
    return float(match.group(1))


def split_tags(value: Any) -> set[str]:
    text = clean_text(value)
    if not text:
        return set()
    return {part.strip() for part in re.split(r"[;,；\s]+", text) if part.strip()}


def bool_from_cell(value: Any) -> bool:
    return clean_text(value).lower() in {"true", "1", "yes", "y"}


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def is_sino_or_international(row: pd.Series) -> bool:
    text = " ".join(
        clean_text(row.get(column))
        for column in ("college_name", "major_name", "remark", "risk_flags", "risk_tags")
    )
    return has_any(
        text,
        (
            "中外合作",
            "合作办学",
            "内地与港澳台合作",
            "高水平大学学生交流",
            "全英文",
            "英文教学",
            "英文授课",
            "sino_foreign",
        ),
    )


def estimate_tuition_rmb(row: pd.Series) -> tuple[float | None, str]:
    raw = clean_text(row.get("tuition_raw"))
    numeric = to_float(row.get("tuition"))
    international = is_sino_or_international(row)

    if raw:
        raw_no_space = re.sub(r"\s+", "", raw)
        wan_match = re.search(r"(\d+(?:\.\d+)?)万", raw_no_space)
        if wan_match:
            return float(wan_match.group(1)) * 10_000, f"tuition_raw={raw}; parsed as wan"

        number = first_number(raw_no_space)
        if number is not None:
            return number, f"tuition_raw={raw}; parsed as RMB number"

    if numeric is None:
        return None, "tuition missing"

    if international and 0 < numeric <= 20:
        return numeric * 10_000, f"tuition={numeric}; compact wan inferred for international program"
    if international and 20 < numeric < 300:
        return numeric * 1_000, f"tuition={numeric}; compact thousand inferred for international program"

    return numeric, f"tuition={numeric}; parsed as RMB number"


def foreign_extra_cost_status(row: pd.Series) -> tuple[str, str]:
    text = " ".join(clean_text(row.get(column)) for column in ("remark", "risk_tags", "next_deep_questions"))
    if not text:
        return "none", ""

    optional_terms = (
        "可选择",
        "自愿",
        "自由选择",
        "可在国内学习4年",
        "可在国内学习四年",
        "也可",
        "可申请",
    )
    mandatory_terms = (
        "须赴",
        "必须赴",
        "第四学年须",
        "第4学年须",
        "3+1",
        "2+2",
    )
    external_cost_terms = (
        "外方学费",
        "外方收费",
        "英方收费",
        "外方高校学费",
        "学费另计",
        "国外学习阶段",
        "赴英期间学费",
        "赴英期间",
        "澳元",
        "新西兰元",
        "国际学生标准",
    )

    has_external_cost = has_any(text, external_cost_terms)
    if not has_external_cost:
        return "none", ""

    if has_any(text, optional_terms):
        return "possible_optional", "foreign phase has extra tuition language, but appears optional"

    if has_any(text, mandatory_terms) or "mandatory_abroad" in split_tags(row.get("risk_tags")):
        return "required_or_unpriced", "foreign phase appears required or unpriced"

    return "possible_unclear", "foreign phase has extra tuition language; requirement unclear"


def count_source_refs(value: Any) -> int:
    text = clean_text(value)
    if not text:
        return 0
    ignored = {"not_found", "none", "nan", "na", "n/a", "-"}
    parts = [part for part in re.split(r"[;,；\s]+", text) if part and part.lower() not in ignored]
    return len(parts)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")


def merge_inputs(pool_path: Path, master_path: Path, run_dir: Path) -> pd.DataFrame:
    pool = read_csv(pool_path)
    master = read_csv(master_path)
    rows = read_csv(run_dir / "qa" / "light_crawl_900_rows_merged.csv")

    quality_row_path = run_dir / "qa" / "light_crawl_quality_row_flags.csv"
    quality_by_shard_path = run_dir / "qa" / "light_crawl_quality_by_shard.csv"
    quality_rows = read_csv(quality_row_path) if quality_row_path.exists() else pd.DataFrame()
    quality_by_shard = read_csv(quality_by_shard_path) if quality_by_shard_path.exists() else pd.DataFrame()

    master_cols = ["volunteer_id", "tuition_raw"]
    df = pool.merge(master[master_cols], on="volunteer_id", how="left")

    light_cols = [
        "shard_id",
        "pool_id",
        "crawl_status",
        "department_name",
        "training_plan_url",
        "core_courses_summary",
        "ai_path_fit_notes",
        "math_foundation_notes",
        "cs_ai_foundation_notes",
        "research_resources_notes",
        "recommendation_policy_notes",
        "learning_freedom_notes",
        "dorm_campus_notes",
        "risk_tags",
        "uncertainty_tags",
        "source_ids",
        "next_deep_questions",
        "agent_confidence",
    ]
    df = df.merge(rows[[column for column in light_cols if column in rows.columns]], on="pool_id", how="left")

    if not quality_rows.empty:
        quality_cols = [
            "pool_id",
            "has_source",
            "has_training_plan_url",
            "has_recommendation_source",
            "has_dorm_source",
            "source_ref_count",
            "low_information",
        ]
        df = df.merge(quality_rows[[column for column in quality_cols if column in quality_rows.columns]], on="pool_id", how="left")

    if not quality_by_shard.empty and "quality_grade" in quality_by_shard.columns:
        df = df.merge(quality_by_shard[["shard_id", "quality_grade"]], on="shard_id", how="left")

    return df.fillna("")


def has_source(row: pd.Series) -> bool:
    if "has_source" in row and clean_text(row.get("has_source")):
        return bool_from_cell(row.get("has_source"))
    return count_source_refs(row.get("source_ids")) > 0


def low_information(row: pd.Series) -> bool:
    if "low_information" in row and clean_text(row.get("low_information")):
        return bool_from_cell(row.get("low_information"))
    return clean_text(row.get("crawl_status")) == "not_found" or count_source_refs(row.get("source_ids")) == 0


def decide_bucket(row: pd.Series, tuition_limit: int) -> dict[str, Any]:
    risk_tags = split_tags(row.get("risk_tags"))
    risk_flags = split_tags(row.get("risk_flags"))
    priority = clean_text(row.get("prescreen_priority"))
    rank_band = clean_text(row.get("rank_band"))
    major_category = clean_text(row.get("major_category"))
    crawl_status = clean_text(row.get("crawl_status"))
    confidence = clean_text(row.get("agent_confidence"))
    quality_grade = clean_text(row.get("quality_grade"))
    source_count = count_source_refs(row.get("source_ids"))
    if "source_ref_count" in row and clean_text(row.get("source_ref_count")):
        parsed_count = to_float(row.get("source_ref_count"))
        if parsed_count is not None:
            source_count = int(parsed_count)

    tuition_rmb, tuition_note = estimate_tuition_rmb(row)
    foreign_cost_status, foreign_cost_note = foreign_extra_cost_status(row)
    over_tuition_limit = tuition_rmb is not None and tuition_rmb > tuition_limit
    at_tuition_limit = tuition_rmb is not None and abs(tuition_rmb - tuition_limit) < 1e-6

    drop_reasons: list[str] = []
    borderline_reasons: list[str] = []
    audit_notes: list[str] = []

    if over_tuition_limit:
        drop_reasons.append(f"tuition_over_{tuition_limit}_rmb")
    if foreign_cost_status == "required_or_unpriced":
        drop_reasons.append("required_or_unpriced_foreign_phase_cost")
    elif foreign_cost_status in {"possible_optional", "possible_unclear"}:
        borderline_reasons.append(foreign_cost_status)
    if at_tuition_limit:
        borderline_reasons.append("tuition_at_limit_check_strictness")

    if "off_target_courses" in risk_tags:
        if priority == "A" and rank_band in STRONG_RANK_BANDS and source_count >= 2:
            borderline_reasons.append("off_target_courses_need_manual_confirmation")
        else:
            drop_reasons.append("off_target_courses_with_weak_context")

    diversion_in_input = (
        "class_diversion" in risk_flags
        or "target_only_in_remark" in risk_flags
        or major_category in {"target_class", "trial_class", "target_in_remark"}
    )
    excluded_in_remark = "contains_excluded_major_in_remark" in risk_flags
    if diversion_in_input and ("major_diversion_risk" in risk_tags or excluded_in_remark):
        drop_reasons.append("unsafe_major_diversion")
    elif diversion_in_input or "major_diversion_risk" in risk_tags:
        borderline_reasons.append("major_diversion_or_department_unclear")

    weak_resource = "remote_or_weak_resource" in risk_tags
    management_heavy = "management_heavy_signal" in risk_tags
    low_evidence = low_information(row) or quality_grade in {"needs_rerun", "low_coverage"} or confidence == "low"

    if management_heavy and (priority in {"B", "C"} or rank_band in LOW_PRIORITY_RANK_BANDS or weak_resource):
        drop_reasons.append("management_heavy_or_training_burden_signal")
    elif management_heavy:
        borderline_reasons.append("management_heavy_signal")

    if weak_resource and low_evidence and (priority in {"B", "C"} or rank_band in LOW_PRIORITY_RANK_BANDS):
        drop_reasons.append("weak_resource_signal_with_low_evidence")
    elif weak_resource:
        borderline_reasons.append("remote_or_weak_resource_signal")

    if "dorm_negative_signal" in risk_tags:
        borderline_reasons.append("dorm_negative_signal")

    if major_category not in CORE_MAJOR_CATEGORIES:
        borderline_reasons.append("non_core_major_category")

    if crawl_status == "not_found":
        if priority == "C" or rank_band in LOW_PRIORITY_RANK_BANDS:
            drop_reasons.append("not_found_and_low_prescreen_priority")
        else:
            borderline_reasons.append("crawl_not_found")
    elif low_information(row):
        borderline_reasons.append("low_information_light_crawl")

    if quality_grade in {"needs_rerun", "low_coverage"}:
        borderline_reasons.append(f"shard_quality_{quality_grade}")

    if not has_source(row):
        borderline_reasons.append("no_referenced_source")

    if "small_plan" in risk_flags or "small_plan" in risk_tags:
        audit_notes.append("small_plan")
    if "new_no_history" in risk_flags or "new_no_history" in risk_tags:
        audit_notes.append("new_no_history")
    if "high_rank_volatility" in risk_flags:
        audit_notes.append("high_rank_volatility")
    if "sino_foreign" in risk_flags or "sino_foreign" in risk_tags:
        audit_notes.append("sino_foreign_not_negative_by_itself")

    if drop_reasons:
        bucket = "drop_by_light_crawl"
    elif borderline_reasons:
        bucket = "borderline_review"
    else:
        bucket = "keep_for_deep_crawl"

    return {
        "triage_bucket": bucket,
        "drop_reasons": ";".join(sorted(set(drop_reasons))),
        "borderline_reasons": ";".join(sorted(set(borderline_reasons))),
        "audit_notes": ";".join(sorted(set(audit_notes))),
        "tuition_rmb_estimate": "" if tuition_rmb is None else round(tuition_rmb, 2),
        "tuition_parse_note": tuition_note,
        "foreign_extra_cost_status": foreign_cost_status,
        "foreign_extra_cost_note": foreign_cost_note,
        "source_ref_count_triage": source_count,
    }


def build_summary(df: pd.DataFrame, tuition_limit: int, out_dir: Path) -> dict[str, Any]:
    def split_counter(column: str) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for value in df[column]:
            counter.update(split_tags(value))
        return dict(counter.most_common())

    summary = {
        "tuition_limit_rmb": tuition_limit,
        "rows": int(len(df)),
        "bucket_counts": df["triage_bucket"].value_counts().to_dict(),
        "bucket_by_major_category": (
            df.groupby(["triage_bucket", "major_category"]).size().unstack(fill_value=0).to_dict(orient="index")
        ),
        "bucket_by_rank_band": df.groupby(["triage_bucket", "rank_band"]).size().unstack(fill_value=0).to_dict(orient="index"),
        "drop_reasons": split_counter("drop_reasons"),
        "borderline_reasons": split_counter("borderline_reasons"),
        "audit_notes": split_counter("audit_notes"),
        "outputs": {
            "all": str(out_dir / "light_crawl_triage_900.csv"),
            "remaining": str(out_dir / "remaining_for_deep_crawl.csv"),
            "keep": str(out_dir / "keep_for_deep_crawl.csv"),
            "borderline": str(out_dir / "borderline_review.csv"),
            "drop": str(out_dir / "drop_by_light_crawl.csv"),
        },
    }
    return summary


def ordered_columns(df: pd.DataFrame) -> list[str]:
    preferred = [
        "triage_bucket",
        "drop_reasons",
        "borderline_reasons",
        "audit_notes",
        "pool_rank",
        "pool_id",
        "volunteer_id",
        "college_code",
        "college_name",
        "major_code",
        "major_name",
        "major_category",
        "major_fit_score",
        "province",
        "city",
        "plan_count",
        "tuition",
        "tuition_raw",
        "tuition_rmb_estimate",
        "tuition_parse_note",
        "foreign_extra_cost_status",
        "foreign_extra_cost_note",
        "remark",
        "rank_2023",
        "rank_2024",
        "rank_2025",
        "score_2025",
        "predicted_rank",
        "rank_certainty",
        "rank_band",
        "rank_volatility",
        "prescreen_score",
        "prescreen_priority",
        "risk_flags",
        "shard_id",
        "quality_grade",
        "crawl_status",
        "agent_confidence",
        "source_ref_count_triage",
        "source_ids",
        "training_plan_url",
        "risk_tags",
        "uncertainty_tags",
        "core_courses_summary",
        "ai_path_fit_notes",
        "research_resources_notes",
        "recommendation_policy_notes",
        "learning_freedom_notes",
        "dorm_campus_notes",
        "next_deep_questions",
    ]
    return [column for column in preferred if column in df.columns] + [column for column in df.columns if column not in preferred]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Conservative triage over the 900 light-crawl candidates.")
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--tuition-limit", type=int, default=OFFICIAL_COST_LIMIT_RMB)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = merge_inputs(args.pool.resolve(), args.master.resolve(), args.run_dir.resolve())
    triage = df.apply(lambda row: decide_bucket(row, args.tuition_limit), axis=1, result_type="expand")
    result = pd.concat([triage, df], axis=1)

    result["triage_bucket_sort"] = result["triage_bucket"].map(BUCKET_ORDER).fillna(99)
    sort_columns = [column for column in ["triage_bucket_sort", "pool_rank"] if column in result.columns]
    if "pool_rank" in result.columns:
        result["pool_rank_sort"] = pd.to_numeric(result["pool_rank"], errors="coerce")
        sort_columns = ["triage_bucket_sort", "pool_rank_sort"]
    result = result.sort_values(sort_columns).drop(columns=["triage_bucket_sort", "pool_rank_sort"], errors="ignore")
    result = result[ordered_columns(result)]

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    result.to_csv(out_dir / "light_crawl_triage_900.csv", index=False, encoding="utf-8-sig")
    result[result["triage_bucket"].isin(["keep_for_deep_crawl", "borderline_review"])].to_csv(
        out_dir / "remaining_for_deep_crawl.csv", index=False, encoding="utf-8-sig"
    )
    for bucket, filename in (
        ("keep_for_deep_crawl", "keep_for_deep_crawl.csv"),
        ("borderline_review", "borderline_review.csv"),
        ("drop_by_light_crawl", "drop_by_light_crawl.csv"),
    ):
        result[result["triage_bucket"].eq(bucket)].to_csv(out_dir / filename, index=False, encoding="utf-8-sig")

    summary = build_summary(result, args.tuition_limit, out_dir)
    (out_dir / "triage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
