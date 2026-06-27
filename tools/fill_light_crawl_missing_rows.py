from __future__ import annotations

import argparse
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


def fill_shard(input_dir: Path, output_dir: Path, shard_id: str) -> int:
    input_path = input_dir / f"{shard_id}_input.csv"
    rows_path = output_dir / f"{shard_id}_light_crawl_rows.csv"
    if not input_path.exists() or not rows_path.exists():
        return 0

    expected = pd.read_csv(input_path, dtype=str, encoding="utf-8-sig").fillna("")
    rows = pd.read_csv(rows_path, dtype=str, encoding="utf-8-sig").fillna("")
    missing = expected[~expected["pool_id"].isin(set(rows["pool_id"].astype(str)))]
    if missing.empty:
        return 0

    additions = []
    for _, item in missing.iterrows():
        additions.append(
            {
                "pool_id": item["pool_id"],
                "volunteer_id": item["volunteer_id"],
                "college_name": item["college_name"],
                "major_name": item["major_name"],
                "crawl_status": "not_found",
                "department_name": "",
                "department_url": "",
                "major_intro_url": "",
                "training_plan_url": "",
                "training_plan_year": "",
                "core_courses_summary": "not_found",
                "ai_path_fit_notes": "not_found; added by main-thread completeness fill after subagent omitted this input row",
                "math_foundation_notes": "not_found",
                "cs_ai_foundation_notes": "not_found",
                "research_resources_notes": "not_found",
                "research_resources_source_ids": "",
                "recommendation_or_honors_notes": "not_found",
                "postgraduate_path_notes": "not_found",
                "recommendation_policy_notes": "not_found",
                "recommendation_source_ids": "",
                "transfer_policy_notes": "not_found",
                "learning_freedom_notes": "not_found",
                "dorm_campus_notes": "not_found",
                "dorm_campus_source_ids": "",
                "risk_tags": "",
                "uncertainty_tags": "training_plan_not_found;recommendation_not_found;transfer_policy_not_found;department_unclear;campus_unclear;dorm_unclear",
                "nonofficial_signals": "",
                "source_ids": "",
                "next_deep_questions": "Subagent omitted this input row; deep crawl must verify all core facts.",
                "agent_confidence": "low",
            }
        )

    rows = pd.concat([rows, pd.DataFrame(additions)], ignore_index=True)
    rows = rows[ROW_COLUMNS]
    expected_order = expected[["pool_id"]].reset_index().rename(columns={"index": "_order"})
    rows = rows.merge(expected_order, on="pool_id", how="left").sort_values("_order").drop(columns=["_order"])
    rows.to_csv(rows_path, index=False, encoding="utf-8-sig")
    return len(additions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill missing light-crawl output rows with low-confidence not_found placeholders.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    input_dir = run_dir / "input_shards"
    output_dir = run_dir / "outputs"
    filled = {}
    for path in sorted(input_dir.glob("shard_*_input.csv")):
        shard_id = path.name.replace("_input.csv", "")
        count = fill_shard(input_dir, output_dir, shard_id)
        if count:
            filled[shard_id] = count
    print(filled if filled else "no missing rows filled")


if __name__ == "__main__":
    main()
