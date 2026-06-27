# 900 Light Crawl Triage V1 Summary

Date: 2026-06-27

Input light-crawl run:

`outputs/ai_path_candidates/light_crawl_900_mini_v6_48shards_20260627`

Output directory:

`outputs/ai_path_candidates/light_crawl_triage_v1_20260627`

## Rule Positioning

This triage is a conservative elimination layer, not a final scoring layer.

Light-crawl evidence is used to remove clearly low-alignment or hard-risk options. Missing evidence is not treated as negative by itself; it usually sends the option to `borderline_review`.

Updated user constraints:

- English-taught programs are acceptable because English practice is necessary for research.
- Sino-foreign cooperation is not negative by itself.
- Tuition line: below 50000 RMB/year is acceptable; above 50000 RMB/year is removed.
- Exactly 50000 RMB/year is kept for boundary review.
- Programs with required foreign study phases and unpriced or extra foreign tuition are removed or strongly flagged.

## Bucket Result

- `keep_for_deep_crawl`: 438
- `borderline_review`: 341
- `drop_by_light_crawl`: 121

Remaining for deeper work:

- `keep_for_deep_crawl` + `borderline_review`: 779

## Drop Reasons

- `tuition_over_50000_rmb`: 67
- `weak_resource_signal_with_low_evidence`: 23
- `not_found_and_low_prescreen_priority`: 19
- `required_or_unpriced_foreign_phase_cost`: 8
- `off_target_courses_with_weak_context`: 7
- `management_heavy_or_training_burden_signal`: 6
- `unsafe_major_diversion`: 2

## Borderline Reasons

- `shard_quality_low_coverage`: 169
- `low_information_light_crawl`: 125
- `no_referenced_source`: 109
- `shard_quality_needs_rerun`: 57
- `major_diversion_or_department_unclear`: 41
- `remote_or_weak_resource_signal`: 33
- `crawl_not_found`: 16
- `off_target_courses_need_manual_confirmation`: 8
- `non_core_major_category`: 6
- `possible_optional`: 5
- `tuition_at_limit_check_strictness`: 4
- `management_heavy_signal`: 1

## Output Files

- `light_crawl_triage_900.csv`: all 900 rows with triage fields.
- `remaining_for_deep_crawl.csv`: 779 rows not eliminated by light crawl.
- `keep_for_deep_crawl.csv`: 438 rows.
- `borderline_review.csv`: 341 rows.
- `drop_by_light_crawl.csv`: 121 rows.
- `triage_summary.json`: machine-readable summary.

## Interpretation

The most reliable removal signal is cost: tuition parsing restores compact values like `11万` or `8.8万` that appeared as `11.0` or `88.0` in the cleaned numeric field.

The remaining 779 should not all be deeply crawled with the same intensity. A practical next step is:

1. Deep-crawl the 438 `keep_for_deep_crawl` rows first.
2. Review the 341 `borderline_review` rows by reason, prioritizing rank-fit and professional fit.
3. Use the deep-crawl results to compress toward the final 300 candidates.
