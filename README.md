# 2026 浙江普通类平行志愿数据库

这个仓库把 2026 年浙江普通类平行计划表和 2023-2025 年普通类平行投档录取情况整理成一个可筛选、可复核的数据库。用途是个人志愿填报筛选，不追求产品化推荐系统。

主表粒度是一个 2026 平行志愿项，即 `院校代码 + 专业代码`。历史录取 PDF 没有 2026 专业代码，因此历史数据按院校身份和专业名称保守匹配到 2026 志愿项。

## 核心文件

- `build_clean_database.py`: 从原始资料构建清洗数据库的脚本。
- `curation_rules.py`: 历史匹配的人工校订规则，作为构建输入保留。
- `requirements.txt`: Python 依赖。
- `2026年_普通类平行计划1_普通类平行录取_物理化学生物.xlsm`: 2026 普通类平行计划原始表。
- `2023录取情况.pdf`, `2024录取情况.pdf`, `2025录取情况.pdf`: 2023-2025 录取情况原始 PDF。
- `outputs/clean_database/`: 当前推荐使用的清洗结果。

## 主要输出

- `outputs/clean_database/volunteer_database.xlsx`: Excel 工作簿，适合直接筛选。
- `outputs/clean_database/zhejiang_parallel_volunteer_database.sqlite`: SQLite 数据库。
- `outputs/clean_database/volunteer_master_2026_with_history.csv`: 主表，一行一个 2026 志愿项，并拼入过去三年录取情况。
- `outputs/clean_database/plan_2026.csv`: 2026 计划清洗表。
- `outputs/clean_database/admissions_history_2023_2025.csv`: 2023-2025 历史录取抽取表。
- `outputs/clean_database/ambiguous_history_matches.csv`: 仍存在多种可能匹配、未自动写入主表的历史候选。
- `outputs/clean_database/college_identity_mismatches.csv`: 同院校代码但院校身份仍不兼容或不确定的候选。
- `outputs/clean_database/curated_rejections.csv`: 校订后从主表移出的高风险非精确历史匹配。

## 当前数据规模

- 2026 计划志愿项: 24,240
- 历史录取记录: 66,481
- 主表志愿项: 24,240
- 仍保留的歧义匹配候选: 263
- 院校身份不兼容/不确定拦截: 2
- 校订排除的非精确匹配: 1,073
- 匹配到 2026 志愿项的历史记录: 2023 年 13,809，2024 年 15,511，2025 年 18,940

## 复现构建

```powershell
python -m pip install -r requirements.txt
python build_clean_database.py
```

脚本会读取仓库根目录下的 2026 计划表、2023-2025 PDF 和 `curation_rules.py`，并写入 `outputs/clean_database/`。

## 重要口径

- 历史 PDF 没有 2026 专业代码，历史匹配不能视为官方专业代码映射。
- 主表中的空白历史列表示没有找到高置信匹配，不等于该专业过去一定没有招生。
- `*_match_level` 记录历史匹配方式；`exact` 最稳，`manual_ambiguous` 表示从歧义候选中按校订规则指定拼回。
- `base` 和 `contains_unique` 中被校订为高风险的候选已移出主表，写入 `curated_rejections.csv`。
- `*_history_source_page` 是历史 PDF 页码，进入最终志愿单前建议回查原始资料。
