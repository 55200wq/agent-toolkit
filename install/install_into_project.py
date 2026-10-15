"""把 agent-tools 里的工具装进一个项目 / 检查项目里的副本是否漂移。

【设计（用户 2026-10-15 决策：D2=A 副本+版本戳）】
    项目里**留一份引擎副本** ✓ 这样项目能被单独拷走、换机器也能跑 ✓
    但副本会漂移 ✗ ⇒ 在项目根写一张"身份证" `.agent-tools.json`（版本 + 每个文件的哈希）✓
    ⇒ 本脚本既能装、也能查：
         一致             → 退出码 0
         被本地改过        → 退出码 1（要么改回去，要么把改动提回 agent-tools）
         落后于 toolkit    → 退出码 2（重跑安装即可）
         未安装            → 退出码 3

【用法】
    python install_into_project.py --project <项目根>            # 安装/更新
    python install_into_project.py --project <项目根> --check    # 只检查漂移
    python install_into_project.py --project <项目根> --only provenance
    python install_into_project.py --project <项目根> --list     # 看会装哪些文件

【绝不覆盖已有配置】✗→✓ —— 配置是项目自己的口径（扫描面/标签/档案路径）
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
STAMP_NAME = '.agent-tools.json'

# 工具 → (源文件, 项目内相对路径, 是否"缺了才写")
MANIFEST = {
    'provenance': [
        ('tools/provenance/provenance_check.py', 'tools/provenance_check.py', False),
        ('tools/provenance/_selftest_provenance.py', 'tools/_selftest_provenance.py', False),
        ('tools/provenance/provenance.example.json', 'tools/provenance.json', True),
    ],
    'selftests': [
        ('tools/selftests/run_all_selftests.py', 'tools/run_all_selftests.py', False),
        ('tools/selftests/selftests.example.json', 'tools/selftests.json', True),
    ],
}


def sha12(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else ''


def version() -> str:
    return VERSION_FILE.read_text(encoding='utf-8').strip() if VERSION_FILE.exists() else '0.0.0'


def entries(only=None):
    for group, items in MANIFEST.items():
        if only and only != group:
            continue
        for src, dst, only_if_missing in items:
            yield group, TOOLKIT / src, dst, only_if_missing


def do_list():
    print('agent-tools %s → 会安装（源 → 项目内）：' % version())
    for group, src, dst, oim in entries():
        print('  [%s] %-46s → %-28s%s' % (group, src.relative_to(TOOLKIT), dst,
                                         '（缺了才写 ✓）' if oim else ''))
    return 0


def do_install(project: Path, only=None):
    (project / 'tools').mkdir(parents=True, exist_ok=True)
    stamp = {'toolkit_version': version(), 'installed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
             'files': {},          # 受管文件（引擎）：参与漂移比较 ✓
             'configs': []}        # 项目自有配置：只登记，**不比较**（各项目本就应该不同 ✓）
    written, kept = [], []
    for group, src, dst, only_if_missing in entries(only):
        target = project / dst
        key = dst.replace('\\', '/')
        if only_if_missing:
            # 配置是**项目自有**：缺了才写、绝不覆盖；只登记，**不参与漂移比较**
            # （各项目的配置本就该不同 ✗ 拿它跟模板比必然报"被改过" ✗）
            if target.exists():
                kept.append(key)
            else:
                shutil.copy2(src, target)
                written.append(key)
            stamp['configs'].append(key)
            continue
        shutil.copy2(src, target)
        written.append(key)
        stamp['files'][key] = sha12(src)
    (project / STAMP_NAME).write_text(json.dumps(stamp, ensure_ascii=False, indent=1),
                                      encoding='utf-8')
    print('已安装到 %s（toolkit %s）' % (project, stamp['toolkit_version']))
    for w in written:
        print('  写入 %s' % w)
    for k in kept:
        print('  保留已有配置 %s（未覆盖 ✓）' % k)
    print('  身份证 %s' % STAMP_NAME)
    print('\n下一步：')
    print('  1) python tools/provenance_check.py --write-assumptions   # 生成未实测清单')
    print('  2) 把 tools/provenance.json 的 scan 改成本项目要扫的文件')
    print('  3) python tools/run_all_selftests.py --list              # 看有哪些自检')
    return 0


def do_check(project: Path):
    sp = project / STAMP_NAME
    if not sp.exists():
        print('[未安装] 找不到 %s（先跑 --project %s 安装）' % (STAMP_NAME, project))
        return 3
    stamp = json.loads(sp.read_text(encoding='utf-8'))
    tv = version()
    modified, outdated, ok = [], [], 0
    for dst, want in (stamp.get('files') or {}).items():
        cur = project / dst
        if not cur.exists():
            modified.append(dst + '（缺失）')
            continue
        h = sha12(cur)
        if want and h != want:
            modified.append(dst)
            continue
        # 与 toolkit 现状比
        for group, src, d2, oim in entries():
            if d2 == dst:
                if sha12(src) != h:
                    outdated.append(dst)
                else:
                    ok += 1
                break
    print('项目：%s' % project)
    print('  身份证版本：%s ｜ toolkit 当前：%s' % (stamp.get('toolkit_version'), tv))
    print('  一致 %d ｜ 被本地改过 %d ｜ 落后于 toolkit %d' % (ok, len(modified), len(outdated)))
    for m in modified:
        print('    ✗ 被本地改过/缺失：%s  ⇒ 要么改回去，要么把改动提交回 agent-tools' % m)
    for o in outdated:
        print('    ⚠ 落后于 toolkit：%s  ⇒ 重跑安装即可' % o)
    if modified:
        return 1
    if outdated or stamp.get('toolkit_version') != tv:
        return 2
    print('  [OK] 与 toolkit 一致')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='把 agent-tools 装进项目 / 检查漂移')
    ap.add_argument('--project', help='项目根目录')
    ap.add_argument('--check', action='store_true', help='只检查漂移，不写文件')
    ap.add_argument('--list', action='store_true', help='列出会安装哪些文件')
    ap.add_argument('--only', choices=sorted(MANIFEST), help='只装某一组工具')
    a = ap.parse_args()

    if a.list:
        return do_list()
    if not a.project:
        ap.error('需要 --project <项目根>（或用 --list 看清单）')
    project = Path(a.project).resolve()
    if not project.is_dir():
        print('[错误] 项目目录不存在：%s' % project)
        return 3
    return do_check(project) if a.check else do_install(project, a.only)


if __name__ == '__main__':
    sys.exit(main())
