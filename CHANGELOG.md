# 变更记录

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
