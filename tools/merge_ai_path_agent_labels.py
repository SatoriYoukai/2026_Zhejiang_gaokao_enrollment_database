from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "ai_path_candidates"
WIDE_PATH = OUT_DIR / "wide_pool_900.csv"
LABEL_DIR = OUT_DIR / "agent_labels"
FALLBACK_LABEL_DIR = OUT_DIR / "agent_labels_fallback"

REQUIRED_LABEL_COLUMNS = [
    "pool_id",
    "agent_major_category",
    "agent_major_fit",
    "agent_keep_priority",
    "agent_risk_level",
    "agent_exclude_hint",
    "agent_notes",
]

RANK_QUOTAS = {
    "超冲": 35,
    "冲": 40,
    "贴合": 60,
    "稳": 65,
    "保": 60,
    "低优先保底": 30,
    "远保底": 10,
}
NO_HISTORY_MIN = 30
PROFILE = os.environ.get("AI_PATH_PROFILE", "balanced")
OUTPUT_SUFFIX = "_math_first" if PROFILE == "math_first" else ""


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def to_number(value: object, default: float = 0) -> float:
    text = clean_text(value).replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def load_labels() -> pd.DataFrame:
    frames = []
    missing = []
    for index in range(1, 13):
        path = LABEL_DIR / f"shard_{index:02d}_labels.csv"
        if not path.exists():
            missing.append(str(path))
            continue
        frame = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
        missing_cols = [col for col in REQUIRED_LABEL_COLUMNS if col not in frame.columns]
        if missing_cols:
            raise ValueError(f"{path} missing columns: {missing_cols}")
        frame = frame[REQUIRED_LABEL_COLUMNS]
        frame["agent_shard"] = f"shard_{index:02d}"
        frames.append(frame)
    if missing:
        raise FileNotFoundError("missing label files:\n" + "\n".join(missing))
    labels = pd.concat(frames, ignore_index=True)
    duplicated = labels["pool_id"][labels["pool_id"].duplicated()].unique().tolist()
    if duplicated:
        raise ValueError(f"duplicated pool_id in labels: {duplicated[:20]}")
    return labels


def build_fallback_labels() -> pd.DataFrame:
    wide = pd.read_csv(WIDE_PATH, dtype=str, encoding="utf-8-sig").fillna("")
    records = []
    for _, row in wide.iterrows():
        category = clean_text(row["major_category"])
        fit = to_number(row["major_fit_score"])
        flags = {f for f in clean_text(row["risk_flags"]).split(";") if f}
        exclude = "no"
        risk = "low"
        priority = 4

        if category in {"target_class", "trial_class", "target_in_remark"}:
            risk = "high" if "contains_excluded_major_in_remark" in flags or "class_diversion" in flags else "medium"
            priority = 2 if risk == "high" else 3
        if "contains_excluded_major_in_remark" in flags:
            exclude = "yes"
        if "sino_foreign" in flags or "very_high_tuition" in flags or "new_no_history" in flags:
            risk = "medium" if risk == "low" else risk
        if "class_diversion" in flags and category != "core_math_stat":
            priority = min(priority, 3)
        if category in {"core_math_stat", "core_cs_ai"} and exclude == "no":
            priority = 5 if fit >= 96 and risk == "low" else 4
        if clean_text(row["rank_band"]) in {"远保底"}:
            priority = min(priority, 3)

        records.append(
            {
                "pool_id": row["pool_id"],
                "agent_major_category": category,
                "agent_major_fit": int(fit),
                "agent_keep_priority": priority,
                "agent_risk_level": risk,
                "agent_exclude_hint": exclude,
                "agent_notes": "兜底规则标签",
            }
        )

    labels = pd.DataFrame(records)
    FALLBACK_LABEL_DIR.mkdir(parents=True, exist_ok=True)
    for index in range(1, 13):
        shard_ids = pd.read_csv(OUT_DIR / "agent_shards" / f"shard_{index:02d}.csv", dtype=str, encoding="utf-8-sig")[
            "pool_id"
        ].astype(str)
        labels[labels["pool_id"].astype(str).isin(shard_ids)].to_csv(
            FALLBACK_LABEL_DIR / f"shard_{index:02d}_labels.csv", index=False, encoding="utf-8-sig"
        )
    return labels


def normalize_agent_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["agent_major_fit"] = df["agent_major_fit"].apply(to_number).clip(0, 100)
    df["agent_keep_priority"] = df["agent_keep_priority"].apply(to_number).clip(1, 5)
    df["agent_risk_level"] = df["agent_risk_level"].str.lower().replace(
        {"中": "medium", "高": "high", "低": "low"}
    )
    df.loc[~df["agent_risk_level"].isin(["low", "medium", "high"]), "agent_risk_level"] = "medium"
    df["agent_exclude_hint"] = df["agent_exclude_hint"].str.lower().replace(
        {"是": "yes", "否": "no", "true": "yes", "false": "no"}
    )
    df.loc[~df["agent_exclude_hint"].isin(["yes", "no"]), "agent_exclude_hint"] = "no"
    return df


