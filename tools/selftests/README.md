# selftests —— 自检汇总器

**做什么**：按 glob 自动发现项目里的自检套件，一条命令跑完并汇总；把"这个项目有 N 套自检"
变成一件可见的事（原版把套件名写死 ✗ 换项目就不能用）。

```bash
python run_all_selftests.py --root <项目根>          # 跑全部
python run_all_selftests.py --root <项目根> --fast   # 跳过 slow=true
python run_all_selftests.py --root <项目根> --list   # 看发现哪些
```

发现规则：默认 `**/*_selftest_*.py`；配置 `selftests.json` 可改 discover / exclude / skip / timeout_s，
并给每个套件加 `label` / `slow` / `desc`。

**自测**：`python test_runner.py`
