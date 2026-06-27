from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_pilot" / "model_ab_test"

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

SOURCE_COLUMNS = [
    "source_id",
    "pool_id_or_school_key",
    "source_level",
    "source_type",
    "title",
    "publisher",
    "url",
    "publish_date",
    "access_date",
    "evidence_excerpt",
    "evidence_summary",
    "used_for_fields",
]


def extract_csv_blocks(text: str) -> list[str]:
    blocks = re.findall(r"```(?:csv)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    return [block.strip() for block in blocks if block.strip()]


def read_csv_block(block: str) -> pd.DataFrame:
    # csv module validates quote structure before pandas gives a more obscure error.
    list(csv.reader(io.StringIO(block)))
    return pd.read_csv(io.StringIO(block), dtype=str).fillna("")


def classify_block(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    if cols == ROW_COLUMNS:
        return "rows"
    if cols == SOURCE_COLUMNS:
        return "sources"
    row_overlap = len(set(cols) & set(ROW_COLUMNS))
    source_overlap = len(set(cols) & set(SOURCE_COLUMNS))
    if row_overlap > source_overlap:
        return "rows_bad_columns"
    return "sources_bad_columns"


def score_result(rows: pd.DataFrame | None, sources: pd.DataFrame | None) -> dict[str, object]:
    result: dict[str, object] = {
        "row_count": 0 if rows is None else int(len(rows)),
        "source_count": 0 if sources is None else int(len(sources)),
        "official_hard_sources": 0,
        "official_soft_sources": 0,
        "nonofficial_sources": 0,
        "rows_with_training_plan_url": 0,
        "rows_with_recommendation_source": 0,
        "rows_with_dorm_source": 0,
        "rows_with_uncertainty": 0,
        "rows_with_nonofficial_signal": 0,
        "missing_source_refs": 0,
        "empty_key_fields": 0,
    }
    if rows is not None:
        result["rows_with_training_plan_url"] = int((rows["training_plan_url"].str.strip() != "").sum())
        result["rows_with_recommendation_source"] = int((rows["recommendation_source_ids"].str.strip() != "").sum())
        result["rows_with_dorm_source"] = int((rows["dorm_campus_source_ids"].str.strip() != "").sum())
        result["rows_with_uncertainty"] = int((rows["uncertainty_tags"].str.strip() != "").sum())
        result["rows_with_nonofficial_signal"] = int((rows["nonofficial_signals"].str.strip() != "").sum())
        key_fields = [
            "department_name",
            "major_intro_url",
            "core_courses_summary",
            "ai_path_fit_notes",
            "recommendation_policy_notes",
            "transfer_policy_notes",
            "dorm_campus_notes",
            "source_ids",
        ]
        result["empty_key_fields"] = int((rows[key_fields].apply(lambda s: s.str.strip() == "").sum()).sum())
    if sources is not None:
        result["official_hard_sources"] = int((sources["source_level"] == "official_hard").sum())
        result["official_soft_sources"] = int((sources["source_level"] == "official_soft").sum())
        result["nonofficial_sources"] = int((sources["source_level"] == "nonofficial").sum())
    if rows is not None and sources is not None:
        source_ids = set(sources["source_id"].astype(str))
        missing = 0
        for value in rows["source_ids"].astype(str):
            for source_id in re.split(r"[;,\s]+", value.strip()):
                if source_id and source_id not in source_ids:
                    missing += 1
        result["missing_source_refs"] = missing
    return result


def parse_one(label: str, text_path: Path) -> dict[str, object]:
    text = text_path.read_text(encoding="utf-8")
    blocks = extract_csv_blocks(text)
    rows = None
    sources = None
    diagnostics: list[str] = []
    for block in blocks:
        try:
            df = read_csv_block(block)
        except Exception as exc:  # noqa: BLE001 - diagnostic script
            diagnostics.append(f"csv_parse_error:{exc}")
            continue
        kind = classify_block(df)
        if kind == "rows":
            rows = df
        elif kind == "sources":
            sources = df
        else:
            diagnostics.append(f"{kind}:{list(df.columns)}")
    if rows is not None:
        rows.to_csv(OUT_DIR / f"{label}_light_crawl_rows.csv", index=False, encoding="utf-8-sig")
    if sources is not None:
        sources.to_csv(OUT_DIR / f"{label}_sources.csv", index=False, encoding="utf-8-sig")
    summary = score_result(rows, sources)
    summary.update(
        {
            "label": label,
            "text_file": str(text_path),
            "csv_blocks": len(blocks),
            "has_rows": rows is not None,
            "has_sources": sources is not None,
            "diagnostics": diagnostics,
        }
    )
    return summary


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) < 3:
        raise SystemExit("usage: parse_light_crawl_ab_results.py <label> <agent_final_text_path>")
    label = sys.argv[1]
    text_path = Path(sys.argv[2]).resolve()
    summary = parse_one(label, text_path)
    summary_path = OUT_DIR / f"{label}_parse_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
