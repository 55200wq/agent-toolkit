"""一条命令跑完全部自检（**通用版：自动发现套件**）。

【目的】
    让"这个项目有 N 套自检"对新会话/新同事可见 ✓
    —— 原版把套件名写死在代码里 ✗ 换项目就不能用，新套件也容易漏 ✓
    现在：按 glob 自动发现 ✓ 可选的 selftests.json 只用来加"标签 / 慢标志 / 跳过" ✓

【发现规则】
    · 默认发现 `**/*_selftest_*.py`（排除 .git/.venv/__pycache__ 等）
    · 可选配置 `selftests.json`（项目根或与引擎同级）：
      discover / exclude / skip / timeout_s / suites{文件名: {label, slow, desc}}
    · 没有配置也能跑：标签直接用文件名 ✓

【用法】
    python run_all_selftests.py            # 跑全部
    python run_all_selftests.py --fast     # 跳过 slow=true 的套件
    python run_all_selftests.py --list     # 只列清单
    python run_all_selftests.py --root DIR # 指定项目根（默认本文件上两级）
    python run_all_selftests.py --config X.json
退出码：0 = 全绿；1 = 有失败
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from pathlib import PurePosixPath as PP

try:                                   # 输出被重定向/走管道时默认编码可能是 GBK ✗
    import sys as _sys_h               # 打印非 ASCII 会 UnicodeEncodeError ✗ ⇒ 统一兜底 ✓
    for _s_h in (_sys_h.stdout, _sys_h.stderr):   # stdout 与 stderr 都要兜 ✗
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:                      # noqa: BLE001
    pass

def guess_root() -> Path:
    """根目录推导 —— **两种布局都要对** ✓

    · 工具集源码布局：`tools/selftests/run_all_selftests.py` ⇒ 根 = 上 3 层
      （原来写的是"上 2 层"✗ ⇒ 根系成了 `tools/` ⇒ 本仓库 5 个套件只跑到 3 个 ✗）
    · 装进项目：      `tools/run_all_selftests.py`          ⇒ 根 = 上 2 层 ✓

    判据：引擎所在目录**叫不叫 `selftests`** ✓（只有源码布局有这一层 ✓）
    ⚠️ 别改成"往上找 selftests.json"✗：装进项目时配置文件就在 `tools/` 里
       ⇒ 那样找会把根认成 `tools/` ✗（差点又踩一次 ✓）
    """
    d = Path(__file__).resolve().parent
    if d.name == 'selftests':          # 源码布局：tools/selftests/ ⇒ 上 3 层 ✓
        return d.parent.parent
    return d.parent                    # 装进项目：tools/ ⇒ 上 2 层 ✓


DEFAULT_ROOT = guess_root()
DEFAULTS = {
    'discover': ['**/*_selftest_*.py'],
    'exclude': ['.git/**', '.venv/**', 'venv/**', 'node_modules/**', '**/__pycache__/**',
                '**/_v4_*.py'],
    'skip': [],
    'timeout_s': 600,
    'suites': {},
}


def load_cfg(root, explicit=None):
    """顺序：`--config` > `<root>/selftests.json` > 引擎同级 `selftests.json`

    ⚠️ **不再把 cwd 当配置来源** ✗ —— 原来 cwd 在候选里 ✗ ⇒ 换个 cwd 就会偷偷用上
       "当前目录的配置"，发现面完全不同 ✗（实测：从别的项目里跑 ⇒ 只剩 2 套 ✗，
        而输出上只有一行"配置：内置默认"容易被忽略 ✗）
    """
    cfg = dict(DEFAULTS)
    cands = ([Path(explicit)] if explicit else []) + [
        root / 'selftests.json',
        Path(__file__).resolve().parent / 'selftests.json']
    tried = [str(c) for c in cands]
    for c in cands:
        if c.exists():
            raw = json.loads(c.read_text(encoding='utf-8'))
            for k, v in raw.items():
                if k == 'suites' and isinstance(v, dict):
                    cfg['suites'] = {**cfg['suites'], **v}
                else:
                    cfg[k] = v
            cfg['_config'] = str(c)
            cfg['_tried'] = tried
            return cfg
    cfg['_config'] = None
    cfg['_tried'] = tried
    return cfg


def warn_if_default_cfg(cfg):
    """退回内置默认时**必须出声** ✗（否则"跑了另一批套件"看不出来 ✗）"""
    if cfg['_config'] is None:
        print('⚠ 没找到 selftests.json ⇒ 正在用【内置默认】发现面 %s ✗' % cfg['discover'],
              file=sys.stderr)
        print('  已找过：%s' % ' ｜ '.join(cfg.get('_tried') or []), file=sys.stderr)


def discover(root, cfg):
    out = []
    for pat in cfg['discover']:
        for f in _glob.glob(str(root / pat), recursive=True):
            p = Path(f)
            if not p.is_file() or p.suffix != '.py':
                continue
            rel = str(p.relative_to(root)).replace('\\', '/')
            if any(PP(rel).match(x.lstrip('./')) for x in cfg['exclude']):
                continue
            out.append(p)
    return sorted(set(out), key=lambda p: p.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--fast', action='store_true', help='跳过 slow=true 的套件')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--config')
    ap.add_argument('--root', help='项目根（默认：往上找带 selftests.json 的那一层 ✓）')
    a = ap.parse_args()
    root = Path(a.root).resolve() if a.root else DEFAULT_ROOT
    cfg = load_cfg(root, a.config)
    warn_if_default_cfg(cfg)          # 退回内置默认必须出声 ✗（原来是静默的 ✗）
    files = discover(root, cfg)

    if a.list:
        print('发现 %d 个套件' % len(files))
        print('  根  ：%s' % root)
        print('  配置：%s' % (cfg['_config'] or '内置默认 ⚠'))
        for p in files:
            meta = cfg['suites'].get(p.name, {})
            mark = '[skip] ' if p.name in cfg['skip'] else ('[slow] ' if meta.get('slow') else '')
            print('  %-10s %s%-32s %s' % (meta.get('label', ''), mark, p.name,
                                          meta.get('desc', '')))
        return 0

    ok = fail = skip = 0
    fails = []
    print('=' * 78)
    print('全部自检（发现 %d 套 ｜ 根：%s ｜ 配置：%s）'
          % (len(files), root, cfg['_config'] or '内置默认 ⚠'))
    print('=' * 78)
    for p in files:
        meta = cfg['suites'].get(p.name, {})
        label = meta.get('label') or p.stem.replace('_selftest_', '')
        desc = meta.get('desc', '')
        if p.name in cfg['skip']:
            print('  %-14s [配置跳过] %s' % (label, desc))
            skip += 1
            continue
        if meta.get('slow') and a.fast:
            print('  %-14s [--fast 跳过] %s' % (label, desc))
            skip += 1
            continue
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, '-X', 'utf8', '-u', str(p)], cwd=str(root),
                               capture_output=True, text=True, encoding='utf-8',
                               errors='replace', env=env, timeout=cfg['timeout_s'])
            rc, out, err = r.returncode, r.stdout or '', r.stderr or ''
        except subprocess.TimeoutExpired:
            rc, out, err = 124, '', '超时（%ds）' % cfg['timeout_s']
        dt = time.time() - t0
        last = ''
        for ln in out.strip().splitlines()[::-1]:
            if ln.strip() and 'Traceback' not in ln:
                last = ln.strip()
                break
        if rc == 0:
            ok += 1
            print('  %-14s OK   %5.1fs  %s' % (label, dt, desc))
            if last:
                print('  %-14s      └ %s' % ('', last[:110]))
        else:
            fail += 1
            fails.append((label, p.name, rc))
            print('  %-14s FAIL %5.1fs  %s' % (label, dt, desc))
            for ln in (err or out).strip().splitlines()[-6:]:
                print('  %-14s      | %s' % ('', ln[:110]))

    n_as = 0
    for c in (root / 'res/sift/nav/assumptions.json', root / 'assumptions.json',
              root / 'docs/unmeasured.json'):
        if c.exists():
            try:
                n_as = len(json.loads(c.read_text(encoding='utf-8')).get('items') or [])
                break
            except Exception:  # noqa: BLE001
                pass
    print('-' * 78)
    print('结果：通过 %d ｜ 失败 %d ｜ 跳过 %d' % (ok, fail, skip))
    if n_as:
        print('⚠️  标为「未实测」的初值：%d 个' % n_as)
    if fails:
        print('失败清单：%s' % ', '.join('%s(%s)' % (n, f) for n, f, _ in fails))
        return 1
    print('[OK] 全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
