# agent-toolkit

> 给 **AI agent** 用的通用工具集：让 agent 别把"拍脑袋的数字"当成依据，也让项目的自检一眼可见。
> 从 GitHub 拉下来一条命令即可装进**你的项目**和**你的 agent**。

- **数值溯源**：搜出项目里所有可调数值，要求每个写明「来历」（实测 / 机制 / 未实测）
- **自检汇总**：一条命令跑完项目全部自检（自动发现套件，不必写死清单）
- **跨 agent 的规则**：一个 skill（`measured-or-flagged-zh`），装进你的 agent 后它会自觉遵守
- **漂移检测**：项目里的工具副本"被改过 / 落后了"都能查出来

许可证：MIT ｜ 版本：见 `VERSION`

---

## 为什么做这个

Agent 写代码时经常会**随手填一个数**（超时 3 秒、阈值 2 像素、重试 5 次）✗，然后把它当依据用。
写的时候它不觉得那是猜，所以这个数**不会出现在任何清单里**，你也无从审查。

真实事故（同一会话内连续六次）：

| 拍的值 | 真相 | 后果 |
|---|---|---|
| 输入延迟 0.5~1.0s | 实测 0.18~0.22s | 按错误前提设计策略 |
| 翻越成功判据 3px | 实测 ≈0.7px | **每次成功翻越都被判失败**，还写负记录 ⇒ 永不翻越 |
| "一个身位 ≈6px" | 那是走路位移，与翻越无关 | 判据取错 |
| 卡死阈值 0.5px | 被挡时 67~82% 的步都 >0.5px | 判据几乎永不触发 |
| 轮询间隔 0.12s | 没有任何依据 | 砍掉 3/4 的时间分辨率 |

⇒ 本工具集把这件事**变成机械检查**：数值没有来历 ⇒ 自检报错 ⇒ 提交被拦 ✗

## 一行安装

```bash
# Linux / macOS / Git-Bash
curl -fsSL https://raw.githubusercontent.com/55200wq/agent-toolkit/main/install/install.sh | bash

# Windows / PowerShell
irm https://raw.githubusercontent.com/55200wq/agent-toolkit/main/install/install.ps1 | iex
```

或者本地克隆：

```bash
git clone https://github.com/55200wq/agent-toolkit.git
python agent-toolkit/install/install.py --all --project /path/to/your/project
```

## 装什么、装到哪

```bash
# 装进你的项目：工具副本 + 配置模板（缺了才写，绝不覆盖）+ 身份证
python install.py --project <项目根> --with-agents --with-hook --with-hook

# 装 skill 给你的 agent（DSH 默认 ~/.dsh/skills；其他 agent 用 --skills-dir 指自己的目录）
python install.py --skills
python install.py --skills --skills-dir ~/.your-agent/skills

# 漂移检查（一致0 被本地改1 落后2 未装3）
python install.py --project <项目根> --check
```

装完在项目里：

```bash
python tools/provenance_check.py --write-assumptions   # 生成"未实测初值"清单
python tools/provenance_check.py --audit               # 看哪些数值还没写来历
python tools/run_all_selftests.py                      # 跑全部自检（自动发现）
```

## 三态：数值必须写明来历

```python
TIMEOUT_S = 3.0        # 依据: 实测（n=30，见 docs/measured.json）
STEP_PX = 8.0          # 依据: 机制（由格粒度决定，无需标定）
WINDOW_S = 45          # 依据: 未实测（初值，见未实测清单）
STATE_OK = 4           # 依据: 语义（状态码，非可调）
```

标注有效范围：**同一行**，或**紧邻上方的整行注释** ✓（上面某个常量的行尾标注不会"罩住"下面 ✗）

规则正文：`docs/数值纪律.md`

## 目录（按功能分）

```
agent-toolkit/
├── skills/      agent 规则（可安装到任意 agent）
├── tools/       可执行工具（每个一目录：引擎 + 自测 + README）
├── templates/   往项目里放的东西（AGENTS 片段 / pre-commit / 配置模板）
├── install/     安装器（install.py + 一行安装脚本）
└── docs/        规则与接入文档
```

| 功能 | 目录 | 说明 |
|---|---|---|
| 数值溯源 | `tools/provenance/` | 引擎 + 配置模板 + 薄封装 + 自测 |
| 自检汇总 | `tools/selftests/` | 自动发现套件 + 自测 |
| 脚本卫生 | `tools/script-hygiene/` | H1 可编译 / H2 路径转义 / H3 输出编码 + 自测（H3 在 Linux 默认关 ✓）|
| agent 规则 | `skills/measured-or-flagged-zh/` | 装进 agent 后它写数值时会有意识标来历 |
| agent 规则 | `skills/script-hygiene-zh/` | 写脚本前：修整类不打补丁 / 校验后写 / 加编码兜底 |
| 项目模板 | `templates/` | AGENTS 片段（标记包裹、幂等）/ git 钩子 / 配置模板 |
| 安装 | `install/` | `--project` / `--skills` / `--all` / `--check` |
| 文档 | `docs/` | 数值纪律 · 接入清单 · 设计方案 |

## 设计约定

| 约定 | 说明 |
|---|---|
| 配置**项目自化** | 引擎不含任何项目知识；扫描面/标签/豁免/清单路径都在项目自己的配置里 |
| 配置**绝不覆盖** | 安装器只在配置缺失时生成 ✓ |
| 项目留**副本 + 身份证** | 项目能被单独拷走；`--check` 能查出漂移 |
| 每个工具**自带自测** | `test_*.py`，只用标准库，造假对象验证行为 |
| **自举** | 工具集自己的代码也要过自己的溯源检查 |
| AGENTS 片段**幂等** | `<!-- agent-tools:begin/end -->` 标记包裹，重复安装不重复追加 |

## 边界（它做不到什么）

| 做不到 | 说明 |
|---|---|
| 判断"值对不对" ✗ | 只保证"有来历或承认没有" |
| 抓回复/文档里的错误断言 ✗ | 那靠 skill 规则 + 人工抽查 |
| 扫函数体内的行内字面量 ✗ | 有意收窄以降低误报（只扫 4 种写法：模块级常量 / `self.x = 数字` / 数值表 / `__init__` 签名默认值）|
| 自动修代码 ✗ | 只报告，决定权在人 |
| 判断脚本逻辑对错 ✗ | 脚本卫生只管 H1/H2/H3 三类反复事故 |

## 新增一个工具

```
1. 建 tools/<名字>/：<名字>.py（引擎）+ test_<名字>.py（自测）+ README.md
2. 引擎里不许出现项目名/路径（项目相关的都进配置）
3. 加进 install/install.py 的 MANIFEST（受管文件或配置模板）
4. 在根目录 selftests.json 登记它的自测
5. 更新 README + CHANGELOG + VERSION
6. 自检：python tools/selftests/run_all_selftests.py --root .
        python tools/provenance/provenance_check.py --root . --audit
```

## 自检（本仓库）

```bash
python tools/selftests/run_all_selftests.py --root .          # 全部自测
python tools/provenance/provenance_check.py --root . --audit  # 本仓库自身溯源
```

## License

MIT（见 `LICENSE`）
