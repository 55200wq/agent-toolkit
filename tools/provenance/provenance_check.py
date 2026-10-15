"""溯源自检（**通用版**）：搜索项目里的可调数值，要求每个都写明「来历」。

【目的】
    本项目里出现过"默默拍一个数当依据用"的事故（`step_dt=0.12`、翻越判据 3px、
    输入延迟 0.5~1.0s …）✗ 且写的时候不觉得那是猜 ⇒ 从没进过任何清单 ⇒ 只能靠人事后抓 ✗
    ⇒ 用机械检查兜住：**不许"不说清某个数从哪来"** ✓

【它不是万能的（边界，必须说清）】
    · 只搜 4 种写法：模块级常量 / `self.x = 数字` / 数值表 / `__init__` 签名默认值 ✓
      函数体内的行内字面量（`x = a * 0.5`）**不搜** ✗（有意收窄以降低误报）
    · 只查"**有没有来历**"，**不查"值对不对"** ✗
      （`VAULT_MIN_PX = 99.0  # 依据: 实测（成功翻越 0.55~0.74px）` 也会通过 ✗）
    · 抓不到**回复/文档里**的错误断言 ✗（那靠行为规则，不靠本工具）

【机制：三态】
    1. `依据: 实测`   有真机/仿真实测出处（最好能追到实测档案）
    2. `依据: 机制`   值由别的机制决定，无需标定
    3. `依据: 未实测` **显式承认是拍的初值** ⇒ 自动进 assumptions 清单
    4. `依据: 语义`   语义常量（状态码等），非可调
    只写"描述"不算依据 ✗

【配置（换项目只改这个）】见同目录 provenance.example.json；
    查找顺序：`--config` > ./provenance.json > <root>/provenance.json > <root>/tools/provenance.json
    配置里的值就是**该项目的口径**；引擎本身不含任何项目知识 ✓

【用法】
    python provenance_check.py                    # 检查（配置自动查找）
    python provenance_check.py --audit            # 只列未标注项
    python provenance_check.py --write-assumptions # 生成"未实测初值"清单
    python provenance_check.py --config X.json
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

DEFAULT_CONFIG_NAME = 'provenance.json'

# 通用默认值（尽量保守；具体项目的口径写在配置里）
DEFAULTS = {
    'scan': ['**/*.py'],
    'exclude': ['.git/**', '.venv/**', 'venv/**', 'node_modules/**', '**/__pycache__/**'],
    'tags': {
        'untested': ['依据: 未实测', 'basis: untested'],
        'measured': ['依据: 实测', 'basis: measured'],
        'mechanism': ['依据: 机制', 'basis: mechanism'],
        'semantic': ['依据: 语义', 'basis: semantic'],
    },
    'lookback_lines': 6,
    'exempt_name_patterns': ['^_', '_T$', '_T0$', '_TIME$', '_UNTIL$', '_TS$'],
    'exempt_self_names': ['t', 'pos', 'x', 'y', 'heading'],
    'semantic_names': [],
    'logic_values': ['0', '1', '2', '-1'],
    'assumptions_out': 'assumptions.json',
    'assumptions_note': '未实测的初值清单（自动生成，勿手改）',
    'premise': '',
}

MOD_CONST = re.compile(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*(-?\d+\.?\d*)\s*(?:#.*)?$')
SELF_ATTR = re.compile(r'^\s*self\.([a-z_][a-z0-9_]*)\s*=\s*(-?\d+\.?\d*)\s*(?:#.*)?$')
NUM_TABLE = re.compile(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*\(\(.*\d.*\)\)\s*(?:#.*)?$')
SIG_DEF = re.compile(r'^\s*def __init__\((.*)\)\s*:(?:\s*#.*)?$')


def find_config(explicit=None, start=None):
    here = Path(start or Path(__file__).resolve().parent).resolve()
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return p if p.exists() else None
    engine_dir = Path(__file__).resolve().parent
    root2 = here.parent if here.name == 'tools' else here
    cands = [Path.cwd() / DEFAULT_CONFIG_NAME, here / DEFAULT_CONFIG_NAME,
             engine_dir / DEFAULT_CONFIG_NAME, root2 / DEFAULT_CONFIG_NAME,
             here.parent / DEFAULT_CONFIG_NAME]
    for c in cands:
        if c.exists():
            return c
    return None


def load_config(path):
    cfg = dict(DEFAULTS)
    if path and path.exists():
        raw = json.loads(path.read_text(encoding='utf-8'))
        for k, v in raw.items():
            if k in ('tags',) and isinstance(v, dict):
                cfg['tags'] = {**DEFAULTS['tags'], **v}
            else:
                cfg[k] = v
    return cfg


def _match_tag(seg, cfg):
    """在一段注释文本里找标签类型。顺序重要：先判 untested，
    否则会被 measured 的子串抢先（"未实测" 含 "实测"）✗"""
    for kind in ('untested', 'measured', 'mechanism', 'semantic'):
        for kw in cfg['tags'].get(kind, []):
            if kw in seg:
                return kind, seg.strip()
    return None, ''


def tag_of(lines, idx, cfg):
    """返回 (标签类型, 说明)。

    **精确规则**（原版"往上 6 行"太宽 ✗ —— 上面某个常量的行尾标注会误罩住下面几行，
    自测 test_provenance.py 一跑就抓到了）：
      ① 同一行的注释里带标签 ⇒ 有效 ✓
      ② 否则向上找：**只接受空行与整行注释**；一旦遇到代码行立即停止 ✓
         （这样"整行注释块 + 紧跟其后的 def/表"仍然有效，
           而"上一行是另一个常量"的情况不会误罩 ✗）
    """
    kind, detail = _match_tag(lines[idx].split('#', 1)[1], cfg) if '#' in lines[idx] else (None, '')
    if kind:
        return kind, detail
    j = idx - 1
    found = (None, '')
    while j >= 0:
        s = lines[j].strip()
        if s == '':
            j -= 1
            continue
        if s.startswith('#'):
            k2, d2 = _match_tag(s.lstrip('#').strip(), cfg)
            if k2:
                found = (k2, d2)
            j -= 1
            continue
        break
    return found


def scan_file(path, root, cfg):
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:  # noqa: BLE001
        return [], []
    bad, untested = [], []
    rel = str(path.relative_to(root)).replace('\\', '/')
    logic = set(cfg['logic_values'])
    sem = set(cfg['semantic_names'])
    for i, ln in enumerate(lines):
        name = val = kind = None
        m = MOD_CONST.match(ln.strip())
        if m:
            name, val, kind = m.group(1), m.group(2), '常量'
        else:
            m = SELF_ATTR.match(ln)
            if m:
                if m.group(1) in cfg['exempt_self_names'] or \
                        any(re.search(p, m.group(1)) for p in cfg['exempt_name_patterns']):
                    continue
                name, val, kind = 'self.' + m.group(1), m.group(2), '属性'
            else:
                m = NUM_TABLE.match(ln.strip())
                if m:
                    name, val, kind = m.group(1), '(数值表)', '常量表'
        if name is None and not SIG_DEF.match(ln):
            continue
        if name is not None:
            if name in sem or (val in logic and kind != '常量表') or \
                    any(re.search(p, name) for p in cfg['exempt_name_patterns']):
                continue
            tag, detail = tag_of(lines, i, cfg)
            item = {'file': rel, 'line': i + 1, 'name': name, 'value': val, 'kind': kind}
            if tag is None:
                bad.append(item)
            elif tag == 'untested':
                item['note'] = detail
                untested.append(item)
        else:
            args = SIG_DEF.match(ln).group(1)
            nums = [(n, v) for n, v in re.findall(r'([a-z_][a-z0-9_]*)\s*=\s*(-?\d+\.?\d*)', args)
                    if v not in logic]
            if not nums:
                continue
            tag, detail = tag_of(lines, i, cfg)
            for n, v in nums:
                item = {'file': rel, 'line': i + 1, 'name': 'arg:' + n, 'value': v,
                        'kind': '签名默认值'}
                if tag is None:
                    bad.append(item)
                elif tag == 'untested':
                    item['note'] = detail
                    untested.append(item)
    return bad, untested


def iter_files(root, cfg):
    seen = set()
    for pat in cfg['scan']:
        for f in _glob.glob(str(root / pat), recursive=True):
            p = Path(f)
            if not p.is_file() or p.suffix != '.py':
                continue
            rel = str(p.relative_to(root)).replace('\\', '/')
            from pathlib import PurePosixPath as _PP

            def _excluded(r):
                # 用 PurePosixPath.match 才能正确处理 **（fnmatch 不行）
                return any(_PP(r).match(x.lstrip('./')) or _PP(r).match(x)
                           for x in cfg['exclude'])

            if _excluded(rel):
                continue
            if rel in seen:
                continue
            seen.add(rel)
            yield p, rel


def main() -> int:
    ap = argparse.ArgumentParser(description='溯源自检：数值必须有「来历」')
    ap.add_argument('--config')
    ap.add_argument('--root', help='项目根（默认为本文件上两级）')
    ap.add_argument('--audit', action='store_true', help='只列未标注项')
    ap.add_argument('--write-assumptions', action='store_true',
                    help='把"未实测"项写成配置里 assumptions_out 指定的文件')
    a = ap.parse_args()

    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parent.parent
    cfg_path = find_config(a.config, root if not a.config else None)
    cfg = load_config(cfg_path)

    bad, untested, n_files = [], [], 0
    for p, rel in iter_files(root, cfg):
        n_files += 1
        b, u = scan_file(p, root, cfg)
        bad += b
        untested += u

    print('扫描 %d 个文件（配置：%s）' % (n_files, cfg_path or '内置默认'))
    print('  缺「来历」标注：%d 个' % len(bad))
    print('  已标为「未实测」：%d 个' % len(untested))
    if bad:
        print('\n缺标注清单（补 `依据: 实测/机制/未实测 …` 即可）：')
        for it in bad[:40]:
            print('  %-30s:%-5d %-26s %s' % (it['file'], it['line'], it['name'], it['value']))
        if len(bad) > 40:
            print('  ...（还有 %d 个）' % (len(bad) - 40))

    if a.write_assumptions:
        out = root / cfg['assumptions_out']
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {'_说明': cfg['assumptions_note'],
                '_前提': cfg.get('premise') or '',
                '_生成': 'python provenance_check.py --write-assumptions',
                'count': len(untested),
                'items': sorted(untested, key=lambda x: (x['file'], x['line']))}
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        print('\n[写入] %s（%d 项）' % (out, len(untested)))

    if a.audit:
        return 0
    if bad:
        print('\n[FAIL] %d 个数没有「来历」标注' % len(bad))
        print('  三态：`依据: 实测 …` / `依据: 机制 …` / `依据: 未实测 …`（只写描述不算）')
        return 1
    print('\n[OK] 所有可调数值都写明了来历')
    return 0


if __name__ == '__main__':
    sys.exit(main())
