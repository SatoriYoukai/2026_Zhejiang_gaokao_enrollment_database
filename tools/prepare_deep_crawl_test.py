from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_INPUT = Path("outputs/ai_path_candidates/light_crawl_triage_v2_20260627/keep_for_deep_crawl.csv")
DEFAULT_OUTPUT = Path("outputs/ai_path_candidates/deep_crawl_test_v1_20260627")

DEFAULT_TEST_SCHOOLS = [
    "浙江师范大学(省重点建设高校)",
    "兰州大学(“双一流”建设高校)",
    "长春理工大学",
    "河海大学(“双一流”建设高校)",
    "深圳大学",
    "浙江科技大学",
    "湖南工商大学",
    "成都信息工程大学",
    "南京信息工程大学(“双一流”建设高校)",
    "南阳理工学院",
]

IDENTITY_COLUMNS = [
    "pool_id",
    "volunteer_id",
    "college_code",
    "college_name",
    "major_code",
    "major_name",
    "major_category",
    "province",
    "city",
    "rank_band",
    "predicted_rank",
    "plan_count",
    "tuition",
    "tuition_rmb_estimate",
    "remark",
    "risk_flags",
    "risk_tags",
    "uncertainty_tags",
    "prescreen_priority",
    "ceiling_level",
    "crawl_status",
    "agent_confidence",
    "source_ids",
    "training_plan_url",
    "core_courses_summary",
    "ai_path_fit_notes",
    "research_resources_notes",
    "recommendation_policy_notes",
    "learning_freedom_notes",
    "dorm_campus_notes",
    "next_deep_questions",
]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig", newline="\n")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def write_csv(path: Path, rows: Iterable[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in fieldnames})


def normalize_rows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.fillna("")
    for col in IDENTITY_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


def make_school_context(
    index: int,
    school: str,
    rows: pd.DataFrame,
    run_root: Path,
    source_pool: Path,
) -> dict[str, object]:
    row_dicts = rows[IDENTITY_COLUMNS].to_dict(orient="records")
    majors = sorted({str(row["major_name"]) for row in row_dicts})
    school_key = f"school_{index:02d}"
    output_dir = run_root / "school_outputs" / school_key
    packet_dir = run_root / "school_packets" / school_key
    return {
        "school_key": school_key,
        "college_name": school,
        "generated_at": date.today().isoformat(),
        "source_pool": str(source_pool.as_posix()),
        "assigned_output_dir": str(output_dir.as_posix()),
        "debugger_output_dir": str((run_root / "debugger" / "sop_debugger_output").as_posix()),
        "packet_dir": str(packet_dir.as_posix()),
        "input_files": {
            "school_context": str((packet_dir / "school_context.json").as_posix()),
            "input_rows": str((packet_dir / "input_rows.csv").as_posix()),
            "deep_crawl_task": str((packet_dir / "deep_crawl_task.md").as_posix()),
        },
        "run_scope": {
            "mode": "deep_crawl_test",
            "one_school_only": True,
            "majors_count": len(majors),
            "row_count": len(row_dicts),
        },
        "majors": majors,
        "input_rows": row_dicts,
        "required_outputs": ["result.json", "sources.csv", "student_search_log.csv", "summary.md", "debug_notes.md"],
        "debugger_required_outputs": [
            "result.json",
            "sources.csv",
            "student_search_log.csv",
            "summary.md",
            "debug_notes.md",
            "sop_debugger_report.md",
        ],
    }


def make_school_task(context: dict[str, object]) -> str:
    school_key = context["school_key"]
    school = context["college_name"]
    output_dir = context["assigned_output_dir"]
    input_files = context["input_files"]
    majors = "\n".join(f"- {major}" for major in context["majors"])
    return f"""# Deep Crawl Task: {school_key}

Read `docs/deep_crawl_subagent_protocol.md` before working.

Process exactly one school:

`{school}`

Majors in scope:

{majors}

Input files:

- `{input_files["school_context"]}`
- `{input_files["input_rows"]}`

Output directory:

`{output_dir}`

Hard constraints:

- Use repo-relative ASCII paths in commands.
- Use UTF-8 or UTF-8-SIG explicitly when reading and writing.
- Do not process any other school.
- Do not change the schema.
- If a path, field, or source is blocked, report it in `debug_notes.md` and continue only when the SOP allows it.
- If the workflow itself is blocked, stop and report instead of inventing a new workflow.

Required outputs:

- `result.json`
- `sources.csv`
- `student_search_log.csv`
- `summary.md`
- `debug_notes.md`
"""


