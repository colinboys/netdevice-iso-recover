# 华三（H3C / 新华三）LLDP / 接口采集数据格式（占位）

> 本文件为占位。华三 Comware V7 平台的 `display lldp neighbor brief` 与 `display interface brief` 输出格式与华为有差异，待补充后再实现解析。

## 待办

- [ ] 收集 `display lldp neighbor brief` 真实样例
- [ ] 收集 `display interface brief` 真实样例
- [ ] 收集 `display link-aggregation verbose` 真实样例
- [ ] 在 `scripts/parse_lldp.py` 中增加 `--vendor h3c` 分支
- [ ] 在 `scripts/parse_trunks.py` 中增加 `--vendor h3c` 分支
- [ ] 在 `scripts/parse_script.py` 中实现 `parse_h3c()`（占位已就绪）

## 提示

华三常见接口命名：`GigabitEthernet1/0/1`、`Ten-GigabitEthernet1/0/25`、`HundredGigE1/0/49` 等。
聚合口关键字：`Bridge-Aggregation`、`Route-Aggregation`、`Link-Aggregation`（不同版本）。

## 隔离/恢复脚本（待实现）

`scripts/parse_script.py` 的 `parse_h3c()` 仍为占位（抛 `NotImplementedError`），需在补齐下列样例后实现。

**待收集的脚本样例要素**：

- 进入配置模式：`system-view`（与华为一致？）
- 接口进入：`interface <ifname>` / `port <ifname>`？
- **关闭/恢复命令**：华三常用 `shutdown` / `undo shutdown`（与华为一致），但需确认是否存在 `no shutdown` 别名。
- 退出配置模式：`return`、`quit`，是否需要 `save` 保存？
- 控制命令：`commit`？（Comware 默认不需要 commit，立即生效；但部分场景可能仍带 `commit`）
- 注释行：`#`？`//`？其他？
- 典型接口名前缀：`GigabitEthernet`、`Ten-GigabitEthernet`、`HundredGigE` 等。

**预期最小骨架（占位）**：

```
system-view
interface GigabitEthernet1/0/1
shutdown
#
interface Ten-GigabitEthernet1/0/25
undo shutdown
#
return
save
```

实现 `parse_h3c()` 时，可参考 `parse_huawei()` 的骨架，差异点主要在 `commit` / `save` / `return` 等控制命令的识别上。

> CLI 调用：`python3 scripts/parse_script.py <script> --vendor h3c`（当前会以 NotImplementedError 拒绝）。
