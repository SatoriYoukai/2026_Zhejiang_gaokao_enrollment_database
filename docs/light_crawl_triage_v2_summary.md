# 900 Light Crawl Triage V2 Summary

Date: 2026-06-27

Input light-crawl run:

`outputs/ai_path_candidates/light_crawl_900_mini_v6_48shards_20260627`

Output directory:

`outputs/ai_path_candidates/light_crawl_triage_v2_20260627`

## What Changed From V1

V1 mainly removed hard-cost risks and a small set of obvious low-alignment rows.

V2 adds conservative removal rules for:

- training-direction drift;
- uncontrolled class or major-diversion risk;
- weak campus/resource evidence;
- multiple missing core evidence fields combined with low school/major upside.

The intent is still not final ranking. V2 removes options that are not worth expensive deep crawling.

## Bucket Result

- `keep_for_deep_crawl`: 201
- `borderline_review`: 488
- `drop_by_light_crawl`: 211

Remaining for deeper work:

- `keep_for_deep_crawl` + `borderline_review`: 689

Compared with V1:

- New drops from V1 keep/borderline: 90
- New drops from V1 `keep_for_deep_crawl`: 19
- New drops from V1 `borderline_review`: 71

## Drop Reasons

- `multiple_core_info_missing_low_ceiling`: 83
- `tuition_over_50000_rmb`: 67
- `training_direction_low_alignment`: 46
- `weak_resource_signal_with_low_evidence`: 23
- `not_found_and_low_prescreen_priority`: 19
- `campus_resource_obviously_weak`: 18
- `domain_drift_with_limited_upside`: 16
- `required_or_unpriced_foreign_phase_cost`: 8
- `off_target_courses_with_weak_context`: 7
- `management_heavy_or_training_burden_signal`: 6
- `uncontrolled_diversion_risk`: 4
- `unsafe_major_diversion`: 2
- `excluded_major_mix_without_selection_guarantee`: 2

## Guardrail Checks

- Remaining rows with `tuition_rmb_estimate > 50000`: 0
- Rows dropped only because of sino-foreign status: 0
- New drops from strong/provincial-key schools: 1

The one strong-school new drop is:

- 中国人民大学(“双一流”建设高校) `统计学类(国民经济与数科创新人才班)`: C priority, heavy evidence missing, and a data-science plus national-economy double-degree structure. It is not a priority deep-crawl target for the AI-scientist path.

## Output Files

- `light_crawl_triage_900.csv`: all 900 rows with V2 triage fields.
- `remaining_for_deep_crawl.csv`: 689 rows not eliminated by V2.
- `keep_for_deep_crawl.csv`: 201 rows.
- `borderline_review.csv`: 488 rows.
- `drop_by_light_crawl.csv`: 211 rows.
- `triage_summary.json`: machine-readable summary.

## Interpretation

V2 is stricter than V1 but still intentionally conservative for high-upside schools and core majors. Missing evidence alone does not remove a row unless it is paired with low upside, weak resources, direction drift, or uncontrollable diversion.

The next practical step is to use `remaining_for_deep_crawl.csv` as the deep-crawl candidate pool, with `keep_for_deep_crawl.csv` first and `borderline_review.csv` sampled or re-ranked before spending full crawl budget.
