from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = ROOT / "outputs" / "ai_path_candidates" / "wide_pool_900.csv"
DEFAULT_OUT_DIR = ROOT / "outputs" / "ai_path_candidates" / "light_crawl_900_mini"
PROTOCOL_PATH = ROOT / "docs" / "light_crawl_subagent_protocol.md"

DEFAULT_SHARD_COUNT = 24
PROMPT_VERSION = "light-crawl-standalone-v6-2026-06-27"

INPUT_COLUMNS = [
    "pool_id",
    "pool_rank",
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
    "rank_certainty",
    "plan_count",
    "tuition",
    "remark",
    "risk_flags",
    "history_years_matched",
    "rank_2023",
    "rank_2024",
    "rank_2025",
    "score_2025",
    "rank_weighted_center",
    "rank_volatility",
    "prescreen_score",
    "prescreen_priority",
]

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

RISK_TAGS = [
    "major_diversion_risk",
    "off_target_courses",
    "sino_foreign",
    "mandatory_abroad",
    "tuition_unit_unclear",
    "very_high_tuition_possible",
    "small_plan",
    "new_no_history",
    "campus_move",
    "remote_or_weak_resource",
    "management_heavy_signal",
    "dorm_negative_signal",
    "source_conflict",
]

UNCERTAINTY_TAGS = [
    "training_plan_not_found",
    "recommendation_not_found",
    "transfer_policy_not_found",
    "department_unclear",
    "campus_unclear",
    "dorm_unclear",
    "forum_signal_sparse",
    "policy_year_unclear",
]


def clean_value(value: object) -> object:
    if pd.isna(value):
        return ""
    return value


