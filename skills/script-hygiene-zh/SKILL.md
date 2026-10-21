---
name: script-hygiene-zh
description: >-
  Windows/中文环境下写脚本的四条硬纪律（编译/路径/编码/**不许静默吞异常**）：① 所有 .py 必须能编译（不许用正则/行号批量改源码）
  ② 路径不许写反斜杠字面量 ③ 打印非 ASCII 的脚本必须有 UTF-8 输出兜底，且 **stdout 与 stderr 都要**兜。
  核心是"修整类，不是修一个文件"——同一类错误重复出现就是因为逐文件打补丁。
  触发词：写脚本、改脚本、批量替换、sed、patch、正则替换源码、UnicodeEncodeError、
  GBK、编码错误、SyntaxError、\U 转义、路径转义、重定向输出、管道输出、控制台乱码。
whenToUse: >-
  任何"要写/改脚本、批量改源码、跑输出会重定向的命令"的场合。
  尤其在 Windows + 中文环境，或脚本要打印中文/✓✗✅ 之类字符时。
  也适用于：准备用 sed/正则/行号改一堆文件之前（此时应当停下来改用精确编辑 ✓）。
  不适用于：纯问答、只读调研、只改一个字符串常量。
---

# 脚本工程纪律（script-hygiene-zh）

## 一句话

> **同一类错误，修整类；不要一个文件一个文件地打补丁。**
> 四类高频事故：**改坏源码 / 路径转义 / 输出编码 / 静默吞异常** —— 都用机械检查兜住 ✓

## 为什么需要（真实统计，同一会话内）

| 类 | 我犯的次数 | 具体长什么样 |
|---|---|---|
| **A 输出编码** | **5 次** | 脚本打印中文/`✓✗✅`，输出被重定向或走管道时用 GBK ✗ ⇒ `UnicodeEncodeError` ✗ |
| **B 路径转义** | **4 次** | 把 `C:\Users\...` 写进 Python 字面量 ✗ ⇒ `\U` 语法错 / `\t` 静默错路径 ✗ |
| **C 源码手术** | **3 次** | 用正则/行号插删源码 ✗ ⇒ 插进多行 import 里 ✗、误删 `import sys` ✗ ⇒ 文件坏掉 ✗ |
| **D 静默吞异常** | **1 次**（2026-10-22，代价 ~40 分钟） | `except Exception: pass` 把 `NameError` 吞掉 ✗ ⇒ 现象是"切图后下拉不刷新"✗ 重开/重启都无效 ✗ |

**共同点**：每次都是"修一个文件"，而不是"修一整类" ✗ ⇒ 于是同类错误再来一次 ✗
**而且**：当时没有任何检查拦住 ✗（改坏文件后没人报错 ✓）

## 四条规则

### H1 所有 .py 必须能编译

- 改源码**只用两种方式** ✓：精确编辑（唯一匹配的替换）✓，或整文件重写 ✓
- **不许**用正则/行号批量插删源码 ✗
- **写文件前**先 `ast.parse(new_source)` 校验 ✓；写完再 `compile()` 复验 ✓
- 理由：AST 校验只要一次就能拦住全部"插错位置/误删行"✗

### H2 路径不写反斜杠字面量

```python
P = 'C:\temp\x'     # ✗ \t 是制表符、\x 是转义 ⇒ 路径静默错
P = 'C:\Users\x'    # ✗ \U 直接 SyntaxError
P = 'C:/temp/x'     # ✓ 正斜杠（Python 在 Windows 上也认）
P = r'C:\temp\x'    # ✓ raw 字符串
```

*同一类陷阱*：`python - <<'PY'` heredoc 里写字面量补丁也容易踩 ✗ ⇒ 改源码请用编辑工具 ✓

### H3 打印非 ASCII 的脚本必须有 UTF-8 兜底（**stdout 与 stderr 都要** ✗）

任何打印中文/符号的脚本，顶部加（**必须在任何打印之前** ✓，且 `from __future__` 之后 ✓）：

```python
try:
    import sys as _sys_h               # 用唯一别名 + del，避免与文件里的名字冲突 ✓
    for _s_h in (_sys_h.stdout, _sys_h.stderr):   # ✗ 只兜 stdout 是假兜底
        _s_h.reconfigure(encoding='utf-8', errors='replace')
    del _sys_h, _s_h
except Exception:
    pass
```

- **只兜 stdout 是假兜底** ✗（2026-10-16 实测）：`stderr` 仍是 GBK ⇒ **报错信息**变乱码、
  `✓/✗` 退化成转义字面量 ✗ —— 而报错信息恰恰都走 stderr ✗
- 老项目里一堆"只兜 stdout"的旧片段 ⇒ 用整类工具升级 ✓，别手工逐个改 ✗：
  `python tools/fix_bootstrap.py --root .`（干跑）→ `--apply`
  （写前 `ast.parse` ✓ 写后 `compile()` 复验 ✓；形态认不出的会报到"需人工"✓ 不许猜 ✗）
- 子进程也要带环境：`PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` ✓
- 或者干脆**别用装饰符号**（`✓✗✅`）✓ —— 用 `[OK]/[FAIL]` 更省事 ✓

### H4 不许 `except: pass` 静默吞异常（**Python 专用** ✓）

```python
try:
    do_something()
except Exception:
    pass                     # ✗✗ 错误消失，现象变成"什么都没发生"
```

**真实事故（2026-10-22，本机）**
```
mapviewer：切地图后"层级下拉不刷新" ✗
查了 ~40 分钟：重开无效 ✗ 重启无效 ✗ 代码逻辑看着全对 ✓
真凶：那段刷新用了变量 `m`，但 `m = active_entry()` 写在它**下面**
      ⇒ NameError ⇒ 被**自己的** `except Exception: pass` 吞掉 ⇒ 静默失败 ✗✗
```

**规则**
1. `except` 必须**做点什么** ✓：打印 / 记录 / raise / 返回明确错误 ✓
2. 允许的唯一形态：兜底并**必须打印**
   ```python
   except Exception as e:                      # noqa: BLE001
       print('[模块] xxx 失败 ✗ %r' % (e,), flush=True)
   ```
3. 收窄异常类型 ✓（`except (ValueError, KeyError)`），别一律 `Exception` ✗
4. **排查期一律不吞** ✓：宁可崩，也别静默 ✗（崩了有栈 ✓ 静默没有 ✓）

**为什么只针对 Python**：别的语言也有 `catch {}` ✗，但 Python 的 `except: pass`
最短、最容易被顺手写出来 ✓（IDE 补全默认就是这个 ✗）⇒ 风险最高 ✓

## 机械检查（别靠自觉）

```bash
python <agent-toolkit>/tools/script-hygiene/hygiene_check.py --root <项目根>
# H1 编译 / H2 路径转义 / H3 输出编码；有问题=非零退出 ✓
```

- 装进项目后可直接跑 `python tools/hygiene_check.py` ✓
- 口径写 `tools/hygiene.json`（scan / exclude / rules / h3_ignore_files）✓
- 第三方 vendored 代码要排除 ✗（别人的代码不归你管 ✓）

## 自查清单（动手前问三句）

1. 我要改的是**一个文件**还是**一整类**？（后者就写个带校验的迁移脚本 ✓）
2. 我要改的源码，**写之前校验了吗**？（`ast.parse` ✓）
3. 这个脚本打印非 ASCII 吗？**兜底加了吗**？（或子进程带 `PYTHONUTF8=1` ✓）
