#!/bin/sh
# agent-toolkit 一行安装（Linux / macOS / Git-Bash）
#   curl -fsSL https://raw.githubusercontent.com/55200wq/agent-toolkit/main/install/install.sh | bash
#   可带参数：... | bash -s -- --project /path/to/project --all
set -e
REPO="${AGENT_TOOLKIT_REPO:-https://github.com/55200wq/agent-toolkit.git}"
TMP="$(mktemp -d)"
echo "[agent-toolkit] 拉到临时目录：$TMP"
git clone --depth 1 "$REPO" "$TMP/agent-toolkit" >/dev/null 2>&1
PY=python; command -v $PY >/dev/null 2>&1 || PY=python3
"$PY" "$TMP/agent-toolkit/install/install.py" "$@"
echo "[agent-toolkit] 完成 ✓（临时目录：$TMP，可自行删除）"