def make_prompt(
    *,
    shard_id: str,
    input_csv: Path,
    input_json: Path,
    rows_csv: Path,
    sources_csv: Path,
    notes_md: Path,
    row_count: int,
    school_count: int,
    model: str,
    purpose: str,
) -> str:
    def repo_relative(path: Path) -> str:
        return path.resolve().relative_to(ROOT).as_posix()

    protocol_ref = repo_relative(PROTOCOL_PATH)
    input_csv_ref = repo_relative(input_csv)
    input_json_ref = repo_relative(input_json)
    rows_csv_ref = repo_relative(rows_csv)
    sources_csv_ref = repo_relative(sources_csv)
    notes_md_ref = repo_relative(notes_md)
    row_columns = json.dumps(ROW_COLUMNS, ensure_ascii=False)
    source_columns = json.dumps(SOURCE_COLUMNS, ensure_ascii=False)
    risk_tags = ";".join(RISK_TAGS)
    uncertainty_tags = ";".join(UNCERTAINTY_TAGS)
    return f"""Light crawl task packet
Prompt version: {PROMPT_VERSION}
Model target: {model}
Purpose: {purpose}
Shard id: {shard_id}
Working directory: current repository root.

Encoding rules:
- This prompt is written with UTF-8 BOM. If any path or Chinese text appears garbled, reread it with UTF-8.
- All paths in this prompt are repository-relative ASCII paths. Do not convert them to absolute paths in Python code.
- Never paste an absolute path containing non-ASCII directory names into Python code.
- Prefer Python/pandas for input reading:
  pd.read_csv(r"{input_csv_ref}", dtype=str, encoding="utf-8-sig").fillna("")
- Do not use PowerShell Get-Content without -Encoding UTF8.
- Do not write CSV or Markdown with PowerShell Set-Content/Out-File default encoding.
- Write CSV with Python/pandas and encoding="utf-8-sig". Write notes with Path.write_text(..., encoding="utf-8-sig").
- If the prompt or input is garbled, stop and report an encoding failure. Do not guess the task.

Windows command-length guardrail:
- Do not put a large rows/sources Python literal into a single inline `python -` command.
- If you need more than a few short lines of Python, write a small temporary script under `outputs/ai_path_candidates/tmp_agent_scripts/` using a repo-relative ASCII path, run it, then leave the script for audit.
- Keep generated text concise. Prefer one-sentence summaries.
- Never abandon the shard after a command-length error; switch to a temporary script and still write the three required files.

Output language rule:
- Use English ASCII text for all generated free-text fields, notes, source titles, publishers, excerpts, and summaries.
- Do not write Chinese characters in generated fields. Translate or paraphrase Chinese source titles into English.
- The identity fields pool_id, volunteer_id, college_name, and major_name should still be copied from input, but the main thread will repair them from pool_id if your local environment corrupts Chinese text.
- URLs and source_ids must remain exact.

Reference protocol, optional but recommended:
{protocol_ref}

Input files:
- CSV: {input_csv_ref}
- JSON: {input_json_ref}
- expected_rows: {row_count}
- school_count: {school_count}

Required output files. Write these exact paths before your final reply:
- row results CSV: {rows_csv_ref}
- sources CSV: {sources_csv_ref}
- short notes Markdown: {notes_md_ref}

Recommended write skeleton:
```python
from pathlib import Path
import pandas as pd

row_columns = {row_columns}
source_columns = {source_columns}

# rows and sources must be lists of dictionaries you have filled.
pd.DataFrame(rows, columns=row_columns).to_csv(
    r"{rows_csv_ref}", index=False, encoding="utf-8-sig"
)
pd.DataFrame(sources, columns=source_columns).to_csv(
    r"{sources_csv_ref}", index=False, encoding="utf-8-sig"
)
Path(r"{notes_md_ref}").write_text(notes, encoding="utf-8-sig")
```

Mission:
You are collecting light evidence for Zhejiang 2026 professional-parallel gaokao choices.
The student wants an AI-scientist path, with locked major fit, good postgraduate recommendation policy, learning freedom, academic resources, academic atmosphere, and decent dorm/campus conditions.
This is not final scoring. Do not rank schools. Do not make broad prestige judgments.

Time-box:
- This is a light crawl, not a deep crawl.
- Spend at most about 8 minutes per small pilot shard, and at most about 3 minutes per school in full shards.
- For each school, prefer 1 to 3 high-value sources over exhaustive searching.
- It is acceptable to mark fields as not_found/partial with uncertainty tags when evidence is not quickly available.
- Write the CSV files as soon as you have complete row coverage; do not wait for perfect evidence.

For every input row:
1. Copy pool_id, volunteer_id, college_name, and major_name exactly from the input row.
2. Search the web for official sources first: admissions pages, department pages, major introductions, training plans, recommendation/postgraduate policies, transfer/learning policy, research resources, campus/dorm information.
3. Nonofficial sources such as Zhihu, Tieba, forums, Xiaohongshu, Bilibili, blogs can only be recorded as weak signals in nonofficial_signals.
4. If evidence is missing, still output the row with crawl_status=partial or not_found and add suitable uncertainty tags.
5. Every factual claim should map to source_ids. Do not invent facts.
6. Keep evidence excerpts short. Summarize in your own words.

Output schema:
- The row results CSV must use exactly these columns in this order:
  {row_columns}
- The sources CSV must use exactly these columns in this order:
  {source_columns}

Allowed values:
- crawl_status: complete, partial, not_found
- agent_confidence: high, medium, low
- source_level: official_hard, official_soft, nonofficial
- source_type: admission, department, training_plan, policy, research, dorm, forum, other
- risk_tags: {risk_tags}
- uncertainty_tags: {uncertainty_tags}

Tag formatting:
- Use ASCII semicolon ';' between multiple risk_tags or uncertainty_tags.
- Do not create new tag names.
- If no tag applies, leave the cell empty.

Self-check before final reply:
- The row CSV has exactly {row_count} data rows.
- The row CSV columns exactly match the required schema.
- The sources CSV columns exactly match the required schema.
- Every input pool_id appears once.
- The four identity fields are copied exactly from input.
- All source_ids referenced in row results exist in the sources CSV.
- The notes file exists and briefly records major missing areas or conflicts.

Final reply:
Only report completion status, the three output file paths, completed row count, source count, and major missing/conflict count. Do not paste the CSV content.
"""


