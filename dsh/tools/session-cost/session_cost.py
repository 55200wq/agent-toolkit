r"""DSH 会话成本分析：把"某一轮为什么这么贵"拆到步级，并归因到具体动作。

【背景（真实案例，2026-10-16）】
    第 151 轮花了 1006 万 token（单轮中位数的 3.8 倍）：
      缓存读 9,183,616（91.2%）｜未缓存输入 860,088（8.5%）｜输出 21,997（0.2%）
    两次"前缀缓存整段作废"贡献了近一半账单：
      步 6  in=669,071  ← **系统提示词被重新写入对话**（system/message, source=system-prompt, 7489B）
                         触发者：上一轮的 ops_bash 改动了工作区文件/AGENTS.md
      步 13 in=180,938  ← **自动检查点（compaction）注入了压缩摘要**（12177B）⇒ 对话前缀重写
    结论：**步数是乘法因子**（每步重读一遍上下文），而"前缀作废"是最贵的单点事件。

【这个工具做什么】
    · 定位会话文件（默认取 ~/.dsh/sessions 下**最近修改**的 v4 jsonl.zstd）
    · 全会话总览：各轮 token、最贵的 N 轮、单轮中位数
    · 单轮时间线：每一步的 in/cache_read/out、工具调用与结果大小、**上下文注入**事件
    · 归因：把"未缓存输入激增"和它前面最近的注入事件关联起来（系统提示重建 / 检查点 / 指令更新）
    · 成本纪律审计：把"该改的操作习惯"变成可度量指标（作废次数、注入次数、步数、平均上下文）

【用法】
    python session_cost.py --list                    # 列出所有会话文件
    python session_cost.py --turns                   # 全会话总览 + 最贵的 10 轮
    python session_cost.py --turn 151                # 第 151 轮完整时间线 + 归因
    python session_cost.py --turn 151 --json         # 机器可读
    python session_cost.py --audit                   # 成本纪律审计（全部轮次）
    python session_cost.py --session <文件路径>       # 指定会话
    python session_cost.py --grep 关键词 --turns      # 只在含该关键词的会话里统计
                                                     # ⚠ --grep 是"筛选会话"✓ 不是"搜内容"✗
                                                     #   （它决定"分析哪个会话"，本身不产出报告 ✗
                                                     #     所以必须再给 --turns / --turn N / --audit）

【环境变量】
    DSH_SESSIONS_ROOT   覆盖会话根目录（默认 ~/.dsh/sessions）✓ 自测与多 profile 用

【退出码（脚本可判定 ✓，不会"什么都没做却返回 0" ✗）】
    0  正常完成 ✓
    1  找不到会话文件 ✗ ／ --grep 没有任何会话命中 ✗
    2  用法错误 ✗：没有指定任何模式（没执行任何事）／ 指定的轮次不存在

【依赖】
    Python 3.14+ 自带 compression.zstd ✓；旧版请装 zstandard ✓

【边界（说清它管不到什么）】
    · 只读日志，不修改任何东西 ✓
    · **不算钱**：单价未实测 ⇒ 只给 token 构成与相对占比 ✗（要精确金额用 dsh-cost-meter）
    · 归因是"相关性"：把未缓存激增与其前最近的注入事件关联 ✗，不做因果证明 ✓
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# 输出兜底：stdout **和 stderr 都要** ✓
# （只兜 stdout 时 stderr 仍是 GBK ✗ ⇒ 报错信息变乱码，✗ 还会退化成 \u2717 字面量 ✗
#   而报错信息恰恰都走 stderr ⇒ 不兜它等于兜了个寂寞 ✗）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass

# 会话根目录：可用环境变量覆盖 ✓（自测要指向假日志 ✓，多 profile 也用得上 ✓）
SESSIONS_ROOT = Path(os.environ.get('DSH_SESSIONS_ROOT') or (Path.home() / '.dsh' / 'sessions'))


# ----------------------------------------------------------------- 压缩读取
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


# ----------------------------------------------------------------- 会话定位
def find_sessions():
    return sorted(SESSIONS_ROOT.glob('**/session.v4.jsonl.zstd'),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def pick_session(args) -> Path:
    if args.session:
        p = Path(args.session).expanduser()
        if not p.exists():
            raise SystemExit('会话文件不存在：%s' % p)
        return p
    files = find_sessions()
    if not files:
        raise SystemExit('找不到会话文件（%s）' % SESSIONS_ROOT)
    if args.grep:
        for p in files:
            hit = False
            for ev in iter_events(p):
                if args.grep in json.dumps(ev, ensure_ascii=False):
                    hit = True
                    break
            if hit:
                return p
        raise SystemExit('没有会话包含：%s' % args.grep)
    return files[0]


# ----------------------------------------------------------------- 解析
def usage_of(u: dict):
    return {
        'in': u.get('inputTokens', 0) or 0,
        'cache_read': u.get('cacheReadTokens', 0) or 0,
        'cache_write': u.get('cacheWriteTokens', 0) or 0,
        'out': u.get('outputTokens', 0) or 0,
    }


def result_text_size(d: dict) -> int:
    """工具结果真正进入上下文的字节数（只算文本内容 ✓，不含 envelope）。

    tool/result 的形状：{turn, step, message:{role:'tool', toolCallId, content:[{type:'text',text}]}}
    """
    msg = d.get('message') or {}
    n = 0
    for c in (msg.get('content') or []):
        if isinstance(c, dict):
            n += len(c.get('text') or '')
    return n or len(json.dumps(d, ensure_ascii=False))


def ts(v):
    if isinstance(v, (int, float)):
        v = v / 1000.0 if v > 1e11 else v
        try:
            return datetime.fromtimestamp(v)
        except Exception:                      # noqa: BLE001
            return None
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except Exception:                          # noqa: BLE001
        return None


def parse(path: Path):
    """返回 turns: {n: {...}} 与 ordering。"""
    turns = defaultdict(lambda: {
        'steps': 0, 'usage': [], 'tools': Counter(), 'results': [],
        'injections': [], 'compactions': 0, 'start': None, 'end': None,
        'first_seq': None, 'last_seq': None, 'user_bytes': 0,
    })
    turn = 0
    cur_step = 0
    pending = {}
    for ev in iter_events(path):
        t = ev.get('type')
        d = ev.get('data') or {}
        if t == 'turn/start':
            turn += 1
            turns[turn]['start'] = ts(ev.get('time'))
            turns[turn]['first_seq'] = ev.get('seq')
            cur_step = 0
            continue
        if turn == 0:
            continue
        T = turns[turn]
        if t == 'turn/end':
            T['end'] = ts(ev.get('time'))
            T['last_seq'] = ev.get('seq')
            T['reason'] = (d.get('reason') or {}).get('kind')
        elif t == 'step/start':
            cur_step = d.get('step') or (cur_step + 1)
        elif t == 'assistant/message':
            u = d.get('usage') or {}
            u = dict(u)
            u['_step'] = d.get('step') or cur_step
            T['usage'].append(u)
            T['steps'] += 1
        elif t == 'tool/call':
            nm = d.get('name') or '?'
            T['tools'][nm] += 1
            pending[d.get('id') or d.get('callId')] = nm
        elif t == 'tool/result':
            # 工具名要通过 toolCallId 反查（result 自己不写 name ✗）
            cid = (d.get('message') or {}).get('toolCallId') or d.get('callId')
            T['results'].append((result_text_size(d),
                                 pending.get(cid) or d.get('name') or '?',
                                 d.get('step') or cur_step))
        elif t == 'user/message':
            kind = (d.get('source') or {}).get('kind')
            T['user_bytes'] += len(json.dumps(d, ensure_ascii=False))
            if kind != 'user':
                T['injections'].append({'kind': kind, 'step': cur_step,
                                        'bytes': len(json.dumps(d, ensure_ascii=False)),
                                        'time': ev.get('time')})
        elif t in ('agent/inbox/spliced', 'system/message'):
            body = json.dumps(d, ensure_ascii=False)
            src = (d.get('message') or {}).get('source') or {}
            T['injections'].append({
                'kind': ('system-prompt' if src.get('kind') == 'system-prompt'
                         else ('inbox-' + str(d.get('target') or 'splice'))),
                'step': cur_step, 'bytes': len(body), 'time': ev.get('time')})
        elif t.startswith('compaction/'):
            if t == 'compaction/end':
                T['compactions'] += 1
    return turns


def turn_total(T):
    agg = Counter()
    for u in T['usage']:
        for k, v in usage_of(u).items():
            agg[k] += v
    return agg


# ----------------------------------------------------------------- 报告
def cmd_list():
    files = find_sessions()
    print('会话文件（按修改时间倒序）：')
    for p in files:
        import time
        st = p.stat()
        print('  %s  %10.1f MB  %s' % (time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime)),
                                       st.st_size / 1e6, p))
    return 0


def cmd_turns(path: Path, top: int = 10):
    turns = parse(path)
    rows = []
    tot = Counter()
    for n in sorted(turns):
        a = turn_total(turns[n])
        s = a['in'] + a['cache_read'] + a['cache_write'] + a['out']
        rows.append((n, s, turns[n]['steps'], sum(turns[n]['tools'].values()), a,
                     turns[n]['compactions']))
        tot.update(a)
    rows.sort(key=lambda r: -r[1])
    print('会话：%s' % path)
    print('轮次数 %d ｜ 总 token: 未缓存输入 %s ｜ 缓存读 %s ｜ 输出 %s'
          % (len(turns), f"{tot['in']:,}", f"{tot['cache_read']:,}", f"{tot['out']:,}"))
    if rows:
        med = sorted(r[1] for r in rows)[len(rows) // 2]
        print('单轮中位数 %s' % f'{med:,}')
        print('\n最贵的 %d 轮：' % min(top, len(rows)))
        print('  轮次   合计        未缓存输入   缓存读       输出      步  工具  压缩')
        for n, s, steps, ntool, a, ncomp in rows[:top]:
            print('  %-5d %10s  %10s  %10s  %8s  %3d  %4d  %4d'
                  % (n, f'{s:,}', f"{a['in']:,}", f"{a['cache_read']:,}", f"{a['out']:,}",
                     steps, ntool, ncomp))
    return 0


def cmd_turn(path: Path, target: int, as_json: bool = False):
    turns = parse(path)
    if target not in turns:
        print('没有第 %d 轮（共 %d 轮）' % (target, len(turns)))
        return 2
    T = turns[target]
    a = turn_total(T)
    total = a['in'] + a['cache_read'] + a['cache_write'] + a['out']
    dur = (T['end'] - T['start']).total_seconds() if (T['start'] and T['end']) else None

    # 归因：未缓存输入 > 5000 的步 ⇒ 看它前面最近的注入
    blame = []
    inj_sorted = sorted(T['injections'], key=lambda x: (x['step'], str(x['time'])))
    for u in T['usage']:
        x = usage_of(u)
        step = u.get('_step')
        if x['in'] <= 5000:
            continue
        prior = [i for i in inj_sorted if (i['step'] or 0) <= (step or 0)]
        near = prior[-1] if prior else None
        same_step = [i for i in inj_sorted if (i['step'] or 0) == (step or 0)]
        blame.append({'step': step, 'in': x['in'], 'by': (same_step or ([near] if near else []))})

    if as_json:
        print(json.dumps({'session': str(path), 'turn': target, 'steps': T['steps'],
                          'usage': dict(a), 'total': total, 'seconds': dur,
                          'tools': dict(T['tools']), 'blame': blame,
                          'injections': inj_sorted}, ensure_ascii=False, indent=1))
        return 0

    print('=== 会话 %s' % path)
    print('=== 第 %d 轮 ===' % target)
    print('步数 %d ｜ 工具调用 %d ｜ 压缩 %d 次 ｜ 用时 %s'
          % (T['steps'], sum(T['tools'].values()), T['compactions'],
             ('%.1f 秒' % dur) if dur else '?'))
    print('token 合计 %s = 未缓存输入 %s + 缓存读 %s + 输出 %s'
          % (f'{total:,}', f"{a['in']:,}", f"{a['cache_read']:,}", f"{a['out']:,}"))
    print('\n工具：' + ' ｜ '.join('%s×%d' % (k, v) for k, v in T['tools'].most_common()))

    if T['injections']:
        print('\n上下文注入（每次注入都可能让前缀缓存作废 ✗）：')
        for i in T['injections']:
            print('  步%-3s %-18s %6d 字节' % (i['step'], i['kind'], i['bytes']))

    big = [r for r in T['results'] if r[0] > 3000]
    if big:
        print('\n较大的工具结果（会一直占着上下文 ✗）：')
        for size, nm, st in sorted(big, reverse=True)[:8]:
            print('  步%-4s %-16s %7d 字节' % (st, nm, size))

    print('\n每步 token：')
    for u in T['usage']:
        x = usage_of(u)
        flag = ' ⚠ 未缓存激增' if x['in'] > 5000 else ''
        print('  步%-4s in %8s  cache_r %9s  out %6s%s'
              % (u.get('_step'), f"{x['in']:,}", f"{x['cache_read']:,}", f"{x['out']:,}", flag))

    if blame:
        print('\n归因（未缓存激增 ← 之前的注入）✗：')
        for b in blame:
            who = b['by'][-1] if b['by'] else None
            print('  步%-4s 未缓存 %9s  ← %s（%s 字节）'
                  % (b['step'], f"{b['in']:,}",
                     who['kind'] if who else '（无可见注入；可能工作区/运行时上下文变化）',
                     who['bytes'] if who else 0))
    return 0


def cmd_audit(path: Path, top: int = 10, ratio: str = '1,0.1,3'):
    """成本纪律审计：把"该改的习惯"变成可度量指标。

    成本当量 = 未缓存输入×r1 + 缓存读×r2 + 输出×r3
    ⚠️ r2/r3 是**假设的比例，未实测** ✗ —— 只为看"谁占大头"的相对关系 ✓
       （要精确金额请用 dsh-cost-meter 插件；可用 --ratio 改成你自己的比例）
    """
    try:
        r1, r2, r3 = (float(x) for x in ratio.split(','))
    except Exception:                          # noqa: BLE001
        r1, r2, r3 = 1.0, 0.1, 3.0
    turns = parse(path)
    rows, tot = [], Counter()
    bad_inj, sys_prompt, chk = 0, 0, 0
    for n in sorted(turns):
        T = turns[n]
        a = turn_total(T)
        s = a['in'] + a['cache_read'] + a['cache_write'] + a['out']
        rows.append((n, s, a, T))
        tot.update(a)
        for i in T['injections']:
            if i['kind'] == 'system-prompt':
                sys_prompt += 1
            if 'compact' in str(i['kind']) or 'checkpoint' in str(i['kind']):
                chk += 1
        bad_inj += sum(1 for u in T['usage'] if usage_of(u)['in'] > 5000)

    med = sorted(r[1] for r in rows)[len(rows) // 2] if rows else 0
    tot_tok = sum(r[1] for r in rows) or 1
    eq = tot['in'] * r1 + tot['cache_read'] * r2 + tot['out'] * r3
    eq = eq or 1
    print('=== 成本纪律审计：%s ===' % path)
    print('轮次 %d ｜ 总 token %s ｜ 单轮中位数 %s'
          % (len(rows), f'{tot_tok:,}', f'{med:,}'))
    print('成本当量（比例 %s ⚠️假设未实测）：%.2f 单位' % (ratio, eq))
    print()
    print('指标（括号里是"越小越好"的期望）：')
    print('  ① 前缀作废次数（未缓存输入 > 5k 的步）：%d 次' % bad_inj)
    print('  ② 其中系统提示重建：%d 次 ✗（每次≈当前上下文全额重发）' % sys_prompt)
    print('  ③ 压缩检查点注入：%d 次（每次一笔全额重发）' % chk)
    print('  ④ token 占比 —— 缓存读 %.1f%% ｜ 未缓存输入 %.1f%% ｜ 输出 %.1f%%'
          % (100.0 * tot['cache_read'] / tot_tok, 100.0 * tot['in'] / tot_tok,
             100.0 * tot['out'] / tot_tok))
    print('  ⑤ 成本当量占比 —— 缓存读 %.1f%% ｜ 未缓存输入 %.1f%% ｜ 输出 %.1f%%'
          % (100.0 * tot['cache_read'] * r2 / eq, 100.0 * tot['in'] * r1 / eq,
             100.0 * tot['out'] * r3 / eq))
    print('     ⇒ 注意 ④ 与 ⑤ 的差别：未缓存输入只占 %.1f%% 的 token，却占 %.1f%% 的成本当量 ✗'
          % (100.0 * tot['in'] / tot_tok, 100.0 * tot['in'] * r1 / eq))
    print()
    print('单轮步数最多的 %d 轮（步数=重读次数 ⇒ 乘法因子 ✗）：' % min(top, len(rows)))
    for n, s, a, T in sorted(rows, key=lambda r: -r[3]['steps'])[:top]:
        spikes = sum(1 for u in T['usage'] if usage_of(u)['in'] > 5000)
        print('  轮%-5d 步%3d  作废%2d  合计 %12s' % (n, T['steps'], spikes, f'{s:,}'))
    print()
    print('行动清单：')
    print('  · 作废次数 > 0 的轮次：检查"改工作区配置类文件（AGENTS.md 等）"是否发生在同一轮 ✗')
    print('  · 步数明显偏大的轮次：考虑拆成多个小轮次 ✓（每步都要重读一遍上下文）')
    print('  · 上下文长期很大：优先压缩，而不是继续硬扛 ✓')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='DSH 会话成本分析（步级 + 归因）')
    ap.add_argument('--session', help='会话文件路径（默认取最近修改的）')
    ap.add_argument('--grep', help='只在包含该关键词的会话里分析（会话筛选 ✓ 需配合 '
                                   '--turns / --turn / --audit ✓ 单独用会报用法错误 ✗）')
    ap.add_argument('--list', action='store_true', help='列出会话文件')
    ap.add_argument('--turns', action='store_true', help='全会话总览 + 最贵的 N 轮')
    ap.add_argument('--turn', type=int, help='分析指定轮次')
    ap.add_argument('--audit', action='store_true', help='成本纪律审计')
    ap.add_argument('--top', type=int, default=10, help='排行条数（默认 10）')
    ap.add_argument('--ratio', default='1,0.1,3',
                    help='成本当量比例 未缓存,缓存读,输出（默认 1,0.1,3 ⚠️假设未实测）')
    ap.add_argument('--json', action='store_true', help='机器可读输出')
    a = ap.parse_args()

    if a.list:
        return cmd_list()

    # 先判"要做什么"，再去找会话文件 ✓
    # 反过来会为了打印帮助去扫几十 MB 日志 ✗；而"什么都没做却返回 0"就是静默失败 ✗
    # （原缺陷：--grep X 单独用时走到 print_help() + return 0 ⇒ 看起来成功，实际没搜也没算 ✗）
    if not (a.turns or a.turn is not None or a.audit):
        print('错误：没有指定要做什么（未执行任何模式）', file=sys.stderr)
        if a.grep:
            print('提示：--grep 只是"筛选会话"（决定分析哪个会话）✗，'
                  '要配合 --turns / --turn N / --audit 才产出报告 ✓', file=sys.stderr)
        ap.print_help(sys.stderr)
        return 2

    path = pick_session(a)
    if a.turns:
        return cmd_turns(path, a.top)
    if a.turn is not None:
        return cmd_turn(path, a.turn, a.json)
    return cmd_audit(path, a.top, a.ratio)


if __name__ == '__main__':
    sys.exit(main())
