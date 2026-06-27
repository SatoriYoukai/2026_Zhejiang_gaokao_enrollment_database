# 900 Light Crawl Run Audit

Date: 2026-06-27

## Summary

The first `gpt-5.4-mini` light-crawl run cannot be treated as fully valid even when individual shard CSV files pass structural validation.

Structural validation only proves:

- output files exist;
- required columns are present;
- input identity fields match;
- controlled tags are syntactically valid;
- referenced `source_id` values exist.

It does not prove:

- the agent correctly read the Chinese prompt/protocol;
- text fields are free of mojibake;
- sources are meaningfully mapped back to each row;
- the result has enough information to help screen from 900 to 300.

## Root Cause

Some prompt and protocol files were generated as UTF-8 without BOM. In this Windows PowerShell environment, default `Get-Content` can display such files as mojibake unless `-Encoding UTF8` is used. Several subagents appear to have read garbled prompt/protocol content, then either:

- ended before writing the required CSV files;
- wrote structurally valid but shallow outputs;
- wrote rows with mojibake in evidence fields;
- returned final messages such as "I will now write the files" while the agent status was already completed.

All generated prompt and JSON files were changed to UTF-8 with BOM, and future agent prompts should explicitly instruct subagents to use `Get-Content -Encoding UTF8` or Python/pandas with `encoding='utf-8-sig'`.

## Current Evidence

After structural validation and quality audit:

- structurally merged rows: 640 / 900;
- shards represented: 17 / 24;
- suspected mojibake rows: 151;
- low-information rows: 194;
- quality grades:
  - `usable_as_light_crawl`: 4 shards;
  - `low_coverage`: 7 shards;
  - `needs_repair`: 6 shards.

The quality audit output is stored at:

- `outputs/ai_path_candidates/light_crawl_900_mini/qa/light_crawl_quality_by_shard.csv`
- `outputs/ai_path_candidates/light_crawl_900_mini/qa/light_crawl_quality_row_flags.csv`
- `outputs/ai_path_candidates/light_crawl_900_mini/qa/light_crawl_quality_result.json`

## Decision

Do not use the current 640 rows as trusted crawl data for screening.

Use them only as:

- a structural test artifact;
- a source of possible URLs after manual or stronger-agent verification;
- evidence that unattended mini-agent crawling is unstable under the current workflow.

## Recommended Recovery

1. Keep the 4 `usable_as_light_crawl` shards as provisional, not final.
2. Re-run `needs_repair`, `low_coverage`, missing, and failed retry shards under a safer workflow.
3. For recovery runs, use one of:
   - `gpt-5.5` for fewer larger shards; or
   - `gpt-5.4-mini` only after a 2-shard smoke test with ASCII/UTF-8-safe prompt handling and mandatory file existence checks.
4. Treat quality audit as mandatory before any 900-to-300 screening step.

