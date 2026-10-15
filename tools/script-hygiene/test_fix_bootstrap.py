r"""fix_bootstrap 的自测：造假项目，验证"替换旧兜底 / 插入新兜底 / 跳过已覆盖 / 不猜怪形态"。

【为什么必须有】这是**批量改源码**的工具 ✗ —— 它一旦改错，坏的是**一整类文件** ✗
    （本项目真出现过"用正则/行号改源码 ⇒ 改坏 3 个文件"✗）
    ⇒ 必须用"已知答案"的假项目验证：改了哪些 ✓ 没改哪些 ✓ 改完全部能编译 ✓

【用法】python test_fix_bootstrap.py      退出码 0=通过 1=失败
"""
from __future__ import annotations

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
FIXER = HERE / 'fix_bootstrap.py'
HYGIENE = HERE / 'hygiene_check.py'
FAILS = []

OLD = '''try:                                   # 旧片段：只兜 stdout ✗
    import sys as _sys_h
    _sys_h.stdout.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h
except Exception:                      # noqa: BLE001
    pass
'''

OK = '''try:                                   # 新片段：两个流都兜 ✓
    import sys as _sys_h
    for _s_h in (_sys_h.stdout, _sys_h.stderr):
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:                      # noqa: BLE001
    pass
'''


def check(name, cond, detail=''):
    print('  %-6s %-48s %s' % ('OK' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


def run(*args, cwd=None):
    e = dict(os.environ)
    e.update({'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
    return subprocess.run([sys.executable, '-X', 'utf8', *[str(x) for x in args]],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=e, cwd=str(cwd) if cwd else None)


def build(root: Path):
    (root / 'a_old.py').write_text('"""a：有旧兜底（只兜 stdout）⇒ 应被替换 ✓"""\n' + OLD
                                   + "\nprint('旧中文 ✗')\n", encoding='utf-8')
    (root / 'b_none.py').write_text('"""b：没兜底但打印中文 ⇒ 应被插入 ✓"""\n'
                                    'from __future__ import annotations\n'
                                    "\nprint('新中文 ✓')\n", encoding='utf-8')
    (root / 'c_ok.py').write_text('"""c：已经两个流都兜 ⇒ 不动 ✓"""\n' + OK
                                  + "\nprint('好中文 ✓')\n", encoding='utf-8')
    (root / 'd_noprint.py').write_text('"""d：不打印 ⇒ 不需要兜底 ✓"""\nX = 1\n', encoding='utf-8')
    (root / 'e_weird.py').write_text(
        '"""e：兜底写在函数里（形态不常见）⇒ 必须报"需人工"✗ 不许自动改 ✗"""\n'
        "def boot():\n"
        "    import sys\n"
        "    sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
        "\nprint('怪中文 ✗')\n", encoding='utf-8')


def snapshot(root: Path):
    return {p.name: p.read_bytes() for p in sorted(root.glob('*.py'))}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='fixboot_'))
    try:
        build(tmp)
        before = snapshot(tmp)

        # ---- 干跑：只报告，不写 ✓
        r = run(FIXER, '--root', tmp)
        o = r.stdout or ''
        check('干跑退出码 0', r.returncode == 0, 'rc=%d' % r.returncode)
        check('干跑报告 2 个待升级', '需要升级兜底的脚本：2 个' in o,
              [l for l in o.splitlines() if l.startswith('需要升级')][:1])
        check('干跑未写任何文件', snapshot(tmp) == before)
        check('干跑把"怪形态"报成需人工', '需人工' in o and 'e_weird.py' in o)

        # ---- 真写 ✓
        r2 = run(FIXER, '--root', tmp, '--apply')
        after = snapshot(tmp)
        check('--apply 退出码 0', r2.returncode == 0, 'rc=%d' % r2.returncode)
        check('已写入 2 个文件', '已写入 2 个文件' in (r2.stdout or ''),
              [l for l in (r2.stdout or '').splitlines() if l.startswith('已写入')][:1])
        check('a_old.py 被改（旧 → 两流）',
              b'_sys_h.stderr' in after['a_old.py'] and b'for _s_h in' in after['a_old.py'])
        check('b_none.py 被插入兜底', b'_sys_h.stderr' in after['b_none.py'])
        check('c_ok.py 未被改', after['c_ok.py'] == before['c_ok.py'])
        check('d_noprint.py 未被改', after['d_noprint.py'] == before['d_noprint.py'])
        check('e_weird.py 未被改（不许猜 ✗）', after['e_weird.py'] == before['e_weird.py'])

        # ---- 改完必须能跑 ✓（不能只看 ast）
        r3 = run(tmp / 'a_old.py')
        check('改后的 a_old.py 能正常运行', r3.returncode == 0 and '旧中文' in (r3.stdout or ''),
              'rc=%d out=%r' % (r3.returncode, (r3.stdout or '')[:20]))
        r4 = run(tmp / 'b_none.py')
        check('改后的 b_none.py 能正常运行', r4.returncode == 0 and '新中文' in (r4.stdout or ''))

        # ---- 端到端：修完只剩"需人工"那一个还报 ✓
        r5 = run(HYGIENE, '--root', tmp, '--all-rules')
        o5 = (r5.stdout or '')
        check('修完 hygiene 只剩 1 处 H3', 'H3 × 1' in o5,
              [l for l in o5.splitlines() if 'H3 ×' in l][:1])
        check('剩的那处正是 e_weird.py', 'e_weird.py' in o5)
        check('剩下的是"只兜了 stdout"这一型', '只兜了 stdout' in o5)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print('[FAIL] 自测未通过：%s' % ', '.join(FAILS))
        return 1
    print('[OK] fix-bootstrap 自测通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
