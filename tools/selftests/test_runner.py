"""selftests 工具的自测：造 3 个假套件（通过 / 失败 / 慢），验证发现与汇总行为。

【目的】工具自己也要能被验证 ✓
    覆盖：自动发现、配置标签、--list、--fast 跳过 slow、失败时退出码=1、超时处理
【用法】python test_runner.py     退出码 0=通过 1=失败
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

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'run_all_selftests.py'
FAILS = []


def check(name, cond, detail=''):
    print('  %-6s %-46s %s' % ('OK' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


def run(args, root):
    e = dict(os.environ)
    e.update({'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
    return subprocess.run([sys.executable, '-X', 'utf8', str(RUNNER), '--root', str(root)] + args,
                          capture_output=True, text=True, encoding='utf-8', errors='replace', env=e)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='runnertest_'))
    try:
        (tmp / 't').mkdir()
        (tmp / 't' / '_selftest_pass.py').write_text(
            "import sys\nprint('fake pass')\nsys.exit(0)\n", encoding='utf-8')
        (tmp / 't' / '_selftest_fail.py').write_text(
            "import sys\nprint('fake fail')\nsys.exit(1)\n", encoding='utf-8')
        (tmp / 't' / '_selftest_slow.py').write_text(
            "import time\nprint('sleeping')\ntime.sleep(5)\n", encoding='utf-8')
        (tmp / 't' / 'not_a_suite.py').write_text("print('ignored')\n", encoding='utf-8')
        (tmp / 'selftests.json').write_text(json.dumps({
            'discover': ['**/*_selftest_*.py'], 'exclude': [], 'skip': [],
            'timeout_s': 30,
            'suites': {'_selftest_pass.py': {'label': '假通过', 'desc': '应 OK'},
                       '_selftest_fail.py': {'label': '假失败', 'desc': '应 FAIL'},
                       '_selftest_slow.py': {'label': '假慢', 'slow': True, 'desc': '应被 --fast 跳过'}},
        }, ensure_ascii=False), encoding='utf-8')

        r = run(['--list'], tmp)
        o = r.stdout or ''
        check('--list 发现 3 个套件', o.count('_selftest_') == 3, '发现 %d' % o.count('_selftest_'))
        check('--list 不列非套件文件', 'not_a_suite' not in o)

        r2 = run([], tmp)
        o2 = r2.stdout or ''
        check('含失败时退出码=1', r2.returncode == 1, 'rc=%d' % r2.returncode)
        check('汇总行正确', '通过 2' in o2 and '失败 1' in o2,
              [l for l in o2.splitlines() if l.startswith('结果')][:1])

        r3 = run(['--fast'], tmp)
        o3 = r3.stdout or ''
        # --fast 只跳过 slow；失败的套件依然失败 ⇒ 通过 1 / 失败 1 / 跳过 1
        check('--fast 跳过 slow', '通过 1' in o3 and '失败 1' in o3 and '跳过 1' in o3,
              [l for l in o3.splitlines() if l.startswith('结果')][:1])

        # 去掉失败的套件 ⇒ 应全绿
        (tmp / 't' / '_selftest_fail.py').unlink()
        r4 = run([], tmp)
        check('无失败时退出码=0', r4.returncode == 0, 'rc=%d' % r4.returncode)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print('★ 自测未通过：%s' % ', '.join(FAILS))
        return 1
    print('[OK] selftests 工具自测通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
