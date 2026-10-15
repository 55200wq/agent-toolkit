r"""session_cost 的自测：造一个假会话文件（含缓存失效与注入），验证解析/汇总/归因/审计。

【为什么必须有】分析工具一旦归因错了 ✗，会把人引到错误的优化方向 ✗
    ⇒ 用"已知答案"的假日志验证：用量汇总、最贵轮排序、未缓存激增的归因、审计指标
【用法】python test_session_cost.py      退出码 0=通过 1=失败
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
ENGINE = HERE / 'session_cost.py'
FAILS = []


def check(name, cond, detail=''):
    print('  %-6s %-46s %s' % ('OK' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


def ev(seq, t, data, time_ms):
    return {'seq': seq, 'type': t, 'time': time_ms, 'data': data}


def build_log(path: Path):
    """造 3 轮：
       轮1：3 步，全命中缓存，便宜
       轮2：2 步，步 2 前注入 system-prompt ⇒ 步 2 未缓存激增（用来验证归因）
       轮3：1 步，普通
    """
    base = 1_792_000_000_000
    rows = []
    s = 0

    def add(t, data, dt=1000):
        nonlocal s
        s += 1
        rows.append(ev(s, t, data, base + s * dt))

    # ---- 轮 1
    add('turn/start', {'turn': 1})
    add('step/start', {'turn': 1, 'step': 1})
    add('assistant/message', {'turn': 1, 'step': 1,
                              'usage': {'inputTokens': 100, 'cacheReadTokens': 1000,
                                        'cacheWriteTokens': 0, 'outputTokens': 50}})
    add('tool/call', {'turn': 1, 'step': 1, 'callId': 'c1', 'name': 'read', 'arguments': '{}'})
    add('tool/result', {'turn': 1, 'step': 1,
                        'message': {'role': 'tool', 'toolCallId': 'c1',
                                    'content': [{'type': 'text', 'text': 'x' * 500}]}})
    add('step/start', {'turn': 1, 'step': 2})
    add('assistant/message', {'turn': 1, 'step': 2,
                              'usage': {'inputTokens': 120, 'cacheReadTokens': 1100,
                                        'outputTokens': 60}})
    add('step/start', {'turn': 1, 'step': 3})
    add('assistant/message', {'turn': 1, 'step': 3,
                              'usage': {'inputTokens': 90, 'cacheReadTokens': 1200,
                                        'outputTokens': 40}})
    add('turn/end', {'turn': 1, 'reason': {'kind': 'completed'}})

    # ---- 轮 2：步 2 前系统提示重建 ⇒ 未缓存激增
    add('turn/start', {'turn': 2})
    add('step/start', {'turn': 2, 'step': 1})
    add('assistant/message', {'turn': 2, 'step': 1,
                              'usage': {'inputTokens': 150, 'cacheReadTokens': 5000,
                                        'outputTokens': 30}})
    add('system/message', {'turn': 2, 'step': 2,
                           'message': {'role': 'system', 'content': [],
                                       'source': {'kind': 'system-prompt'}}})
    add('step/start', {'turn': 2, 'step': 2})
    add('assistant/message', {'turn': 2, 'step': 2,
                              'usage': {'inputTokens': 90000, 'cacheReadTokens': 300,
                                        'outputTokens': 25}})
    add('turn/end', {'turn': 2, 'reason': {'kind': 'completed'}})

    # ---- 轮 3：一次压缩检查点注入（不激增，用于验证统计）
    add('turn/start', {'turn': 3})
    add('step/start', {'turn': 3, 'step': 1})
    add('assistant/message', {'turn': 3, 'step': 1,
                              'usage': {'inputTokens': 200, 'cacheReadTokens': 800,
                                        'outputTokens': 10}})
    add('compaction/end', {'compactionId': 'z', 'turn': 3})
    add('turn/end', {'turn': 3, 'reason': {'kind': 'completed'}})

    try:
        from compression import zstd
        raw = '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows).encode('utf-8')
        path.write_bytes(zstd.compress(raw))
    except Exception:                          # noqa: BLE001
        import zstandard as zstd
        path.write_bytes(zstd.ZstdCompressor().compress(
            '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows).encode('utf-8')))


def run(sess: Path, *args):
    import os
    e = dict(os.environ)
    e.update({'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    return subprocess.run([sys.executable, '-X', 'utf8', str(ENGINE), '--session', str(sess), *args],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=e)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='sesscost_'))
    try:
        sess = tmp / 'session.v4.jsonl.zstd'
        build_log(sess)

        r = run(sess, '--turns', '--top', '3')
        o = r.stdout or ''
        check('--turns 退出码 0', r.returncode == 0, 'rc=%d' % r.returncode)
        check('轮次数=3', '轮次数 3' in o)
        # 轮2 = 150+5000+30 + 90000+300+25 = 95505；轮1 = 2170；轮3 = 1010
        # 最贵排行里第一行数据应是轮 2（跳过表头行 ✓）
        top_line = next((l for l in o.split('最贵的')[-1].splitlines()
                         if '95,505' in l), '')
        check('最贵轮是轮 2', top_line.strip().startswith('2'), top_line.strip()[:40])
        check('轮2 合计 95,505 出现', '95,505' in o, [l for l in o.splitlines() if '95,505' in l][:1])

        r2 = run(sess, '--turn', '2')
        o2 = r2.stdout or ''
        check('--turn 2 退出码 0', r2.returncode == 0, 'rc=%d' % r2.returncode)
        check('列出 system-prompt 注入', 'system-prompt' in o2)
        check('归因指向步 2 与 system-prompt',
              '步2' in o2.replace('步 2', '步2') and 'system-prompt' in o2.split('归因')[-1])
        check('步2 标记未缓存激增', '未缓存激增' in o2)

        r3 = run(sess, '--audit')
        o3 = r3.stdout or ''
        check('--audit 退出码 0', r3.returncode == 0, 'rc=%d' % r3.returncode)
        check('审计报出"系统提示重建 1 次"', '系统提示重建：1 次' in o3)
        check('审计报出"前缀作废 1 次"', '前缀作废次数（未缓存输入 > 5k 的步）：1 次' in o3)

        r4 = run(sess, '--turn', '2', '--json')
        try:
            j = json.loads(r4.stdout)
            ok = (j['turn'] == 2 and j['usage']['in'] == 90150
                  and len(j['blame']) == 1 and j['blame'][0]['step'] == 2)
        except Exception as e:                  # noqa: BLE001
            ok = False
            print('    JSON 解析失败:', e)
        check('--json 结构正确', ok)

        r5 = run(sess, '--turn', '99')
        check('不存在的轮次 ⇒ 退出码 2', r5.returncode == 2, 'rc=%d' % r5.returncode)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print('[FAIL] 自测未通过：%s' % ', '.join(FAILS))
        return 1
    print('[OK] session-cost 自测通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
