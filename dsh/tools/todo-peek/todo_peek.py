r"""从 DSH 会话日志里读「任务列表」（`todo/write` 事件）—— **不依赖界面** ✓

【为什么需要它（实测，2026-10-16）】
    DSH 的任务列表在界面上**只有一处**：对话里一行工具行（标题「更新任务清单」✓，
    摘要 `{done}/{total} 已完成 · <进行中的那条>`）✗ 而且
      · 它折叠在"工作步骤"里 ✗（桌面版默认 `transcriptView = standard` ⇒ 折叠 ✗）
      · **投影在下一轮开始时清空** ✗（只有"当轮"是活的计划 ✓）
    ⇒ 结果就是用户的原话："经常找不到任务列表 ⇒ 不知道执行到哪 ⇒ 后面走偏 ⇒
      最后连任务列表是什么都不知道了" ✗
    ⇒ 那就别靠界面：状态是**事件溯源**的 ✓（`todo/write` 落在会话日志里 ✓）⇒ 直接读日志 ✓

【用法】
    python todo_peek.py                    # 最近一个会话的最后一次写入（= 当前清单）
    python todo_peek.py --all              # 该会话全部历次写入（看计划怎么变的）
    python todo_peek.py --turn 168         # 只看第 168 轮内写入的（配 --all 看该轮全部）
    python todo_peek.py --session <路径>    # 指定会话
    python todo_peek.py --json             # 机器可读

【环境变量】
    DSH_SESSIONS_ROOT   覆盖会话根目录（默认 ~/.dsh/sessions）✓ 自测与多 profile 用

【新鲜度（实测发生过的坑 ✗）】
    输出会带一行「最后一次写入：<时间>（<距今>）｜仍挂着 N 项进行中 ✗ / 无进行中悬空 ✓」✓
    用途：分清界面上的"转"到底是**真的在做** ✓ 还是**做完忘了更新状态** ✗
    ⚠️ 只**如实显示时间** ✓ 不拍任何"多久算过期"的阈值 ✗（那需要实测，不能猜 ✗）

【退出码（脚本可判定 ✓）】
    0  正常（含"这个会话没有 todo/write 记录"✓ —— 那不是错误 ✓）
    1  找不到会话文件 ✗ ／ 指定轮次里没有写入 ✗ ／ 参数非法 ✗

【边界（说清它管不到什么）】
    · 只读日志 ✓ 不改任何东西 ✓
    · 不判断计划好不好 ✗（只把 agent 写进去的东西如实打出来 ✓）
    · DSH **没有**任务列表面板/命令 ✗ —— 本工具补的就是这个缺口 ✓
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:                                   # 输出被重定向/走管道时默认编码可能是 GBK ✗
    import sys as _sys_h               # 打印非 ASCII 会 UnicodeEncodeError ✗ ⇒ 统一兜底 ✓
    for _s_h in (_sys_h.stdout, _sys_h.stderr):   # stdout 与 stderr 都要兜 ✗
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:                      # noqa: BLE001
    pass

# 会话根目录：可用环境变量覆盖 ✓（自测要指向假日志 ✓，多 profile 也用得上 ✓）
SESSIONS_ROOT = Path(os.environ.get('DSH_SESSIONS_ROOT') or (Path.home() / '.dsh' / 'sessions'))

MARK = {'completed': '[x]', 'in_progress': '[~]', 'pending': '[ ]'}
VALID = set(MARK)


def open_log(path: Path):
    try:
        from compression import zstd          # Python 3.14+
        return zstd.open(path, 'rt', encoding='utf-8', errors='replace')
    except Exception:                          # noqa: BLE001
        try:
            import zstandard as zstd           # 后备
            return zstd.ZstdDecompressor().stream_reader(open(path, 'rb'))
        except Exception as e:                 # noqa: BLE001
            raise SystemExit('无法解压（缺 zstd 支持）：%s' % e)


def iter_events(path: Path):
    with open_log(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:                  # noqa: BLE001
                continue


def pick_session(explicit):
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise SystemExit('会话文件不存在：%s' % p)
        return p
    files = sorted(SESSIONS_ROOT.glob('**/session.v4.jsonl.zstd'),
                   key=lambda q: q.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit('找不到会话文件（%s）' % SESSIONS_ROOT)
    return files[0]


def collect(path: Path):
    """⇒ [(轮次, seq, todos, 事件时间), …]，按日志顺序 ✓"""
    turn, out = 0, []
    for ev in iter_events(path):
        t = ev.get('type')
        if t == 'turn/start':
            turn += 1
        elif t == 'todo/write':
            out.append((turn, ev.get('seq'), (ev.get('data') or {}).get('todos') or [],
                        ev.get('time')))
    return out


def when(ts):
    """事件时间 ⇒ (datetime 或 None, 秒 或 None)。毫秒/秒都认 ✓"""
    if not isinstance(ts, (int, float)):
        return None, None
    secs = ts / 1000.0 if ts > 1e11 else float(ts)   # 依据: 机制（毫秒时间戳 > 1e11 ✓ 与 session_cost 同口径 ✓）
    try:
        return datetime.fromtimestamp(secs), secs
    except Exception:                                # noqa: BLE001
        return None, secs


def age_text(seconds):
    """把"距今多久"写成中文 —— **只用来显示** ✓ 不参与任何判断 ✗（所以阈值只是单位换算）"""
    if seconds is None:
        return '时间未知'
    if seconds < 90:              # 依据: 语义（显示单位阈值，不做判断 ✓）
        return '%d 秒前' % max(int(seconds), 0)
    if seconds < 5400:            # 依据: 语义（同上 ✓）
        return '%.0f 分钟前' % (seconds / 60)
    return '%.1f 小时前' % (seconds / 3600)


def counts(todos):
    done = sum(1 for x in todos if x.get('status') == 'completed')
    run = [x.get('content') for x in todos if x.get('status') == 'in_progress']
    return done, run


def render(tn, seq, todos, ts, now):
    done, run = counts(todos)
    dt, secs = when(ts)
    head = '—— 第 %d 轮（seq=%s）｜%d/%d 已完成' % (tn, seq, done, len(todos))
    if dt is not None:
        head += ' ｜ 写入于 %s（%s）' % (dt.strftime('%m-%d %H:%M'), age_text(now - secs))
    if run:
        head += ' ｜ 进行中：' + ' / '.join(str(r) for r in run)
    lines = [head]
    for x in todos:
        st = x.get('status')
        lines.append('   %s %s' % (MARK.get(st, '[?%s]' % st), x.get('content')))
    return '\n'.join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description='看 DSH 会话里的任务列表（todo_write）')
    ap.add_argument('--session', help='会话文件路径（默认取最近修改的）')
    ap.add_argument('--turn', type=int, help='只看该轮次内写入的列表')
    ap.add_argument('--all', action='store_true', help='打印全部历次写入（默认只打最后一次）')
    ap.add_argument('--json', action='store_true', help='机器可读')
    a = ap.parse_args()
    if a.turn is not None and a.turn < 1:
        print('错误：--turn 必须 ≥ 1（轮次从 1 开始）', file=sys.stderr)
        return 1

    path = pick_session(a.session)
    writes = collect(path)
    sel = [w for w in writes if a.turn is None or w[0] == a.turn]
    show = sel if a.all else sel[-1:]
    now = time.time()
    hanging = sum(1 for _tn, _sq, todos, _ts in show
                  for x in todos if x.get('status') == 'in_progress')

    if a.json:
        last = show[-1] if show else None
        _dt, last_secs = when(last[3]) if last else (None, None)
        print(json.dumps({
            'session': str(path),
            'writes_total': len(writes),
            'turns_with_writes': sorted({w[0] for w in writes}),
            'last_write_age_s': (now - last_secs) if last_secs else None,
            'shown_in_progress': hanging,
            'shown': [{'turn': tn, 'seq': seq, 'todos': todos, 'time': ts,
                       'age_s': (now - when(ts)[1]) if when(ts)[1] else None}
                      for tn, seq, todos, ts in show],
        }, ensure_ascii=False, indent=2))
    else:
        print('会话：%s' % path)
        if not writes:
            print('  （这个会话里没有 todo/write 记录 ⇒ 没建过任务列表 ✓）')
            return 0
        if a.turn is not None and not sel:
            print('  第 %d 轮里没有写入 ✗；该会话共 %d 次写入（轮次：%s）'
                  % (a.turn, len(writes), ', '.join(str(x) for x in sorted({w[0] for w in writes}))))
            return 1
        print('  共 %d 次写入 ｜ 下面显示 %d 次%s'
              % (len(writes), len(show), '（全部）' if a.all else '（最后一次 ✓）'))
        for tn, seq, todos, ts in show:
            print()
            print(render(tn, seq, todos, ts, now))
        # 新鲜度：让"还在转"到底是"真在做"还是"忘了改"一眼可分 ✓（不拍阈值 ✗ 只如实显示 ✓）
        if show:
            dt, secs = when(show[-1][3])
            if dt is not None:
                tail = ('｜仍挂着 %d 项进行中 ✗（若已做完 ⇒ 该更新状态了 ✗）' % hanging) if hanging \
                    else '｜无进行中悬空 ✓'
                print('\n  最后一次写入：%s（%s）%s'
                      % (dt.strftime('%Y-%m-%d %H:%M:%S'), age_text(now - secs), tail))

    if a.turn is not None and not sel:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
