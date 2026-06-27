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
DEFAULT_OUT_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_triage_v2_20260627"

LOW_PRIORITY_RANK_BANDS = {"低优先保底", "远保底"}
STRONG_RANK_BANDS = {"超冲", "冲", "贴合", "稳", "保"}
CORE_MAJOR_CATEGORIES = {"core_math_stat", "core_cs_ai"}
CLASS_OR_REMARK_CATEGORIES = {"target_class", "trial_class", "target_in_remark"}

OFFICIAL_COST_LIMIT_RMB = 50_000
BUCKET_ORDER = {
    "keep_for_deep_crawl": 0,
    "borderline_review": 1,
    "drop_by_light_crawl": 2,
}

DOMAIN_DRIFT_TERMS = (
    "金融",
    "经济",
    "审计",
    "法学",
    "治理",
    "民航",
    "海事",
    "海洋",
    "农业",
    "林业",
    "水利",
    "石油",
    "电力",
    "劳动",
    "就业",
    "外语",
    "语言",
    "财经",
    "政法",
)
TEXT_ALIGNMENT_DRIFT_TERMS = (
    "finance",
    "financial",
    "economics",
    "economic",
    "audit",
    "auditing",
    "law",
    "governance",
    "civil aviation",
    "aviation",
    "maritime",
    "agriculture",
    "labor",
    "employment",
    "foreign-language",
    "foreign language",
    "language-plus",
    "market research",
    "consulting",
    "teacher-oriented",
    "industry-oriented",
    "application oriented",
    "applied ai route",
    "not a pure",
    "not direct",
    "not ai-centered",
    "not ai-native",
    "not ai-specialized",
    "moderate ai-path fit only",
    "weakly evidenced fit",
)
UNRELATED_DIVERSION_TERMS = (
    "软件工程",
    "网络工程",
    "物联网",
    "数字媒体",
    "数据科学与大数据",
    "数据科学",
    "大数据",
    "通信工程",
    "电子信息",
    "机器人工程",
    "机械",
    "环境",
    "木材",
    "风景园林",
    "食品",
    "生物",
    "经济统计",
    "金融",
    "法学",
    "管理",
)
SELECTION_GUARANTEE_TERMS = (
    "任选",
    "自选专业",
    "自由选择",
    "专业任选",
    "类内专业任选",
    "分流时上述专业任选",
    "第四学期末在同一实验班内自选专业",
)
TARGET_SELECTION_TERMS = (
    "计算机科学与技术",
    "人工智能",
    "智能科学与技术",
    "信息与计算科学",
    "数学与应用数学",
    "数理基础科学",
    "数据计算及应用",
    "统计学",
    "应用统计学",
)
RESOURCE_WEAK_TEXT_TERMS = (
    "not_found",
    "not found",
    "under-evidenced",
    "weak signal",
    "weakly evidenced",
    "school-level context",
    "school-level only",
    "no program-level",
    "no project-specific",
    "no direct research resource",
    "research depth appears limited",
    "only weak official signals",
    "does not support a strong",
    "too thin for a strong",
)


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


def joined_text(row: pd.Series, columns: tuple[str, ...]) -> str:
    return " ".join(clean_text(row.get(column)) for column in columns)


def is_sino_or_international(row: pd.Series) -> bool:
    text = joined_text(row, ("college_name", "major_name", "remark", "risk_flags", "risk_tags"))
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


def core_missing_count(row: pd.Series, quality_grade: str, crawl_status: str, source_count: int) -> int:
    count = 0
    if crawl_status == "not_found":
        count += 2
    if low_information(row):
        count += 1
    if source_count == 0:
        count += 1
    if quality_grade == "needs_rerun":
        count += 2
    elif quality_grade == "low_coverage":
        count += 1
    for column in ("has_training_plan_url", "has_recommendation_source", "has_dorm_source"):
        if column in row and clean_text(row.get(column)) and not bool_from_cell(row.get(column)):
            count += 1
    return count


