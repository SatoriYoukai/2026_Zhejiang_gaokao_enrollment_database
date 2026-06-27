# Deep Crawl Subagent Protocol

Date: 2026-06-27

This protocol is for deep crawling the candidate volunteers that survived light-crawl triage. Deep crawl is evidence collection and structured reporting. It is not final scoring, ranking, or volunteer-list filling.

## Mission

For one school at a time, collect auditable evidence about whether the selected majors support the user's AI-research undergraduate path:

- major alignment with math, statistics, CS, AI, and research preparation;
- postgraduate and recommendation-path support;
- research resources and undergraduate research access;
- learning freedom, transfer/minor/course-choice policies, and management burden;
- campus, dormitory, and resource-location risks;
- tuition and mandatory-abroad risks;
- student-facing atmosphere signals, with clear separation between official evidence and informal signals.

The output must help the main thread decide whether the school should move into the next 300-level deep-review set, remain borderline, or be dropped before expensive scoring.

Every school report must answer three final-goal questions:

- Can the student learn the needed foundations for AI research: math, CS systems, ML/AI, and research method?
- Can the student self-study and build/research with low time-tax: limited formalism, manageable management burden, stable campus/dorm logistics?
- Does the school improve the postgraduate path: predictable recommendation policy, accessible research resources, and credible upward mobility?

## Hard Rules

1. Process exactly one `college_name` per run.
2. Use only repo-relative ASCII paths from the task packet. Do not use Chinese absolute paths in shell commands.
3. Read text files with explicit UTF-8 handling.
   - PowerShell: `Get-Content -LiteralPath <path> -Encoding UTF8`
   - Python CSV/JSON: use `encoding="utf-8-sig"` for reads and writes.
4. Never silently repair the workflow. If a required path, file, column, or output directory is missing, stop and report it in the debugger report or task final message.
5. Never change the output schema. If the schema is insufficient, fill the required fields and write the proposed change under `protocol_issues`.
6. Do not expand from one school to a batch. If multiple majors are listed for the school, cover them inside the same school report.
7. Do not score or rank the school. Use evidence labels and gap labels only.
8. Do not treat nonofficial sources as facts. They are only signals.
9. Do not infer good policy from absence of bad evidence. Missing evidence must be marked as missing.
10. Do not paste long copied text. Use short excerpts and your own summaries.

