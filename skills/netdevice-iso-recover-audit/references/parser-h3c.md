# 华三（H3C / 新华三）LLDP / 聚合口 / 脚本格式

当前已支持 H3C DCGW 样例中的三类输入：

- LLDP：`display lldp neighbor-information list`
- 聚合口：`display link-aggregation verbose`
- 隔离/恢复脚本：txt 或 xlsx；xlsx 读取第一列命令，并可按设备名截取对应脚本块

## LLDP 邻居信息

支持表格：

```text
LocalIf         Nbr chassis ID  Nbr port ID                     Nbr system name
HGE2/0/1        4873-97f2-6800  HundredGigE2/0/1                NFV-D-HNZJI-04A-1802-AD02-E-RT-02
XGE6/2/2        6ce2-d32e-e800  Ten-GigabitEthernet3/1/3        NFV-D-HNZJI-04A-1802-AC03-S-FW-01
```

字段映射：

| 输出字段 | 内部字段 |
| --- | --- |
| `LocalIf` | `local_intf` |
| `Nbr port ID` | `neighbor_intf` |
| `Nbr system name` | `neighbor_dev` |
| TTL / 老化时间 | 暂无，记为 `None` |

## 聚合口-物理口映射

支持 `display link-aggregation verbose` 中的 `Aggregate Interface` 段落：

```text
Aggregate Interface: Route-Aggregation5
Local:
  Port                Status   Priority Index    Oper-Key               Flag
  XGE6/2/2            S        32768    32       5                      {ABCDEF}
  XGE6/2/3            S        32768    38       5                      {ABCDEF}
Remote:
```

解析规则：

- `Aggregate Interface:` 后的值作为聚合口名，例如 `Route-Aggregation5`。
- 只采集 `Local:` 段下的本端成员口。
- `Remote:` 段为对端 Actor 信息，不纳入本端成员。

## 隔离/恢复脚本

支持文本脚本和 Excel 脚本。Excel 脚本约定：

- 第一列为命令或段落标题。
- 第二列可为端口描述，解析器忽略。
- 工作表名优先使用 `隔离脚本` / `恢复脚本`。
- 如果同一工作表包含多台设备脚本，主入口 `audit.py` 会按 `--device-name` 截取对应设备块。

支持命令：

```text
interface Route-Aggregation3
interfaceRoute-Aggregation3
shutdown
undo shutdown
no shutdown
quit
save
return
```

识别现场样例中的常见错拼，并作为严重错误报告：

- `shutdwon` 记录为 `invalid_shutdown_typo`。
- `undo shutdwon` 记录为 `invalid_undo_shutdown_typo`。

> 注意：错拼只用于定位该行属于哪个接口上下文，报告会保留原始命令并标记为严重异常；该行不作为有效端口操作参与顺序、主备、重复或覆盖检查。
