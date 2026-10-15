r"""整类升级「UTF-8 输出兜底」：把**只兜 stdout** 的旧片段换成 stdout + stderr 都兜 ✓

【为什么必须有这个工具（2026-10-16 实测抓到的缺口 ✗）】
    H3 原来只要求"**有**兜底" ✗ ⇒ 大量脚本只兜了 stdout ✗
    ⇒ stderr 仍是 GBK：**报错信息**变乱码 ✗、✓/✗ 退化成转义字面量 ✗
      （而报错信息恰恰都走 stderr ⇒ 不兜它等于兜了个寂寞 ✗）
    ⇒ H3 已加强为"两个流都要" ✓ ⇒ 已有项目升级后会**一次性报红** ✗
    ⇒ 这个工具就是那个"整类修"的机械手段 ✓
      （"一次只修一个文件"正是这三类事故反复出现的成因 ✗）

【做三件事】
    A 已覆盖两个流 ⇒ 跳过 ✓
    B 有旧兜底（只兜 stdout）⇒ **原地替换**为两流版本 ✓（AST 定位行号 ✓ 不用正则改源码 ✗）
    C 没有兜底但 `print` 了非 ASCII ⇒ 插入到 docstring / `__future__` 之后 ✓

【安全（吃过"改坏 3 个文件"的教训 ✗）】
    · 默认**干跑** ✓，加 `--apply` 才写 ✓
    · 只动"**顶层 try + stdout.reconfigure**"这一处 ✗，且该节点不得超过 MAX_TRY_LINES 行
      （再大就可能是别的大 try 块 ✗ ⇒ 跳过并报到"需人工"里 ✓ 不许猜 ✗）
    · 写前 `ast.parse` 校验新文本 ✓；写后 `compile()` 复验 ✓；BOM 原样保留 ✓
    · 判据与文件发现**复用 hygiene_check** ✓（不另立一套口径 ✗）

【用法】
    python fix_bootstrap.py --root <项目根>                  # 干跑（只报告，不写）
    python fix_bootstrap.py --root <项目根> --apply           # 真写
    python fix_bootstrap.py --root <项目根> --glob "**/*.py"   # 临时换扫描面
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

try:                                   # 输出被重定向/走管道时默认编码可能是 GBK ✗
    import sys as _sys_h               # 打印非 ASCII 会 UnicodeEncodeError ✗ ⇒ 统一兜底 ✓
    for _s_h in (_sys_h.stdout, _sys_h.stderr):   # stdout 与 stderr 都要兜 ✗
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:                      # noqa: BLE001
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hygiene_check as HC              # noqa: E402  复用判据/发现 ✓（同一目录，不另立口径 ✗）

# 要写进目标文件的兜底片段（与 hygiene_check.py 的 H3 推荐片段**逐字一致** ✓）
NEW = '''try:                                   # 输出被重定向/走管道时默认编码可能是 GBK ✗
    import sys as _sys_h               # 打印非 ASCII 会 UnicodeEncodeError ✗ ⇒ 统一兜底 ✓
    for _s_h in (_sys_h.stdout, _sys_h.stderr):   # stdout 与 stderr 都要兜 ✗
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:                      # noqa: BLE001
    pass
'''

MAX_TRY_LINES = 12                     # 依据: 机制（本模板 7 行；留余量到 12，再大就可能是别的大 try 块 ✗）


def find_old_bootstrap(tree):
    """找"顶层 try 里只兜 stdout"的旧片段 ⇒ 返回节点；没有/不敢认 返回 None ✓"""
    for node in tree.body:
        if not isinstance(node, ast.Try):
            continue
        dump = ast.dump(node)
        if 'reconfigure' in dump and 'stdout' in dump and 'stderr' not in dump:
            if (node.end_lineno - node.lineno + 1) <= MAX_TRY_LINES:
                return node
    return None


def insertion_line(tree) -> int:
    """返回 0 基行号：docstring 与 `__future__` 之后（与上一版迁移脚本同口径 ✓）。"""
    at = 0
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        at = body[0].end_lineno
        body = body[1:]
    for node in body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            at = max(at, node.end_lineno)
        else:
            break
    return at


def prints_non_ascii(tree) -> bool:
    return any(any(ord(c) > 127 for c in v) for v, _ in HC.printed_strings(tree))


def upgrade(text: str, cfg):
    """⇒ (新文本或 None, 动作说明)。动作以「需人工」开头 ⇒ 必须人看 ✗ 不许自动改 ✗"""
    tree = ast.parse(text)
    got = HC.covered_streams(text, tree, cfg)
    if 'stdout' in got and 'stderr' in got:
        return None, '已覆盖'
    lines = text.splitlines()
    node = find_old_bootstrap(tree)
    if node is not None:                                   # B：原地替换 ✓
        new = '\n'.join(lines[:node.lineno - 1] + NEW.splitlines()
                        + lines[node.end_lineno:]) + '\n'
        return new, '替换旧兜底（原第 %d~%d 行）' % (node.lineno, node.end_lineno)
    if got:
        # 有兜底、但形态不是"顶层 try + stdout.reconfigure" ⇒ 不许猜 ✗
        return None, '需人工：有兜底但形态不常见（覆盖 %s），未自动改 ✗' % ','.join(sorted(got))
    if not prints_non_ascii(tree):
        return None, '不需要（没打印非 ASCII）'
    at = insertion_line(tree)                              # C：插入 ✓
    new = '\n'.join(lines[:at] + [''] + NEW.splitlines() + lines[at:]) + '\n'
    return new, '插入新兜底（第 %d 行后）' % at


def main() -> int:
    ap = argparse.ArgumentParser(description='整类升级 UTF-8 输出兜底（stdout + stderr）')
    ap.add_argument('--root', required=True, help='项目根')
    ap.add_argument('--apply', action='store_true', help='真写（默认只干跑 ✓）')
    ap.add_argument('--glob', help='临时覆盖扫描面（默认用 hygiene.json 的 scan ✓）')
    ap.add_argument('--config', help='指定 hygiene.json')
    a = ap.parse_args()
    root = Path(a.root).resolve()
    cfg = HC.load_cfg(root, a.config)
    if a.glob:
        cfg['scan'] = [a.glob]
    files = list(HC.iter_files(root, cfg))

    todo, manual, broken = [], [], []
    for p, rel in files:
        raw = p.read_bytes()
        bom = raw.startswith(b'\xef\xbb\xbf')               # BOM 是合法源码 ✓ 原样保留 ✓
        text = raw.decode('utf-8-sig', errors='replace')
        try:
            new, action = upgrade(text, cfg)
        except SyntaxError as e:
            broken.append((rel, '改前 AST 解析失败：%s' % str(e)[:40]))
            continue
        if new is None:
            if action.startswith('需人工'):
                manual.append((rel, action))
            continue
        try:
            ast.parse(new)                                  # 写前校验 ✓
        except SyntaxError as e:
            broken.append((rel, '改后语法错，已跳过：%s' % str(e)[:40]))
            continue
        todo.append((p, rel, new, action, bom))

    print('需要升级兜底的脚本：%d 个（扫描 %d 个文件 ｜ 根：%s ｜ 配置：%s）'
          % (len(todo), len(files), root, cfg.get('_config') or '默认'))
    for _, rel, _, action, _ in todo[:15]:
        print('  %-56s %s' % (rel, action))
    if len(todo) > 15:
        print('  ...（还有 %d 个）' % (len(todo) - 15))
    for title, items in (('需人工确认（不许猜 ✗）', manual), ('有问题，已跳过 ✗', broken)):
        if items:
            print('%s：' % title)
            for rel, why in items:
                print('  %-56s %s' % (rel, why))

    if not a.apply:
        print('\n（干跑 ✓ 未写任何文件；确认后加 --apply ✓）')
        return 0

    written = 0
    for p, rel, new, _, bom in todo:
        p.write_text(new, encoding='utf-8-sig' if bom else 'utf-8')
        try:
            compile(p.read_text(encoding='utf-8-sig'), str(p), 'exec')    # 写后复验 ✓
            written += 1
        except SyntaxError as e:
            print('  [严重] 写入后编译失败：%s %s ⇒ 请 git 回滚该文件 ✗' % (rel, e))
    print('\n已写入 %d 个文件 ✓' % written)
    return 0


if __name__ == '__main__':
    sys.exit(main())
