"""script-hygiene 的自测：造假文件，验证 H1/H2/H3 都能按预期报红与放行。

【目的】工具自己也要能被验证 ✓（而且要证明它**真的抓得住**那三类事故 ✓）
【用法】python test_hygiene.py     退出码 0=通过 1=失败
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
ENGINE = HERE / 'hygiene_check.py'
FAILS = []


def check(name, cond, detail=''):
    print('  %-6s %-44s %s' % ('OK' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


def run(root, args=()):
    e = dict(os.environ)
    e.update({'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    return subprocess.run([sys.executable, '-X', 'utf8', str(ENGINE), '--root', str(root), *args],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', env=e)


# 各造一个"应该报红/应该放行"的文件
GOOD_ASCII = "print('plain ascii only')\n"
# ✓ 两个流都兜（这是 H3 的新口径 ✗ 只兜 stdout 不算 ✓）
GOOD_BOOT = (
    "import sys\n"
    "try:\n"
    "    for _s in (sys.stdout, sys.stderr):\n"
    "        _s.reconfigure(encoding='utf-8', errors='replace')\n"
    "except Exception:\n"
    "    pass\n"
    "print('中文输出 ✓ 两个流都兜底')\n")
# ✓ 本项目模板的写法：**别名 + 循环** ⇒ 字符串标记认不出，必须靠 AST 认 ✓
GOOD_ALIAS_LOOP = (
    "try:\n"
    "    import sys as _sys_h\n"
    "    for _s_h in (_sys_h.stdout, _sys_h.stderr):\n"
    "        _s_h.reconfigure(encoding='utf-8', errors='replace')\n"
    "    del _sys_h, _s_h\n"
    "except Exception:\n"
    "    pass\n"
    "print('中文 ✓ 别名+循环也算兜住了')\n")
# ✓ 另一种形态：TextIOWrapper ✓
GOOD_TEXTIO = (
    "import io, sys\n"
    "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')\n"
    "sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')\n"
    "print('中文 ✓ TextIOWrapper')\n")
GOOD_RAW_PATH = "P = r'C:\\Users\\x'\nprint(len(P))\n"
BAD_COMPILE = "def broken(:\n    pass\n"
BAD_BACKSLASH = "P = 'C:\\temp\\new'\nprint(P)\n"          # \t \n 会被当转义 ✗
BAD_PRINT = "print('完成 ✓')\n"                                # 无兜底 ✗
# ✗ 只兜 stdout = 假兜底（2026-10-16 实测缺口 ⇒ 这条就是它的回归项 ✓）
BAD_ONLY_STDOUT = (
    "import sys\n"
    "try:\n"
    "    sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
    "except Exception:\n"
    "    pass\n"
    "print('完成 ✓ 只兜了 stdout')\n")
# ✗ 文件里出现 PYTHONIOENCODING **不算数**（那是给子进程设的，管不到自己 ✗）
BAD_PIO_INFILE = (
    "import os\n"
    "os.environ['PYTHONIOENCODING'] = 'utf-8'\n"
    "print('完成 ✓ 只设了环境变量')\n")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='hygienetest_'))
    try:
        src = tmp / 'src'
        src.mkdir()
        (src / 'good_ascii.py').write_text(GOOD_ASCII, encoding='utf-8')
        (src / 'good_boot.py').write_text(GOOD_BOOT, encoding='utf-8')
        (src / 'good_alias_loop.py').write_text(GOOD_ALIAS_LOOP, encoding='utf-8')
        (src / 'good_textio.py').write_text(GOOD_TEXTIO, encoding='utf-8')
        (src / 'good_raw.py').write_text(GOOD_RAW_PATH, encoding='utf-8')
        (src / 'bad_compile.py').write_text(BAD_COMPILE, encoding='utf-8')
        (src / 'bad_backslash.py').write_text(BAD_BACKSLASH, encoding='utf-8')
        (src / 'bad_print.py').write_text(BAD_PRINT, encoding='utf-8')
        (src / 'bad_only_stdout.py').write_text(BAD_ONLY_STDOUT, encoding='utf-8')
        (src / 'bad_pio.py').write_text(BAD_PIO_INFILE, encoding='utf-8')
        (tmp / 'hygiene.json').write_text(json.dumps({
            'scan': ['src/*.py'], 'exclude': [],
            'rules': {'H1': True, 'H2': True, 'H3': True},
        }), encoding='utf-8')

        r = run(tmp)
        o = r.stdout or ''
        check('有问题时退出码=1', r.returncode == 1, 'rc=%d' % r.returncode)
        check('H1 抓到改坏的源码', 'bad_compile.py' in o and 'H1' in o)
        check('H2 抓到反斜杠路径', 'bad_backslash.py' in o and 'H2' in o)
        check('H3 抓到缺兜底的非 ASCII 打印', 'bad_print.py' in o and 'H3' in o)
        check('H3 抓到"只兜 stdout"（假兜底 ✗）',
              'bad_only_stdout.py' in o and '只兜了 stdout' in o)
        check('H3 抓到"文件里写 PYTHONIOENCODING 不算数"', 'bad_pio.py' in o)
        check('放行：纯 ASCII', 'good_ascii.py' not in o)
        check('放行：两个流都兜的中文输出', 'good_boot.py' not in o)
        check('放行：别名+循环兜底（AST 认得出 ✓）', 'good_alias_loop.py' not in o)
        check('放行：TextIOWrapper 两个流', 'good_textio.py' not in o)
        check('放行：raw 路径', 'good_raw.py' not in o)

        # 全部修好后应通过
        (src / 'bad_compile.py').write_text("def ok():\n    return 1\n", encoding='utf-8')
        (src / 'bad_backslash.py').write_text("P = 'C:/temp/new'\nprint(P)\n", encoding='utf-8')
        (src / 'bad_print.py').write_text(GOOD_BOOT, encoding='utf-8')
        (src / 'bad_only_stdout.py').write_text(GOOD_BOOT, encoding='utf-8')
        (src / 'bad_pio.py').write_text(GOOD_BOOT, encoding='utf-8')
        r2 = run(tmp)
        check('全部修好后退出码=0', r2.returncode == 0, 'rc=%d' % r2.returncode)

        # H3 可被 h3_ignore_files 豁免
        (src / 'bad_print.py').write_text(BAD_PRINT, encoding='utf-8')
        (tmp / 'hygiene.json').write_text(json.dumps({
            'scan': ['src/*.py'], 'exclude': [],
            'rules': {'H1': True, 'H2': True, 'H3': True},
            'h3_ignore_files': ['src/bad_print.py'],
        }), encoding='utf-8')
        r3 = run(tmp)
        check('H3 可豁免指定文件', r3.returncode == 0, 'rc=%d' % r3.returncode)

        # 单条规则可关闭
        (tmp / 'hygiene.json').write_text(json.dumps({
            'scan': ['src/*.py'], 'exclude': [], 'rules': {'H1': True, 'H2': True, 'H3': False},
        }), encoding='utf-8')
        r4 = run(tmp)
        check('可单独关闭 H3', r4.returncode == 0, 'rc=%d' % r4.returncode)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print('[FAIL] 自测未通过：%s' % ', '.join(FAILS))
        return 1
    print('[OK] script-hygiene 自测通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
