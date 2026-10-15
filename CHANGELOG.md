# 变更记录

## 0.5.0 — 2026-10-16
> 主题：**把上一版只"记录"的三个整类缺陷修掉** ✗（细纲见 0.4.1 末段 ✓）

- **H3 加强：UTF-8 兜底必须覆盖 stdout 与 stderr 两个流** ✗（原来是"有兜底就行"✗）
  实测缺口：只兜 stdout ⇒ **stderr 仍是 GBK** ⇒ 报错信息变乱码、`✓/✗` 退化成转义字面量 ✗
  ⇒ 而报错信息**恰恰都走 stderr** ✗（不兜它等于兜了个寂寞）
  - 判据改成 **AST**（`covered_streams` ✓）而不是字符串匹配 ✗：
    本项目模板的写法是 `import sys as _sys_h` + `for _s_h in (_sys_h.stdout, _sys_h.stderr)`
    ⇒ 任何"认 `sys.stdout.reconfigure` 字样"的口径都认不出它 ✗（实测踩到 ✓）
  - 认三种写法 ✓：`sys.x.reconfigure(...)` / 循环别名 / `io.TextIOWrapper(sys.x.buffer)`
  - 新增配置 `bootstrap_stderr_markers`（给检查器认不出的写法留后门 ✓ 老配置不会静默放行 ✓）
  - **实测抓到的假阴性** ✗：`PYTHONIOENCODING` 出现在文件里**不算数** ✗
    （大量 `test_*.py` 是"给**子进程**设环境变量"✗ ⇒ 管不到自己 ✗ 且运行时设它对已建的流无效 ✗）
- **新增 `tools/script-hygiene/fix_bootstrap.py`：整类升级兜底** ✓
  · 干跑为默认 ✓ / `--apply` 才写 ✓ · 写前 `ast.parse` ✓ 写后 `compile()` 复验 ✓ · BOM 原样保留 ✓
  · 只动"顶层 try + stdout.reconfigure"这一处 ✗（节点 > 12 行就跳过并报"需人工"✓ 不许猜 ✗）
  · 覆盖三种情形：已两流覆盖 ⇒ 跳过 ✓ / 旧兜底 ⇒ 原地替换 ✓ / 没兜底但打印非 ASCII ⇒ 插入 ✓
  · 新增自测 `test_fix_bootstrap.py`（16 项 ✓：改了哪些、没改哪些、改完能不能跑 ✓、端到端只剩余下的 ✗）
  · 已加进安装器 `MANAGED` ✓ ⇒ 项目重装即可获得（`tools/fix_bootstrap.py`）
- **runner 根目录推导修对** ✗（它自己的 5 个套件原来只跑 3 个 ✗）
  · 根因：源码布局是 `tools/selftests/run_all_selftests.py` ⇒ `parent.parent` = `tools/` ✗
    （装进项目才是对的 ✓ —— 所以这个 bug 一直没暴露 ✗）
  · 判据改成"引擎所在目录**叫不叫 `selftests`**"✓（源码 ⇒ 上 3 层 / 装进项目 ⇒ 上 2 层 ✓）
    ⚠️ 特意**不用**"往上找 selftests.json"✗：装进项目时配置就在 `tools/` 里 ⇒ 会把根认成 `tools/` ✗
  · **不再拿 cwd 当配置来源** ✗（原来 cwd 在候选里 ⇒ 换个 cwd 就静默用上别的配置 ✗ 实测只剩 2 套 ✗）
  · 没找到配置 ⇒ **明确告警并列出"已找过哪些路径"** ✗（原来是静默退回内置默认 ✗）
  · 自测补布局回归项 ✓：源码布局 / 装进项目布局 / 没有配置时告警 ✓
- **文档同步**：`templates/AGENTS.snippet.md`、`skills/script-hygiene-zh`、两处 README、
  配置模板与 `dsh/hygiene.json` 全部改成"两个流都要兜"✓ 并给出新片段 ✓
- **落地实测（两个仓库都跑通）**：
  · 工具集：14 个 `.py` 全部升到两流兜底 ✓ 卫生 0 问题 ✓ **6 套自测全绿** ✓（原来只跑到 3 套 ✗）
  · 项目（sift-match）：H3 报红 **152 个** ✗ ⇒ `fix_bootstrap.py --apply` 写入 152 个 ✓
    ⇒ 卫生 171 个文件 0 问题 ✓ 溯源 0 缺 ✓ 自检 **14 通过 / 0 失败 / 3 跳过**（与基线一致 ✓）
    ⇒ 全项目 221 个 `.py` 编译复验 0 失败 ✓

## 0.4.1 — 2026-10-16
- **修 `session_cost.py` 的 `--grep` 静默失败** ✗（由用户选定要修的那一项）
  原行为：`--grep 关键词` 单独用 ⇒ 走到 `print_help()` + `return 0`
  ⇒ **看起来成功，实际一个模式都没执行** ✗（而且为了打印帮助还去扫了几十 MB 日志 ✗）
  现行为：**先判"要做什么"，再去找会话文件** ✓ ⇒ 无模式 ⇒ 退出码 **2** ✗
  且额外提示"`--grep` 只是筛选会话，要配合 `--turns` / `--turn N` / `--audit`" ✓
