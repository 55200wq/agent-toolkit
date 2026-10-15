r"""脚本工程卫生检查（script hygiene）：拦住"改坏源码 / 路径转义 / 输出编码"三类重复事故。

【为什么要做（用户 2026-10-16 提出）】
    在一次会话里我反复犯同一类错，而且每类只修一个文件 ✗ ⇒ 出现"好多重复报错" ✗：
      A 编码   —— 脚本打印中文/✓✗✅，输出被重定向或走管道时用 GBK ✗ ⇒ UnicodeEncodeError ✗（犯了 5 次）
      B 转义   —— 把 Windows 路径写进 Python 字面量 ✗ ⇒ `\U`/`\t` 转义错或静默错路径 ✗（犯了 4 次）
      C 手术   —— 用正则/行号批量改源码 ✗ ⇒ 改坏文件 ✗，而且**没有任何检查拦住** ✗（犯了 3 次）
    对策：把三类都变成**机械检查** ✓ 一次管住整类，而不是逐个文件打补丁 ✗

【三条规则】
    H1 所有扫描到的 .py 必须能编译 ✓      （兜住 C 类：改坏立刻红 ✗）
    H2 不许把 Windows 反斜杠路径写进字面量 ✓（兜住 B 类：`'C:\\temp'` 里 `\t` 是制表符 ✗ 静默错 ✓）
       —— 用正斜杠 `C:/temp` ✓ 或 raw 字符串 r'C:\\temp' ✓
    H3 打印非 ASCII 的脚本必须有 UTF-8 输出兜底 ✓（兜住 A 类：重定向/走管道不再崩 ✓）
       —— **stdout 和 stderr 必须都兜** ✓（判据用 AST ✓ 认别名/循环写法 ✓ 见 covered_streams）
          ⚠️ 只兜 stdout 是**假兜底** ✗（2026-10-16 实测抓到的缺口 ✗）：
             stderr 仍是 GBK ⇒ **报错信息**变乱码 ✗、✓/✗ 退化成转义字面量 ✗；
             而报错信息恰恰都走 stderr ✗ ⇒ 不兜它等于兜了个寂寞 ✗
          ⚠️ 老配置只写 bootstrap_markers 也不会静默放行 ✓（stderr 那一半另算 ✓）

【配置 hygiene.json（可选；不写就用默认）】
    {
      "scan": ["**/*.py"], "exclude": [".git/**", ".venv/**"],
      "rules": {"H1": true, "H2": true, "H3": true},
      "bootstrap_markers": ["reconfigure(encoding", "TextIOWrapper(sys.stdout.buffer"],
      "bootstrap_stderr_markers": ["_sys_h.stderr", "(sys.stdout, sys.stderr)"],
      "h3_ignore_files": []
    }

【推荐兜底片段（stdout 与 stderr 都兜 ✓；工具：fix_bootstrap.py 可整类升级 ✓）】
    try:                                   # 输出被重定向/走管道时默认编码可能是 GBK ✗
        import sys as _sys_h               # 打印非 ASCII 会 UnicodeEncodeError ✗ ⇒ 统一兜底 ✓
        for _s_h in (_sys_h.stdout, _sys_h.stderr):   # 两个流都要兜 ✗
            _s_h.reconfigure(encoding='utf-8', errors='replace')
        del _sys_h, _s_h
    except Exception:                      # noqa: BLE001
        pass

【用法】
    python hygiene_check.py --root <项目根>            # 检查（有问题=非零退出）
    python hygiene_check.py --root <项目根> --list     # 只列扫描文件
    python hygiene_check.py --root <项目根> --fix-note # 打印修复指引

【边界（说清它管不到什么）】
    · H3 只看 `print(...)` 里的字符串 ✗（logging / sys.stdout.write 不查 ✓ 见 README）
    · H2 只查"看起来像盘符路径"的字面量 ✗（其他转义问题靠 H1 暴露 ✓）
    · 它不判断代码逻辑对不对 ✗ —— 只管这三类**反复出现**的工程事故 ✓
"""
from __future__ import annotations

import argparse
import ast
import glob as _glob
import json
import sys
from pathlib import Path, PurePosixPath as PP

try:                                   # 输出被重定向/走管道时默认编码可能是 GBK ✗
    import sys as _sys_h               # 打印非 ASCII 会 UnicodeEncodeError ✗ ⇒ 统一兜底 ✓
    for _s_h in (_sys_h.stdout, _sys_h.stderr):   # stdout 与 stderr 都要兜 ✗
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:                      # noqa: BLE001
    pass

