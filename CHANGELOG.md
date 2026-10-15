# 变更记录

## 0.8.0 — 2026-10-16
- 按用户决定，**再收 4 个技能** ✓（全部来自 `~/.dsh/skills/`）
  · 通用区 `skills/`：`plan-first-tooling-zh` ✓ `scope-drift-guard` ✓ `grill-me` ✓
  · DSH 区 `dsh/skills/`：`sandbox-device-access-zh` ✗ ——
    判据是"**正文里有没有平台专有名词**"✓：它有 `DSH_*` 沙箱变量与"DSH 文件策略" ✗；
    而 `grill-me` 正文**没有** ✗（只多一个 frontmatter 字段 `disable-model-invocation` ✓）
- **更正 0.7.0 的结论** ✗：当时说这 4 个"来源查不清" ✗ —— **漏查了
  `~/.dsh/skills/变更说明.md`**（214 行的技能变更日志 ✓）⇒ 其中 3 个其实**是本项目会话的产出** ✓：
  · `plan-first-tooling-zh`（2026-10-12 ✓ **用户明确要求** ✓ 起因：技巧段执行器边写边调出两次事故 ✗）
  · `scope-drift-guard`（2026-10-10 ✓ 起因：全自动作业里加了未声明的**隐式回退** ✗）
  · `sandbox-device-access-zh`（2026-10-12 ✓ **用户要求写进全局 skills** ✓ 起因：采集卡权限事故 ✗）
  · 只有 `grill-me` **来源仍不明** ✗（2026-10-10 基线盘点登记为"已存在"✓ 未改动 ✓）
- 新增 **`docs/技能来源与许可.md`** ✓：11 个技能逐个列 **来源 / 许可 / 依据 / 回退方式** ✓
  （含"`grill-me` 待考"✗ —— 将来若有许可顾虑，删目录即可完全回退 ✓）
- 安装器 `SKILLS` 登记到 **11 个技能** ✓（通用区 8 ✓ / DSH 区 3 ✓）
- 自测：`test_installer.py` 的期望表**自动跟随 `SKILLS`** ✓ ⇒ 这次加 4 个技能**一行测试都不用改** ✓
  （这正是 0.6.2 把它从"手写清单"改成"读 `SKILLS`"的收益 ✓）

## 0.7.0 — 2026-10-16
- **收进 3 个第三方技能（MIT ✓，带署名与许可证原文 ✓）** —— 用户从技能市场装的：
  · `skills/indiv-captain--domain-modeling-zh/`（领域建模 · 术语表 · CONTEXT.md / ADR ✓
    4 文件：SKILL + CONTEXT-FORMAT + ADR-FORMAT + **ATTRIBUTION** ✓）
  · `skills/indiv-captain--handoff-doc-zh/`（会话交接单 ✓ 2 文件 ✓）
  · `skills/indiv-captain--re-pitch-zh/`（没听懂，重讲一遍 ✓ 2 文件 ✓）
  · 来源：`https://github.com/po-et/workbuddy-skills`（作者 Captain v0.1.1 ✓）；
    三者均改编自 `mattpocock/skills`（**MIT · Copyright Matt Pocock** ✓）
  · ⇒ 再分发合规：`ATTRIBUTION.md` 逐字保留 ✓ **必须跟技能一起装** ✗（见下条 ✓）
- **安装器 `SKILLS` 改成"按目录装"** ✗→✓（这次踩到的真缺陷 ✓）：
  · 原来只 `copy2(源, d/'SKILL.md')` ✗ ⇒ 多文件技能的 `ATTRIBUTION.md` / `*-FORMAT.md`
    **一个都不会装** ✗ ⇒ **署名缺失 = 许可问题** ✗（不是小事 ✓）
  · 现在：源是目录 ⇒ **整个目录一起装** ✓（源是单文件 ⇒ 老行为 ✓ 向后兼容 ✓）
  · `test_installer.py` 相应加固 ✓：期望表**从 install.py 自己的 `SKILLS` 读** ✓
    （手写清单已过期过一次 ✗）+ 逐个技能**核对文件齐全** ✓（4/2/2 个 ✓）
- **未收的 4 个**（按用户约定：来源查不清 ⇒ 只留本地 ✗ 不进公开仓库 ✓）：
  `grill-me` / `scope-drift-guard` / `plan-first-tooling-zh` / `sandbox-device-access-zh`
  —— 实测：文件里搜不到任何 `license/许可/MIT/来源/作者/Copyright/http` 线索 ✗，
  插件管理器 git 日志显示当时连 github.com **超时** ✗，磁盘上也无其它副本 ✗
- 自测：工具集 **7 套全绿** ✓；`install --skills` 实装 **7 个技能** ✓（文件齐全 ✓）

## 0.6.2 — 2026-10-16
- `task-list-discipline-zh` 技能加**纪律⑤：状态如实** ✓（**按用户口径** ✓）
  · 用户要求：`in_progress` **要留着** ✓（用它看"正在做哪条"✓）—— 要改的是
    "**做完不及时更新状态**" ✗（我上一条提的"不许留 in_progress"太严 ✗，已按用户改回 ✓）
  · 反例（**实测发生过两次** ✗）：任务做完了仍挂 `in_progress` ⇒ 界面上一直"转" ✗
    ⇒ 用户分不清"还在跑"和"忘了改" ✗
  · 附：界面上那个"转"**只等于列表状态** ✗ **不等于进程在跑** ✗
