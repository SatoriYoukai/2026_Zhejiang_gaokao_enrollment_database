# 浙江普通类平行志愿清洗数据库

## 文件

- `zhejiang_parallel_volunteer_database.sqlite`: SQLite 数据库。
- `volunteer_database.xlsx`: Excel 工作簿，方便直接筛选查看。
- `volunteer_master_2026_with_history.csv`: 主表，一行一个 2026 平行志愿项。
- `plan_2026.csv`: 2026 普通类平行计划清洗表。
- `admissions_history_2023_2025.csv`: 2023-2025 普通类平行投档录取 PDF 抽取表。
- `ambiguous_history_matches.csv`: 同院校同专业名存在多个可能历史匹配的疑点清单。
- `college_identity_mismatches.csv`: 同院校代码但历史院校名与 2026 院校名不兼容，未自动拼回的清单。
- `curated_rejections.csv`: 按校订规则从主表移出的高风险非精确历史匹配。

## SQLite 表

- `plan_2026`: 2026 计划表，粒度为院校代码 + 专业代码。
- `admissions_history`: 历史录取抽取表，粒度为 PDF 中的院校 + 专业行。
- `volunteer_master`: 已把历史录取列拼回 2026 志愿项的宽表。
- `ambiguous_matches`: 未自动写入主表的歧义匹配。
- `college_identity_mismatches`: 院校身份不兼容而被拦截的历史候选。
- `curated_rejections`: 按校订规则不再自动写入主表的历史候选。

## 统计

- 2026 计划志愿项: 24,240
- 历史抽取记录: 66,481
- 歧义匹配候选: 215
- 院校身份不兼容拦截: 2
- 校订排除的非精确匹配: 1,074
- 2023 匹配到 2026 志愿项: 13,809
- 2024 匹配到 2026 志愿项: 15,965
- 2025 匹配到 2026 志愿项: 18,940

## 重要口径

- 历史 PDF 没有 2026 专业代码，因此匹配规则是保守的：先按院校代码 + 专业全名，再按去括号专业名，最后仅在同院校同年唯一包含关系时写入。
- 同一院校代码跨年可能对应不同院校；当前版本会先校验院校名/alias，身份不兼容则不写入主表。
- `*_match_level` 记录匹配方式；`manual_ambiguous` 表示从歧义候选中按校订规则指定拼回。
- `base` 和 `contains_unique` 里被校订规则判为 DROP/UNCERTAIN 的候选已移出主表，写入 `curated_rejections.csv`。
- `tuition` 统一为元/年；`tuition_raw` 保留原始计划表中的学费写法，例如 `11万`、`见简注`。
- `*_history_source_page` 是 PDF 页码，进入最终志愿单前应回查原 PDF。
- 主表中空白历史列表示未找到高置信匹配，不等于该专业过去没有招生。
