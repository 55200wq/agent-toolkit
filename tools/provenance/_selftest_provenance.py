"""溯源自检（**本项目的薄封装**）。

真正的引擎是通用版 `tools/provenance_check.py`（配置驱动、不含任何项目知识）✓
本文件只是让老入口继续可用（自检套件与 pre-commit 钩子都在调它）✓

口径写在 `tools/provenance.json`（扫描面 / 标签关键字 / 豁免 / 档案路径）✓
引擎用法：
    python tools/provenance_check.py --audit               # 看哪些数值没写来历
    python tools/provenance_check.py --write-assumptions   # 重新生成未实测清单

（历史：用户 2026-10-15 发现我会"默默拍一个数当依据用"（step_dt=0.12、翻越判据 3px、
  输入延迟 0.5~1.0s …）且从不提示 ⇒ 要求做成机械检查 ⇒ 本套机制由此而来 ✓）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:                                   # 输出被重定向/走管道时默认 GBK，打印 ✅ 等字符会崩
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                      # noqa: BLE001
    pass

import provenance_check as _pc         # noqa: E402

if __name__ == '__main__':
    sys.exit(_pc.main())
