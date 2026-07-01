#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv-estimator-mac}"
DIST_DIR="${DIST_DIR:-dist_macos}"
BUILD_DIR="${BUILD_DIR:-build_macos}"
APP_NAME="志愿落点概率估算器"
PACKAGE_DIR="$DIST_DIR/$APP_NAME"

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r packaging/requirements_estimator.txt

pyinstaller packaging/zytb_landing_estimator_macos.spec \
  --clean \
  --noconfirm \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR"

cp packaging/run_estimator.command "$PACKAGE_DIR/运行_志愿落点概率估算器.command"
chmod +x "$PACKAGE_DIR/运行_志愿落点概率估算器.command"

cat > "$PACKAGE_DIR/README_使用说明.txt" <<'EOF'
浙江志愿落点概率估算器 macOS 版

双击“运行_志愿落点概率估算器.command”启动。
程序会先询问考生位次，再要求拖入兼容浙江志愿填报系统的志愿录入表。

支持输入：
- .xls
- .xlsx
- .csv

输出会写到输入志愿表同目录：
- *_落点概率估算.xlsx
- *_落点概率估算.csv
- *_落点概率估算报告.txt

如果 macOS 提示来自未知开发者：
1. 右键点击“运行_志愿落点概率估算器.command”
2. 选择“打开”
3. 在弹窗中再次选择“打开”

模型只适合做志愿表结构体检，不适合把小数点后的概率当作精确预测。
EOF

(
  cd "$DIST_DIR"
  zip -qr "${APP_NAME}_macos.zip" "$APP_NAME"
)

echo "macOS package created:"
echo "$DIST_DIR/${APP_NAME}_macos.zip"