- 按"修整类"办 ✓（不是只堵 `--grep` 一个洞）：**任何"没执行任何事却返回 0"的路径都改成 2** ✗
  （无参数 / 只给 `--top` / 只给 `--session` 同样明确失败 ✓）；帮助文本改走 **stderr** ✓ 不在 stdout 冒充报告 ✓
- 退出码口径写进 docstring 与 `--help`：`0` 完成 ✓ ｜ `1` 找不到会话 / `--grep` 无命中 ✗ ｜ `2` 用法错误 ✗
- 新增环境变量 `DSH_SESSIONS_ROOT`（覆盖会话根目录 ✓ 自测与多 profile 都用得上 ✓）
- 自测 **14 项 → 22 项** ✓：补 `--grep` 命中 / 无命中 / 单独用 / 无参数 这 4 条退出码路径 ✓
- **顺带实测出更严重的同一类缺陷** ✗（本次只修了本工具自己那处 ✗）：
  UTF-8 兜底片段**只兜 `stdout`** ✗ ⇒ `stderr` 仍是 GBK ⇒ 报错信息变乱码、
  `✓/✗` 退化成 `\u2713`/`\u2717` 字面量 ✗；而报错恰恰都走 stderr ✗（不兜它等于兜了个寂寞）
  ⇒ `session_cost.py` 已改为 **stdout + stderr 都兜** ✓
  ⇒ `templates/AGENTS.snippet.md`、本仓库其余脚本、以及项目里已装的 124 个脚本**仍是只兜 stdout** ✗
  ⇒ H3 的 `bootstrap_markers` 只要求"出现 `reconfigure(encoding`"⇒ **这个缺口检查不出来** ✗（**待定：是否整类修**）
- 修 `dsh/README.md` 一处**死链** ✗：`tools/session-cost/README.md` 并不存在 ⇒ 改指 `session_cost.py` ✓
- **自测收尾时又抓到两个真缺陷** ✗（**本次只记录、未动手** ⇒ 待定是否 0.4.2 一并修 ✗）
  - `tools/selftests/run_all_selftests.py` 的 `DEFAULT_ROOT` 在**源码布局**下少一层 ✗：
    源码里它在 `tools/selftests/` ⇒ `parent.parent` = `tools/` ✗（安装到项目里才是对的 ✓）
    ⇒ 本工具集自己的 5 个套件**只跑到 3 个** ✗ —— `dsh/tools/session-cost/test_session_cost.py`
      与 `install/test_installer.py` **从来没进过套件** ✗（实测：`--list` 只列 3 个 ✓）
    ⇒ 而且配置文件是靠 **cwd** 兜住的 ✗ ⇒ **换个 cwd 就静默退回"内置默认"**
      （发现面完全不同：实测变成 2 套 ✗）⇒ 又一处"看起来跑过了，其实跑的是另一批" ✗
  - UTF-8 兜底只兜 `stdout`（见上一条 ✓）—— 影响面含 `templates/AGENTS.snippet.md`（发给别人的模板 ✗）
- 项目侧实测（未改任何 MANAGED 文件 ✓）：`install.py --project <sift_match> --check`
  ⇒ **落后 1**（`tools/hygiene_check.py` ✗，项目身份证版本还是 0.3.0）
  ⇒ 属**既有漂移** ✗，与本次改动无关 ✓（重跑安装即可 ✓）

## 0.1.0 — 2026-10-16
- 首次整合：把原先散在 skill 与项目里的两份工具集中到本目录
  - `tools/provenance/`：数值溯源自检（引擎 + 配置模板 + 薄封装 + 自测）
  - `tools/selftests/`：自检汇总器（自动发现套件 + 配置模板 + 自测）
  - `install/install_into_project.py`：装进项目 / 漂移检测（一致0 被改1 落后2 未装3）
- 引擎通用化：项目相关信息全部外置为配置（扫描面/标签/豁免/档案路径）
- 自测抓到并修掉两个真 bug：
  - 标签回溯范围过宽（"往上 6 行"⇒ 上面常量的行尾标注会误罩住下面几行）
  - `__init__` 签名带行尾注释时不被识别
- skill 只保留规则与指针（不再存程序副本 ✗→✓）

## 0.1.0（补丁，同日）
- 修：引擎与汇总器找配置时**先看 cwd** ✗ ⇒ 跑自测时会误用工具集自己的配置
  ⇒ 改为**以 --root 的配置优先**，cwd 放最后（自举时抓到）
- 修：工具集自己的测试夹具常量被溯源检查误报 ⇒ 配置里排除 `test_*.py`
- 补：`tools/*/README.md`、`docs/数值纪律.md`、本 CHANGELOG

