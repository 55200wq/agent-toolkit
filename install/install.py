"""agent-toolkit 安装器：把工具装进项目、把规则装进 agent、把 AGENTS 片段写进项目。

【这是什么】
    本脚本是 agent-toolkit（https://github.com/55200wq/agent-toolkit）的安装入口 ✓
    它把工具集的**完整实现**分发到三处：
      · 项目：可执行工具副本 + 配置模板（**缺了才写，绝不覆盖** ✓）+ 身份证 `.agent-tools.json`（文件名保持稳定，改名不影响已装项目）
      · agent：规则 skill（DSH 默认 `~/.dsh/skills/`，其他 agent 用 `--skills-dir`）
      · 项目 AGENTS.md：数值纪律片段（**标记包裹、幂等替换** ✓）

【用法】
    python install.py --project <项目根> [--with-agents] [--with-hook]   # 装进项目
    python install.py --skills [--skills-dir <目录>]                     # 装 skill 给 agent
    python install.py --all --project <项目根>                           # 两者都装
    python install.py --project <项目根> --check                         # 漂移检查
    python install.py --list                                             # 看会装什么

【退出码】
    0 成功/一致 ｜ 1 项目副本被本地改过 ｜ 2 落后于工具集 ｜ 3 未安装或参数缺失

【设计约定（改本文件前先读）】
    · 配置是**项目自有**：缺了才写、不覆盖、也不参与漂移比较（各项目本应不同 ✓）
    · 受管文件（引擎）参与哈希比较 ⇒ 能查出"被本地改过"与"落后" ✓
    · AGENTS 片段用 `<!-- agent-tools:begin/end -->` 标记 ⇒ 重复安装不重复追加 ✓
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

TOOLKIT = Path(__file__).resolve().parent.parent
VERSION_FILE = TOOLKIT / 'VERSION'
STAMP_NAME = '.agent-tools.json'          # 身份证文件名保持稳定（改名不影响已装项目）
BEGIN = '<!-- agent-toolkit:begin'
END = '<!-- agent-toolkit:end -->'
# 改名前的旧标记：迁移时**替换**旧块，而不是重复追加 ✓
LEGACY_BEGIN = '<!-- agent-tools:begin'
LEGACY_END = '<!-- agent-tools:end -->'
DEFAULT_SKILLS_DIR = Path.home() / '.dsh' / 'skills'      # DSH 默认；其他 agent 用 --skills-dir

# 受管文件：源 → 项目内相对路径（参与漂移比较 ✓）
MANAGED = [
    ('tools/provenance/provenance_check.py', 'tools/provenance_check.py'),
    ('tools/provenance/_selftest_provenance.py', 'tools/_selftest_provenance.py'),
    ('tools/selftests/run_all_selftests.py', 'tools/run_all_selftests.py'),
]
# 配置模板：源 → 项目内相对路径（缺了才写 ✓ 不参与比较 ✓）
CONFIGS = [
    ('templates/provenance.example.json', 'tools/provenance.json'),
    ('templates/selftests.example.json', 'tools/selftests.json'),
]
# skill：源 → 目标子目录名
SKILLS = [
    ('skills/measured-or-flagged-zh/SKILL.md', 'measured-or-flagged-zh'),
]
AGENTS_SNIPPET = 'templates/AGENTS.snippet.md'
HOOK = 'templates/pre-commit'


def sha12(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else ''


def version() -> str:
    return VERSION_FILE.read_text(encoding='utf-8').strip() if VERSION_FILE.exists() else '0.0.0'


# ------------------------------------------------------------------ 列表
def do_list() -> int:
    print('agent-toolkit %s' % version())
    print('受管文件（参与漂移比较）：')
    for src, dst in MANAGED:
        print('  %-46s → %s' % (src, dst))
    print('配置模板（缺了才写、绝不覆盖）：')
    for src, dst in CONFIGS:
        print('  %-46s → %s' % (src, dst))
    print('skill（装到 agent 的 skills 目录）：')
    for src, name in SKILLS:
        print('  %-46s → %s/SKILL.md' % (src, name))
    print('可选：--with-agents（写 AGENTS 片段）｜ --with-hook（装 git 钩子）')
    return 0


# ------------------------------------------------------------------ 装进项目
def install_project(project: Path, with_agents=False, with_hook=False) -> int:
    (project / 'tools').mkdir(parents=True, exist_ok=True)
    stamp = {'toolkit_version': version(), 'installed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
             'files': {}, 'configs': []}
    written, kept = [], []
    for src, dst in MANAGED:
        s = TOOLKIT / src
        shutil.copy2(s, project / dst)
        written.append(dst)
        stamp['files'][dst] = sha12(s)
    for src, dst in CONFIGS:
        s = TOOLKIT / src
        target = project / dst
        stamp['configs'].append(dst)              # 项目自有 ⇒ 不比较 ✓
        if target.exists():
            kept.append(dst)
        else:
            shutil.copy2(s, target)
            written.append(dst)
    if with_agents:
        changed = write_agents_snippet(project)
        print('  AGENTS 片段：%s' % ('已写入/更新 ✓' if changed else '已是最新 ✓'))
    if with_hook:
        ok, msg = install_hook(project)
        print('  git 钩子：%s' % msg)
    (project / STAMP_NAME).write_text(json.dumps(stamp, ensure_ascii=False, indent=1),
                                      encoding='utf-8')
    print('已装进项目：%s（toolkit %s）' % (project, stamp['toolkit_version']))
    for w in written:
        print('  写入 %s' % w)
    for k in kept:
        print('  保留已有配置 %s（未覆盖 ✓）' % k)
    print('  身份证 %s' % STAMP_NAME)
    return 0


def write_agents_snippet(project: Path) -> bool:
    """把 AGENTS 片段**幂等**写进项目的 AGENTS.md（标记包裹，旧段落被替换）。"""
    snippet = (TOOLKIT / AGENTS_SNIPPET).read_text(encoding='utf-8').rstrip() + '\n'
    f = project / 'AGENTS.md'
    old = f.read_text(encoding='utf-8') if f.exists() else ''
    if BEGIN in old:
        new = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\n?', snippet, old,
                     flags=re.S)
    elif LEGACY_BEGIN in old:                  # 改名前的旧块 ⇒ 替换（**不重复追加** ✓）
        new = re.sub(re.escape(LEGACY_BEGIN) + r'.*?' + re.escape(LEGACY_END) + r'\n?',
                     snippet, old, flags=re.S)
    elif old.strip():
        new = old.rstrip() + '\n\n' + snippet
    else:
        new = ('# AGENTS.md —— 给 AI 会话的工程纪律（动手前先读这一页）\n\n'
               '本文件是仓库级约定。**任何会话（人或 AI）改这个项目之前，先看这里。**\n\n'
               + snippet)
    if new == old:
        return False
    f.write_text(new, encoding='utf-8')
    return True


def install_hook(project: Path):
    gd = project / '.git'
    if not gd.is_dir():
        return False, '不是 git 仓库，跳过（可稍后手动拷 templates/pre-commit）'
    dst = gd / 'hooks' / 'pre-commit'
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TOOLKIT / HOOK, dst)
    try:
        dst.chmod(0o755)
    except Exception:  # noqa: BLE001
        pass
    return True, '已装到 .git/hooks/pre-commit ✓'


# ------------------------------------------------------------------ 装 skill
def install_skills(skills_dir: Path) -> int:
    n = 0
    for src, name in SKILLS:
        d = skills_dir / name
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TOOLKIT / src, d / 'SKILL.md')
        print('  已装 skill：%s' % (d / 'SKILL.md'))
        n += 1
    print('共装 %d 个 skill 到 %s（其他 agent 用 --skills-dir 指定自己的目录）'
          % (n, skills_dir))
    return 0


# ------------------------------------------------------------------ 漂移检查
def check(project: Path) -> int:
    sp = project / STAMP_NAME
    if not sp.exists():
        print('[未安装] 找不到 %s（先跑：--project %s）' % (STAMP_NAME, project))
        return 3
    stamp = json.loads(sp.read_text(encoding='utf-8'))
    modified, outdated, ok = [], [], 0
    src_by_dst = {dst: TOOLKIT / src for src, dst in MANAGED}
    for dst, want in (stamp.get('files') or {}).items():
        cur = project / dst
        if not cur.exists():
            modified.append(dst + '（缺失）')
            continue
        h = sha12(cur)
        if want and h != want:
            modified.append(dst)
            continue
        if dst in src_by_dst:
            if sha12(src_by_dst[dst]) != h:
                outdated.append(dst)
            else:
                ok += 1
    print('项目：%s' % project)
    print('  身份证版本：%s ｜ toolkit 当前：%s' % (stamp.get('toolkit_version'), version()))
    print('  一致 %d ｜ 被本地改过 %d ｜ 落后于 toolkit %d' % (ok, len(modified), len(outdated)))
    for m in modified:
        print('    ✗ 被本地改过/缺失：%s  ⇒ 要么改回去，要么把改动提回 agent-toolkit' % m)
    for o in outdated:
        print('    ⚠ 落后于 toolkit：%s  ⇒ 重跑安装即可' % o)
    if modified:
        return 1
    if outdated or stamp.get('toolkit_version') != version():
        return 2
    print('  [OK] 与 toolkit 一致')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='agent-toolkit 安装器')
    ap.add_argument('--project', help='项目根目录（装工具/配置/AGENTS/钩子）')
    ap.add_argument('--skills', action='store_true', help='把 skill 装到 agent 的 skills 目录')
    ap.add_argument('--skills-dir', help='skills 目录（默认 %s）' % DEFAULT_SKILLS_DIR)
    ap.add_argument('--all', action='store_true', help='项目 + skill 都装')
    ap.add_argument('--with-agents', action='store_true', help='同时写 AGENTS.md 规则片段')
    ap.add_argument('--with-hook', action='store_true', help='同时装 git pre-commit 钩子')
    ap.add_argument('--check', action='store_true', help='只检查项目副本漂移')
    ap.add_argument('--list', action='store_true', help='列出会安装什么')
    a = ap.parse_args()

    if a.list:
        return do_list()
    rc = 0
    if a.project:
        project = Path(a.project).resolve()
        if not project.is_dir():
            print('[错误] 项目目录不存在：%s' % project)
            return 3
        if a.check:
            return check(project)
        rc = install_project(project, a.with_agents or a.all, a.with_hook or a.all)
    if a.skills or a.all:
        rc = max(rc, install_skills(Path(a.skills_dir).resolve() if a.skills_dir
                                    else DEFAULT_SKILLS_DIR))
    if not (a.project or a.skills or a.all):
        ap.print_help()
        return 3
    return rc


if __name__ == '__main__':
    sys.exit(main())
