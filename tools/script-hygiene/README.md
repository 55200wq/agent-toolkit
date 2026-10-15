# script-hygiene —— 脚本工程卫生检查

**做什么**：一次拦住三类**反复出现**的工程事故 ✓（不是逐个文件打补丁 ✗）

| 规则 | 检查什么 | 对应事故 |
|---|---|---|
| **H1** | 所有扫描到的 `.py` 必须能编译 | 用正则/行号批量改源码 ⇒ 改坏文件 ✗ 而且没人拦住 ✗ |
| **H2** | 不许把 Windows 反斜杠路径写进字符串字面量 | `'C:\temp\x'` 里 `\t` 是制表符 ✗ 静默错路径；`\U` 直接语法错 ✗ |
| **H3** | 打印非 ASCII 的脚本必须有 UTF-8 输出兜底，且 **stdout 与 stderr 都要** ✗ | 输出被重定向/走管道时用 GBK ✗ ⇒ `UnicodeEncodeError` ✗；**只兜 stdout** ⇒ 报错信息仍乱码 ✗（报错都走 stderr ✗）|

**Why**：同一会话里这三类分别犯了 **5 / 4 / 3 次** ✗，根因是"一类错只修一个文件"✗
⇒ 现在改成机械检查，整类一次管住 ✓ 规则正文见 `../../skills/script-hygiene-zh/SKILL.md`

> ⚠️ **H3 的"两半"是 2026-10-16 补上的** ✗：原来的口径只要求"**有**兜底"✗
> ⇒ 满项目都是"只兜 stdout"的假兜底 ✗ ⇒ 报错信息（走 stderr）照样乱码 ✗
> 判据用 **AST**（认 `import sys as _sys_h` + 循环别名、`io.TextIOWrapper` ✓），不是字符串匹配 ✓
> 存量项目用 [`fix_bootstrap.py`](fix_bootstrap.py) 一次改完 ✓（别手工逐个改 ✗）

## 用法

```bash
python hygiene_check.py --root <项目根>                 # 检查（有问题=非零退出）
python hygiene_check.py --root <项目根> --list          # 看扫描面与启用的规则
python hygiene_check.py --root <项目根> --fix-note      # 打印修复指引
python hygiene_check.py --root <项目根> --all-rules     # 三条全开（跨平台核查）
python hygiene_check.py --root <项目根> --rules H1,H3   # 只开指定规则

# 整类升级兜底（把"只兜 stdout"的旧片段一次换成两个流 ✓）
python fix_bootstrap.py --root <项目根>                 # 干跑（默认不写 ✓）
python fix_bootstrap.py --root <项目根> --apply          # 真写（写前 ast 校验 ✓ 写后 compile 复验 ✓）
```

配置：拷 `../../templates/hygiene.example.json` 成项目的 `hygiene.json`（放项目根或 `tools/` 均可 ✓）

## 平台差异（实测确认 ✓）

| 规则 | Windows | Linux / macOS | 说明 |
|---|---|---|---|
| **H1** 编译 | 开 ✓ | 开 ✓ | 纯 AST，平台无关 ✓ —— **这条在 Linux 上价值最大** ✓ |
| **H2** 路径转义 | 开 ✓ | 开 ✓（但很少触发 ✗） | 只认"盘符路径"（`C:\...`）⇒ Linux 项目基本不命中 ✓ 无害但很窄 ✗ |
| **H3** 输出编码 | **开** ✓ | **默认关** ✓ | Windows 重定向/管道默认 GBK ✗ 是真问题 ✓；Linux 默认 UTF-8 ✓（PEP 538/540 连 C locale 也会 coerce）⇒ 全开就是误报 ✗ |

- 默认值随平台走：引擎里 `'H3': _IS_WINDOWS` ✓
- 报告会打印当前平台与启用规则 ✓：

```
脚本卫生检查：扫描 10 个文件 ｜ 平台=windows ｜ 启用的规则=H1,H2,H3 ｜ 配置：默认
```

> ⚠️ 若项目配置里**显式**写了 `"H3": true` ✗，那在 Linux 上也会开 ✓（各项目自己决定 ✓）

## Linux 上怎么用

```bash
git clone https://github.com/55200wq/agent-toolkit.git
cd agent-toolkit
python3 tools/selftests/run_all_selftests.py --root .      # 6 套自测（含本工具）
python3 tools/script-hygiene/hygiene_check.py --root .     # 默认 H1+H2
python3 install/install.py --project /path/to/project --with-agents --with-hook
```

三个引擎（`hygiene_check` / `provenance_check` / `run_all_selftests`）都自带
UTF-8 兜底（**stdout 与 stderr 都兜** ✓）⇒ 在 `LANG=C` 之类环境下打印中文/报错都不会崩 ✓
（shell 脚本在 git 里是 LF 且有执行位 ✓ 可直接 `./install/install.sh` ✓）

## 边界（它管不到什么）

| 管不到 | 说明 |
|---|---|
| H1：语法以外的问题 | 只保证"能编译"✓；逻辑对错不看 ✗ |
| H2：非盘符形式 | 只查"盘符路径"✗；`'\d'`/`'\s'` 这类正则转义不查 ✓ |
| H3：logging / sys.stdout.write | 只看 `print(...)`（含 f-string 与关键字参数 ✓）|
| H3：认不出的兜底写法 | AST 认三种（`reconfigure` / 循环别名 / `TextIOWrapper`）✗；更冷门的写法请用配置 `bootstrap_stderr_markers` 或 `h3_ignore_files` ✓ |
| H3：文件里写 `PYTHONIOENCODING` | **不算数** ✗（那是给子进程设的，管不到自己 ✗；只有外部启动环境里设好才算 ✓）|
| 自动修复 | 检查器只报告 ✓；兜底可用 `fix_bootstrap.py` 自动升级 ✓（它自己先 `ast.parse` 再写、写完 `compile()` 复验 ✓；形态认不出的会报"需人工"✓ 不许猜 ✗）|

## 自测

```bash
python test_hygiene.py         # 造假文件验证 H1/H2/H3 报红与放行（含"只兜 stdout"回归项 ✓）
python test_fix_bootstrap.py   # 造假项目验证替换/插入/不猜怪形态（16 项 ✓）
```
