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

本项目的通用工具来自 **agent-toolkit**（https://github.com/55200wq/agent-toolkit）：

```bash
# 查项目副本是否被改过 / 落后（一致0 被改1 落后2 未装3）
python <agent-toolkit>/install/install.py --project . --check
# 更新到最新版
python <agent-toolkit>/install/install.py --project .
```

⚠️ **改这些工具要改工具集里的源** ✗ —— 在项目里直接改会被 `--check` 报"被本地改过" ✓

## 脚本工程纪律（Windows / 中文环境）

**三类事故会反复发生** ✗，由 `python tools/hygiene_check.py` 强制检查（H1/H2/H3）：

| 规则 | 要求 | 事故长什么样 |
|---|---|---|
| **H1** | 所有 `.py` 必须能编译 | 用正则/行号批量改源码 ⇒ 改坏文件 ✗ 而且没有任何检查拦住 ✗ |
| **H2** | 路径不写反斜杠字面量 | `'C:\temp\x'` 里 `\t` 是制表符 ✗ 静默错路径；`\U` 直接语法错 ✗ |
| **H3** | 打印非 ASCII 的脚本必须有 UTF-8 兜底，**stdout 与 stderr 都要** ✗（只兜 stdout 是**假兜底** ✗；**Linux 默认关闭** ✓ 那边默认就是 UTF-8）| 输出被重定向/走管道时用 GBK ✗ ⇒ `UnicodeEncodeError`；只兜 stdout ⇒ **报错信息仍乱码 / ✓✗ 变转义字面量** ✗ |

```python
# H1：改源码只用精确编辑或整文件重写 ✗ 不要用正则/行号；写文件前 ast.parse 校验 ✓
# H2：路径写正斜杠 C:/x/y ✓ 或 raw 字符串 r'C:\x\y' ✓
# H3：文件顶部加兜底（必须在任何打印之前执行 ✓；**两个流都要** ✗）
try:
    import sys as _sys_h
    for _s_h in (_sys_h.stdout, _sys_h.stderr):
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:
    pass
```

```
检查：python tools/hygiene_check.py          # 全项目
      python tools/hygiene_check.py --list   # 看扫描面与口径
整类升级兜底（把"只兜 stdout"的旧片段一次改完 ✓）：
      python tools/fix_bootstrap.py --root .            # 干跑（默认不写 ✓）
      python tools/fix_bootstrap.py --root . --apply     # 真写（写前 ast 校验 ✓ 写后 compile 复验 ✓）
口径：tools/hygiene.json（scan / exclude / rules）
```

⚠️ **要修"整类"，不是修一个文件** ✗ —— 这三类在同一项目里分别犯过 5 次 / 4 次 / 3 次，
正是因为"一次只修一个文件"才反复出现 ✓

<!-- agent-toolkit:end -->
