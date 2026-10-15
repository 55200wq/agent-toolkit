# agent-tools —— 给 AI 会话用的通用工具集

> 这里放**与具体项目无关**的工具与规则 ✓ 项目只带走"配置 + 一份带身份证的引擎副本" ✓
> **以后新增工具，都登记到本页** ✗→✓

## 目录

```
agent-tools/
├── VERSION                     版本号
├── CHANGELOG.md                变更记录
├── README.md                   ← 你在这里（工具索引）
├── provenance.json             本工具集自己的溯源口径（自举用）
├── selftests.json              本工具集自己的自测清单
├── tools/
│   ├── provenance/             数值溯源：搜出可调数值，要求写明「来历」
│   │   ├── provenance_check.py      引擎（配置驱动，无项目知识）
│   │   ├── provenance.example.json  配置模板
│   │   ├── _selftest_provenance.py  薄封装（装进项目后保持套件命名）
│   │   ├── test_provenance.py       自带自测（造假项目验证行为）
│   │   └── README.md
│   └── selftests/              自检汇总：一条命令跑项目全部自检
│       ├── run_all_selftests.py
│       ├── selftests.example.json
│       ├── test_runner.py
│       └── README.md
├── install/
│   └── install_into_project.py 装进项目 / 检查项目副本是否漂移
└── docs/
    ├── 数值纪律.md             规则全文（三态、边界、为什么）
    ├── 接入清单.md             三步接入 + pre-commit + AGENTS 片段
    └── 方案_目录整合.md        本工具集的由来与设计取舍
```

## 快速开始（装进任意项目，约 2 分钟）

```bash
# 看会装哪些文件
python agent-tools/install/install_into_project.py --list

# 装进项目（**缺配置才写，绝不覆盖已有配置** ✓）
python agent-tools/install/install_into_project.py --project <项目根>

# 检查项目里的副本：一致0 / 被本地改过1 / 落后2 / 未装3
python agent-tools/install/install_into_project.py --project <项目根> --check
```

装完在项目里：

```bash
python tools/provenance_check.py --write-assumptions   # 生成"未实测初值"清单
python tools/provenance_check.py --audit               # 看哪些数值没写来历
python tools/run_all_selftests.py                      # 跑全部自检（自动发现）
```

## 设计约定（改工具前先读）

| 约定 | 说明 |
|---|---|
| **唯一来源在这里** ✓ | skill 里只放规则、不放程序；项目里放副本 + 身份证 |
| **引擎不含项目知识** ✓ | 项目相关的一切（扫描面/标签/豁免/档案路径）都进项目自己的配置 |
| **配置绝不覆盖** ✓ | 安装器只在配置缺失时生成 |
| **项目自带副本 + `.agent-tools.json`** ✓ | 项目能单独拷走；`--check` 能查出"被改过 / 落后" |
| **每个工具自带自测** ✓ | `test_*.py`，只依赖标准库，造假对象验证行为 |
| **自举** ✓ | 本工具集自己的代码也要过自己的溯源检查 |

## 怎么新增一个工具（流程）

```
1. 建 tools/<名字>/ 目录：<名字>.py（引擎）+ <名字>.example.json（模板）
                          + test_<名字>.py（自测）+ README.md
2. 引擎里**不许出现具体项目名/路径** ✗（项目相关的都进配置 ✓）
3. 把新条目加进 install/install_into_project.py 的 MANIFEST
4. 在 selftests.json 里登记它的自测（label/desc）
5. 更新本 README 的目录与索引 + CHANGELOG.md + VERSION
6. 自检：python tools/provenance/provenance_check.py --root . --audit
        python tools/selftests/run_all_selftests.py --root .
```

## 自检

```bash
python tools/selftests/run_all_selftests.py --root .        # 跑本工具集全部自测
python tools/provenance/provenance_check.py --root . --audit # 本工具集自身的溯源检查
```

## 边界（这些工具做不到什么）

| 做不到 | 说明 |
|---|---|
| 判断"值对不对" ✗ | 只保证"有来历或承认没有" |
| 抓回复/文档里的错误断言 ✗ | 那靠规则与人工抽查（见 `docs/数值纪律.md`）|
| 扫函数体内的行内字面量 ✗ | 有意收窄以降低误报 |
| 自动修代码 ✗ | 只报告，决定权在人 |
