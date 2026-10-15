r"""session_cost 的自测：造一个假会话文件（含缓存失效与注入），验证解析/汇总/归因/审计/退出码。

【为什么必须有】分析工具一旦归因错了 ✗，会把人引到错误的优化方向 ✗
    ⇒ 用"已知答案"的假日志验证：用量汇总、最贵轮排序、未缓存激增的归因、审计指标
【回归项】--grep 曾单独使用时"打印帮助 + 退出码 0"✗（静默失败）
    ⇒ 现在：无模式 ⇒ 2 ✗；--grep 无命中 ⇒ 1 ✗；命中 + --turns ⇒ 0 ✓
【用法】python test_session_cost.py      退出码 0=通过 1=失败
"""
from __future__ import annotations

import json
import os
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
       轮1：3 步，全命中缓存，便宜（内含关键词 UNIQUEKW_ABC ⇒ 给 --grep 用 ✓）
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
    # 埋一个只在这里出现的关键词：给 --grep（会话筛选）用 ✓
    # 用 source.kind='user' ⇒ 只计入 user_bytes ✓ 不会被当成"注入"影响审计数字 ✓
    add('user/message', {'turn': 1, 'step': 1,
                         'message': {'role': 'user',
                                     'content': [{'type': 'text', 'text': 'UNIQUEKW_ABC'}]},
                         'source': {'kind': 'user'}})
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


def _env(**extra):
    e = dict(os.environ)
    e.update({'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
    e.update(extra)
    return e


def run(sess: Path, *args):
    return subprocess.run([sys.executable, '-X', 'utf8', str(ENGINE), '--session', str(sess), *args],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=_env())


def run_env(root: Path, *args):
    """不给 --session，改用 DSH_SESSIONS_ROOT 指向临时根目录 ✓
    —— 只有这样才测得到"会话定位 + --grep 筛选"这条路径 ✓"""
    return subprocess.run([sys.executable, '-X', 'utf8', str(ENGINE), *args],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=_env(DSH_SESSIONS_ROOT=str(root)))


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

        # ---- 缺陷回归：--grep 曾是"静默空操作"✗（单独用 ⇒ 打印帮助 + 退出码 0）
        r6 = run_env(tmp, '--grep', 'UNIQUEKW_ABC', '--turns')
        o6 = r6.stdout or ''
        check('--grep 命中 + --turns ⇒ 退出码 0', r6.returncode == 0, 'rc=%d' % r6.returncode)
        check('--grep 选中了含关键词的会话', '轮次数 3' in o6)

        r7 = run_env(tmp, '--grep', 'zzz_never_used_zzz', '--turns')
        check('--grep 无命中 ⇒ 退出码 1（不是 0 ✗）', r7.returncode == 1, 'rc=%d' % r7.returncode)
        check('--grep 无命中 ⇒ 明确报"没有会话包含"',
              '没有会话包含' in ((r7.stdout or '') + (r7.stderr or '')))

        r8 = run_env(tmp, '--grep', 'UNIQUEKW_ABC')
        check('--grep 单独用 ⇒ 退出码 2（原为 0 ✗）', r8.returncode == 2, 'rc=%d' % r8.returncode)
        check('--grep 单独用 ⇒ 不产出任何报告（stdout 为空 ✓）',
              not (r8.stdout or '').strip(), repr((r8.stdout or '')[:40]))
        check('--grep 单独用 ⇒ stderr 说明它只是筛选',
              '--grep 只是' in (r8.stderr or ''))

        r9 = run_env(tmp)
        check('无参数 ⇒ 退出码 2（原为 0 ✗）', r9.returncode == 2, 'rc=%d' % r9.returncode)
        check('无参数 ⇒ 帮助走 stderr ✗ 不在 stdout 冒充报告',
              not (r9.stdout or '').strip())
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
