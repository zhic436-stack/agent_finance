#!/usr/bin/env bash
# =============================================================================
# 一键迁移到 AtomGit (赛事源码平台要求)
# 用法:
#   bash scripts/push_to_atomgit.sh https://atomgit.com/<用户名>/agent_finance.git
#
# 前提:
#   1. 已在 atomgit.com 新建空仓库 agent_finance (不要勾选初始化 README)
#   2. 本机有 git (Windows 可用 Git Bash / PowerShell)
# =============================================================================
set -e
cd "$(dirname "$0")/.."

URL="${1:?用法: bash scripts/push_to_atomgit.sh https://atomgit.com/<用户名>/agent_finance.git}"

echo "[1/3] 配置 AtomGit 远端..."
if git remote | grep -q "^atomgit$"; then
    git remote set-url atomgit "$URL"
else
    git remote add atomgit "$URL"
fi

echo "[2/3] 推送 master 分支到 AtomGit..."
git push atomgit master

echo "[3/3] 完成!"
echo "仓库地址: $URL"
echo "之后更新: git push atomgit master"
