r"""todo_peek 的自测：造假会话日志，验证"取最后一次 / 全部 / 指定轮次 / 没有记录 / 坏路径"。

【为什么必须有】这个工具是**替用户的眼睛**看得东西 ✓ —— 它一旦取错列表 ✗
    （取成上一轮的、漏掉最后一条、把没有记录说成有 ✗）用户就会照着错的计划干活 ✗
    ⇒ 必须用"已知答案"的假日志把每条路径都钉死 ✓

【用法】python test_todo_peek.py      退出码 0=通过 1=失败
"""
from __future__ import annotations

import json
import os
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
ENGINE = HERE / 'todo_peek.py'
FAILS = []


def check(name, cond, detail=''):
    print('  %-6s %-46s %s' % ('OK' if cond else 'FAIL', name, detail))
    if not cond:
        FAILS.append(name)


def ev(seq, t, data):
    return {'seq': seq, 'type': t, 'time': 1_792_000_000_000 + seq * 1000, 'data': data}


def todos(*pairs):
    return [{'content': c, 'status': s} for c, s in pairs]


def write_log(path: Path, rows):
    raw = '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows).encode('utf-8')
    try:
        from compression import zstd
        path.write_bytes(zstd.compress(raw))
    except Exception:                          # noqa: BLE001
        import zstandard as zstd
        path.write_bytes(zstd.ZstdCompressor().compress(raw))


def build_a(path: Path):
    """轮 1：写两次（0/2 → 1/2）；轮 2：没写；轮 3：写一次（2/2）✓"""
    rows = [
        ev(1, 'turn/start', {'turn': 1}),
        ev(2, 'todo/write', {'todos': todos(('甲', 'pending'), ('乙', 'pending'))}),
        ev(3, 'todo/write', {'todos': todos(('甲', 'completed'), ('乙', 'in_progress'))}),
        ev(4, 'turn/end', {'reason': {'kind': 'completed'}}),
        ev(5, 'turn/start', {'turn': 2}),
        ev(6, 'turn/end', {'reason': {'kind': 'completed'}}),
        ev(7, 'turn/start', {'turn': 3}),
        ev(8, 'todo/write', {'todos': todos(('甲', 'completed'), ('乙', 'completed'))}),
        ev(9, 'turn/end', {'reason': {'kind': 'completed'}}),
    ]
    write_log(path, rows)


def build_b(path: Path):
    """只有轮次、没有 todo/write ⇒ 应报"没建过任务列表"✓"""
    write_log(path, [ev(1, 'turn/start', {'turn': 1}), ev(2, 'turn/end', {})])


def run(*args, root=None):
    e = dict(os.environ)
    e.update({'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
    if root:
        e['DSH_SESSIONS_ROOT'] = str(root)
    return subprocess.run([sys.executable, '-X', 'utf8', str(ENGINE), *[str(x) for x in args]],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=e)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='todopeek_'))
    try:
        sa, sb = tmp / 'a', tmp / 'b'
        sa.mkdir()
        sb.mkdir()
        build_a(sa / 'session.v4.jsonl.zstd')
        build_b(sb / 'session.v4.jsonl.zstd')

        r = run('--session', sa / 'session.v4.jsonl.zstd')
        o = r.stdout or ''
        check('默认只打最后一次 ⇒ 退出码 0', r.returncode == 0, 'rc=%d' % r.returncode)
        check('取到的是第 3 轮（最新那次）✓', '第 3 轮' in o and '2/2 已完成' in o)
        check('打了条目内容与勾选状态', '[x] 甲' in o and '[x] 乙' in o)
        check('没有多打历史（第 1 轮不该出现）', '第 1 轮' not in o)

        r2 = run('--session', sa / 'session.v4.jsonl.zstd', '--all')
        o2 = r2.stdout or ''
        check('--all ⇒ 列出 3 次写入', '共 3 次写入' in o2, [l for l in o2.splitlines() if '共' in l][:1])
        check('--all ⇒ 第 1 轮出现两次（写了两次）✓', o2.count('第 1 轮') == 2)
        check('--all ⇒ 进行中那条也打出来', '进行中：乙' in o2)

        r3 = run('--session', sa / 'session.v4.jsonl.zstd', '--turn', 1)
        o3 = r3.stdout or ''
        check('--turn 1 ⇒ 只打该轮最后一次（1/2）✓',
              '第 1 轮' in o3 and '1/2 已完成' in o3 and '第 3 轮' not in o3)

        r4 = run('--session', sa / 'session.v4.jsonl.zstd', '--turn', 1, '--all')
        check('--turn 1 --all ⇒ 该轮两次都打', '下面显示 2 次' in (r4.stdout or ''))

        r5 = run('--session', sa / 'session.v4.jsonl.zstd', '--turn', 2)
        check('--turn 2（该轮没写入）⇒ 退出码 1 ✗', r5.returncode == 1, 'rc=%d' % r5.returncode)
        check('并说明该会话有哪些轮次写过',
              '第 2 轮里没有写入' in ((r5.stdout or '') + (r5.stderr or ''))
              and '1, 3' in (r5.stdout or ''))

        r6 = run('--session', sa / 'session.v4.jsonl.zstd', '--json')
        try:
            j = json.loads(r6.stdout)
            ok = (j['writes_total'] == 3 and j['turns_with_writes'] == [1, 3]
                  and j['shown'][-1]['turn'] == 3 and len(j['shown'][-1]['todos']) == 2)
        except Exception as e:                  # noqa: BLE001
            ok = False
            print('    JSON 解析失败:', e)
        check('--json 结构正确', ok)

        r7 = run('--session', sb / 'session.v4.jsonl.zstd')
        check('没有 todo/write ⇒ 退出码 0（不是错误 ✓）', r7.returncode == 0, 'rc=%d' % r7.returncode)
        check('并明确说"没建过任务列表"', '没有 todo/write 记录' in (r7.stdout or ''))

        r8 = run('--session', tmp / 'nope' / 'session.v4.jsonl.zstd')
        check('会话文件不存在 ⇒ 退出码 1 ✗', r8.returncode == 1, 'rc=%d' % r8.returncode)
        check('并明确报"不存在"', '不存在' in ((r8.stdout or '') + (r8.stderr or '')))

        r9 = run('--session', sa / 'session.v4.jsonl.zstd', '--turn', 0)
        check('--turn 0 非法 ⇒ 退出码 1 ✗', r9.returncode == 1, 'rc=%d' % r9.returncode)

        # 不给 --session：应按 DSH_SESSIONS_ROOT 找**最近修改**的那个 ✓
        os.utime(sb / 'session.v4.jsonl.zstd', None)          # 把 b 摸成最新 ✓
        r10 = run(root=tmp)
        check('默认会话 = 最近修改的那个（b）✓',
              'b' in (r10.stdout or '') and '没有 todo/write 记录' in (r10.stdout or ''),
              (r10.stdout or '').splitlines()[0][-30:] if r10.stdout else '')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print('[FAIL] 自测未通过：%s' % ', '.join(FAILS))
        return 1
    print('[OK] todo-peek 自测通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
