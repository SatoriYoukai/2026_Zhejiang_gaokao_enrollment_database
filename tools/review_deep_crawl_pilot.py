from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()

    run_dir = args.run_dir
    selected = pd.read_csv(run_dir / "selected_schools.csv", dtype=str, encoding="utf-8-sig").fillna("")
    validation_path = run_dir / "qa" / "deep_crawl_validation.csv"
    validation = pd.read_csv(validation_path, dtype=str, encoding="utf-8-sig").fillna("") if validation_path.exists() else pd.DataFrame()

    rows: list[dict[str, str]] = []
    for _, school in selected.iterrows():
        key = school["school_key"]
        out_dir = run_dir / "school_outputs" / key
        result = read_json(out_dir / "result.json")
        sources = pd.read_csv(out_dir / "sources.csv", dtype=str, encoding="utf-8-sig").fillna("")
        student = pd.read_csv(out_dir / "student_search_log.csv", dtype=str, encoding="utf-8-sig").fillna("")
        decision = result.get("decision_snapshot", {})
        rows.append(
            {
                "school_key": key,
                "college_name": school["college_name"],
                "crawl_status": result.get("crawl_status", ""),
                "bucket": decision.get("provisional_bucket", ""),
                "row_findings": str(len(result.get("row_findings", []))),
                "sources": str(len(sources)),
                "official_hard": str(int((sources["source_level"] == "official_hard").sum())) if "source_level" in sources else "0",
                "student_searches": str(len(student)),
                "best_keep_reason": decision.get("best_keep_reason", ""),
                "largest_risk": decision.get("largest_risk", ""),
                "manual_questions": "；".join(decision.get("manual_questions_that_change_decision", []))
                if isinstance(decision.get("manual_questions_that_change_decision"), list)
                else str(decision.get("manual_questions_that_change_decision", "")),
            }
        )

    summary = pd.DataFrame(rows)
    qa_dir = run_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(qa_dir / "pilot10_review_summary.csv", index=False, encoding="utf-8-sig")

    bucket_counts = summary["bucket"].value_counts().to_dict()
    status_counts = summary["crawl_status"].value_counts().to_dict()
    total_sources = int(summary["sources"].astype(int).sum())
    official_hard = int(summary["official_hard"].astype(int).sum())
    student_searches = int(summary["student_searches"].astype(int).sum())
    valid_text = ""
    if not validation.empty and "valid" in validation.columns:
        valid_text = f"- Hard validation: {(validation['valid'].astype(str).str.lower() == 'true').sum()} / {len(validation)} schools passed.\n"

    lines = [
        "# Deep Crawl Pilot10 Review",
        "",
        f"Run directory: `{run_dir.as_posix()}`",
        "",
        "## Machine QA",
        "",
        valid_text.rstrip(),
        f"- Crawl status counts: `{status_counts}`",
        f"- Decision bucket counts: `{bucket_counts}`",
        f"- Total sources: {total_sources}",
        f"- Official hard sources: {official_hard}",
        f"- Student-search records: {student_searches}",
        "",
        "## Content Review",
        "",
        "- The reports are generally aligned with the final goal: foundations, time-tax/self-study freedom, and postgraduate/research path.",
        "- All 10 schools are `partial`, which is acceptable for pilot but means the full 201 run should treat missing evidence as a first-class output, not as failure.",
        "- The most common blockers are path drift in generated task files, training-plan attachments, OCR/image PDFs, official-site anti-scraping, captcha-gated attachments, source conflicts in plan counts, and sparse high-quality student signals.",
        "- The summaries are detailed enough for human review and triage, but not yet enough for final scoring without targeted manual confirmation for high-impact gaps.",
        "",
        "## Systemic Issues Found In Pilot",
        "",
        "- Fix generated `deep_crawl_task.md` paths so each run points to its own packet directory.",
        "- Add row-level official-major match confidence to separate exact matches from near matches and ordinary vs sino-foreign pages.",
        "- Add controlled tags for plan-count conflicts, captcha-blocked attachments, OCR-needed documents, no recommendation path, weak postgraduate path, and exact-major mismatch.",
        "- Standardize attachment handling: PDF/DOC/DOCX/RAR/ZIP download, extraction method, local artifact path, and failure status.",
        "- Keep student signals as signals only; student platforms are useful for time-tax and dorm clues but sparse and noisy.",
        "",
        "## School Summary",
        "",
        "| School | Status | Bucket | Sources | Official Hard | Main Risk |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        risk = row["largest_risk"].replace("|", "/")
        lines.append(
            f"| {row['school_key']} {row['college_name']} | {row['crawl_status']} | {row['bucket']} | "
            f"{row['sources']} | {row['official_hard']} | {risk} |"
        )

    lines.extend(
        [
            "",
            "## Readiness Judgment",
            "",
            "The pilot passes the content-alignment test after the systemic fixes above. It is reasonable to proceed to the 201-school deep crawl only after regenerating packets with the fixed task paths and using the updated SOP/schema.",
        ]
    )
    (qa_dir / "pilot10_review.md").write_text("\n".join(line for line in lines if line is not None), encoding="utf-8-sig")
    print(qa_dir / "pilot10_review.md")


if __name__ == "__main__":
    main()
