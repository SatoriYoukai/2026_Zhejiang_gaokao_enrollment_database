#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP="./志愿落点概率估算器"
if [[ ! -x "$APP" ]]; then
  APP="./zytb_landing_estimator"
fi

if [[ ! -x "$APP" ]]; then
  echo "ERROR: 未找到可执行文件：志愿落点概率估算器"
  echo "请确认这个 .command 文件和可执行文件在同一个目录。"
  read -r -n 1 -s -p "按任意键退出..."
  echo
  exit 1
fi

"$APP" "$@"
status=$?

echo
if [[ "$status" -ne 0 ]]; then
  echo "ERROR: 估算器退出码：$status"
fi
read -r -n 1 -s -p "运行结束，按任意键关闭窗口..."
echo
exit "$status"
