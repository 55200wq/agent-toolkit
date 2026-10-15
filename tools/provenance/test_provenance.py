"""provenance 工具的自测：造一个假项目，验证检查器的行为符合预期。

【目的】工具集自己也要能被验证 ✓（不能只靠"我在本项目里跑过一次" ✗）
    覆盖：已标注 / 未标注 / 数值表 / self 属性 / 签名默认值 / 语义常量 / 私有状态（应豁免）/
          --write-assumptions 产出是否正确 / 退出码是否正确
【用法】python test_provenance.py        退出码 0=通过 1=失败
【依赖】只用标准库（能在任何项目里跑 ✓）
"""
from __future__ import annotations

import json
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
ENGINE = HERE / 'provenance_check.py'
FAILS = []


def check(name, cond, detail=''):
    print('  %-6s %-46s %s' % ('OK' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


FAKE_MAIN = '''"""假项目主文件。"""
GOOD_MEASURED = 1.5      # 依据: 实测（假数据 n=3）
GOOD_MECH = 2.0          # 依据: 机制（与某机制对齐）
STATE_OK = 4             # 依据: 语义（状态码）
BAD_UNTAGGED = 3.0
BAD_DESC_ONLY = 5.0      # 位移小于此值判为没动（只有描述，不算依据）
TABLE_BAD = ((30.0, 12.0), (8.0, 6.0))


class Thing:
    def __init__(self, step_dt=0.12, ok=1.0):      # 依据: 未实测（签名默认值）
        self.latency = 0.4                          # 依据: 未实测（假初值）
        self._last_t = 0.0                          # 私有状态：应豁免
        self.t = 0.0                                # 模拟器时钟：应豁免
        self.plain = 9.9                            # 未标注：应报错
'''

FAKE_CFG = {
    'scan': ['src/*.py'],
    'exclude': [],
    'tags': {'untested': ['依据: 未实测'], 'measured': ['依据: 实测'],
             'mechanism': ['依据: 机制'], 'semantic': ['依据: 语义']},
    'lookback_lines': 6,
    'exempt_name_patterns': ['^_', '_T$'],
    'exempt_self_names': ['t'],
    'semantic_names': ['STATE_OK'],
    'logic_values': ['0', '1', '2', '-1'],
    'assumptions_out': 'out/unmeasured.json',
    'assumptions_note': 'test',
    'premise': 'test premise',
}


def run(args, root):
    env = {'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1', 'PATH': ''}
    import os
    e = dict(os.environ)
    e.update(env)
    return subprocess.run([sys.executable, '-X', 'utf8', str(ENGINE), '--root', str(root)] + args,
                          capture_output=True, text=True, encoding='utf-8', errors='replace', env=e)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='provtest_'))
    try:
        (tmp / 'src').mkdir()
        (tmp / 'src' / 'main.py').write_text(FAKE_MAIN, encoding='utf-8')
        (tmp / 'provenance.json').write_text(json.dumps(FAKE_CFG, ensure_ascii=False), encoding='utf-8')

        r = run([], tmp)
        out = r.stdout or ''
        check('退出码=1（有未标注项）', r.returncode == 1, 'rc=%d' % r.returncode)
        for nm in ('BAD_UNTAGGED', 'BAD_DESC_ONLY', 'TABLE_BAD', 'self.plain'):
            check('报出 %s' % nm, nm in out)
        for nm in ('GOOD_MEASURED', 'GOOD_MECH', 'STATE_OK', 'self._last_t', 'self.t'):
            check('不报 %s（应有来历/豁免）' % nm, nm not in out)

        r2 = run(['--write-assumptions'], tmp)
        f = tmp / 'out' / 'unmeasured.json'
        check('生成清单文件', f.exists())
        if f.exists():
            d = json.loads(f.read_text(encoding='utf-8'))
            names = {i['name'] for i in d['items']}
            check('清单含 self.latency', 'self.latency' in names, str(sorted(names))[:70])
            check('清单含签名默认值', any(n.startswith('arg:') for n in names))
            check('清单不含未标注项', not any(n in names for n in
                                        ('BAD_UNTAGGED', 'BAD_DESC_ONLY', 'self.plain')))
            check('清单带上前提', d.get('_前提') == 'test premise')

        # 修好后应该通过
        fixed = FAKE_MAIN.replace('BAD_UNTAGGED = 3.0', 'BAD_UNTAGGED = 3.0   # 依据: 未实测') \
                          .replace('BAD_DESC_ONLY = 5.0      # 位移小于此值判为没动（只有描述，不算依据）',
                                   'BAD_DESC_ONLY = 5.0      # 依据: 未实测') \
                          .replace('TABLE_BAD = ((30.0, 12.0), (8.0, 6.0))',
                                   'TABLE_BAD = ((30.0, 12.0), (8.0, 6.0))  # 依据: 未实测') \
                          .replace('self.plain = 9.9                            # 未标注：应报错',
                                   'self.plain = 9.9                            # 依据: 未实测')
        (tmp / 'src' / 'main.py').write_text(fixed, encoding='utf-8')
        r3 = run([], tmp)
        check('全部标注后退出码=0', r3.returncode == 0, 'rc=%d' % r3.returncode)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print('★ 自测未通过：%s' % ', '.join(FAILS))
        return 1
    print('[OK] provenance 工具自测通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