## 0.2.0 — 2026-10-16
- **定位修正（v2）**：本仓库是**可发布的 Agent 工具集**，含**完整实现**，按功能分子目录
  - `skills/`：agent 规则（可 `--skills` 装到任意 agent 的 skills 目录）
  - `tools/`：可执行工具（provenance / selftests，各自带自测与 README）
  - `templates/`：AGENTS 片段（标记包裹、幂等）/ pre-commit / 配置模板
  - `install/`：`install.py`（--project / --skills / --all / --check）+ `install.sh` / `install.ps1`
  - `docs/`：数值纪律 / 接入清单 / 设计方案
- 新增 **MIT LICENSE**
- 安装器升级：受管文件参与哈希漂移比较；配置"缺了才写、绝不覆盖"；AGENTS 片段幂等替换
- 自举抓到并修掉 4 个 bug：标签回溯过宽、`__init__` 带注释不识别、引擎与汇总器**找配置先看 cwd**

## 0.3.0 — 2026-10-16
- 新增工具 **`tools/script-hygiene/`**：脚本工程卫生检查（引擎 + 自测 + 薄封装）
  - H1 所有 .py 必须能编译（拦"用正则/行号改坏源码"✗）
  - H2 不许把 Windows 反斜杠路径写进字面量（`\t`/`\n`/`\U` 陷阱 ✗）
  - H3 打印非 ASCII 的脚本必须有 UTF-8 输出兜底（重定向/管道不再崩 ✓）
- 新增 skill **`script-hygiene-zh`**（与数值纪律并列，装进 agent 后写脚本前会读到 ✓）
- `templates/AGENTS.snippet.md` 增加「脚本工程纪律」一节 ✓
- 安装器 MANIFEST/SKILLS 登记新工具与配置模板（`templates/hygiene.example.json` ✓）
- **现场修复**（选项 A：一次修完整类 ✓）：
  - 项目里 **124 个脚本**统一补上 UTF-8 输出兜底（111 个 tools/ + 13 个仓库根 ✓）
  - 7 个带 UTF-8 BOM 的文件清掉 BOM ✓；检查器改用 `utf-8-sig` 读取（BOM 是合法源码 ✓）
  - 自测抓到引擎自身 2 个 bug：docstring 里的 `\U` 转义 ✗、H2 误用"解析后的值"判断 ✗

## 0.3.1 — 2026-10-16
- 回答"Linux 下是否有效"并实测确认三规则的平台差异：
  - **H1 平台无关 ✓**（Linux 上价值最大 ✓）
  - **H2 只认盘符路径 ✗** ⇒ Linux 项目几乎不触发（无害但窄 ✓）
  - **H3 默认改为按平台开** ✓：Windows 开 ✓ / POSIX 关 ✓（Linux 默认 UTF-8，全开会误报 ✗）
- 新增 `--rules H1,H3` / `--all-rules`（跨平台核查用 ✓）+ 报告打印平台与启用规则 ✓
- 新增 `.gitattributes`（shell 脚本强制 LF ✓ 防止 Linux 克隆到 CRLF 导致 shebang 失效 ✗）
- `install.sh` / `templates/pre-commit` 补上**执行位**（100755 ✓，Linux 上可直接运行 ✓）
- 文档补「平台差异」与「Linux 上怎么用」两节 ✓

## 0.4.0 — 2026-10-16
- 新增 **`dsh/`：DSH 专用工具区**（原独立的 `share_data/dsh-tools` 并入 ✓）
  - `dsh/tools/session-cost/session_cost.py`：**会话成本分析**（定位会话 → 最贵的 N 轮 →
    单轮步级时间线 → **把"贵"归因到具体事件**：系统提示重建 / 压缩注入 / 指令更新）+ 成本纪律审计
  - `dsh/tools/session-cost/test_session_cost.py`：造假日志自测（14 项 ✓）
  - `dsh/skills/dsh-turn-cost-zh/`：轮次成本纪律技能（已可 `--skills` 安装 ✓）
  - `dsh/成本纪律.md`：实测得来的三条动手前自检 + 验收方式
- README 增加**分区约定**：`tools/` 只放通用工具 ✓；依赖 DSH 的东西一律进 `dsh/` ✓
- 安装器 `SKILLS` 登记 `dsh-turn-cost-zh` ✓；`provenance.json` 扫描面纳入 `dsh/**` ✓
- 修两个真 bug（都是本项目踩过的同一类 ✗）：
  - 引擎读配置不支持 BOM/空文件 ⇒ 现在用 `utf-8-sig` 且**容错跳过**并告警 ✓
  - 一个 0 字节的 `hygiene.json` 让检查器崩 ✗（工具链自己写出来的）⇒ 已删
- 实测发现（会话日志）：成本当量 **90% 是缓存读** = 步数 × 上下文 ✗；
  "改工作区配置类文件（AGENTS.md）"会触发系统提示重建 ⇒ **≈ 当前上下文全额重发** ✗
