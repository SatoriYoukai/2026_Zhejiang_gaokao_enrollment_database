# 2026 浙江普通类平行志愿数据库

这个仓库把 2026 年浙江普通类平行招生计划和 2023-2025 年普通类平行投档录取情况整理成一套可筛选、可复核、可二次分析的数据包。

主表一行对应一个 2026 平行志愿项，即 `院校代码 + 专业代码`，并尽量拼入过去三年的最低录取分数、位次和来源页码。

这是一套个人填报研究中沉淀出来的工程产物。它能辅助筛选、排序和结构体检，但不能替代最终填报前对官方计划、学校招生章程、体检限制、单科限制和个人偏好的核对。

## 主要内容

- `outputs/clean_database/`: 清洗后的核心数据库，包含 CSV、Excel 和 SQLite。
- `outputs/volunteer_browser/`: 面向全量志愿数据库的静态筛选浏览器。
- `outputs/ai_path_tag_browser/`: 面向 AI/数学/计算机路径候选池的标签浏览器，半成品，保留作复盘和二次开发参考。
- `tools/estimate_volunteer_landing_portable.py`: 浙江专业平行志愿落点概率估计器。
- `data/rank_model_database.csv`: 落点估计器使用的轻量位次模型数据库。
- `packaging/`: 便携版估计器的 Windows/macOS 打包说明、启动脚本模板和 macOS GitHub Actions 构建工作流。

## 快速使用

### 1. 使用清洗数据

最直接的文件：

- `outputs/clean_database/volunteer_master_2026_with_history.csv`
- `outputs/clean_database/volunteer_database.xlsx`
- `outputs/clean_database/zhejiang_parallel_volunteer_database.sqlite`

### 2. 打开普通筛选浏览器

```powershell
python -m http.server 8765 --directory outputs/volunteer_browser
```

然后访问：

```text
http://127.0.0.1:8765/
```

也可以直接打开 `outputs/volunteer_browser/index.html`。如果浏览器限制本地大文件脚本，使用上面的本地 HTTP 服务。

### 3. 打开 AI 路径标签浏览器

```powershell
python -m http.server 8771 --directory outputs/ai_path_tag_browser
```

然后访问：

```text
http://127.0.0.1:8771/
```

注意：这个 browser 是半成品，里面的标签、权重和证据摘要带有本次实际填报研究的个人偏好。它适合复盘和辅助浏览，不适合当作通用自动决策工具。

### 4. 运行落点概率估计器

开发环境运行：

```powershell
python -X utf8 tools\estimate_volunteer_landing_portable.py "你的志愿表.xlsx" --master data\rank_model_database.csv --user-rank 39000
```

支持 `.xls`、`.xlsx`、`.csv` 志愿录入表。输出会生成在输入文件同目录，包括 CSV、Excel 和 TXT 报告。默认在交互式终端中显示 Monte Carlo 进度条。

更详细说明见：

```text
docs/volunteer_landing_probability_tool.md
packaging/README_portable.md
```

## 数据口径

- `tuition` 统一为元/年；`tuition_raw` 保留原始计划表中的学费写法。
- 2023-2025 历史 PDF 没有 2026 专业代码，因此历史记录按院校身份和专业名称保守匹配到 2026 志愿项。
- 主表中的空白历史列表示没有找到高置信匹配，不等于该专业过去一定没有招生。
- `*_match_level` 记录历史匹配方式；`exact` 最稳，`manual_ambiguous` 表示从歧义候选中按校订规则指定。
- `*_history_source_page` 是历史 PDF 页码，正式使用前建议按页码回查原始资料。

## 核心输出

- `plan_2026.csv`: 2026 计划清洗表。
- `admissions_history_2023_2025.csv`: 2023-2025 历史录取抽取表。
- `volunteer_master_2026_with_history.csv`: 主表，一行一个 2026 志愿项，并拼入过去三年录取情况。
- `volunteer_database.xlsx`: Excel 工作簿。
- `zhejiang_parallel_volunteer_database.sqlite`: SQLite 数据库。
- `ambiguous_history_matches.csv`: 仍存在多种可能匹配、未自动写入主表的历史候选。
- `college_identity_mismatches.csv`: 同院校代码但院校身份仍不兼容或不确定的候选。
- `curated_rejections.csv`: 校订后从主表移出的高风险非精确历史匹配。

## 当前数据规模

- 2026 计划志愿项：24,240
- 历史录取记录：66,481
- 主表志愿项：24,240
- 仍保留的歧义匹配候选：215
- 院校身份不兼容或不确定拦截：2
- 校订排除的非精确匹配：1,074
- 匹配到 2026 志愿项的历史记录：2023 年 13,809，2024 年 15,965，2025 年 18,940

## 复现构建

```powershell
python -m pip install -r requirements.txt
python build_clean_database.py
python tools/build_volunteer_browser.py
```

`build_clean_database.py` 会读取仓库根目录下的 2026 计划表、2023-2025 PDF 和 `curation_rules.py`，并写入 `outputs/clean_database/`。重建数据库后，再运行 `tools/build_volunteer_browser.py` 生成 `outputs/volunteer_browser/` 的前端数据。

AI 路径标签浏览器的生成脚本是：

```powershell
python tools/build_ai_path_tag_browser.py
```

它依赖本次研究过程中产生的筛选、打标、证据汇总文件。若要通用化，需要重做数据契约。

## 质量控制

- 歧义匹配不会直接写入主表，会进入 `ambiguous_history_matches.csv`。
- 院校身份不兼容或不确定的候选会进入 `college_identity_mismatches.csv`。
- 经人工校订判定为高风险的非精确匹配会移出主表，进入 `curated_rejections.csv`。
- 最近一次固定随机 3,000 个志愿项抽查已对照原始资料复核；此前发现的跨校区短名追溯风险已通过院校身份键修正。

## 重要限制

- 历史匹配不能视为官方专业代码映射。
- 数据清洗不能替代最终填报前的官方文件核对。
- 落点概率估计器适合做志愿表结构体检，不适合把小数点后的概率当作精确预测。
- 标签 browser 中的证据缺口不能直接解释为学校或专业质量差。
- 本仓库不完整处理个人偏好、体检限制、单科限制、招生章程特殊要求等最终决策问题。
