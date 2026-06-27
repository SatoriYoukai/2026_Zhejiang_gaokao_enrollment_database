from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_900_mini"

TAG_REPLACEMENTS = {
    "very_high_tuition": "very_high_tuition_possible",
    "high_tuition": "very_high_tuition_possible",
    "tuition_high": "very_high_tuition_possible",
    "new_major_no_history": "new_no_history",
    "no_history": "new_no_history",
    "small_enrollment": "small_plan",
    "high_rank_volatility": "",
    "contains_excluded_major_in_remark": "major_diversion_risk",
    "target_only_in_remark": "major_diversion_risk",
    "class_diversion": "major_diversion_risk",
    "policy_year_unclear": "",
    "department_unclear": "",
    "training_plan_not_found": "",
    "recommendation_not_found": "",
    "transfer_policy_not_found": "",
    "campus_unclear": "",
    "dorm_unclear": "",
    "forum_signal_sparse": "",
}

SOURCE_TYPE_REPLACEMENTS = {
    "course": "other",
}

SOURCE_REF_COLUMNS = [
    "research_resources_source_ids",
    "recommendation_source_ids",
    "dorm_campus_source_ids",
    "source_ids",
]

STATUS_REPLACEMENTS = {
    "": "partial",
    "unknown": "partial",
    "incomplete": "partial",
    "partially_found": "partial",
}

CONFIDENCE_REPLACEMENTS = {
    "": "low",
    "unknown": "low",
}


def split_cell(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [part.strip() for part in re.split(r"[;；,，\s]+", str(value)) if part.strip()]


def normalize_tag_cell(value: object) -> str:
    tags = []
    for tag in split_cell(value):
        replacement = TAG_REPLACEMENTS.get(tag, tag)
        if replacement and replacement not in tags:
            tags.append(replacement)
    return ";".join(tags)


def normalize_source_refs(value: object, valid_source_ids: set[str]) -> str:
    ignored = {"not_found", "none", "nan", "na", "n/a", "-"}
    refs = []
    for ref in split_cell(value):
        if ref.lower() in ignored:
            continue
        if ref in valid_source_ids and ref not in refs:
            refs.append(ref)
    return ";".join(refs)


def normalize_file(path: Path) -> bool:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    changed = False
    if "crawl_status" in df.columns:
        old_status = df["crawl_status"].copy()
        df["crawl_status"] = df["crawl_status"].map(lambda value: STATUS_REPLACEMENTS.get(str(value).strip().lower(), str(value).strip().lower()))
        df.loc[df["crawl_status"].isin(["low", "medium", "high"]), "crawl_status"] = "partial"
        changed = changed or not old_status.equals(df["crawl_status"])
    if "agent_confidence" in df.columns:
        old_confidence = df["agent_confidence"].copy()
        df["agent_confidence"] = df["agent_confidence"].map(
            lambda value: CONFIDENCE_REPLACEMENTS.get(str(value).strip().lower(), str(value).strip().lower())
        )
        df.loc[df["agent_confidence"].isin(["complete", "partial", "not_found"]), "agent_confidence"] = "low"
        valid_confidence = {"high", "medium", "low"}
        df.loc[~df["agent_confidence"].isin(valid_confidence), "agent_confidence"] = "low"
        changed = changed or not old_confidence.equals(df["agent_confidence"])
    for column in ["risk_tags", "uncertainty_tags"]:
        if column in df.columns:
            old = df[column].copy()
            df[column] = df[column].map(normalize_tag_cell)
            changed = changed or not old.equals(df[column])
    source_path = Path(str(path).replace("_light_crawl_rows.csv", "_sources.csv"))
    if source_path.exists():
        sources = pd.read_csv(source_path, dtype=str, encoding="utf-8-sig").fillna("")
        if "source_type" in sources.columns:
            old_source_type = sources["source_type"].copy()
            sources["source_type"] = sources["source_type"].map(lambda value: SOURCE_TYPE_REPLACEMENTS.get(value, value))
            if not old_source_type.equals(sources["source_type"]):
                sources.to_csv(source_path, index=False, encoding="utf-8-sig")
                changed = True
        if "source_id" in sources.columns:
            valid_source_ids = set(sources["source_id"].astype(str))
            for column in SOURCE_REF_COLUMNS:
                if column in df.columns:
                    old_refs = df[column].copy()
                    df[column] = df[column].map(lambda value: normalize_source_refs(value, valid_source_ids))
                    changed = changed or not old_refs.equals(df[column])
    if changed:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize minor mechanical issues in light-crawl outputs.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.run_dir.resolve() / "outputs"
    changed = []
    for path in sorted(output_dir.glob("*_light_crawl_rows.csv")):
        if normalize_file(path):
            changed.append(str(path))
    print("\n".join(changed) if changed else "no changes")


if __name__ == "__main__":
    main()
