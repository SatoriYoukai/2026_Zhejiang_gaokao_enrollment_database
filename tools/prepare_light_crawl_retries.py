from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from prepare_light_crawl_900 import DEFAULT_OUT_DIR, make_prompt


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAILED_OR_MISSING_SHARDS = ["shard_12", "shard_13", "shard_15", "shard_16", "shard_19", "shard_23", "shard_24"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare smaller retry shards for failed light-crawl shards.")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--failed-shards", nargs="*", default=DEFAULT_FAILED_OR_MISSING_SHARDS)
    parser.add_argument("--model", default="gpt-5.4-mini")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    input_dir = run_dir / "input_shards"
    retry_dir = run_dir / "retry_shards"
    output_dir = run_dir / "outputs"
    log_dir = run_dir / "logs"

    retry_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for shard_id in args.failed_shards:
        input_path = input_dir / f"{shard_id}_input.csv"
        if not input_path.exists():
            raise FileNotFoundError(input_path)
        df = pd.read_csv(input_path, dtype=str, encoding="utf-8-sig").fillna("")
        midpoint = (len(df) + 1) // 2
        parts = [("a", df.iloc[:midpoint].copy()), ("b", df.iloc[midpoint:].copy())]
        for suffix, part in parts:
            retry_id = f"{shard_id}{suffix}"
            csv_path = retry_dir / f"{retry_id}_input.csv"
            json_path = retry_dir / f"{retry_id}_input.json"
            prompt_path = retry_dir / f"{retry_id}_prompt.md"
            rows_csv = output_dir / f"{retry_id}_light_crawl_rows.csv"
            sources_csv = output_dir / f"{retry_id}_sources.csv"
            notes_md = log_dir / f"{retry_id}_notes.md"

            part.to_csv(csv_path, index=False, encoding="utf-8-sig")
            json_path.write_text(part.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8-sig")
            prompt_path.write_text(
                make_prompt(
                    shard_id=retry_id,
                    input_csv=csv_path,
                    input_json=json_path,
                    rows_csv=rows_csv,
                    sources_csv=sources_csv,
                    notes_md=notes_md,
                    row_count=len(part),
                    school_count=part["college_name"].nunique(),
                    model=args.model,
                    purpose=f"retry for failed parent shard {shard_id}",
                ),
                encoding="utf-8-sig",
            )
            manifest.append(
                {
                    "retry_id": retry_id,
                    "parent_shard_id": shard_id,
                    "input_csv": str(csv_path),
                    "input_json": str(json_path),
                    "prompt": str(prompt_path),
                    "rows_csv": str(rows_csv),
                    "sources_csv": str(sources_csv),
                    "notes_md": str(notes_md),
                    "row_count": int(len(part)),
                    "school_count": int(part["college_name"].nunique()),
                }
            )
    (run_dir / "retry_manifest.json").write_text(json.dumps({"retries": manifest}, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    pd.DataFrame(manifest).to_csv(run_dir / "retry_manifest.csv", index=False, encoding="utf-8-sig")
    print(json.dumps({"retry_count": len(manifest), "rows": int(sum(item["row_count"] for item in manifest))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
