# 发布到 GitHub（逐步）

> 前提：本目录已经是 git 仓库（`git log` 有历史 ✓），分支为 `main` ✓

## 一、替换占位 `55200wq`

仓库里所有外部 URL 都用了占位 `55200wq` ✓，发布前替换成你的 GitHub 用户名：

```bash
cd agent-toolkit
grep -rn "55200wq" . --include="*.md" --include="*.sh" --include="*.ps1" --include="*.py"
# 批量替换（把 YOURNAME 换成你的用户名）
grep -rl "55200wq" . --include="*.md" --include="*.sh" --include="*.ps1" \
  | xargs sed -i 's|55200wq|YOURNAME|g'
git add -A && git commit -m "替换 GitHub 用户名为 YOURNAME"
```

## 二、建远程并推送

GitHub 上新建仓库（**不要**勾选自动生成 README/LICENSE，否则要合并 ✗）：

```bash
git remote add origin https://github.com/YOURNAME/agent-toolkit.git
git push -u origin main
```

首次推送会弹登录（浏览器或 Personal Access Token）✓ 之后就不用再输 ✓

*若用 SSH：* `git remote add origin git@github.com:YOURNAME/agent-toolkit.git`

## 三、推送后自检（重要）

```bash
# 1) 一行安装脚本能拉到吗（把 URL 里的 YOURNAME 换成你的）
curl -fsSL https://raw.githubusercontent.com/YOURNAME/agent-toolkit/main/install/install.sh | head -5

# 2) 真装一次到临时目录，验证端到端
tmp=$(mktemp -d) && mkdir -p "$tmp/proj" && cd "$tmp/proj" && git init -q
python <agent-toolkit>/install/install.py --project . --with-agents --with-hook
python tools/provenance_check.py --audit
python tools/run_all_selftests.py --list
```

## 四、README 首页建议补三样

| 补什么 | 为什么 |
|---|---|
| **演示**：一段"装之前/装之后"的真实报错输出 | 一眼看懂价值 |
| **徽章**（可选）：license / python 版本 | 显得正规 |
| **一张结构图** | 别人 30 秒理解按功能分目录 |

## 五、以后更新工具集

```bash
# 工具集自身
python tools/selftests/run_all_selftests.py --root .
python tools/provenance/provenance_check.py --root . --audit
git add -A && git commit -m "..." && git push

# 各项目更新到最新版（配置不会被覆盖 ✓）
python install/install.py --project <项目根>
python install/install.py --project <项目根> --check
```

> **约定**：项目里的工具副本不要手改 ✗ —— 改源、提交、再让项目更新 ✓
