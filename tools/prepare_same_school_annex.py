from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_RUN_DIR = Path("outputs/ai_path_candidates/deep_crawl_201_v1_20260627")
DEFAULT_BORDERLINE = Path("outputs/ai_path_candidates/light_crawl_triage_v2_20260627/borderline_review.csv")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--borderline", type=Path, default=DEFAULT_BORDERLINE)
    args = parser.parse_args()

    selected_path = args.run_dir / "selected_schools.csv"
    if not selected_path.exists():
        raise SystemExit(f"Missing selected_schools.csv: {selected_path}")
    if not args.borderline.exists():
        raise SystemExit(f"Missing borderline_review.csv: {args.borderline}")

    selected = pd.read_csv(selected_path, dtype=str, encoding="utf-8-sig").fillna("")
    borderline = pd.read_csv(args.borderline, dtype=str, encoding="utf-8-sig").fillna("")

    school_key_by_name = dict(zip(selected["college_name"], selected["school_key"]))
    annex = borderline[borderline["college_name"].isin(school_key_by_name)].copy()
    annex.insert(0, "school_key", annex["college_name"].map(school_key_by_name))
    annex = annex.sort_values(["school_key", "prescreen_priority", "predicted_rank", "major_name"], kind="stable")

    out_path = args.run_dir / "same_school_borderline_annex.csv"
    annex.to_csv(out_path, index=False, encoding="utf-8-sig")

    for school_key, part in annex.groupby("school_key", sort=False):
        packet_path = args.run_dir / "school_packets" / school_key / "annex_rows.csv"
        part.to_csv(packet_path, index=False, encoding="utf-8-sig")

    summary = (
        annex.groupby(["school_key", "college_name"], sort=False)
        .size()
        .reset_index(name="annex_rows")
    )
    summary.to_csv(args.run_dir / "same_school_borderline_annex_summary.csv", index=False, encoding="utf-8-sig")

    print(f"annex_rows={len(annex)}")
    print(f"annex_schools={annex['school_key'].nunique()}")
    print(f"wrote={out_path.as_posix()}")


if __name__ == "__main__":
    main()
