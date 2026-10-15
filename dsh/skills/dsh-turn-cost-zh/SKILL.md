---
name: dsh-turn-cost-zh
description: >-
  DSH（DeepSeek Harness）会话的**轮次成本纪律**：成本当量 90% 来自"缓存读"= 步数 × 上下文大小；
  "改工作区配置类文件（AGENTS.md 等）"会让系统提示重建 ⇒ 等于当前上下文全额重发一次。
  动手前按三条自检：要改工作区配置吗 / 这轮会超过 20 步吗 / 上下文是否已 >50 万。
  触发词：这轮好贵、token 消耗、花费、成本、轮次、上下文太大、压缩、compaction、AGENTS.md 改动、
  系统提示、缓存、cache、便宜点、省 token、dsh 会话分析。
whenToUse: >-
  在 DSH 里做**长任务/大重构**之前，或用户提到"贵/token/成本/轮次"时。
  也适用于：准备改工作区配置类文件（AGENTS.md、.gitattributes、项目根配置）、
  准备一轮里做很多步（> 20 步）、上下文已经很大还想继续硬扛时。
  不适用于：纯问答、几步就能完成的小改动、用户明确说"别管成本，做完就行"。
---

# DSH 轮次成本纪律（dsh-turn-cost-zh）

## 一句话

> **贵不在"说得多"，在"重读得多"** ✓
> 成本当量 ≈ **步数 × 上下文大小 × 缓存命中率**，其中"缓存整段作废"是最贵的单点 ✗

## 事实（实测，2026-10-16，来自真实会话日志）

| 事实 | 数值 |
|---|---|
| 会话成本当量主要来源 | **缓存读 ≈ 90%** ✗（每步都重读一遍上下文）|
| 最贵的一轮 | 轮 26：**131 步** ⇒ 4958 万 token ✗ |
| 输出的影响 | token 0.2% ｜ 成本当量 ≈ 6.5% ⇒ **几乎不是问题** ✓ |
| 缓存 TTL | 实测 **> 48 秒**（48 秒间隔后仍命中 ✓）|
| 单轮中位数 | 265 万 token（这个会话）|

## 三种"前缀作废"（实测归因）

| 触发者 | 日志事件 | 代价 |
|---|---|---|
| **改工作区配置类文件**（`AGENTS.md` / `.gitattributes` / 项目根配置）✗ | `system/message` `source.kind=system-prompt` | **≈ 当前上下文全额重发** ✗✗ |
| 自动检查点（compaction） | 注入压缩摘要 | 一笔全额重发（但顺带把上下文压小 ✓）|
| 工作区指令更新 | `agent-instructions` 注入 | 只重发增量 ✓ 便宜 ✓ |

> 实证（轮 151）：步 6 未缓存 **66.9 万** ← 上一步 `ops_bash` 把 toolkit 装进项目、改了 `AGENTS.md` ✗
> 步 13 未缓存 **18.1 万** ← 检查点注入 ✓
> 这两次占了那轮**近一半**成本当量 ✗

## 动手前的三条自检（可判定 ✓，不是"注意一点" ✗）

```
① 我要改"工作区配置类文件"吗？（AGENTS.md / .gitattributes / 项目根配置）
     会 ⇒ 系统提示会重建 ⇒ 等于当前上下文全额重发一次 ✗
     ⇒ 先跑 session_cost.py --turns 看上下文规模，
       把代价告诉用户："这一步会让上下文 X 全额重发一次" ✓ 由他决定时机 ✓

② 这一轮预计超过 ~20 步吗？
     会 ⇒ 每步重读一遍 ✗ ⇒ 拆成多个小轮次 ✓，或先压缩再干 ✓

③ 上下文已经 > 50 万 token 而任务是大重构吗？
     是 ⇒ 先压缩 ✓ / 拆会话 ✓，别硬扛 ✗
```

## 工具（在 agent-toolkit 仓库的 `dsh/` 下）

仓库：https://github.com/55200wq/agent-toolkit
本地默认：`C:\Users\57226\Desktop\share_data\agent-toolkit`

```powershell
$T = "$env:USERPROFILE\Desktop\share_data\agent-toolkit"   # 或你的克隆位置
python "$T\dsh\tools\session-cost\session_cost.py" --turns        # 最贵的 N 轮
python "$T\dsh\tools\session-cost\session_cost.py" --turn 151     # 单轮步级时间线 + 归因
python "$T\dsh\tools\session-cost\session_cost.py" --audit        # 成本纪律指标（验收用）
```

**验收方式**：看 `--audit` 的 ①作废次数 ②系统提示重建 ③压缩次数 是否下降 ✓
—— 靠数字，不靠自我感觉 ✓

## 诚实边界

- 工具**不算钱** ✗：`--ratio` 默认 `1,0.1,3` 是**假设，未实测**（要精确金额装 `dsh-cost-meter`）
- 归因是**相关性** ✗：把"未缓存激增"与其前最近的注入关联，不做因果证明
- 不同模型/供应商的缓存策略不同 ⇒ 结论只在 DSH + 当前模型上实测过 ✓