def make_debugger_checklist() -> str:
    return """# Deep Crawl SOP Debugger Checklist

The debugger validates process reliability before normal subagents are launched.

## File And Encoding Checks

- Can the protocol be read with `Get-Content -Encoding UTF8`?
- Can `school_context.json` be read with Python `encoding="utf-8-sig"`?
- Can `input_rows.csv` be read with pandas `encoding="utf-8-sig"`?
- Do Chinese school and major names display correctly?
- Are all task paths repo-relative and ASCII?

## Schema Checks

- Are all protocol-required identity fields present?
- Is exactly one `college_name` present in `school_01`?
- Is the assigned output directory present or creatable?
- Are controlled tag fields present?
- Are there obvious missing columns that would block normal deep crawl?

## Thin-Slice Crawl Checks

- Can the agent find official school/admissions/major/policy sources?
- Does the fallback chain work when normal web open fails?
- Are PDF, DOC, DOCX, and WeChat-style pages handled or reported cleanly?
- Are key pages static HTML, PDF, or JavaScript-heavy?
- Is PDF extraction needed?
- Are student-facing sources accessible enough for signals?
- Is `student_search_log.csv` written even when signals are not adopted?
- Does the one-school-per-run structure prevent context overload?

## Reporting Checks

- Does the agent report blockers rather than silently fixing them?
- Does the sample `sources.csv` support every factual statement?
- Does the sample `result.json` preserve input identity fields exactly?
- Are evidence gaps explicit instead of filled by inference?
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--schools", nargs="*", default=DEFAULT_TEST_SCHOOLS)
    args = parser.parse_args()

    df = pd.read_csv(args.input, dtype=str, encoding="utf-8-sig")
    df = normalize_rows(df)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet_dir = args.output_dir / "school_packets"
    debugger_dir = args.output_dir / "debugger"
    selected_rows: list[dict[str, str]] = []
    manifest_schools: list[dict[str, object]] = []

    for index, school in enumerate(args.schools, start=1):
        rows = df[df["college_name"] == school].copy()
        if rows.empty:
            raise SystemExit(f"School not found in input: {school}")

        school_key = f"school_{index:02d}"
        school_dir = packet_dir / school_key
        output_dir = args.output_dir / "school_outputs" / school_key
        context = make_school_context(index, school, rows, args.output_dir, args.input)

        write_json(school_dir / "school_context.json", context)
        write_csv(school_dir / "input_rows.csv", rows[IDENTITY_COLUMNS].to_dict(orient="records"), IDENTITY_COLUMNS)
        write_text(school_dir / "deep_crawl_task.md", make_school_task(context))
        output_dir.mkdir(parents=True, exist_ok=True)

        for row in rows[IDENTITY_COLUMNS].to_dict(orient="records"):
            row["school_key"] = school_key
            selected_rows.append(row)

        manifest_schools.append(
            {
                "school_key": school_key,
                "college_name": school,
                "row_count": int(len(rows)),
                "majors": context["majors"],
                "packet_dir": str(school_dir.as_posix()),
                "output_dir": str(output_dir.as_posix()),
            }
        )

    write_csv(args.output_dir / "selected_rows.csv", selected_rows, ["school_key", *IDENTITY_COLUMNS])
    write_csv(
        args.output_dir / "selected_schools.csv",
        [
            {
                "school_key": item["school_key"],
                "college_name": item["college_name"],
                "row_count": str(item["row_count"]),
                "majors": ";".join(item["majors"]),
                "packet_dir": item["packet_dir"],
                "output_dir": item["output_dir"],
            }
            for item in manifest_schools
        ],
        ["school_key", "college_name", "row_count", "majors", "packet_dir", "output_dir"],
    )
    write_json(
        args.output_dir / "deep_crawl_test_manifest.json",
        {
            "generated_at": date.today().isoformat(),
            "input": str(args.input.as_posix()),
            "protocol": "docs/deep_crawl_subagent_protocol.md",
            "debugger_prompt": "docs/deep_crawl_sop_debugger_prompt.md",
            "schools": manifest_schools,
        },
    )
    write_text(debugger_dir / "debugger_checklist.md", make_debugger_checklist())
    (debugger_dir / "sop_debugger_output").mkdir(parents=True, exist_ok=True)

    print(f"Wrote deep-crawl test package: {args.output_dir}")
    print(f"Schools: {len(manifest_schools)}")
    print(f"Rows: {len(selected_rows)}")


if __name__ == "__main__":
    main()
