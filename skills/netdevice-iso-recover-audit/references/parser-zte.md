# 中兴（ZTE）LLDP / 接口采集数据格式（占位）

> 本文件为占位。中兴数通设备的 `show lldp neighbor` 与 `show interface brief` 格式与华为存在差异，待补充后再实现 `scripts/parse_lldp.py` 的中兴分支。

## 待办

- [ ] 收集 `show lldp neighbor brief` 真实样例
- [ ] 收集 `show interface brief` 真实样例
- [ ] 收集 `show port-aggregation` / `show xgpon-onu-config` 等聚合口信息
- [ ] 在 `scripts/parse_lldp.py` 中增加 `--vendor zte` 分支
- [ ] 在 `scripts/parse_trunks.py` 中增加 `--vendor zte` 分支
- [ ] 在 `scripts/parse_script.py` 中实现 `parse_zte()`（占位已就绪）

## 提示

中兴常见接口命名：`xgei-0/0/0/2`、`cgei-0/3/0/29`、`xge-1/1`、`gei-0/0/0/5` 等。
聚合口关键字可能为 `smartgroup`、`lag`、`port-channel` 之一。

## 隔离/恢复脚本（待实现）

`scripts/parse_script.py` 的 `parse_zte()` 仍为占位（抛 `NotImplementedError`），需在补齐下列样例后实现。

**待收集的脚本样例要素**：

- 进入配置模式的关键字：`configure terminal`？`system-view`？其他？
- 接口进入/退出：`interface <ifname>` / `exit` / `end`？
- **关闭/恢复命令风格**（关键差异点）：
  - 中兴常见 `shutdown` / `no shutdown`（Cisco 风格）
  - 部分平台支持 `undo shutdown`
  - 确认两套写法是否同时存在，写实现时需兼容
- 控制命令：`commit`？`write`？`save`？`end`？`quit`？
- 注释行格式：`!`？`#`？`/* ... */`？是否支持 `//` 段注释？
- 典型接口名前缀：`xgei-` / `cgei-` / `gei-` / `smartgroup` 等。

**预期最小骨架（占位）**：

```
configure terminal
interface xgei-0/0/0/2
shutdown
!
interface smartgroup1
shutdown
!
end
write
```

实现 `parse_zte()` 时，可直接复用 `_classify_shutdown_line()` 把 `no shutdown` 归一为 `undo_shutdown`，与 `audit.py` 的 op 语义保持一致。

> CLI 调用：`python3 scripts/parse_script.py <script> --vendor zte`（当前会以 NotImplementedError 拒绝）。
