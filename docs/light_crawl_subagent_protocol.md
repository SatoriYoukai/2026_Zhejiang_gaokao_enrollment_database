# 900 宽池轻爬 Subagent 操作协议

## 目标

轻爬不是最终评分，也不是替代深爬。它的目标是给 900 个宽池志愿补一层可追溯的事实信息，用来：

- 防止 300 粗筛误伤高潜力志愿；
- 标出需要人工复核的风险项；
- 为后续筛到 300 后的深爬和打分提供入口链接；
- 减少重复搜索同一所学校、同一学院、同一政策。

Subagent 只做资料检索、摘录、归档和风险标记。不要替考生做最终排序，不要泛泛评价学校好坏。

## 输入

主线程会给每个 subagent 一个任务分片，至少包含这些字段：

- `pool_id`
- `volunteer_id`
- `college_name`
- `major_name`
- `major_category`
- `province`
- `city`
- `rank_band`
- `predicted_rank`
- `plan_count`
- `tuition`
- `remark`
- `risk_flags`

工作单元优先按 `college_name + major_name` 处理；同一学校的校级政策只查一次，但输出仍需能映射回每个 `volunteer_id`。

## 全量 900 执行硬约束

全量轻爬会优先使用 `gpt-5.4-mini`。为降低 mini 在字段稳定性和来源错配上的风险，正式运行时必须遵守以下约束：

1. 输入身份字段锁死：`pool_id`、`volunteer_id`、`college_name`、`major_name` 必须从输入逐字复制，不允许改成学院名、简称、英文名或备注名。
2. 每个输入行都必须输出一行轻爬结果；即使完全找不到资料，也要输出该行并把 `crawl_status` 写成 `not_found`。
3. `risk_tags` 只能使用本文档给出的英文受控词表；多个标签用英文分号 `;` 分隔，不要使用中文标签、逗号或顿号。
4. `uncertainty_tags` 只能使用本文档给出的英文受控词表；多个标签用英文分号 `;` 分隔。
5. 事实字段不要写无来源的推断。需要推断时，只能写在 `ai_path_fit_notes`、`next_deep_questions` 或 `nonofficial_signals` 中，并显式标注 `inference:` 或 `nonofficial:`。
6. 同一事实如果来源之间冲突，必须在 `risk_tags` 加 `source_conflict`，并在相关字段中写清冲突点，例如“2026 招章写 100000/年；旧 FAQ 写 70000/年，需深爬复核”。
7. 非官方资料只能作为信号，不能把论坛、贴吧、知乎、小红书的说法写成已确认事实。
8. 来源必须与学校/合作项目相关。除中外合作的外方学校外，不能把 A 学校网页作为 B 学校条目的证据。
9. 输出文件必须写到主线程指定的 shard 路径，不要另起文件名，不要只在最终消息里贴 CSV。
10. 最终回复只需要说明完成状态、文件路径、缺失/冲突的高风险项数量，不要重复粘贴完整 CSV。

## 核心判断框架

轻爬只围绕本项目的核心需求收集信息：

- 专业是否服务 AI 科研路径；
- 本科阶段是否利于数学、统计、计算机基础和自学；
- 是否有保研、科研、直博或高质量升学加成；
- 是否存在分流、培养方向偏离、强制出国、高学费、校区搬迁等风险；
- 学校和学院是否有足够学术资源；
- 住宿、校区和生活条件是否存在明显硬伤；
- 是否有明显形式主义、课程负担、管理强度或学习自由度问题。

## 信息源优先级

### A 级：官方硬资料，必须优先

每个学校/专业尽量查到：

1. 学校本科招生网或招生章程；
2. 专业介绍页；
3. 专业所在学院官网；
4. 培养方案、课程体系或教学计划；
5. 教务处/本科生院政策：转专业、辅修、双学位、选课、学业管理；
6. 推免政策：学校推免办法、学院推免细则、近年推免名单；
7. 科研资源：实验室、研究所、导师团队、本科生科研训练计划；
8. 宿舍、校区、迎新、后勤或学生手册信息。

### B 级：官方软资料，作为补充

- 学院新闻；
- 本科生科研、竞赛、优秀毕业生去向；
- 实验班、拔尖班、荣誉学院、卓越学院相关页面；
- 夏令营、保研经验分享中来自学校或学院的公开页面。

### C 级：非官方资料，只能做口碑信号

可查但必须标明“非官方/口碑”：

- 知乎；
- 百度贴吧；
- 小红书；
- B 站；
- 高考论坛；
- 保研论坛；
- 新生群、经验帖或学生博客。

非官方资料不能单独支撑强结论，只能形成待复核信号。例如“疑似形式主义重”“宿舍差评多”“课程偏水”“转专业实际难”等。

## 推荐搜索式

优先用学校名、学院名和专业名组合搜索：

- `{学校} {专业} 培养方案`
- `{学校} {专业} 课程体系`
- `{学校} {专业} 专业介绍`
- `{学校} {学院} {专业} 本科培养方案`
- `{学校} 推免 办法 本科`
- `{学校} {学院} 推免 细则`
- `{学校} {专业} 保研`
- `{学校} {专业} 科研训练`
- `{学校} 转专业 办法`
- `{学校} 辅修 双学位 办法`
- `{学校} 宿舍 校区 {专业}`
- `{学校} {专业} 贴吧`
- `{学校} {专业} 知乎`

如果学校官网检索困难，优先尝试：

- `site:{学校官网域名} {专业} 培养方案`
- `site:{学校官网域名} 推免 办法`
- `site:{学院官网域名} {专业} 课程`

