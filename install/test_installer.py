r"""install.py 的自测：假项目上全程试跑（安装 / 漂移 / 不覆盖 / AGENTS 幂等与转义 ✓）。

【为什么要这份自测】安装器原先**没有自测** ✗ ⇒ 一个真 bug 没被兜住 ✗：
    AGENTS 片段里有 `'C:\temp\x'` 这类路径 ✗，直接当 `re.sub` 的替换串会被当转义 ✗
    ⇒ 安装器崩在 `bad escape \x` ✗（本文件覆盖这个场景 ✓）
【用法】python test_installer.py     退出码 0=通过 1=失败
【依赖】只用标准库
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:                                   # 输出被重定向/走管道时默认编码可能是 GBK ✗
    import sys as _sys_h               # 打印非 ASCII 会 UnicodeEncodeError ✗ ⇒ 统一兜底 ✓
    for _s_h in (_sys_h.stdout, _sys_h.stderr):   # stdout 与 stderr 都要兜 ✗
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:                      # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
INSTALL = HERE / 'install.py'
FAILS = []


def check(name, cond, detail=''):
    print('  %-6s %-46s %s' % ('OK' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


def run(args):
    e = dict(os.environ)
    e.update({'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    return subprocess.run([sys.executable, '-X', 'utf8', str(INSTALL), *args],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=e)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='installtest_'))
    proj = tmp / 'proj'
    skills = tmp / 'skills'
    try:
        proj.mkdir()
        (proj / '.git').mkdir()                     # 假装是 git 仓库 ⇒ 钩子应装上 ✓

        r = run(['--project', str(proj), '--with-agents', '--with-hook'])
        check('安装退出码=0', r.returncode == 0, 'rc=%d' % r.returncode)
        check('工具已落盘', (proj / 'tools/provenance_check.py').exists()
              and (proj / 'tools/hygiene_check.py').exists()
              and (proj / 'tools/run_all_selftests.py').exists())
        check('配置模板已生成', (proj / 'tools/provenance.json').exists()
              and (proj / 'tools/hygiene.json').exists())
        check('身份证已写', (proj / '.agent-tools.json').exists())
        check('git 钩子已装', (proj / '.git/hooks/pre-commit').exists())
        agents = (proj / 'AGENTS.md').read_text(encoding='utf-8')
        check('AGENTS 片段含路径示例（反斜杠转义场景）', "'C:\\temp\\x'" in agents)
        check('AGENTS 片段含脚本纪律一节', '脚本工程纪律' in agents)

        # 幂等：再装一次不应重复
        run(['--project', str(proj), '--with-agents'])
        agents2 = (proj / 'AGENTS.md').read_text(encoding='utf-8')
        check('AGENTS 幂等（标记仍只有 1 个）', agents2.count('agent-toolkit:begin') == 1)

        # 不覆盖已有配置
        cfg = proj / 'tools/provenance.json'
        cfg.write_text('{"scan": ["my/own.py"]}', encoding='utf-8')
        run(['--project', str(proj)])
        check('不覆盖已有配置 ✓', 'my/own.py' in cfg.read_text(encoding='utf-8'))

        # 漂移：一致
        r2 = run(['--project', str(proj), '--check'])
        check('一致时退出码=0', r2.returncode == 0, 'rc=%d' % r2.returncode)

        # 漂移：被本地改过 ⇒ 1
        f = proj / 'tools/hygiene_check.py'
        f.write_text(f.read_text(encoding='utf-8') + '\n# tampered\n', encoding='utf-8')
        r3 = run(['--project', str(proj), '--check'])
        check('被本地改过 ⇒ 退出码=1', r3.returncode == 1, 'rc=%d' % r3.returncode)
        run(['--project', str(proj)])               # 重装恢复
        check('重装后恢复一致', run(['--project', str(proj), '--check']).returncode == 0)

        # 未安装 ⇒ 3
        empty = tmp / 'empty'
        empty.mkdir()
        check('未安装 ⇒ 退出码=3', run(['--project', str(empty), '--check']).returncode == 3)

        # 装 skill
        r4 = run(['--skills', '--skills-dir', str(skills)])
        check('装 skill 退出码=0', r4.returncode == 0, 'rc=%d' % r4.returncode)
        check('两个 skill 都装了',
              (skills / 'measured-or-flagged-zh/SKILL.md').exists()
              and (skills / 'script-hygiene-zh/SKILL.md').exists())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print('[FAIL] 安装器自测未通过：%s' % ', '.join(FAILS))
        return 1
    print('[OK] 安装器自测通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