def ceiling_level(row: pd.Series, risk_flags: set[str], risk_tags: set[str]) -> str:
    college_name = clean_text(row.get("college_name"))
    priority = clean_text(row.get("prescreen_priority"))
    rank_band = clean_text(row.get("rank_band"))
    prescreen_score = to_float(row.get("prescreen_score")) or 0
    major_category = clean_text(row.get("major_category"))

    strong_school = "双一流" in college_name or "2011计划" in college_name or "省重点建设高校" in college_name
    weak_school = has_any(college_name, ("学院", "民办", "独立学院", "职业", "商学院", "科技学院", "文理学院"))

    if strong_school and major_category in CORE_MAJOR_CATEGORIES and priority in {"A", "B"}:
        return "high"
    if rank_band == "远保底" or priority == "C" or prescreen_score < 88:
        return "low"
    if weak_school and rank_band in LOW_PRIORITY_RANK_BANDS:
        return "low"
    if "very_high_tuition" in risk_flags and priority in {"B", "C"}:
        return "low"
    if rank_band == "低优先保底" and (priority == "B" or "remote_or_weak_resource" in risk_tags):
        return "low"
    if not strong_school and major_category not in CORE_MAJOR_CATEGORIES and priority != "A":
        return "low"
    if strong_school or rank_band in {"超冲", "冲", "贴合"} or prescreen_score >= 115:
        return "high"
    return "medium"


def guaranteed_target_selection(row: pd.Series) -> bool:
    text = joined_text(row, ("remark", "core_courses_summary", "ai_path_fit_notes", "next_deep_questions"))
    remark = clean_text(row.get("remark"))
    target_mentions = sum(1 for term in TARGET_SELECTION_TERMS if term in remark)
    unrelated_mentions = sum(1 for term in UNRELATED_DIVERSION_TERMS if term in remark)
    if target_mentions >= 1 and unrelated_mentions == 0:
        return True
    return has_any(text, SELECTION_GUARANTEE_TERMS)


def domain_drift_flags(row: pd.Series) -> set[str]:
    flags: set[str] = set()
    structured_text = joined_text(row, ("college_name", "major_name", "remark"))
    evidence_text = joined_text(
        row,
        (
            "core_courses_summary",
            "ai_path_fit_notes",
            "math_foundation_notes",
            "cs_ai_foundation_notes",
            "research_resources_notes",
            "next_deep_questions",
        ),
    ).lower()

    if has_any(structured_text, DOMAIN_DRIFT_TERMS):
        flags.add("domain_name_or_remark_drift")
    if has_any(evidence_text, TEXT_ALIGNMENT_DRIFT_TERMS):
        flags.add("light_crawl_alignment_drift")
    return flags


def diversion_risk_flags(row: pd.Series, risk_flags: set[str], risk_tags: set[str]) -> set[str]:
    flags: set[str] = set()
    major_category = clean_text(row.get("major_category"))
    remark = clean_text(row.get("remark"))
    major_name = clean_text(row.get("major_name"))
    text = f"{major_name} {remark}"
    has_structural_diversion = (
        major_category in CLASS_OR_REMARK_CATEGORIES
        or "class_diversion" in risk_flags
        or "target_only_in_remark" in risk_flags
    )

    if has_structural_diversion:
        flags.add("class_or_target_only_diversion")
    if "major_diversion_risk" in risk_tags:
        flags.add("light_crawl_major_diversion")
    if "contains_excluded_major_in_remark" in risk_flags:
        flags.add("excluded_major_in_remark")
    if (has_structural_diversion or "contains_excluded_major_in_remark" in risk_flags) and has_any(text, UNRELATED_DIVERSION_TERMS):
        flags.add("unrelated_major_in_diversion_pool")
    if guaranteed_target_selection(row):
        flags.add("selection_guarantee_signal")
    return flags


def resource_weak_flags(row: pd.Series, risk_tags: set[str], source_count: int) -> set[str]:
    flags: set[str] = set()
    if "remote_or_weak_resource" in risk_tags:
        flags.add("remote_or_weak_resource_tag")
    if "campus_move" in risk_tags:
        flags.add("campus_move_tag")
    resource_text = joined_text(
        row,
        (
            "research_resources_notes",
            "recommendation_policy_notes",
            "learning_freedom_notes",
            "dorm_campus_notes",
            "next_deep_questions",
        ),
    ).lower()
    if has_any(resource_text, RESOURCE_WEAK_TEXT_TERMS):
        flags.add("resource_or_policy_evidence_weak")
    if source_count <= 1 and not bool_from_cell(row.get("has_recommendation_source")):
        flags.add("resource_sources_sparse")
    return flags


