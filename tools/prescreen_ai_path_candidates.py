from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs" / "clean_database" / "volunteer_master_2026_with_history.csv"
OUT_DIR = ROOT / "outputs" / "ai_path_candidates"
SHARD_DIR = OUT_DIR / "agent_shards"
LABEL_DIR = OUT_DIR / "agent_labels"

USER_RANK = 39000
TARGET_SUBJECTS = {"物理", "化学", "生物"}

LOW_FIT_SCHOOL_MARKERS = ("民办", "独立学院", "职业", "专科")
EXCLUDE_MAJOR_NAME_MARKERS = (
    "师范",
    "软件工程",
    "网络安全",
    "网络空间安全",
    "信息安全",
    "密码",
    "精算",
    "金融数学",
    "经济统计",
    "生物统计",
    "大气",
    "气象",
    "数据科学与大数据",
    "大数据管理",
    "大数据技术",
)
RISK_TEXT_MARKERS = (
    "软件工程",
    "网络安全",
    "网络空间安全",
    "信息安全",
    "密码",
    "经济统计",
    "生物统计",
    "数据科学",
    "数据科学与大数据",
    "大数据管理",
    "大数据技术",
    "卓师",
)

MATH_STAT_TERMS = (
    "信息与计算科学",
    "数学与应用数学",
    "数学类",
    "数理基础科学",
    "数据计算及应用",
    "统计学类",
    "统计学",
    "应用统计学",
)
CS_AI_TERMS = ("计算机科学与技术", "人工智能", "智能科学与技术")
CLASS_TERMS = ("计算机类", "数学类", "统计学类")
TRIAL_TERMS = ("试验班", "拔尖", "强基", "元培", "匡亚明")
TARGET_TERMS = MATH_STAT_TERMS + CS_AI_TERMS + CLASS_TERMS


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def to_number(value: object) -> float | None:
    text = clean_text(value).replace(",", "")
    if not text or text.lower() == "nan":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def subject_compatible(subject_key: str) -> bool:
    subject_key = clean_text(subject_key)
    if not subject_key or subject_key == "不限":
        return True
    required = {part for part in subject_key.split("&") if part}
    return required.issubset(TARGET_SUBJECTS)


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def classify_major(major_name: str, remark: str) -> tuple[bool, str, int, list[str], str]:
    text = f"{major_name} {remark}"
    if has_any(major_name, EXCLUDE_MAJOR_NAME_MARKERS) or "师范" in text:
        return False, "excluded_major", 0, ["excluded_major_name"], "专业名或备注命中排除项"

    risks: list[str] = []
    if has_any(remark, RISK_TEXT_MARKERS):
        risks.append("contains_excluded_major_in_remark")
    if "中外合作" in text or "合作办学" in text:
        risks.append("sino_foreign")
    if "校企" in text or "产业学院" in text:
        risks.append("industry_or_enterprise_track")

    if has_any(major_name, MATH_STAT_TERMS):
        category = "core_math_stat"
        fit = 100
        reason = "专业名直接命中数学/统计核心池"
    elif has_any(major_name, CS_AI_TERMS):
        category = "core_cs_ai"
        fit = 96
        reason = "专业名直接命中计算机/AI核心池"
    elif has_any(major_name, CLASS_TERMS):
        category = "target_class"
        fit = 74
        risks.append("class_diversion")
        reason = "专业名为目标相关大类，需后续核验分流"
    elif has_any(major_name, TRIAL_TERMS) and has_any(text, TARGET_TERMS):
        category = "trial_class"
        fit = 66
        risks.append("trial_or_experimental_class")
        risks.append("class_diversion")
        reason = "试验班/拔尖班备注含目标方向，需核验分流"
    elif has_any(text, TARGET_TERMS):
        category = "target_in_remark"
        fit = 58
        risks.append("target_only_in_remark")
        reason = "目标方向只出现在备注或培养说明中"
    else:
        return False, "not_target", 0, [], "未命中目标专业池"

    return True, category, fit, sorted(set(risks)), reason


def rank_band(rank: float | None) -> str:
    if rank is None:
        return "无历史"
    if rank <= 18000:
        return "超冲"
    if rank <= 32000:
        return "冲"
    if rank <= 46000:
        return "贴合"
    if rank <= 65000:
        return "稳"
    if rank <= 90000:
        return "保"
    if rank <= 120000:
        return "低优先保底"
    return "远保底"


def rank_score(band: str) -> int:
    return {
        "超冲": 8,
        "冲": 24,
        "贴合": 35,
        "稳": 32,
        "保": 22,
        "低优先保底": 8,
        "远保底": -12,
        "无历史": 14,
    }.get(band, 0)