DEFAULT_CONFIG_NAME = 'hygiene.json'
DECOR = set('✓✗✅❌⚠★☆→←↔※')          # 装饰性符号（中文也算非 ASCII ✓）

# 平台差异（实测确认 ✓）：
#   H1 编译      —— 平台无关 ✓（纯 AST）全平台默认开 ✓
#   H2 路径转义  —— 逻辑平台无关 ✓，但只认"盘符路径"⇒ 在 Linux 上几乎不会触发 ✗（无害但很窄 ✓）
#   H3 输出编码  —— **Windows 才是真问题** ✗：重定向/走管道时默认 GBK ⇒ UnicodeEncodeError ✓
#                  Linux 默认就是 UTF-8 ✓（PEP 538/540 连 C locale 也会coerce ✓）⇒ 在 Linux 上是误报 ✗
#                  ⇒ 默认按平台开：Windows 开 ✓ / 其他平台关 ✓（可用配置或 --all-rules 打开 ✓）
_IS_WINDOWS = (__import__('os').name == 'nt')

DEFAULTS = {
    'scan': ['**/*.py'],
    'exclude': ['.git/**', '.venv/**', 'venv/**', 'node_modules/**', '**/__pycache__/**'],
    'rules': {'H1': True, 'H2': True, 'H3': _IS_WINDOWS},
    'bootstrap_markers': ["reconfigure(encoding", "TextIOWrapper(sys.stdout.buffer",
                          "PYTHONIOENCODING"],
    # stderr 那一半：主判据是 **AST**（认别名/循环写法 ✓，见 covered_streams ✓）；
    # 这里只是给"检查器认不出的写法"留的后门 ✓（老配置没有这个键 ⇒ 用默认 ✓ 不会静默放行 ✗）
    'bootstrap_stderr_markers': ["_sys_h.stderr", "sys.stderr.reconfigure",
                                 "TextIOWrapper(sys.stderr.buffer)", "(sys.stdout, sys.stderr)",
                                 "(_sys_h.stdout, _sys_h.stderr)"],
    'h3_ignore_files': [],
}


def load_cfg(root: Path, explicit=None):
    cfg = dict(DEFAULTS)
    # 顺序：显式 > root 自己的 > root/tools/（装进项目后配置就放在 tools/ ✓）> 引擎同级 > cwd
    cands = ([Path(explicit)] if explicit else []) + [
        root / DEFAULT_CONFIG_NAME, root / 'tools' / DEFAULT_CONFIG_NAME,
        Path(__file__).resolve().parent / DEFAULT_CONFIG_NAME,
        Path.cwd() / DEFAULT_CONFIG_NAME]
    for c in cands:
        if c.exists():
            try:                           # 空文件/坏 JSON 不该让工具崩 ✗（本项目真踩过 ✓）
                raw = json.loads(c.read_text(encoding='utf-8-sig'))
            except Exception as e:         # noqa: BLE001
                print('[警告] 配置无法解析，已跳过：%s（%s）' % (c, str(e)[:60]))
                continue
            for k, v in raw.items():
                if k == 'rules' and isinstance(v, dict):
                    cfg['rules'] = {**DEFAULTS['rules'], **v}
                else:
                    cfg[k] = v
            cfg['_config'] = str(c)
            return cfg
    cfg['_config'] = None
    return cfg


def iter_files(root: Path, cfg):
    for pat in cfg['scan']:
        for f in _glob.glob(str(root / pat), recursive=True):
            p = Path(f)
            if not p.is_file() or p.suffix != '.py':
                continue
            rel = str(p.relative_to(root)).replace('\\', '/')
            if any(PP(rel).match(x.lstrip('./')) for x in cfg['exclude']):
                continue
            yield p, rel


# ---------------------------------------------------------------- H1
def check_compiles(src: str, rel: str):
    try:
        compile(src, rel, 'exec')
        return None
    except SyntaxError as e:
        return {'rule': 'H1', 'file': rel, 'line': e.lineno or 0,
                'detail': '%s（改坏了源码 ⇒ 写文件前必须 ast.parse 校验）' % e.msg}


# ---------------------------------------------------------------- H2
DRIVE_SRC = __import__('re').compile(r"""^[rR]?['"]([A-Za-z]:\\)""")
RAW_PREFIX = __import__('re').compile(r"""^[rR]['"]""")


