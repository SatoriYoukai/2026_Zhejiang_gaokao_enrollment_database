from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_900_mini"

IDENTITY_COLUMNS = ["pool_id", "volunteer_id", "college_name", "major_name"]


def repair_shard(input_dir: Path, output_dir: Path, shard_id: str) -> int:
    input_path = input_dir / f"{shard_id}_input.csv"
    rows_path = output_dir / f"{shard_id}_light_crawl_rows.csv"
    if not input_path.exists() or not rows_path.exists():
        return 0
    expected = pd.read_csv(input_path, dtype=str, encoding="utf-8-sig").fillna("")
    rows = pd.read_csv(rows_path, dtype=str, encoding="utf-8-sig").fillna("")
    expected_map = expected.set_index("pool_id")[IDENTITY_COLUMNS[1:]].to_dict(orient="index")
    changed = 0
    for index, row in rows.iterrows():
        pool_id = str(row["pool_id"])
        if pool_id not in expected_map:
            continue
        for column in IDENTITY_COLUMNS[1:]:
            expected_value = expected_map[pool_id][column]
            if str(row[column]) != expected_value:
                rows.at[index, column] = expected_value
                changed += 1
    if changed:
        rows.to_csv(rows_path, index=False, encoding="utf-8-sig")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair identity columns in light-crawl rows from the input shard.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    input_dir = run_dir / "input_shards"
    output_dir = run_dir / "outputs"
    repaired = {}
    for path in sorted(input_dir.glob("shard_*_input.csv")):
        shard_id = path.name.replace("_input.csv", "")
        count = repair_shard(input_dir, output_dir, shard_id)
        if count:
            repaired[shard_id] = count
    print(repaired if repaired else "no identity repairs")


if __name__ == "__main__":
    main()