def weighted_rank(row: pd.Series) -> float | None:
    parts: list[tuple[float, float]] = []
    for year, weight in (("2023", 0.2), ("2024", 0.3), ("2025", 0.5)):
        rank = to_number(row.get(f"{year}_history_lowest_rank"))
        if rank is not None:
            parts.append((rank, weight))
    if not parts:
        return None
    total_weight = sum(weight for _, weight in parts)
    return sum(rank * weight for rank, weight in parts) / total_weight


def history_ranks(row: pd.Series) -> list[float]:
    ranks = []
    for year in ("2023", "2024", "2025"):
        rank = to_number(row.get(f"{year}_history_lowest_rank"))
        if rank is not None:
            ranks.append(rank)
    return ranks


def risk_penalty(flags: list[str]) -> int:
    penalty = 0
    weights = {
        "contains_excluded_major_in_remark": 18,
        "class_diversion": 18,
        "trial_or_experimental_class": 8,
        "target_only_in_remark": 14,
        "sino_foreign": 12,
        "industry_or_enterprise_track": 8,
        "new_no_history": 9,
        "small_plan": 8,
        "high_rank_volatility": 7,
        "very_high_tuition": 8,
        "low_fit_school": 100,
    }
    for flag in flags:
        penalty += weights.get(flag, 0)
    return penalty


def label_priority(score: float) -> str:
    if score >= 100:
        return "A"
    if score >= 84:
        return "B"
    if score >= 68:
        return "C"
    if score >= 52:
        return "D"
    return "E"


def build_candidates() -> pd.DataFrame:
    df = pd.read_csv(INPUT, dtype=str, encoding="utf-8-sig").fillna("")
    records: list[dict[str, object]] = []

    for _, row in df.iterrows():
        college_name = clean_text(row.get("college_name"))
        major_name = clean_text(row.get("major_name"))
        remark = clean_text(row.get("remark"))
        if clean_text(row.get("degree_level")) != "本科":
            continue
        if not subject_compatible(clean_text(row.get("subject_key"))):
            continue

        school_risks = []
        if has_any(college_name, LOW_FIT_SCHOOL_MARKERS):
            school_risks.append("low_fit_school")

        keep, category, fit, major_risks, reason = classify_major(major_name, remark)
        if not keep:
            continue
        risks = sorted(set(school_risks + major_risks))
        if "low_fit_school" in risks:
            continue

        ranks = history_ranks(row)
        center = weighted_rank(row)
        volatility = max(ranks) - min(ranks) if len(ranks) >= 2 else 0
        if not ranks:
            risks.append("new_no_history")
        if volatility >= 30000:
            risks.append("high_rank_volatility")
        plan_count = to_number(row.get("plan_count")) or 0
        if plan_count <= 2:
            risks.append("small_plan")
        tuition = to_number(row.get("tuition"))
        if tuition is not None and tuition >= 20000:
            risks.append("very_high_tuition")

        latest_admitted = None
        for year in ("2025", "2024", "2023"):
            latest_admitted = to_number(row.get(f"{year}_history_admitted_count"))
            if latest_admitted is not None:
                break
        plan_delta = plan_count - latest_admitted if latest_admitted is not None else None

        records.append(
            {
                "volunteer_id": clean_text(row.get("volunteer_id")),
                "college_code": clean_text(row.get("college_code")),
                "college_name": college_name,
                "major_code": clean_text(row.get("major_code")),
                "major_name": major_name,
                "major_category": category,
                "major_fit_score": fit,
                "major_fit_reason": reason,
                "province": clean_text(row.get("province")),
                "city": clean_text(row.get("city")),
                "duration": clean_text(row.get("duration")),
                "degree_level": clean_text(row.get("degree_level")),
                "subject_key": clean_text(row.get("subject_key")),
                "subject_requirement": clean_text(row.get("subject_requirement")),
                "plan_count": int(plan_count) if plan_count else 0,
                "tuition": tuition,
                "remark": remark,
                "history_years_matched": int(to_number(row.get("history_years_matched")) or 0),
                "rank_2023": to_number(row.get("2023_history_lowest_rank")),
                "rank_2024": to_number(row.get("2024_history_lowest_rank")),
                "rank_2025": to_number(row.get("2025_history_lowest_rank")),
                "score_2025": to_number(row.get("2025_history_lowest_score")),
                "rank_weighted_center": center,
                "rank_volatility": volatility,
                "plan_delta_vs_latest_admit": plan_delta,
                "risk_flags": ";".join(sorted(set(risks))),
                "source_history_ranks": clean_text(row.get("history_ranks")),
            }
        )

    out = pd.DataFrame(records)
    if out.empty:
        return out

    known = out[out["rank_weighted_center"].notna()].copy()
    school_medians = known.groupby("college_code")["rank_weighted_center"].median().to_dict()
    category_medians = known.groupby("major_category")["rank_weighted_center"].median().to_dict()
    global_median = float(known["rank_weighted_center"].median())

    predicted = []
    certainty = []
    for _, row in out.iterrows():
        center = row["rank_weighted_center"]
        if pd.notna(center):
            predicted.append(float(center))
            certainty.append("history")
            continue
        school = school_medians.get(row["college_code"])
        category = category_medians.get(row["major_category"])
        if school is not None and category is not None:
            predicted.append(float(0.65 * school + 0.35 * category))
            certainty.append("school_category_proxy")
        elif school is not None:
            predicted.append(float(school))
            certainty.append("school_proxy")
        elif category is not None:
            predicted.append(float(category))
            certainty.append("category_proxy")
        else:
            predicted.append(global_median)
            certainty.append("global_proxy")

    out["predicted_rank"] = predicted
    out["rank_certainty"] = certainty
    out["rank_band"] = out["predicted_rank"].apply(rank_band)

    scores = []
    for _, row in out.iterrows():
        flags = [f for f in clean_text(row["risk_flags"]).split(";") if f]
        score = float(row["major_fit_score"]) + rank_score(clean_text(row["rank_band"])) - risk_penalty(flags)
        if row["history_years_matched"] >= 3:
            score += 5
        elif row["history_years_matched"] == 2:
            score += 3
        if row["plan_count"] >= 10:
            score += 4
        elif row["plan_count"] >= 5:
            score += 2
        if row["plan_delta_vs_latest_admit"] is not None:
            if row["plan_delta_vs_latest_admit"] >= 5:
                score += 3
            elif row["plan_delta_vs_latest_admit"] <= -3:
                score -= 4
        scores.append(score)

    out["prescreen_score"] = scores
    out["prescreen_priority"] = out["prescreen_score"].apply(label_priority)
    out = out.sort_values(
        by=["prescreen_score", "major_fit_score", "predicted_rank", "plan_count"],
        ascending=[False, False, True, False],
    ).reset_index(drop=True)
    out.insert(0, "pool_rank", range(1, len(out) + 1))
    return out


