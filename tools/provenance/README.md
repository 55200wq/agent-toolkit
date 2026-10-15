# provenance —— 数值溯源自检

**做什么**：搜出项目里的可调数值（模块级常量 / `self.x = 数字` / 数值表 / `__init__` 签名默认值），
要求每个都写明「来历」（三态：实测 / 机制 / 未实测）；没写就报错，写了"未实测"就收进清单。

**规则正文**：`../../docs/数值纪律.md`

```bash
python provenance_check.py --root <项目根> --audit               # 列出没写来历的
python provenance_check.py --root <项目根> --write-assumptions    # 生成未实测清单
```

配置：`provenance.example.json`（拷成项目根的 `provenance.json` 再改）

**不做**：不查值对错 ✗；不扫函数体内的行内字面量 ✗；抓不到回复里的错误断言 ✗
**自测**：`python test_provenance.py`