- 技能「诚实边界」补一条**实测事实** ✓（这次误判的根因 ✗）：
  "正在运行 / 后台任务"入口由 `dsh-client-ui-jobs` 挂在
  `conversation.session.header.actions` ✓，源码里有 `if (visibleCount === 0) return null;` ✗
  ⇒ **本会话没有任何 job 时它整个不渲染** ✗ ⇒ "它不见了"通常只是**没有 job** ✓
  **不是**装插件（`dsh-cost-meter` / `dsh-ops`）把它挤掉了 ✗
- `todo_peek.py` 加**新鲜度** ✓（就是上面那个混淆的机械解法 ✓）：
  · 输出加一行「最后一次写入：<时间>（<距今>）｜仍挂着 N 项进行中 ✗ / 无进行中悬空 ✓」
  · `--json` 加 `last_write_age_s` / `shown_in_progress` / 每项 `age_s` ✓
  · ⚠️ 只**如实显示时间** ✓ **不拍**"多久算过期"的阈值 ✗（那要实测，不能猜 ✗）
  · 自测 18 → **22 项** ✓（含"有悬空要点出来"✗"无悬空要写明"✓"--json 带 age"✓）

## 0.6.1 — 2026-10-16
- **安装器拒绝"自我安装"** ✗（兑现 0.6.0 记的那条待定缺陷 ✓）：
  `--project` 指向**工具集自己**或其**子目录** ⇒ 直接拒绝、**不写任何文件** ✓
  · 退出码 **4**（"非法目标"✓ —— 与 `--check` 的 0/1/2/3 分开，免得混淆 ✗）
  · 拒绝时**明确说清原因与正确用法** ✓：
    装技能用 `--skills`（不带 `--project`）✓；跑工具集自测用
    `tools/selftests/run_all_selftests.py --root .` ✓
  · 起因：0.6.0 里我用 `--project . --skills` 误装，在 `tools/` 下造出 10 个
    **与真源重名**的 untracked 副本 ✗（逐个核验后删除 ✓）⇒ 现在这条路被堵死 ✓
- `install/test_installer.py` 补回归项 ✓：自己/子目录都被拦 ✓、**拒绝时 tools/ 目录内容不变** ✓、
  正确用法出现在提示里 ✓
- 顺手修正同文件里一处**过期断言** ✗：原来只检查 2 个 skill（"两个 skill 都装了"✗），
  现在按 `SKILLS` 登记表**逐个检查** ✓（4 个 ✓）—— 加 skill 时忘了改断言就是"看起来绿了"✗
- 自测：工具集 **7 套全绿** ✓；卫生 16 文件 0 问题 ✓；溯源 0 缺 ✓

## 0.6.0 — 2026-10-16
- 新增 **`dsh/tools/todo-peek/`：从会话日志读任务列表** ✓（`todo_write` 的历次写入 ✓）
  · 起因（用户原话）："经常找不到任务列表 ⇒ 不知道执行到哪 ⇒ 后面走偏 ⇒
    最后连任务列表是什么都不知道了" ✗
  · 实测（读 `app.asar` 的 `dsh-tool-todo` / `dsh-client-ui-tool` + 真实会话日志）：
    界面上**只有一行**折叠的工具行（标题「更新任务清单」，摘要 `x/y 已完成 · <进行中那条>` ✗
    **没有**面板、**没有**命令 ✗）；它折叠在"工作步骤"里 ✗
    （桌面版默认 `transcriptView = standard` ⇒ `stepGrouping: collapsed`）；
    而且 `todos` 投影**在下一轮开始时清空** ✗（只有"当轮"是活的 ✓）
    ⇒ **靠界面就是会丢** ✗ ⇒ 状态是事件溯源的 ✓ 那就直接读日志 ✓
  · 用法：默认打最后一次（= 当前清单）／`--all` 历次／`--turn N` 指定轮次／`--json`；
    `DSH_SESSIONS_ROOT` 可覆盖会话根目录 ✓（自测与多 profile ✓）
  · 只读日志 ✓；退出码明确 ✓（"这个会话没建过列表"算 **0** ✓ —— 那不是错误 ✓；
    坏路径/该轮没写入/参数非法 ⇒ **1** ✗）
  · 自测 `test_todo_peek.py` **18 项** ✓：含"别取成上一轮"✗"没记录要如实说"✗"坏路径要报错"✗
- 新增技能 **`dsh/skills/task-list-discipline-zh/`：任务列表纪律** ✓（已登记进安装器 `SKILLS` ✓）
  · 四条硬纪律：① **开工先贴**列表 ✓ ② **变更就整表更新** ✓ ③ **收尾再贴**最终列表 +
    下一轮第一件事 ✓ ④ **闸门：想做的事不在列表里 ⇒ 停下问** ✗（这条是防走偏的核心 ✓）
  · 附"怎么把列表读出来"（`todo_peek` ✓）与"让它少折叠"（设置 →「工作步骤展示」→
    详细 / 完全展开 ✓ **治标** ✓ 纪律才是治本 ✓）
- `dsh/README.md` 的工具表 / 快速开始 / 自检 补 `todo-peek` 与新技能 ✓；
  `selftests.json` 登记新套件 ✓（工具集自测 **7 套** ✓）
- 自测：工具集 **7 套全绿** ✓；卫生 16 文件 0 问题 ✓（`dsh` 区 4 文件 0 问题 ✓）；溯源 0 缺 ✓
- ⚠️ **待定的自身缺陷** ✗（本次我自己误踩 ✓）：`install.py --project .` 指向**工具集自己**时，
  会把受管副本与配置模板写进 `tools/` ✗
  （我用 `--project . --skills` 造出 10 个 untracked 文件 ✗，已逐条核验后删除 ✓）
  ⇒ **待定：加一道"目标就是工具集自己"的拦截** ✓

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