def write_shards(wide: pd.DataFrame) -> None:
    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    shard_cols = [
        "pool_id",
        "volunteer_id",
        "college_name",
        "major_name",
        "major_category",
        "major_fit_score",
        "rank_band",
        "predicted_rank",
        "rank_certainty",
        "history_years_matched",
        "plan_count",
        "risk_flags",
        "remark",
    ]
    for shard_index in range(12):
        part = wide.iloc[shard_index::12].copy()
        path = SHARD_DIR / f"shard_{shard_index + 1:02d}.csv"
        part[shard_cols].to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def summarize(df: pd.DataFrame, wide: pd.DataFrame) -> dict[str, object]:
    def vc(frame: pd.DataFrame, col: str) -> dict[str, int]:
        return {str(k): int(v) for k, v in frame[col].value_counts(dropna=False).items()}

    return {
        "input_rows": int(pd.read_csv(INPUT, usecols=["volunteer_id"], dtype=str).shape[0]),
        "eligible_target_rows": int(len(df)),
        "wide_rows": int(len(wide)),
        "wide_by_major_category": vc(wide, "major_category"),
        "wide_by_rank_band": vc(wide, "rank_band"),
        "wide_by_rank_certainty": vc(wide, "rank_certainty"),
        "wide_no_history_rows": int((wide["history_years_matched"] == 0).sum()),
        "wide_risk_flag_rows": int(wide["risk_flags"].astype(str).str.len().gt(0).sum()),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = build_candidates()
    wide = candidates.head(900).copy()
    wide.insert(0, "pool_id", range(1, len(wide) + 1))

    candidates.to_csv(OUT_DIR / "eligible_target_pool.csv", index=False, encoding="utf-8-sig")
    wide.to_csv(OUT_DIR / "wide_pool_900.csv", index=False, encoding="utf-8-sig")
    wide.to_json(OUT_DIR / "wide_pool_900.json", orient="records", force_ascii=False, indent=2)
    write_shards(wide)

    summary = summarize(candidates, wide)
    (OUT_DIR / "prescreen_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
