"""脚本卫生检查（薄封装）：让项目的 run_all_selftests 能自动发现并运行它。

真正的引擎是同目录的 hygiene_check.py（配置驱动，不含项目知识 ✓）
口径写在项目的 `tools/hygiene.json` ✓（缺省时用引擎默认值）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:                                   # 输出被重定向/走管道时默认编码可能是 GBK ✗
    import sys as _sys_h               # 打印非 ASCII 会 UnicodeEncodeError ✗ ⇒ 统一兜底 ✓
    for _s_h in (_sys_h.stdout, _sys_h.stderr):   # stdout 与 stderr 都要兜 ✗
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:                      # noqa: BLE001
    pass

import hygiene_check as _hc            # noqa: E402

if __name__ == '__main__':
    # 默认以"本文件所在项目的上两级"为根（装进项目后就是项目根 ✓）
    sys.exit(_hc.main())
