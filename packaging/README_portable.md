# 浙江志愿落点概率估算器打包说明

仓库提交的是估算器源码、内置位次模型数据库和打包脚本，不提交 PyInstaller 生成的完整便携版目录。

原因：完整便携版会包含 Python 运行时和依赖库，通常几十 MB，更适合放到 GitHub Release 或网盘，不适合直接进入 git 历史。

## 开发环境运行

Windows:

```powershell
python -X utf8 tools\estimate_volunteer_landing_portable.py "你的志愿表.xlsx" --master data\rank_model_database.csv --user-rank 39000
```

macOS:

```bash
python3 tools/estimate_volunteer_landing_portable.py "你的志愿表.xlsx" --master data/rank_model_database.csv --user-rank 39000
```

支持输入：

- `.xls` 浙江志愿录入模板；
- `.xlsx` 浙江志愿录入模板；
- `.csv`，四列为 `院校代码/院校名称/专业代码/专业名称`。

输出会生成在输入文件同目录：

- `*_落点概率估算.xlsx`
- `*_落点概率估算.csv`
- `*_落点概率估算报告.txt`

## 进度条

默认参数 `--progress auto`：在交互式终端里显示 Monte Carlo 进度条，在重定向输出或自动化环境中自动关闭。

常用参数：

```bash
--progress on
--progress off
--progress-interval 0.5
```

进度条没有引入 `tqdm` 等额外依赖，便携包体积和兼容性更稳。

## Windows 打包

推荐直接运行 Windows 打包脚本：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_package.ps1
```

脚本会运行 PyInstaller，并把启动器和说明文件复制进发布目录，最后生成：

```text
dist/志愿落点概率估算器_windows.zip
```

需要本机安装打包依赖：

```powershell
python -m pip install pyinstaller openpyxl xlrd
```

发布便携版时，建议把生成目录整体压缩为 zip。目录中通常包括：

- `志愿落点概率估算器.exe`
- `_internal/`
- `README_使用说明.txt`
- `运行_志愿落点概率估算器.bat`

`packaging/run_estimator.bat` 是 Windows 启动脚本模板，会寻找同目录下的 `.exe` 并运行。

不要让普通用户直接双击 `.exe`。这是控制台程序，运行结束或报错后窗口可能立刻关闭，看起来像“闪退”。发布包里应当让用户双击 `运行_志愿落点概率估算器.bat`。

## macOS 打包

PyInstaller 不能可靠地从 Windows 交叉编译 macOS 可执行文件。macOS 包需要在 Mac 或 GitHub Actions 的 `macos-latest` runner 上构建。

在 Mac 本机执行：

```bash
bash packaging/build_macos_package.sh
```

脚本会创建本地虚拟环境、安装打包依赖、运行 `packaging/zytb_landing_estimator_macos.spec`，并生成：

```text
dist_macos/志愿落点概率估算器_macos.zip
```

zip 内包含：

- `志愿落点概率估算器`
- `_internal/`
- `运行_志愿落点概率估算器.command`
- `README_使用说明.txt`

仓库还提供了 GitHub Actions 工作流 `.github/workflows/build-estimator-macos.yml`，可手动触发并下载 macOS artifact。

## 参考位次口径

工具内置 `data/rank_model_database.csv`，每条志愿的参考位次按以下规则生成：

1. 如果有 2025 年历史位次，直接使用 2025 年最低录取位次。
2. 如果没有 2025 年，但有 2024 或 2023 年历史位次，使用最近一年历史位次。
3. 如果该志愿完全无历史位次，使用同校所有有历史专业的截尾均值作为参考位次。
4. 如果仍然无法预测，运行时要求用户手动输入参考位次。

同校截尾均值规则：

- 同校历史专业数大于 2 时，去掉最高位次和最低位次后取平均；
- 同校历史专业数不大于 2 时，直接取平均。

无历史预测位次只适合做结构估算，不应当作真实录取位次。

## 模型说明

模型把位次转换成全省参考人数下的 logit 百分位：

```text
p = rank / population
z = log(p / (1 - p))
```

再使用 `2023 -> 2024`、`2024 -> 2025` 的历史年际变化作为经验残差，按以下相似度为每个志愿抽样：

- 位次段接近；
- 专业族接近；
- 招生计划数接近；
- 浙江省内/省外接近。

最后按浙江专业平行志愿的检索规则做 Monte Carlo 模拟，输出到达概率、到达后可录概率和最终落点概率。

这个模型适合做志愿表结构体检，不适合把小数点后的概率当成精确预测。