def final_score(row: pd.Series) -> float:
    risk_penalty = {"low": 0, "medium": 5, "high": 13}.get(clean_text(row["agent_risk_level"]), 5)
    exclude_penalty = 45 if clean_text(row["agent_exclude_hint"]).lower() == "yes" else 0
    category_penalty = 28 if clean_text(row["agent_major_category"]) == "reject" else 0
    score = (
        to_number(row["prescreen_score"]) * 0.62
        + to_number(row["agent_major_fit"]) * 0.28
        + to_number(row["agent_keep_priority"]) * 6
        - risk_penalty
        - exclude_penalty
        - category_penalty
    )
    if PROFILE == "math_first":
        if clean_text(row["major_category"]) == "core_math_stat":
            score += 9
        elif clean_text(row["major_category"]) == "core_cs_ai":
            score -= 6
            if clean_text(row["rank_band"]) in {"保", "低优先保底", "远保底"}:
                score -= 6
    return score


def select_by_quota(df: pd.DataFrame) -> pd.DataFrame:
    selected_ids: set[int] = set()
    selected_frames: list[pd.DataFrame] = []

    eligible = df[
        ~(
            (df["agent_exclude_hint"].str.lower() == "yes")
            & (df["agent_keep_priority"] <= 2)
        )
    ].copy()

    if PROFILE == "math_first":
        ordered = eligible.sort_values(
            by=["final_score", "agent_keep_priority", "agent_major_fit", "predicted_rank"],
            ascending=[False, False, False, True],
        )
        math_part = ordered[ordered["major_category"] == "core_math_stat"].head(200)
        cs_part = ordered[ordered["major_category"] == "core_cs_ai"].head(100)
        selected = pd.concat([math_part, cs_part], ignore_index=True).drop_duplicates(subset=["pool_id"])
        if len(selected) < 300:
            selected_ids = set(selected["pool_id"].astype(int).tolist())
            fill = ordered[~ordered["pool_id"].astype(int).isin(selected_ids)].head(300 - len(selected))
            selected = pd.concat([selected, fill], ignore_index=True)

        no_history_count = int((selected["history_years_matched"].astype(float) == 0).sum())
        if no_history_count < NO_HISTORY_MIN:
            need = NO_HISTORY_MIN - no_history_count
            selected_ids = set(selected["pool_id"].astype(int).tolist())
            no_history_extra = ordered[
                (ordered["history_years_matched"].astype(float) == 0)
                & ~ordered["pool_id"].astype(int).isin(selected_ids)
            ].head(need)
            replaceable = selected[selected["history_years_matched"].astype(float) != 0].sort_values(
                by=["final_score"], ascending=True
            ).head(len(no_history_extra))
            selected = selected[~selected["pool_id"].astype(int).isin(replaceable["pool_id"].astype(int))]
            selected = pd.concat([selected, no_history_extra], ignore_index=True)

        selected = selected.sort_values(
            by=["major_category", "final_score", "agent_keep_priority", "agent_major_fit", "predicted_rank"],
            ascending=[False, False, False, False, True],
        ).head(300)
        selected = selected.reset_index(drop=True)
        selected.insert(0, "final_rank", range(1, len(selected) + 1))
        return selected

    for band, quota in RANK_QUOTAS.items():
        part = eligible[eligible["rank_band"] == band].sort_values(
            by=["final_score", "agent_keep_priority", "agent_major_fit", "predicted_rank"],
            ascending=[False, False, False, True],
        )
        take = part.head(quota)
        selected_frames.append(take)
        selected_ids.update(take["pool_id"].astype(int).tolist())

    selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    if len(selected) < 300:
        remaining = eligible[~eligible["pool_id"].astype(int).isin(selected_ids)].sort_values(
            by=["final_score", "agent_keep_priority", "agent_major_fit"],
            ascending=[False, False, False],
        )
        selected = pd.concat([selected, remaining.head(300 - len(selected))], ignore_index=True)

    no_history_count = int((selected["history_years_matched"].astype(float) == 0).sum())
    if no_history_count < NO_HISTORY_MIN:
        need = NO_HISTORY_MIN - no_history_count
        selected_ids = set(selected["pool_id"].astype(int).tolist())
        no_history_extra = eligible[
            (eligible["history_years_matched"].astype(float) == 0)
            & ~eligible["pool_id"].astype(int).isin(selected_ids)
        ].sort_values(
            by=["final_score", "agent_keep_priority", "agent_major_fit"],
            ascending=[False, False, False],
        ).head(need)
        if not no_history_extra.empty:
            selected = pd.concat([selected, no_history_extra], ignore_index=True)

    selected = selected.sort_values(
        by=["final_score", "agent_keep_priority", "agent_major_fit", "predicted_rank"],
        ascending=[False, False, False, True],
    ).drop_duplicates(subset=["pool_id"], keep="first")

    if len(selected) > 300:
        no_history = selected[selected["history_years_matched"].astype(float) == 0]
        history = selected[selected["history_years_matched"].astype(float) != 0]
        keep_no_history = no_history.head(min(NO_HISTORY_MIN, len(no_history)))
        remaining_slots = 300 - len(keep_no_history)
        history_and_extra = pd.concat(
            [
                history,
                no_history[~no_history["pool_id"].astype(int).isin(keep_no_history["pool_id"].astype(int))],
            ],
            ignore_index=True,
        ).sort_values(
            by=["final_score", "agent_keep_priority", "agent_major_fit", "predicted_rank"],
            ascending=[False, False, False, True],
        )
        selected = pd.concat([keep_no_history, history_and_extra.head(remaining_slots)], ignore_index=True)

    selected = selected.reset_index(drop=True)
    selected.insert(0, "final_rank", range(1, len(selected) + 1))
    return selected