## 输出文件

每个 subagent 输出两个 CSV 或 JSONL 文件。CSV 推荐使用 UTF-8 with BOM。

### 1. 行级轻爬结果

文件名：`<shard_id>_light_crawl_rows.csv`

字段：

- `pool_id`
- `volunteer_id`
- `college_name`
- `major_name`
- `crawl_status`：`complete` / `partial` / `not_found`
- `department_name`
- `department_url`
- `major_intro_url`
- `training_plan_url`
- `training_plan_year`
- `core_courses_summary`
- `ai_path_fit_notes`
- `math_foundation_notes`
- `cs_ai_foundation_notes`
- `research_resources_notes`
- `research_resources_source_ids`
- `recommendation_or_honors_notes`
- `postgraduate_path_notes`
- `recommendation_policy_notes`
- `recommendation_source_ids`
- `transfer_policy_notes`
- `learning_freedom_notes`
- `dorm_campus_notes`
- `dorm_campus_source_ids`
- `risk_tags`
- `uncertainty_tags`
- `nonofficial_signals`
- `source_ids`
- `next_deep_questions`
- `agent_confidence`：`high` / `medium` / `low`

`recommendation` 字段指推免/保研相关信息。字段名不用中文是为了后续脚本稳定合并。

### 2. 证据来源表

文件名：`<shard_id>_sources.csv`

字段：

- `source_id`
- `pool_id_or_school_key`
- `source_level`：`official_hard` / `official_soft` / `nonofficial`
- `source_type`：`admission` / `department` / `training_plan` / `policy` / `research` / `dorm` / `forum` / `other`
- `title`
- `publisher`
- `url`
- `publish_date`
- `access_date`
- `evidence_excerpt`
- `evidence_summary`
- `used_for_fields`

`evidence_excerpt` 只放短摘录，不要长篇复制。优先用自己的话概括。

## 风险标签

`risk_tags` 可以包含多个，用英文分号分隔：

- `major_diversion_risk`：大类或实验班分流不确定；
- `off_target_courses`：课程明显偏离数学/统计/计算机/AI 基础；
- `sino_foreign`：中外合作；
- `mandatory_abroad`：强制或高度绑定出国阶段；
- `tuition_unit_unclear`：学费字段疑似万元、美元或单位不明；
- `very_high_tuition_possible`：学费可能显著高于普通专业；
- `small_plan`：招生计划很小；
- `new_no_history`：无历史位次；
- `campus_move`：存在校区搬迁；
- `remote_or_weak_resource`：资源或校区位置可能影响科研机会；
- `management_heavy_signal`：口碑显示管理强或形式主义重；
- `dorm_negative_signal`：住宿口碑明显负面；
- `source_conflict`：官方资料或口碑资料相互矛盾。

`uncertainty_tags` 用来记录还没查清的问题：

- `training_plan_not_found`
- `recommendation_not_found`
- `transfer_policy_not_found`
- `department_unclear`
- `campus_unclear`
- `dorm_unclear`
- `forum_signal_sparse`
- `policy_year_unclear`

除以上标签外，不要自造风险或不确定性标签。需要补充说明时写入 `next_deep_questions`。

## 证据标准

每个事实性判断都要能追溯到 `source_id`。

允许写：

- “培养方案显示核心课程包含数学分析、高等代数、概率统计、数值分析；AI 相关课程较少，需要自学补足。”
- “学院官网显示有智能计算/机器学习相关团队，但未找到本科生进入课题组的明确机制。”
- “未找到学院级推免细则，只找到学校级推免办法，需深爬确认学院执行口径。”

不允许写：

- “学校很好，氛围不错。”
- “这个专业适合 AI 科学家。”
- “保研应该可以。”
- “宿舍还行。”

如果信息缺失，写 `not_found` 或对应 `uncertainty_tags`，不要脑补。

## 轻爬停止条件

对每个学校，轻爬优先保证覆盖面，不追求论坛深挖。

建议上限：

- 每所学校 8 到 12 个有效来源；
- 每个专业至少尝试找到专业介绍或培养方案；
- 校级推免、转专业、宿舍/校区各至少尝试一次；
- 非官方资料最多记录 3 条高信号结果；
- 搜不到时记录搜索式和 `not_found`，不要无限搜索。

## Pilot 10 所测试办法

正式爬 900 前，先抽 10 所做校准。样本应覆盖：

- 2 所省内数学/信计/统计强相关；
- 2 所 CS/AI 被筛掉但看起来有吸引力；
- 2 所无历史/新专业；
- 2 所中外/英文授课项目；
- 2 所备份池里可能被误伤的高上限学校。

Pilot 的目标不是打分，而是验证：

- 字段是否足够；
- 官方资料是否容易找到；
- subagent 是否会泛泛评价；
- 哪些信息源最有价值；
- 哪些字段需要拆分或合并；
- 后续自动合并是否顺畅。

Pilot 完成后，主线程检查 10 所结果，再决定是否修改协议、字段和风险标签。

## 汇总与后续筛选

主线程合并所有 `<shard_id>_light_crawl_rows.csv` 和 `<shard_id>_sources.csv` 后，生成一张 900 轻爬总表。

筛到 300 时，轻爬信息只作为以下信号：

- 强保留信号：培养方案高度贴合、学院科研资源强、推免信息清楚、学习自由度高；
- 强降权信号：分流风险、专业偏离、政策缺失、校区/住宿硬伤、明显管理负担；
- 待复核信号：无历史、新专业、中外合作、学费单位不明、小计划、口碑矛盾。

进入 300 后再做深爬，深爬才进行正式打分。
