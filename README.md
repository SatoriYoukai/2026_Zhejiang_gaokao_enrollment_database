# 2026 浙江普通类平行志愿数据库

这个仓库把 2026 年浙江普通类平行计划表和 2023-2025 年普通类平行投档录取情况整理成一个可筛选、可复核的数据包。主表一行对应一个 2026 平行志愿项，即 `院校代码 + 专业代码`，并尽量拼入过去三年的录取分数、位次和来源页码。

这是个人在志愿填报时筛选用的数据整理项目。正式填报前请回查原始计划表、历史 PDF 和浙江省教育考试院发布的最新文件。

## 最快使用

推荐先用离线浏览器筛选器：

1. 下载或克隆本仓库。
2. 打开 `outputs/volunteer_browser/index.html`。
3. 如果浏览器拦截本地大文件脚本，改用本地服务打开：

```powershell
python -m http.server 8765 --directory outputs/volunteer_browser
```

然后访问 `http://127.0.0.1:8765/`。

也可以直接使用这些数据文件：

- `outputs/clean_database/volunteer_database.xlsx`: Excel 工作簿，适合手动筛选。
- `outputs/clean_database/zhejiang_parallel_volunteer_database.sqlite`: SQLite 数据库，适合写 SQL 查询。
- `outputs/clean_database/volunteer_master_2026_with_history.csv`: 主表 CSV，适合二次处理。

当前推荐目录是 `outputs/clean_database/` 和 `outputs/volunteer_browser/`，没有 `v2`、`v3` 之类旧版本目录。

## 数据口径

- 2026 计划表提供志愿项、院校、专业、选科、计划数、学费、备注等字段。
- `tuition` 统一为元/年；`tuition_raw` 保留原始计划表中的学费写法，例如 `11万`、`见简注`。
- 2023-2025 历史 PDF 没有 2026 专业代码，因此历史记录按院校身份和专业名称保守匹配到 2026 志愿项。
- 主表中的空白历史列表示没有找到高置信匹配，不等于该专业过去一定没有招生。
- `*_match_level` 记录历史匹配方式；`exact` 最稳，`manual_ambiguous` 表示从歧义候选中按校订规则指定拼回。
- `*_history_source_page` 是历史 PDF 页码，进入最终志愿单前建议按页码回查原始资料。

## 仓库内容

- `build_clean_database.py`: 从原始资料构建清洗数据库的脚本。
- `curation_rules.py`: 历史匹配的人工校订规则。
- `tools/build_volunteer_browser.py`: 从主表 CSV 生成离线 HTML 筛选器数据。
- `requirements.txt`: Python 依赖。
- `2026年_普通类平行计划1_普通类平行录取_物理化学生物.xlsm`: 2026 普通类平行计划原始表。
- `2023录取情况.pdf`, `2024录取情况.pdf`, `2025录取情况.pdf`: 2023-2025 录取情况原始 PDF。
- `outputs/clean_database/`: 清洗后的 Excel、CSV、SQLite 和复核辅助表。
- `outputs/volunteer_browser/`: 可离线打开的 HTML 筛选器。

## 主要输出

- `volunteer_database.xlsx`: Excel 工作簿。
- `zhejiang_parallel_volunteer_database.sqlite`: SQLite 数据库。
- `volunteer_master_2026_with_history.csv`: 主表，一行一个 2026 志愿项，并拼入过去三年录取情况。
- `plan_2026.csv`: 2026 计划清洗表。
- `admissions_history_2023_2025.csv`: 2023-2025 历史录取抽取表。
- `ambiguous_history_matches.csv`: 仍存在多种可能匹配、未自动写入主表的历史候选。
- `college_identity_mismatches.csv`: 同院校代码但院校身份仍不兼容或不确定的候选。
- `curated_rejections.csv`: 校订后从主表移出的高风险非精确历史匹配。

## 当前数据规模

- 2026 计划志愿项: 24,240
- 历史录取记录: 66,481
- 主表志愿项: 24,240
- 仍保留的歧义匹配候选: 215
- 院校身份不兼容或不确定拦截: 2
- 校订排除的非精确匹配: 1,074
- 匹配到 2026 志愿项的历史记录: 2023 年 13,809，2024 年 15,965，2025 年 18,940

## 复现构建

```powershell
python -m pip install -r requirements.txt
python build_clean_database.py
python tools/build_volunteer_browser.py
```

`build_clean_database.py` 会读取仓库根目录下的 2026 计划表、2023-2025 PDF 和 `curation_rules.py`，并写入 `outputs/clean_database/`。重建数据库后，再运行 `tools/build_volunteer_browser.py` 生成 `outputs/volunteer_browser/` 的前端数据。

## 质量控制

- 歧义匹配不会直接写入主表，会进入 `ambiguous_history_matches.csv`。
- 院校身份不兼容或不确定的候选会进入 `college_identity_mismatches.csv`。
- 经人工校订判定为高风险的非精确匹配会移出主表，进入 `curated_rejections.csv`。
- 最近一次固定随机 3,000 个志愿项抽查已对照原始资料复核；此前发现的跨校区短名追溯风险已通过院校身份键修正。

## 重要限制

- 历史匹配不能视为官方专业代码映射。
- 数据清洗不能替代最终填报前的官方文件核对。
- 本项目只整理计划和历史投档信息，不预测录取概率，也不处理个人偏好、体检限制、单科要求等完整填报决策问题。