def summarize(merged: pd.DataFrame, selected: pd.DataFrame) -> dict[str, object]:
    def vc(frame: pd.DataFrame, col: str) -> dict[str, int]:
        return {str(k): int(v) for k, v in frame[col].value_counts(dropna=False).items()}

    return {
        "wide_rows": int(len(merged)),
        "selected_rows": int(len(selected)),
        "selected_by_rank_band": vc(selected, "rank_band"),
        "selected_by_major_category": vc(selected, "major_category"),
        "selected_by_agent_category": vc(selected, "agent_major_category"),
        "selected_by_agent_risk_level": vc(selected, "agent_risk_level"),
        "selected_no_history_rows": int((selected["history_years_matched"].astype(float) == 0).sum()),
        "selected_agent_exclude_hint_rows": int((selected["agent_exclude_hint"].str.lower() == "yes").sum()),
        "backup_rows": int(len(merged) - len(selected)),
    }


def main() -> None:
    wide = pd.read_csv(WIDE_PATH, dtype=str, encoding="utf-8-sig").fillna("")
    try:
        labels = load_labels()
        label_source = "subagent"
    except FileNotFoundError:
        labels = build_fallback_labels()
        label_source = "fallback"
    labels = normalize_agent_values(labels)
    merged = wide.merge(labels, on="pool_id", how="left", validate="one_to_one")
    if merged[REQUIRED_LABEL_COLUMNS[1]].isna().any():
        missing = merged.loc[merged[REQUIRED_LABEL_COLUMNS[1]].isna(), "pool_id"].tolist()
        raise ValueError(f"missing labels for pool ids: {missing[:20]}")

    merged["prescreen_score"] = merged["prescreen_score"].apply(to_number)
    merged["predicted_rank"] = merged["predicted_rank"].apply(to_number)
    merged["history_years_matched"] = merged["history_years_matched"].apply(to_number)
    merged["final_score"] = merged.apply(final_score, axis=1)
    merged["category_disagreement"] = merged["major_category"] != merged["agent_major_category"]
    merged = merged.sort_values(
        by=["final_score", "agent_keep_priority", "agent_major_fit", "predicted_rank"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    selected = select_by_quota(merged)
    selected_ids = set(selected["pool_id"].astype(int).tolist())
    backup = merged[~merged["pool_id"].astype(int).isin(selected_ids)].copy()
    backup = backup.sort_values(by=["final_score"], ascending=False).reset_index(drop=True)

    merged.to_csv(OUT_DIR / f"wide_pool_900_with_agent_labels{OUTPUT_SUFFIX}.csv", index=False, encoding="utf-8-sig")
    merged.to_json(
        OUT_DIR / f"wide_pool_900_with_agent_labels{OUTPUT_SUFFIX}.json",
        orient="records",
        force_ascii=False,
        indent=2,
    )
    selected.to_csv(OUT_DIR / f"candidate_300{OUTPUT_SUFFIX}.csv", index=False, encoding="utf-8-sig")
    selected.to_json(OUT_DIR / f"candidate_300{OUTPUT_SUFFIX}.json", orient="records", force_ascii=False, indent=2)
    backup.to_csv(OUT_DIR / f"backup_pool_600{OUTPUT_SUFFIX}.csv", index=False, encoding="utf-8-sig")
    backup.to_json(OUT_DIR / f"backup_pool_600{OUTPUT_SUFFIX}.json", orient="records", force_ascii=False, indent=2)

    summary = summarize(merged, selected)
    summary["label_source"] = label_source
    summary["profile"] = PROFILE
    (OUT_DIR / f"selection_summary{OUTPUT_SUFFIX}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
