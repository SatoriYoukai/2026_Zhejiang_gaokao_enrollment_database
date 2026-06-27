#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a static browser for Zhejiang 2026 volunteer plan data."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


DEFAULT_INPUT = Path("outputs/clean_database/volunteer_master_2026_with_history.csv")
DEFAULT_OUTPUT = Path("outputs/volunteer_browser")


KEEP_FIELDS = [
    "volunteer_id",
    "college_code",
    "college_name",
    "college_key",
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
    "2023_match_level",
    "2023_history_major_name",
    "2023_history_subject",
    "2023_history_admitted_count",
    "2023_history_avg_score",
    "2023_history_lowest_score",
    "2023_history_lowest_rank",
    "2023_history_source_page",
    "2024_match_level",
    "2024_history_major_name",
    "2024_history_subject",
    "2024_history_admitted_count",
    "2024_history_avg_score",
    "2024_history_lowest_score",
    "2024_history_lowest_rank",
    "2024_history_source_page",
    "2025_match_level",
    "2025_history_major_name",
    "2025_history_subject",
    "2025_history_admitted_count",
    "2025_history_avg_score",
    "2025_history_lowest_score",
    "2025_history_lowest_rank",
    "2025_history_source_page",
    "history_years_matched",
    "history_ranks",
    "history_latest_rank",
    "history_latest_score",
    "history_avg_rank",
    "history_best_rank",
    "history_easiest_rank",
]


def to_number(value: str):
    text = (value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number


def clean_row(row: dict) -> dict:
    out = {}
    for field in KEEP_FIELDS:
        value = (row.get(field) or "").strip()
        if field in {
            "duration",
            "plan_count",
            "tuition",
            "2023_history_admitted_count",
            "2023_history_avg_score",
            "2023_history_lowest_score",
            "2023_history_lowest_rank",
            "2023_history_source_page",
            "2024_history_admitted_count",
            "2024_history_avg_score",
            "2024_history_lowest_score",
            "2024_history_lowest_rank",
            "2024_history_source_page",
            "2025_history_admitted_count",
            "2025_history_avg_score",
            "2025_history_lowest_score",
            "2025_history_lowest_rank",
            "2025_history_source_page",
            "history_years_matched",
            "history_latest_rank",
            "history_latest_score",
            "history_avg_rank",
            "history_best_rank",
            "history_easiest_rank",
        }:
            out[field] = to_number(value)
        else:
            out[field] = value or None
    return out


def unique_sorted(rows: list[dict], field: str) -> list[str]:
    return sorted({r[field] for r in rows if r.get(field)})


def build_payload(rows: list[dict]) -> dict:
    return {
        "generated_from": str(DEFAULT_INPUT).replace("\\", "/"),
        "row_count": len(rows),
        "fields": KEEP_FIELDS,
        "facets": {
            "province": unique_sorted(rows, "province"),
            "city": unique_sorted(rows, "city"),
            "degree_level": unique_sorted(rows, "degree_level"),
            "subject_key": unique_sorted(rows, "subject_key"),
            "history_years_matched": sorted({r["history_years_matched"] for r in rows if r.get("history_years_matched") is not None}),
        },
        "summary": {
            "degree_level": Counter(r.get("degree_level") for r in rows if r.get("degree_level")),
            "subject_key": Counter(r.get("subject_key") for r in rows if r.get("subject_key")),
            "history_years_matched": Counter(str(r.get("history_years_matched")) for r in rows if r.get("history_years_matched") is not None),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [clean_row(row) for row in csv.DictReader(handle)]

    payload = build_payload(rows)
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (output_dir / "data.js").write_text(
        "window.VOLUNTEER_DATA = " + data_json + ";\n",
        encoding="utf-8",
    )
    (output_dir / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows to {output_dir}")


if __name__ == "__main__":
    main()
