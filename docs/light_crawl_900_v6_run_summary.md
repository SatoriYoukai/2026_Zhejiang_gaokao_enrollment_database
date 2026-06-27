# 900 Light Crawl V6 Run Summary

Date: 2026-06-27

Run directory:

`outputs/ai_path_candidates/light_crawl_900_mini_v6_48shards_20260627`

## Engineering Result

- Shards completed: 48 / 48
- Row results: 900 / 900
- Source records: 1327
- Structural validation errors: 0
- Row mojibake rows: 0
- Source mojibake rows: 0

## Quality Result

- `usable_as_light_crawl`: 36 shards
- `low_coverage`: 9 shards
- `needs_rerun`: 3 shards
- Low-information rows: 160

## Quality Follow-Up Queue

`needs_rerun`:

- `shard_04`
- `shard_16`
- `shard_22`

`low_coverage`:

- `shard_01`
- `shard_10`
- `shard_13`
- `shard_18`
- `shard_19`
- `shard_25`
- `shard_31`
- `shard_41`
- `shard_45`

## Operational Fixes Applied

- Subagent prompts now use repo-relative ASCII paths instead of absolute paths containing Chinese directory names.
- An ASCII junction path is available at `C:\Users\lsysir\Documents\gaokao_zytb_workspace`.
- Generated free-text fields are constrained to English ASCII to avoid Windows command/output mojibake.
- CSV and notes writing is constrained to UTF-8-SIG.
- Prompts include a Windows command-length guardrail: use temporary scripts instead of large inline Python commands.
- Validation separates structural correctness from content quality.
