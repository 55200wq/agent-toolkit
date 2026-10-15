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
       —— 兜底形式见配置 bootstrap_markers ✓（默认认 sys.stdout.reconfigure ✓）

【配置 hygiene.json（可选；不写就用默认）】
    {
      "scan": ["**/*.py"], "exclude": [".git/**", ".venv/**"],
      "rules": {"H1": true, "H2": true, "H3": true},
      "bootstrap_markers": ["reconfigure(encoding", "TextIOWrapper(sys.stdout.buffer"],
      "h3_ignore_files": []
    }

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

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
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


def check_print_encoding(src: str, rel: str, tree, cfg):
    if rel in (cfg.get('h3_ignore_files') or []):
        return []
    has_bootstrap = any(m in src for m in cfg['bootstrap_markers'])
    if has_bootstrap:
        return []
    bad = [(v, ln) for v, ln in printed_strings(tree) if any(ord(c) > 127 for c in v)]
    if not bad:
        return []
    v, ln = bad[0]
    return [{'rule': 'H3', 'file': rel, 'line': ln,
             'detail': 'print 里有非 ASCII（如 %r…）但文件缺 UTF-8 输出兜底 ✗ '
                       '⇒ 加 sys.stdout.reconfigure(encoding=\'utf-8\', errors=\'replace\')'
                       % v[:12]}]


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
        print('  [OK] H1 全部可编译 ｜ H2 无路径转义隐患 ｜ H3 打印非 ASCII 的都有兜底')
        return 0
    by_rule = {}
    for it in problems:
        by_rule.setdefault(it['rule'], []).append(it)
    for rule in ('H1', 'H2', 'H3'):
        items = by_rule.get(rule) or []
        if not items:
            continue
        title = {'H1': '编译失败（改坏了源码）', 'H2': 'Windows 反斜杠路径字面量',
                 'H3': '打印非 ASCII 但缺 UTF-8 兜底'}[rule]
        print('\n%s × %d —— %s' % (rule, len(items), title))
        for it in items[:25]:
            print('  %-42s:%-5d %s' % (it['file'], it['line'], it['detail']))
        if len(items) > 25:
            print('  ...（还有 %d 个）' % (len(items) - 25))
    if a.fix_note:
        print('\n修复指引：')
        print('  H1：写文件前 ast.parse 校验；不要用正则/行号改源码 ✗')
        print('  H2：路径用正斜杠 C:/x/y ✓ 或 r\'C:\\x\\y\' ✓')
        print("  H3：文件顶部加 try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')")
    print('\n[FAIL] 脚本卫生检查未通过：%d 处' % len(problems))
    return 1


if __name__ == '__main__':
    sys.exit(main())