def decide_bucket(row: pd.Series, tuition_limit: int) -> dict[str, Any]:
    risk_tags = split_tags(row.get("risk_tags"))
    risk_flags = split_tags(row.get("risk_flags"))
    priority = clean_text(row.get("prescreen_priority"))
    rank_band = clean_text(row.get("rank_band"))
    major_category = clean_text(row.get("major_category"))
    crawl_status = clean_text(row.get("crawl_status"))
    confidence = clean_text(row.get("agent_confidence"))
    quality_grade = clean_text(row.get("quality_grade"))
    college_name = clean_text(row.get("college_name"))
    strong_school = "双一流" in college_name or "2011计划" in college_name or "省重点建设高校" in college_name
    source_count = count_source_refs(row.get("source_ids"))
    if "source_ref_count" in row and clean_text(row.get("source_ref_count")):
        parsed_count = to_float(row.get("source_ref_count"))
        if parsed_count is not None:
            source_count = int(parsed_count)

    tuition_rmb, tuition_note = estimate_tuition_rmb(row)
    foreign_cost_status, foreign_cost_note = foreign_extra_cost_status(row)
    over_tuition_limit = tuition_rmb is not None and tuition_rmb > tuition_limit
    at_tuition_limit = tuition_rmb is not None and abs(tuition_rmb - tuition_limit) < 1e-6
    missing_count = core_missing_count(row, quality_grade, crawl_status, source_count)
    ceiling = ceiling_level(row, risk_flags, risk_tags)
    alignment_flags = domain_drift_flags(row)
    diversion_flags = diversion_risk_flags(row, risk_flags, risk_tags)
    resource_flags = resource_weak_flags(row, risk_tags, source_count)

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

    if alignment_flags:
        borderline_reasons.append("possible_training_direction_drift")
    if (
        ("off_target_courses" in risk_tags or "light_crawl_alignment_drift" in alignment_flags)
        and ceiling in {"low", "medium"}
        and (missing_count >= 3 or rank_band in LOW_PRIORITY_RANK_BANDS or priority in {"B", "C"})
        and not (priority == "A" and rank_band not in LOW_PRIORITY_RANK_BANDS and missing_count < 3)
    ):
        drop_reasons.append("training_direction_low_alignment")
    if (
        "domain_name_or_remark_drift" in alignment_flags
        and "light_crawl_alignment_drift" in alignment_flags
        and ceiling != "high"
    ):
        drop_reasons.append("domain_drift_with_limited_upside")

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
    if diversion_flags - {"selection_guarantee_signal"}:
        borderline_reasons.append("diversion_risk_needs_manual_check")
    if (
        ("class_or_target_only_diversion" in diversion_flags or "unrelated_major_in_diversion_pool" in diversion_flags)
        and "selection_guarantee_signal" not in diversion_flags
        and ceiling != "high"
    ):
        drop_reasons.append("uncontrolled_diversion_risk")
    if (
        "excluded_major_in_remark" in diversion_flags
        and "unrelated_major_in_diversion_pool" in diversion_flags
        and "selection_guarantee_signal" not in diversion_flags
        and ceiling != "high"
    ):
        drop_reasons.append("excluded_major_mix_without_selection_guarantee")

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
    if resource_flags:
        borderline_reasons.append("campus_or_resource_weak_signal")
    if (
        {"remote_or_weak_resource_tag", "resource_or_policy_evidence_weak"} <= resource_flags
        and ceiling in {"low", "medium"}
        and missing_count >= 2
    ):
        drop_reasons.append("campus_resource_obviously_weak")
    if (
        "campus_move_tag" in resource_flags
        and "resource_or_policy_evidence_weak" in resource_flags
        and ceiling == "low"
    ):
        drop_reasons.append("campus_resource_obviously_weak")

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

    if missing_count >= 5 and ceiling == "low" and not strong_school:
        drop_reasons.append("multiple_core_info_missing_low_ceiling")
    elif missing_count >= 5:
        borderline_reasons.append("multiple_core_info_missing")
    elif missing_count >= 3 and ceiling == "low" and priority != "A" and not strong_school:
        drop_reasons.append("multiple_core_info_missing_low_ceiling")

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
        "ceiling_level": ceiling,
        "core_missing_count": missing_count,
        "alignment_flags": ";".join(sorted(alignment_flags)),
        "diversion_flags": ";".join(sorted(diversion_flags)),
        "resource_flags": ";".join(sorted(resource_flags)),
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
        "ceiling_level",
        "core_missing_count",
        "alignment_flags",
        "diversion_flags",
        "resource_flags",
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