def assign_shards(df: pd.DataFrame, shard_count: int) -> list[pd.DataFrame]:
    groups = []
    for college_name, group in df.groupby("college_name", sort=False):
        groups.append((college_name, group.copy()))
    groups.sort(key=lambda item: (-len(item[1]), str(item[0])))

    shard_groups: list[list[pd.DataFrame]] = [[] for _ in range(shard_count)]
    shard_sizes = [0] * shard_count
    for _, group in groups:
        target = min(range(shard_count), key=lambda idx: shard_sizes[idx])
        shard_groups[target].append(group)
        shard_sizes[target] += len(group)

    shards = []
    for groups_for_shard in shard_groups:
        if not groups_for_shard:
            shards.append(pd.DataFrame(columns=df.columns))
            continue
        shard = pd.concat(groups_for_shard, ignore_index=True)
        shard = shard.sort_values(["pool_rank", "pool_id"]).reset_index(drop=True)
        shards.append(shard)
    return shards


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare light-crawl input shards.")
    parser.add_argument("--pool-path", type=Path, default=POOL_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--shard-count", type=int, default=DEFAULT_SHARD_COUNT)
    parser.add_argument("--limit", type=int, default=None, help="Optional first-N row limit for pilot runs.")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--purpose", default="900 light crawl")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pool_path = args.pool_path.resolve()
    out_dir = args.out_dir.resolve()
    input_dir = out_dir / "input_shards"
    output_dir = out_dir / "outputs"
    log_dir = out_dir / "logs"

    if not pool_path.exists():
        raise FileNotFoundError(pool_path)
    if args.shard_count <= 0:
        raise ValueError("--shard-count must be positive")

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(pool_path, dtype=str, encoding="utf-8-sig").fillna("")
    missing = [column for column in INPUT_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"missing input columns: {missing}")

    df = df[INPUT_COLUMNS].copy()
    df["pool_id_num"] = pd.to_numeric(df["pool_id"], errors="coerce")
    df["pool_rank_num"] = pd.to_numeric(df["pool_rank"], errors="coerce")
    df = df.sort_values(["pool_rank_num", "pool_id_num"]).drop(columns=["pool_id_num", "pool_rank_num"])
    if args.limit is not None:
        df = df.head(args.limit).copy()

    shards = assign_shards(df, args.shard_count)
    manifest = {
        "source_pool": str(pool_path),
        "protocol": str(PROTOCOL_PATH),
        "prompt_version": PROMPT_VERSION,
        "model": args.model,
        "shard_count": args.shard_count,
        "total_rows": int(len(df)),
        "purpose": args.purpose,
        "output_dir": str(out_dir),
        "shards": [],
    }

    for index, shard in enumerate(shards, start=1):
        shard_id = f"shard_{index:02d}"
        shard = shard.map(clean_value)
        csv_path = input_dir / f"{shard_id}_input.csv"
        json_path = input_dir / f"{shard_id}_input.json"
        prompt_path = input_dir / f"{shard_id}_prompt.md"
        rows_csv = output_dir / f"{shard_id}_light_crawl_rows.csv"
        sources_csv = output_dir / f"{shard_id}_sources.csv"
        notes_md = log_dir / f"{shard_id}_notes.md"

        shard.to_csv(csv_path, index=False, encoding="utf-8-sig")
        json_path.write_text(shard.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8-sig")
        prompt_path.write_text(
            make_prompt(
                shard_id=shard_id,
                input_csv=csv_path,
                input_json=json_path,
                rows_csv=rows_csv,
                sources_csv=sources_csv,
                notes_md=notes_md,
                row_count=len(shard),
                school_count=shard["college_name"].nunique(),
                model=args.model,
                purpose=args.purpose,
            ),
            encoding="utf-8-sig",
        )
        manifest["shards"].append(
            {
                "shard_id": shard_id,
                "input_csv": str(csv_path),
                "input_json": str(json_path),
                "prompt": str(prompt_path),
                "rows_csv": str(rows_csv),
                "sources_csv": str(sources_csv),
                "notes_md": str(notes_md),
                "row_count": int(len(shard)),
                "school_count": int(shard["college_name"].nunique()),
                "category_counts": shard["major_category"].value_counts().to_dict(),
                "priority_counts": shard["prescreen_priority"].value_counts().to_dict(),
            }
        )

    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    pd.DataFrame(manifest["shards"]).to_csv(out_dir / "manifest.csv", index=False, encoding="utf-8-sig")
    print(json.dumps({"output_dir": str(out_dir), "rows": len(df), "shards": len(shards)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