Before running Python from PowerShell, set UTF-8 output explicitly:

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
```

Avoid putting Chinese string literals inside a PowerShell here-string piped to Python. Prefer reading Chinese text from UTF-8-SIG files.

## Required Input Packet

Each school packet contains:

- `school_context.json`: one school and all selected rows for that school;
- `input_rows.csv`: the same rows in tabular form;
- `deep_crawl_task.md`: the exact per-school task instructions;
- an assigned output directory.

The input rows preserve these core identity fields:

- `pool_id`
- `volunteer_id`
- `college_name`
- `major_name`
- `province`
- `city`
- `rank_band`
- `predicted_rank`
- `plan_count`
- `tuition`
- `remark`
- `risk_flags`
- `risk_tags`
- `uncertainty_tags`

Identity fields must be copied exactly into row-level output. Do not normalize school names, strip parenthetical labels, or replace majors with department names.

Normal deep-crawl agents write only to `assigned_output_dir`. Debugger runs may use `debugger_output_dir` when it is present; this is a test-only override and must be reported in `sop_debugger_report.md`.

## Evidence Levels

Use these source levels:

- `official_hard`: admissions plan, admissions regulation, official major page, training plan, curriculum table, school policy, college policy, official postgraduate recommendation policy, official dorm/campus notice.
- `official_soft`: college news, honors program pages, lab news, undergraduate research news, competition news, graduate-destination news.
- `student_high_value`: long-form student reports, course-plan walkthroughs, campus-life reports, Baoyan/保研 experience posts, serious forum summaries, public student blogs.
- `student_soft`: scattered Zhihu, Tieba, Xiaohongshu, Bilibili, forum, or comment signals.
- `third_party_reference`: aggregated admissions sites or encyclopedic pages. These can help discovery but should not carry key conclusions unless official sources are absent and the fact is low-stakes.
- `local_task_packet`: local input packet, local admissions row, or generated task context. Use this only for input-row remarks and task metadata, not as evidence for external facts.

Official evidence has priority. Student evidence is useful mainly for learning freedom, management burden, dorms, and actual experience.

## Source Discovery Directions

Start from official sources:

- `{学校} 本科招生网 {专业}`
- `{学校} {专业} 专业介绍`
- `{学校} {学院} {专业} 培养方案`
- `{学校} {专业} 课程体系`
- `{学校} 推免 办法 本科`
- `{学校} {学院} 推免 细则`
- `{学校} 转专业 办法`
- `{学校} 辅修 双学位 选课`
- `{学校} 宿舍 校区 {专业}`
- `{学校} 本科生科研训练`
- `{学校} {学院} 实验室 机器学习 人工智能 计算数学 统计`

Then discover student-facing sources:

- `{学校} {专业} 保研 经验`
- `{学校} {专业} 课程 知乎`
- `{学校} {专业} 贴吧`
- `{学校} 宿舍 校区 小红书`
- `{学校} 管理 严 形式主义`
- `{学校} 转专业 难`
- `{学校} {专业} B站`
- `{学校} {专业} 学长 学姐 经验`
- `{学校} 早晚自习 查寝 跑操 管理`
- `{学校} 形式主义 活动 学业压力`
- `{学校} {专业} 本科生 进组 导师制 大创`
- `{学校} {专业} 升学去向 保研去向`

When search results are thin, search by college name and by likely department names. If official pages are JavaScript-heavy, use browser/Playwright tools. If a PDF is found, extract text and record the PDF URL.

## Tool Fallback

Use the least fragile tool that can obtain the evidence.

1. Try normal web search/open first.
2. If a page times out or renders poorly, try `curl.exe -L <url>` from the repo root.
3. If PowerShell `Invoke-WebRequest` fails on headers or downloads, retry with `curl.exe -I` or `curl.exe -L -o`.
4. If a page is JavaScript-heavy, login-gated, or requires clicking, use browser/Playwright and record that this was needed.
5. If all methods fail, write the URL, attempted method, and error summary in `debug_notes.md`.

For official WeChat articles:

- If the official school page only links to WeChat and the article cannot be fetched cleanly, record the official entry page and the WeChat jump as source friction.
- Do not spend unlimited time bypassing WeChat restrictions in a normal run.
- Use browser tools only when the article is likely to contain a key missing fact such as professional curriculum or official program details.

For `.pdf`, `.doc`, and `.docx` attachments:

- If the attachment is a training plan or policy source, try to download or inspect it.
- Record the attachment URL even if extraction fails.
- For PDFs, extract text when possible.
- For Word files, try available document-conversion or text-extraction tools only if the attachment is central to a key field.
- If extraction fails, mark the relevant field as found-but-unparsed and add `policy_year_unclear` or `training_plan_not_found` only if the content cannot be determined from surrounding official text.

## Minimum Coverage Target

For a normal school run, try to collect:

- 1 admissions or official major source;
- 1 training-plan or curriculum source for each major, or a clear not-found record;
- 1 school-level recommendation/postgraduate-path policy source;
- 1 college-level recommendation detail or a clear not-found record;
- 1 transfer/minor/course-choice policy source;
- 1 research-resource source;
- 1 undergraduate research access source or a clear not-found record;
- 1 postgraduate outcome or recommendation-destination source if available;
- 1 dorm/campus source;
- 1 to 3 student-facing signals if available.

Stop when either:

- the above coverage is reached with enough evidence to identify risks and gaps; or
- 90 minutes of focused work is reached; or
- official sources are repeatedly inaccessible and the access failure is documented.

## Output Files

Write all files under the assigned school output directory. Use UTF-8 with BOM.

### `result.json`

Required top-level fields:

- `school_key`
- `college_name`
- `crawl_status`: `complete`, `partial`, `blocked`, or `failed`
- `run_scope`
- `majors`
- `school_level_findings`
- `decision_snapshot`
- `row_findings`
- `evidence_gaps`
- `risk_tags`
- `uncertainty_tags`
- `protocol_issues`
- `agent_notes`

Each `row_findings` item must include:

- `pool_id`
- `volunteer_id`
- `college_name`
- `major_name`
- `risk_tags`
- `uncertainty_tags`
- `major_alignment`
- `goal_alignment`
- `training_plan`
- `math_foundation`
- `cs_ai_foundation`
- `research_access`
- `postgraduate_path`
- `learning_freedom`
- `campus_dorm`
- `tuition_abroad`
- `student_signals`
- `source_ids`
- `evidence_gaps`

Row-level `risk_tags` and `uncertainty_tags` use the same controlled vocabularies as school-level tags. Use them to distinguish risks that affect only one major, such as `new_no_history` for a new AI direction or `campus_move` for one computer major.

`decision_snapshot` must be a compact object with these fields:

- `provisional_bucket`: `strong_keep`, `keep`, `borderline`, `defer`, or `drop`
- `can_learn_needed_foundations`
- `low_time_tax_likelihood`
- `postgraduate_path_strength`
- `best_keep_reason`
- `largest_risk`
- `manual_questions_that_change_decision`

Each row-level `goal_alignment` must explicitly discuss:

- `foundation_fit`: math, CS systems, ML/AI, and research-method preparation;
- `learning_freedom_fit`: expected room for self-study and independent projects;
- `research_postgrad_fit`: research access, recommendation path, and upward mobility;
- `time_tax_risk`: management/formalism/campus-move/course-fragmentation risk.

### `sources.csv`

Required columns:

- `source_id`
- `source_level`
- `source_type`
- `title`
- `publisher`
- `url`
- `publish_date`
- `access_date`
- `applies_to`
- `evidence_excerpt`
- `evidence_summary`
- `used_for_fields`
- `access_method`
- `local_artifact_path`
- `extraction_method`
- `reliability_notes`

For downloaded attachments, keep the official URL in `url`. If the file was downloaded or extracted locally, record the repo-relative local path and method. Examples:

- `access_method`: `web.open`, `curl.exe -L`, `browser`, `manual_search_result`, `local_task_packet`
- `local_artifact_path`: `outputs/.../artifacts/15-computer.rar` or blank
- `extraction_method`: `pdf_text`, `doc_word_com`, `docx_text`, `tar_extract`, `not_extracted`, or blank

Search snippets may guide discovery, but they should not carry a key fact unless the agent can reach a stable URL or record the limitation under `reliability_notes`.

### `student_search_log.csv`

Required columns:

- `query`
- `platform`
- `result_url`
- `result_title`
- `adoption_status`: `used_signal`, `not_used_low_quality`, `not_accessible`, or `not_found`
- `reason`
- `related_fields`

This file is required even when no student-facing source is adopted. In that case, record the attempted queries and `not_found` or `not_used_low_quality`.

### `summary.md`

A readable Chinese report with:

- school and majors covered;
- provisional decision bucket: `strong_keep`, `keep`, `borderline`, `defer`, or `drop`;
- strongest positive evidence;
- strongest risks;
- missing evidence;
- student-facing signals;
- final-goal alignment: foundations, low time-tax, postgraduate path;
- decision-changing manual questions;
- questions for the next deep-review/scoring stage.

### `debug_notes.md`

Operational notes:

- search queries tried;
- blocked pages or failed downloads;
- JavaScript/PDF/OCR needs;
- schema or SOP friction;
- time sinks or source-quality issues.

Normal required outputs:

- `result.json`
- `sources.csv`
- `student_search_log.csv`
- `summary.md`
- `debug_notes.md`

## Controlled Tags

Use semicolon-separated tags from this list. Do not invent tags in machine fields.

Risk tags:

- `major_diversion_risk`
- `off_target_courses`
- `sino_foreign`
- `mandatory_abroad`
- `tuition_over_limit`
- `foreign_cost_unclear`
- `small_plan`
- `new_no_history`
- `campus_move`
- `remote_or_weak_resource`
- `management_heavy_signal`
- `time_tax_high_signal`
- `dorm_negative_signal`
- `source_conflict`
- `low_research_signal`
- `policy_restrictive_signal`

Uncertainty tags:

- `training_plan_not_found`
- `recommendation_not_found`
- `transfer_policy_not_found`
- `department_unclear`
- `campus_unclear`
- `dorm_unclear`
- `student_signal_sparse`
- `policy_year_unclear`
- `research_access_unclear`
- `major_diversion_unclear`
- `postgraduate_outcome_unclear`
- `time_tax_unclear`

## Debugger-Specific Rules

The SOP debugger tests the workflow, not the school.

The debugger should:

- read this protocol and one generated school packet;
- verify all referenced paths and required fields;
- run a thin-slice crawl for one school and at most two majors;
- write sample outputs to the assigned debugger output directory;
- report every workflow problem explicitly;
- avoid silently solving around missing directories, bad field names, encoding problems, or unclear instructions.

The debugger should not:

- process all 10 schools;
- perform final deep crawl;
- improve the dataset by inventing new scripts unless asked;
- change the SOP or task files directly.

Debugger required outputs:

- `result.json`
- `sources.csv`
- `student_search_log.csv`
- `summary.md`
- `debug_notes.md`
- `sop_debugger_report.md`