def check_backslash_paths(src: str, rel: str, tree):
    """查"把 Windows 反斜杠路径写进字面量"。

    注意：**必须看源码片段**，不能看解析后的值 ✗ —— 因为 `'C:\\temp'` 解析后
    反斜杠已变成制表符 ✗，值里根本看不到反斜杠（这正是它危险的地方 ✓）。
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        seg = ast.get_source_segment(src, node)
        if not seg:
            continue
        if not DRIVE_SRC.match(seg):
            continue
        if RAW_PREFIX.match(seg):
            continue                       # raw 字符串 ✓ 允许
        out.append({'rule': 'H2', 'file': rel, 'line': node.lineno,
                    'detail': "字面量里有 Windows 反斜杠路径（\\t \\n \\U 会被当转义 ✗ 或静默错 ✓）"
                              "⇒ 改用正斜杠 'C:/...' ✓ 或 raw 字符串 r'C:\\...' ✓"})
    return out


# ---------------------------------------------------------------- H3
def printed_strings(tree):
    """收集 print(...) 里出现的所有字符串常量（含 f-string 片段）。"""
    vals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'print':
            for arg in list(node.args) + [k.value for k in node.keywords if k.value]:
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        vals.append((sub.value, sub.lineno))
    return vals


def _stream_of(node):
    """把表达式判成 'stdout' / 'stderr' / None（认 `sys.x` 与 `sys.x.buffer` 两种 ✓）。"""
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == 'sys' \
                and node.attr in ('stdout', 'stderr'):
            return node.attr
        if node.attr == 'buffer':
            return _stream_of(node.value)
    return None


def covered_streams(src: str, tree, cfg):
    """判断文件里的 UTF-8 兜底**覆盖了哪些流** ⇒ 返回 {'stdout'} / {'stderr'} / 两者 ✓

    为什么不能只看字符串标记 ✗：本项目模板的写法是**别名 + 循环**
        `import sys as _sys_h` … `for _s_h in (_sys_h.stdout, _sys_h.stderr): _s_h.reconfigure(…)`
    ⇒ 任何"认 `sys.stdout.reconfigure` 字样"的口径都认不出它 ✗（实测踩到 ✓）
    ⇒ 所以主力判据用 AST ✓，字符串标记只作后备 ✓

    认三种写法 ✓：① `sys.x.reconfigure(...)` ② 循环别名（把 for 的迭代元组解出来 ✓）
                 ③ `TextIOWrapper(sys.x.buffer, ...)`

    ⚠️ `PYTHONIOENCODING` 这个**字符串出现在文件里不算数** ✗（实测踩到 ✓）：
       很多脚本是"给**子进程**设 PYTHONIOENCODING"（`subprocess(env={...})`）✗
       ⇒ 那**管不到自己**的 stderr ✗；而且运行时再设它对已创建的流也无效 ✗
       ⇒ 只有"外部启动环境里设好"才算 ✓ ⇒ 那种项目请在配置里显式写
         `bootstrap_stderr_markers: ["PYTHONIOENCODING"]` ✓（后门 ✓）
    """
    got = set()
    if any(m in src for m in cfg['bootstrap_markers']):
        got.add('stdout')                  # 后备口径：有兜底 ⇒ 至少兜了 stdout ✓（旧口径就是它 ✓）
    # ① 循环别名：先把 for 目标名 → 覆盖的流 记下来 ✓
    loops = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            elts = node.iter.elts if isinstance(node.iter, (ast.Tuple, ast.List)) else [node.iter]
            streams = {_stream_of(e) for e in elts} - {None}
            if streams:
                loops[node.target.id] = streams
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == 'reconfigure':      # ①②
            s = _stream_of(f.value)
            if s:
                got.add(s)
            elif isinstance(f.value, ast.Name) and f.value.id in loops:
                got |= loops[f.value.id]
        elif ((isinstance(f, ast.Name) and f.id == 'TextIOWrapper')          # ③
                or (isinstance(f, ast.Attribute) and f.attr == 'TextIOWrapper')):   # io.X ✓
            for arg in node.args:
                s = _stream_of(arg)
                if s:
                    got.add(s)
    for m in (cfg.get('bootstrap_stderr_markers') or []):                  # 后门 ✓
        if m in src:
            got.add('stderr')
    return got


def check_print_encoding(src: str, rel: str, tree, cfg):
    if rel in (cfg.get('h3_ignore_files') or []):
        return []
    # 兜底要**两半都在** ✓：只兜 stdout = 假兜底 ✗（stderr 报错照样乱码 ✗）
    got = covered_streams(src, tree, cfg)
    if 'stdout' in got and 'stderr' in got:
        return []
    bad = [(v, ln) for v, ln in printed_strings(tree) if any(ord(c) > 127 for c in v)]
    if not bad:
        return []
    v, ln = bad[0]
    if 'stdout' not in got and 'stderr' not in got:
        detail = ("print 里有非 ASCII（如 %r…）但文件缺 UTF-8 输出兜底 ✗ ⇒ 加 "
                  "for _s in (sys.stdout, sys.stderr): _s.reconfigure("
                  "encoding='utf-8', errors='replace')" % v[:12])
    else:
        have = 'stdout' if 'stdout' in got else 'stderr'
        detail = ("print 里有非 ASCII（如 %r…）但兜底**只兜了 %s** ✗ ⇒ 另一个流仍是 GBK "
                  "⇒ 报错信息变乱码、✓/✗ 退化成转义字面量 ✗ ⇒ 两个流都要 reconfigure ✓"
                  % (v[:12], have))
    return [{'rule': 'H3', 'file': rel, 'line': ln, 'detail': detail}]


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description='脚本卫生检查（编译/路径转义/输出编码）')
    ap.add_argument('--root', help='项目根（默认本文件上两级）')
    ap.add_argument('--config')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--fix-note', action='store_true', help='打印修复指引')
    ap.add_argument('--rules', help='临时覆盖规则，如 H1,H3（逗号分隔；用于跨平台验证）')
    ap.add_argument('--all-rules', action='store_true', help='打开全部规则（跨平台验证用）')
    a = ap.parse_args()
    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent.parent
    cfg = load_cfg(root, a.config)
    if a.all_rules:
        cfg['rules'] = {'H1': True, 'H2': True, 'H3': True}
    elif a.rules:
        want = {x.strip().upper() for x in a.rules.split(',') if x.strip()}
        cfg['rules'] = {k: (k in want) for k in ('H1', 'H2', 'H3')}
    files = list(iter_files(root, cfg))

    if a.list:
        print('扫描面（%s）：' % (cfg['_config'] or '默认'))
        for _, rel in files:
            print('  %s' % rel)
        return 0

    problems, n_ok = [], 0
    for p, rel in files:
        # 用 utf-8-sig 读：带 BOM 的文件是**合法的 Python 源码** ✓ 不该判成编译失败 ✗
        src = p.read_text(encoding='utf-8-sig', errors='ignore')
        p1 = check_compiles(src, rel) if cfg['rules'].get('H1') else None
        if p1:
            problems.append(p1)
            continue                        # 编译不过就不再做 AST 检查 ✓
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        if cfg['rules'].get('H2'):
            problems += check_backslash_paths(src, rel, tree)
        if cfg['rules'].get('H3'):
            problems += check_print_encoding(src, rel, tree, cfg)
        n_ok += 1

    on = ','.join(k for k in ('H1', 'H2', 'H3') if cfg['rules'].get(k)) or '（全部关闭）'
    print('脚本卫生检查：扫描 %d 个文件 ｜ 平台=%s ｜ 启用的规则=%s ｜ 配置：%s'
          % (len(files), 'windows' if _IS_WINDOWS else 'posix', on, cfg['_config'] or '默认'))
    if not problems:
        print('  [OK] H1 全部可编译 ｜ H2 无路径转义隐患 ｜ H3 打印非 ASCII 的 stdout+stderr 都兜住了')
        return 0
    by_rule = {}
    for it in problems:
        by_rule.setdefault(it['rule'], []).append(it)
    for rule in ('H1', 'H2', 'H3'):
        items = by_rule.get(rule) or []
        if not items:
            continue
        title = {'H1': '编译失败（改坏了源码）', 'H2': 'Windows 反斜杠路径字面量',
                 'H3': '打印非 ASCII 但 UTF-8 兜底不全（stdout/stderr 漏了）'}[rule]
        print('\n%s × %d —— %s' % (rule, len(items), title))
        for it in items[:25]:
            print('  %-42s:%-5d %s' % (it['file'], it['line'], it['detail']))
        if len(items) > 25:
            print('  ...（还有 %d 个）' % (len(items) - 25))
    if a.fix_note:
        print('\n修复指引：')
        print('  H1：写文件前 ast.parse 校验；不要用正则/行号改源码 ✗')
        print('  H2：路径用正斜杠 C:/x/y ✓ 或 r\'C:\\x\\y\' ✓')
        print("  H3：文件顶部加（stdout 与 stderr **都要** ✗ 只兜 stdout 是假兜底）")
        print("      for _s in (sys.stdout, sys.stderr):")
        print("          _s.reconfigure(encoding='utf-8', errors='replace')")
    print('\n[FAIL] 脚本卫生检查未通过：%d 处' % len(problems))
    return 1


if __name__ == '__main__':
    sys.exit(main())
