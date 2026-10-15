<!-- agent-toolkit:begin（这一段由 agent-toolkit 安装器维护；手工改动会在下次安装时被替换）-->

## 数值纪律（必读）

**每个可调数值必须写「来历」，三态之一** —— 由 `python tools/provenance_check.py` 强制检查：

```python
TIMEOUT_S = 3.0        # 依据: 实测（n=30，见 <项目实测档案>）
STEP_PX = 8.0          # 依据: 机制（由格粒度决定，无需标定）
WINDOW_S = 45          # 依据: 未实测（初值，见未实测清单）
STATE_OK = 4           # 依据: 语义（状态码，非可调）
```

| 形态 | 要求 |
|---|---|
| `依据: 实测 …` | 必须能追到项目的**实测档案**（含样本数 n 与可信度）|
| `依据: 机制 …` | 说明由什么机制决定 |
| `依据: 未实测 …` | 显式承认是初值 ⇒ 自动进**未实测清单** |

- **只写"描述"不算依据** ✗（`TIMEOUT = 3.0  # 位移小于此值判为没动` 会被判失败）
- 标注的有效范围：**同一行**，或**紧邻上方的整行注释**（中间只能空行/注释）✓

**结论性数字**：只有两份权威 —— 项目的**实测档案**与**未实测清单**。
任何当依据用的数字必须能追到其中之一 ✓ 追不到就必须在回复里**当场说明"这是初值"** ✗

**改代码前先写方案**（`docs/方案_*.md`），实现不符预期时**先改方案再改代码** ✗
**收工前必须全绿**：`python tools/run_all_selftests.py`

## 工具从哪来、怎么查漂移

本项目的通用工具来自 **agent-toolkit**（https://github.com/<user>/agent-toolkit）：

```bash
# 查项目副本是否被改过 / 落后（一致0 被改1 落后2 未装3）
python <agent-toolkit>/install/install.py --project . --check
# 更新到最新版
python <agent-toolkit>/install/install.py --project .
```

⚠️ **改这些工具要改工具集里的源** ✗ —— 在项目里直接改会被 `--check` 报"被本地改过" ✓

<!-- agent-toolkit:end -->
