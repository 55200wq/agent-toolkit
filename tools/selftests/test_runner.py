"""selftests 工具的自测：造 3 个假套件（通过 / 失败 / 慢），验证发现与汇总行为。

【目的】工具自己也要能被验证 ✓
    覆盖：自动发现、配置标签、--list、--fast 跳过 slow、失败时退出码=1、超时处理
【用法】python test_runner.py     退出码 0=通过 1=失败
【依赖】只用标准库
"""
from __future__ import annotations

import importlib.util
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

        # ---- 布局推导（回归项 ✗）：源码布局与"装进项目"布局都必须认对**根** ✓
        # 原缺陷：源码布局下 root 认成 `tools/` ⇒ 本仓库 5 个套件只跑到 3 个 ✗
        spec = importlib.util.spec_from_file_location('ras_mod', RUNNER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        check('guess_root：源码布局 ⇒ 工具集根',
              mod.guess_root() == RUNNER.resolve().parent.parent.parent, str(mod.guess_root()))

        inst = Path(tempfile.mkdtemp(prefix='instlayout_'))
        try:
            (inst / 'tools').mkdir()
            shutil.copy(RUNNER, inst / 'tools' / 'run_all_selftests.py')
            (inst / 'tools' / 'selftests.json').write_text(json.dumps(
                {'discover': ['**/*_selftest_*.py'], 'exclude': [], 'skip': [], 'timeout_s': 30,
                 'suites': {}}, ensure_ascii=False), encoding='utf-8')
            (inst / 'x_selftest_ok.py').write_text("print('hi')\n", encoding='utf-8')
            e = dict(os.environ)
            e.update({'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
            r5 = subprocess.run(                       # 故意**不给 --root**，且在别的 cwd 里跑 ✓
                [sys.executable, '-X', 'utf8', str(inst / 'tools' / 'run_all_selftests.py'), '--list'],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                env=e, cwd=str(HERE))
            o5 = r5.stdout or ''
            check('装进项目布局 ⇒ 根=项目根（不是 tools/ ✗）',
                  ('根  ：%s' % inst.resolve()) in o5, o5.splitlines()[1] if o5 else '')
            check('装进项目布局 ⇒ 能扫到项目根的套件', '发现 1 个套件' in o5,
                  [l for l in o5.splitlines() if l.startswith('发现')][:1])

            # 没有配置时必须**出声**（原缺陷：静默退回内置默认 ⇒ "跑了另一批"看不出来 ✗）
            bare = Path(tempfile.mkdtemp(prefix='barecfg_'))
            try:
                shutil.copy(RUNNER, bare / 'run_all_selftests.py')
                r6 = subprocess.run(
                    [sys.executable, '-X', 'utf8', str(bare / 'run_all_selftests.py'), '--list'],
                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                    env=e, cwd=str(HERE))
                check('没有配置 ⇒ 明确告警（不静默退回 ✗）',
                      '【内置默认】' in (r6.stdout or '') + (r6.stderr or ''),
                      ((r6.stderr or '') + (r6.stdout or ''))[:60])
                check('告警里列出"已找过哪些路径"',
                      '已找过' in (r6.stderr or '') + (r6.stdout or ''))
            finally:
                shutil.rmtree(bare, ignore_errors=True)
        finally:
            shutil.rmtree(inst, ignore_errors=True)
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
