# 锐捷（Ruijie）LLDP / 接口采集数据格式（占位）

> 本文件为占位。锐捷 RGOS 平台的 `show lldp neighbor brief` 与 `show interface status` 输出格式与华为有差异，待补充后再实现解析。

## 待办

- [ ] 收集 `show lldp neighbor brief` 真实样例
- [ ] 收集 `show interface status` 真实样例
- [ ] 收集 `show aggregatorport` / `show link-aggregation` 真实样例
- [ ] 在 `scripts/parse_lldp.py` 中增加 `--vendor ruijie` 分支
- [ ] 在 `scripts/parse_trunks.py` 中增加 `--vendor ruijie` 分支
- [ ] 在 `scripts/parse_script.py` 中实现 `parse_ruijie()`（占位已就绪）

## 提示

锐捷常见接口命名：`GigabitEthernet 0/1`、`TenGigabitEthernet 1/0/2`、`XGigabitEthernet 0/1`（注意中间有空格）。
聚合口关键字：`AggregatePort`、`AP`。

## 隔离/恢复脚本（待实现）

`scripts/parse_script.py` 的 `parse_ruijie()` 仍为占位（抛 `NotImplementedError`），需在补齐下列样例后实现。

**待收集的脚本样例要素**：

- 进入配置模式：`configure terminal`？`enable` + `configure terminal`？其他？
- 接口进入：`interface <ifname>`？（注意锐捷接口名常含空格，如 `GigabitEthernet 0/1`）
- **关闭/恢复命令**（关键差异点）：
  - 锐捷常用 `shutdown` / `no shutdown`（Cisco 风格）
  - 需确认是否同时支持 `undo shutdown`
- 控制命令：`end`、`write`、`exit`？是否需要 `exit` 逐级退到顶层？
- 注释行：`!`（Cisco 风格）？`#`？`//`？
- 典型接口名前缀：`GigabitEthernet `（带空格）、`TenGigabitEthernet `、`XGigabitEthernet `、`FastEthernet ` 等。
- 聚合口关键字：`AggregatePort 1`、`AP 1`，接口名同样可能含空格。

**预期最小骨架（占位）**：

```
configure terminal
interface GigabitEthernet 0/1
shutdown
!
interface AggregatePort 1
shutdown
!
end
write
```

实现 `parse_ruijie()` 时，可直接复用 `_classify_shutdown_line()` 把 `no shutdown` 归一为 `undo_shutdown`。
需要特别留意：接口名中的空格在 `IFACE_RE` 的非贪婪匹配下会被一并截到 iface 字段中（保留原始大小写），与上游 `audit.py` 的接口名归一化逻辑兼容。

> CLI 调用：`python3 scripts/parse_script.py <script> --vendor ruijie`（当前会以 NotImplementedError 拒绝）。
