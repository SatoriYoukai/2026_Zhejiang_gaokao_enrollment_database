from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


KEEP_COLUMNS = [
    "volunteer_id",
    "college_code",
    "college_name",
    "major_code",
    "major_name",
    "major_base_key",
    "duration",
    "province",
    "city",
    "degree_level",
    "plan_count",
    "subject_requirement",
    "subject_key",
    "tuition",
    "tuition_raw",
    "remark",
    "2023_history_lowest_rank",
    "2024_history_lowest_rank",
    "2025_history_lowest_rank",
    "history_latest_rank",
    "history_years_matched",
]


def major_family(major: str) -> str:
    major = "" if pd.isna(major) else str(major)
    if any(k in major for k in ["计算机", "软件工程", "网络工程"]):
        return "cs"
    if any(k in major for k in ["人工智能", "智能科学"]):
        return "ai"
    if "信息与计算科学" in major:
        return "info_compute"
    if any(k in major for k in ["统计", "应用统计"]):
        return "statistics"
    if any(k in major for k in ["数学", "数据计算"]):
        return "math"
    return "other"


def trimmed_mean(values: pd.Series) -> float:
    xs = pd.to_numeric(values, errors="coerce").dropna().sort_values()
    if len(xs) == 0:
        return np.nan
    if len(xs) > 2:
        xs = xs.iloc[1:-1]
    return float(xs.mean())


def latest_history_rank(row: pd.Series) -> tuple[float, str, str]:
    for year in ["2025", "2024", "2023"]:
        value = row[f"{year}_history_lowest_rank"]
        if pd.notna(value):
            confidence = "high" if year == "2025" else "medium_high"
            return float(value), f"{year}_history", confidence
    return np.nan, "", ""


def main() -> None:
    source = Path.home() / "Documents" / "志愿填报" / "outputs" / "clean_database" / "volunteer_master_2026_with_history.csv"
    out_dir = Path(r"C:\Users\lsysir\Documents\gaokao_zytb_workspace\data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "rank_model_database.csv"

    df = pd.read_csv(source, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["2023_history_lowest_rank", "2024_history_lowest_rank", "2025_history_lowest_rank", "history_latest_rank", "plan_count"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["major_family_model"] = df["major_name"].map(major_family)

    latest = df.apply(latest_history_rank, axis=1, result_type="expand")
    latest.columns = ["rank_ref", "rank_ref_source", "rank_ref_confidence"]
    df[latest.columns] = latest

    school_anchor = (
        df[df["rank_ref"].notna()]
        .groupby("college_code")["rank_ref"]
        .apply(trimmed_mean)
        .rename("school_anchor_rank")
        .reset_index()
    )
    df = df.merge(school_anchor, on="college_code", how="left")

    missing = df["rank_ref"].isna()
    df.loc[missing, "rank_ref"] = df.loc[missing, "school_anchor_rank"]
    df.loc[missing & df["school_anchor_rank"].notna(), "rank_ref_source"] = "same_school_all_majors_trimmed_mean"
    df.loc[missing & df["school_anchor_rank"].notna(), "rank_ref_confidence"] = "low"
    still_missing = df["rank_ref"].isna()
    df.loc[still_missing, "rank_ref_source"] = "missing_need_user_input"
    df.loc[still_missing, "rank_ref_confidence"] = "need_user_input"

    keep = [c for c in KEEP_COLUMNS if c in df.columns]
    final = df[
        keep
        + [
            "major_family_model",
            "rank_ref",
            "rank_ref_source",
            "rank_ref_confidence",
            "school_anchor_rank",
        ]
    ].copy()
    final.to_csv(out, index=False, encoding="utf-8-sig")

    print("source", source)
    print("rows", len(final))
    print("rank_ref_missing", int(final["rank_ref"].isna().sum()))
    print("wrote", out)
    print("size_mb", round(out.stat().st_size / 1024 / 1024, 2))
    print(final["rank_ref_source"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
