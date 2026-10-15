# dsh/ —— DSH（DeepSeek Harness）专用工具

> ⚠️ **与仓库里通用部分的分工**：
> `../tools/` 只放**通用**、不含平台/项目知识的工具 ✓；
> 本目录放**DSH 专用**工具 ✓（读 DSH 会话日志、按 DSH 事件模型分析）——
> 所以本目录 `dsh/` 专放 DSH 相关的东西 ✓，不混进通用区 ✗

## 工具

| 工具 | 作用 |
|---|---|
| [`session-cost`](tools/session-cost/session_cost.py) | **会话成本分析**：定位会话 → 全会话总览 → 单轮步级时间线 → **把"贵"归因到具体动作**（系统提示重建 / 压缩注入 / 指令更新）+ 成本纪律审计 |

## 快速开始

```bash
cd agent-toolkit/dsh

# 最近一个会话里最贵的 10 轮
python tools/session-cost/session_cost.py --turns

# 某一轮的完整过程 + 归因（步级 token + 上下文注入 + 谁把缓存打废了）
python tools/session-cost/session_cost.py --turn 151

# 成本纪律审计（把"该改的习惯"变成可度量指标）
python tools/session-cost/session_cost.py --audit

# 别的会话 / 指定会话
python tools/session-cost/session_cost.py --list
# ⚠ --grep 是"筛选会话"✓（决定分析哪个会话），**不是**"搜内容"✗ ⇒ 必须再给一个模式 ✓
python tools/session-cost/session_cost.py --grep 关键词 --turns
```

## 规则（给 agent 读）

- [`成本纪律.md`](成本纪律.md) —— **轮次成本纪律**（实测得来，含三条动手前自检）
- [`skills/dsh-turn-cost-zh/SKILL.md`](skills/dsh-turn-cost-zh/SKILL.md) —— 装进 agent 的技能：什么时候该停下来看看成本

```bash
# 把技能装到 DSH 的 skills 目录（其他 agent 用 --skills-dir 的道理同 agent-toolkit）
copy skills\dsh-turn-cost-zh\SKILL.md %USERPROFILE%\.dsh\skills\dsh-turn-cost-zh\SKILL.md
```

## 自检

```bash
python tools/session-cost/test_session_cost.py                    # 造假日志验证解析/归因/审计
python ..\tools\script-hygiene\hygiene_check.py --root .   # 复用通用工具集的卫生检查 ✓
```

## 为什么需要它（真实案例）

第 151 轮（就是"把 agent-tools 做成可发布工具集"那一轮）花了 **1006 万 token**（单轮中位数 2.65M 的 3.8 倍）：
- 两次**前缀缓存整段作废**占了那轮近一半的成本当量 ✗
  - 步 6：**系统提示被重新写入**（7489 字节）← 上一步的 `ops_bash` 改动了工作区文件/AGENTS.md
  - 步 13：**自动检查点注入压缩摘要**（12542 字节）
- 会话整体看：成本当量 **90% 是"缓存读"** ✓ ⇒ 真正的乘法因子是 **步数 × 上下文大小** ✗

⇒ 结论：**能省的不是输出，而是"重读次数"和"重读量"** ✓
