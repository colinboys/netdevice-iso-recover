# 网络设备整机隔离/恢复脚本安全性稽核报告

- 被稽核设备：`NFV-D-HNZJI-04A-1802-AC02-E-RT-01`
- 设备类型：**DCGW**
- 设备厂家：h3c

## 一、LLDP 端口分类（带聚合口关联）

| 本端物理口 | 对端设备 | 对端接口 | 所属聚合口 | 端口分类 | 主备 | 防火墙对 |
| --- | --- | --- | --- | --- | --- | --- |
| `HGE2/0/2` | GDZJI-NETCN04-CE09-ZTEM60008S | `cgei-0/0/0/2` | `Route-Aggregation3` | **上行** | - | - |
| `HGE2/0/5` | NFV-D-HNZJI-04A-1802-AC05-S-FW-01 | `100GE6/0/0` | `Route-Aggregation151` | **上行** | 主 | Pair-S-FW-2 |
| `HGE3/0/2` | GDZJI-NETCN04-CE09-ZTEM60008S | `cgei-0/1/0/2` | `Route-Aggregation3` | **上行** | - | - |
| `HGE3/0/5` | NFV-D-HNZJI-04A-1802-AC05-S-FW-01 | `100GE5/0/0` | `Route-Aggregation151` | **上行** | 主 | Pair-S-FW-2 |
| `HGE4/0/4` | NFV-D-HNZJI-04A-1802-AD06-S-FW-02 | `100GE6/0/0` | `Route-Aggregation152` | **上行** | 备 | Pair-S-FW-2 |
| `HGE5/0/4` | NFV-D-HNZJI-04A-1802-AD06-S-FW-02 | `100GE5/0/0` | `Route-Aggregation152` | **上行** | 备 | Pair-S-FW-2 |
| `XGE6/2/2` | NFV-D-HNZJI-04A-1802-AC03-S-FW-01 | `Ten-GigabitEthernet3/1/3` | `Route-Aggregation5` | **上行** | 主 | Pair-S-FW-1 |
| `XGE6/2/3` | NFV-D-HNZJI-04A-1802-AC03-S-FW-01 | `Ten-GigabitEthernet3/1/4` | `Route-Aggregation5` | **上行** | 主 | Pair-S-FW-1 |
| `XGE6/2/4` | NFV-D-HNZJI-04A-1802-AC03-S-FW-01 | `Ten-GigabitEthernet3/1/5` | `Route-Aggregation5` | **上行** | 主 | Pair-S-FW-1 |
| `XGE6/2/5` | NFV-D-HNZJI-04A-1802-AD04-S-FW-02 | `Ten-GigabitEthernet3/1/3` | `Route-Aggregation6` | **上行** | 备 | Pair-S-FW-1 |
| `XGE6/2/6` | NFV-D-HNZJI-04A-1802-AD04-S-FW-02 | `Ten-GigabitEthernet3/1/4` | `Route-Aggregation6` | **上行** | 备 | Pair-S-FW-1 |
| `XGE6/2/7` | NFV-D-HNZJI-04A-1802-AD04-S-FW-02 | `Ten-GigabitEthernet3/1/5` | `Route-Aggregation6` | **上行** | 备 | Pair-S-FW-1 |
| `XGE7/2/2` | NFV-D-HNZJI-04A-1802-AC03-S-FW-01 | `Ten-GigabitEthernet2/1/6` | `Route-Aggregation5` | **上行** | 主 | Pair-S-FW-1 |
| `XGE7/2/3` | NFV-D-HNZJI-04A-1802-AC03-S-FW-01 | `Ten-GigabitEthernet2/1/7` | `Route-Aggregation5` | **上行** | 主 | Pair-S-FW-1 |
| `XGE7/2/4` | NFV-D-HNZJI-04A-1802-AD04-S-FW-02 | `Ten-GigabitEthernet2/1/6` | `Route-Aggregation6` | **上行** | 备 | Pair-S-FW-1 |
| `XGE7/2/5` | NFV-D-HNZJI-04A-1802-AD04-S-FW-02 | `Ten-GigabitEthernet2/1/7` | `Route-Aggregation6` | **上行** | 备 | Pair-S-FW-1 |
| `HGE2/0/3` | NFV-D-HNZJI-04A-1802-AC08-S-EOR-01 | `HundredGigE2/0/34` | `Route-Aggregation11` | **下行** | - | - |
| `HGE2/0/4` | NFV-D-HNZJI-04A-1802-AD09-S-EOR-02 | `HundredGigE2/0/34` | `Route-Aggregation11` | **下行** | - | - |
| `HGE3/0/3` | NFV-D-HNZJI-04A-1802-AC08-S-EOR-01 | `HundredGigE3/0/34` | `Route-Aggregation11` | **下行** | - | - |
| `HGE3/0/4` | NFV-D-HNZJI-04A-1802-AD09-S-EOR-02 | `HundredGigE3/0/34` | `Route-Aggregation11` | **下行** | - | - |
| `HGE4/0/2` | NFV-D-HNZJI-04A-1802-AC08-S-EOR-01 | `HundredGigE4/0/34` | `Route-Aggregation11` | **下行** | - | - |
| `HGE4/0/3` | NFV-D-HNZJI-04A-1802-AD09-S-EOR-02 | `HundredGigE4/0/34` | `Route-Aggregation11` | **下行** | - | - |
| `HGE5/0/2` | NFV-D-HNZJI-04A-1802-AC08-S-EOR-01 | `HundredGigE5/0/34` | `Route-Aggregation11` | **下行** | - | - |
| `HGE5/0/3` | NFV-D-HNZJI-04A-1802-AD09-S-EOR-02 | `HundredGigE5/0/34` | `Route-Aggregation11` | **下行** | - | - |
| `XGE6/1/20` | NFV-D-HNZJI-04A-1802-AB02-00-LB-03 | `Ten-GigabitEthernet1/0/12` | - | **下行** | - | - |
| `XGE6/2/10` | NFV-D-HNZJI-04A-1802-AB02-00-LB-01 | `Ten-GigabitEthernet1/0/12` | `Route-Aggregation191` | **下行** | - | - |
| `XGE6/2/11` | NFV-D-HNZJI-04A-1802-AB02-00-LB-01 | `Ten-GigabitEthernet1/0/13` | `Route-Aggregation191` | **下行** | - | - |
| `XGE6/2/12` | NFV-D-HNZJI-04A-1802-AB02-00-LB-01 | `Ten-GigabitEthernet1/0/14` | `Route-Aggregation191` | **下行** | - | - |
| `XGE6/2/13` | NFV-D-HNZJI-04A-1802-AE02-00-LB-02 | `Ten-GigabitEthernet1/0/12` | `Route-Aggregation192` | **下行** | - | - |
| `XGE6/2/14` | NFV-D-HNZJI-04A-1802-AE02-00-LB-02 | `Ten-GigabitEthernet1/0/13` | `Route-Aggregation192` | **下行** | - | - |
| `XGE6/2/15` | NFV-D-HNZJI-04A-1802-AE02-00-LB-02 | `Ten-GigabitEthernet1/0/14` | `Route-Aggregation192` | **下行** | - | - |
| `XGE6/2/16` | NFV-D-HNZJI-04A-1802-AB02-00-LB-03 | `Ten-GigabitEthernet1/0/13` | - | **下行** | - | - |
| `XGE6/2/17` | NFV-D-HNZJI-04A-1802-AB02-00-LB-03 | `Ten-GigabitEthernet1/0/14` | - | **下行** | - | - |
| `XGE6/2/18` | NFV-D-HNZJI-04A-1802-AE02-00-LB-04 | `Ten-GigabitEthernet1/0/12` | - | **下行** | - | - |
| `XGE6/2/19` | NFV-D-HNZJI-04A-1802-AE02-00-LB-04 | `Ten-GigabitEthernet1/0/13` | - | **下行** | - | - |
| `XGE6/2/20` | NFV-D-HNZJI-04A-1802-AE02-00-LB-04 | `Ten-GigabitEthernet1/0/14` | - | **下行** | - | - |
| `XGE7/2/10` | NFV-D-HNZJI-04A-1802-AB02-00-LB-01 | `Ten-GigabitEthernet1/0/20` | `Route-Aggregation191` | **下行** | - | - |
| `XGE7/2/11` | NFV-D-HNZJI-04A-1802-AE02-00-LB-02 | `Ten-GigabitEthernet1/0/18` | `Route-Aggregation192` | **下行** | - | - |
| `XGE7/2/12` | NFV-D-HNZJI-04A-1802-AE02-00-LB-02 | `Ten-GigabitEthernet1/0/19` | `Route-Aggregation192` | **下行** | - | - |
| `XGE7/2/13` | NFV-D-HNZJI-04A-1802-AE02-00-LB-02 | `Ten-GigabitEthernet1/0/20` | `Route-Aggregation192` | **下行** | - | - |
| `XGE7/2/14` | NFV-D-HNZJI-04A-1802-AB02-00-LB-03 | `Ten-GigabitEthernet1/0/18` | - | **下行** | - | - |
| `XGE7/2/15` | NFV-D-HNZJI-04A-1802-AB02-00-LB-03 | `Ten-GigabitEthernet1/0/19` | - | **下行** | - | - |
| `XGE7/2/16` | NFV-D-HNZJI-04A-1802-AB02-00-LB-03 | `Ten-GigabitEthernet1/0/20` | - | **下行** | - | - |
| `XGE7/2/17` | NFV-D-HNZJI-04A-1802-AE02-00-LB-04 | `Ten-GigabitEthernet1/0/18` | - | **下行** | - | - |
| `XGE7/2/18` | NFV-D-HNZJI-04A-1802-AE02-00-LB-04 | `Ten-GigabitEthernet1/0/19` | - | **下行** | - | - |
| `XGE7/2/19` | NFV-D-HNZJI-04A-1802-AE02-00-LB-04 | `Ten-GigabitEthernet1/0/20` | - | **下行** | - | - |
| `XGE7/2/8` | NFV-D-HNZJI-04A-1802-AB02-00-LB-01 | `Ten-GigabitEthernet1/0/18` | `Route-Aggregation191` | **下行** | - | - |
| `XGE7/2/9` | NFV-D-HNZJI-04A-1802-AB02-00-LB-01 | `Ten-GigabitEthernet1/0/19` | `Route-Aggregation191` | **下行** | - | - |
| `HGE2/0/1` | NFV-D-HNZJI-04A-1802-AD02-E-RT-02 | `HundredGigE2/0/1` | `Route-Aggregation1` | **互联** | - | - |
| `HGE3/0/1` | NFV-D-HNZJI-04A-1802-AD02-E-RT-02 | `HundredGigE3/0/1` | `Route-Aggregation1` | **互联** | - | - |
| `HGE4/0/1` | NFV-D-HNZJI-04A-1802-AD02-E-RT-02 | `HundredGigE4/0/1` | `Route-Aggregation1` | **互联** | - | - |
| `HGE5/0/1` | NFV-D-HNZJI-04A-1802-AD02-E-RT-02 | `HundredGigE5/0/1` | `Route-Aggregation1` | **互联** | - | - |
| `XGE6/2/1` | NFV-D-HNZJI-04A-1802-AD02-E-RT-02 | `Ten-GigabitEthernet6/2/1` | `Route-Aggregation2` | **互联** | - | - |
| `XGE7/2/1` | NFV-D-HNZJI-04A-1802-AD02-E-RT-02 | `Ten-GigabitEthernet7/2/1` | `Route-Aggregation2` | **互联** | - | - |
| `MGE0/0/0` | NFV-D-HNZJI-04A-1802-AC03-DM-TOR-01 | `GigabitEthernet1/0/7` | - | **剩余** | - | - |
| `XGE6/1/10` | 401-ZJISJZX-1805-AD18-ZJIZYCYWHJSW001/002 | `XGigabitEthernet0/0/5` | `Route-Aggregation16` | **剩余** | - | - |
| `XGE6/1/19` | NFV-D-HNZJI-04A-1802-AB02-00-WAF-01 | `tengige0_0` | `Bridge-Aggregation161` | **剩余** | - | - |
| `XGE7/1/20` | - | - | `Bridge-Aggregation162` | **剩余** | - | - |

## 二、隔离脚本稽核

**期望顺序**：上行 → 下行 → 互联

| 序号 | 行号 | 接口 | 操作 | 期望分类 | 实际分类 | 合法性 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4 | `Route-Aggregation3` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 2 | 7 | `Route-Aggregation6` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 3 | 10 | `Route-Aggregation5` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 4 | 13 | `Route-Aggregation152` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 5 | 16 | `Route-Aggregation151` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 6 | 19 | `Route-Aggregation192` | invalid_shutdown_typo | 下行 | 下行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 7 | 22 | `Route-Aggregation191` | invalid_shutdown_typo | 下行 | 下行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 8 | 26 | `Route-Aggregation11` | shutdown | 下行 | 下行 | 异常：期望起始分类 上行，但首条 op 为 下行（顺序 2/3） |
| 9 | 30 | `Route-Aggregation1` | invalid_shutdown_typo | 互联 | 互联 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 10 | 33 | `Route-Aggregation2` | invalid_shutdown_typo | 互联 | 互联 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |

**发现项**：
- 隔离脚本存在严重命令拼写错误：行 4(Route-Aggregation3: shutdwon)、行 7(Route-Aggregation6: shutdwon)、行 10(Route-Aggregation5: shutdwon)、行 13(Route-Aggregation152: shutdwon)、行 16(Route-Aggregation151: shutdwon)、行 19(Route-Aggregation192: shutdwon)、行 22(Route-Aggregation191: shutdwon)、行 30(Route-Aggregation1: shutdwon)、行 33(Route-Aggregation2: shutdwon)。这些命令不会被视为有效端口操作。
- 顺序异常：脚本起始分类为 下行，但期望从 上行 开始，期望顺序：上行→下行→互联。
- 缺少以下应操作的端口（不在脚本内）：HGE2/0/2(上行)、HGE2/0/5(上行)、HGE3/0/2(上行)、HGE3/0/5(上行)、HGE4/0/4(上行)、HGE5/0/4(上行)、XGE6/2/2(上行)、XGE6/2/3(上行)、XGE6/2/4(上行)、XGE6/2/5(上行)、XGE6/2/6(上行)、XGE6/2/7(上行)、XGE7/2/2(上行)、XGE7/2/3(上行)、XGE7/2/4(上行)、XGE7/2/5(上行)、XGE6/1/20(下行)、XGE6/2/10(下行)、XGE6/2/11(下行)、XGE6/2/12(下行)、XGE6/2/13(下行)、XGE6/2/14(下行)、XGE6/2/15(下行)、XGE6/2/16(下行)、XGE6/2/17(下行)、XGE6/2/18(下行)、XGE6/2/19(下行)、XGE6/2/20(下行)、XGE7/2/10(下行)、XGE7/2/11(下行)、XGE7/2/12(下行)、XGE7/2/13(下行)、XGE7/2/14(下行)、XGE7/2/15(下行)、XGE7/2/16(下行)、XGE7/2/17(下行)、XGE7/2/18(下行)、XGE7/2/19(下行)、XGE7/2/8(下行)、XGE7/2/9(下行)、HGE2/0/1(互联)、HGE3/0/1(互联)、HGE4/0/1(互联)、HGE5/0/1(互联)、XGE6/2/1(互联)、XGE7/2/1(互联)

## 三、恢复脚本稽核

**期望顺序**：互联 → 上行 → 下行

| 序号 | 行号 | 接口 | 操作 | 期望分类 | 实际分类 | 合法性 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4 | `Route-Aggregation1` | invalid_shutdown_typo | 互联 | 互联 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 2 | 7 | `Route-Aggregation2` | invalid_shutdown_typo | 互联 | 互联 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 3 | 12 | `Route-Aggregation3` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 4 | 15 | `Route-Aggregation5` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 5 | 18 | `Route-Aggregation6` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 6 | 21 | `Route-Aggregation151` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 7 | 24 | `Route-Aggregation152` | invalid_shutdown_typo | 上行 | 上行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 8 | 27 | `Route-Aggregation191` | invalid_shutdown_typo | 下行 | 下行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 9 | 30 | `Route-Aggregation192` | invalid_shutdown_typo | 下行 | 下行 | 严重异常：命令拼写错误（原始命令：shutdwon），该行不计为有效端口操作 |
| 10 | 34 | `Route-Aggregation11` | shutdown | 下行 | 下行 | 异常：期望起始分类 互联，但首条 op 为 下行（顺序 3/3） |

**发现项**：
- 恢复脚本存在严重命令拼写错误：行 4(Route-Aggregation1: shutdwon)、行 7(Route-Aggregation2: shutdwon)、行 12(Route-Aggregation3: shutdwon)、行 15(Route-Aggregation5: shutdwon)、行 18(Route-Aggregation6: shutdwon)、行 21(Route-Aggregation151: shutdwon)、行 24(Route-Aggregation152: shutdwon)、行 27(Route-Aggregation191: shutdwon)、行 30(Route-Aggregation192: shutdwon)。这些命令不会被视为有效端口操作。
- 恢复脚本操作类型异常：期望使用 undo shutdown，但 行 34(Route-Aggregation11: shutdown) 不符合。
- 顺序异常：脚本起始分类为 下行，但期望从 互联 开始，期望顺序：互联→上行→下行。
- 缺少以下应操作的端口（不在脚本内）：HGE2/0/2(上行)、HGE2/0/5(上行)、HGE3/0/2(上行)、HGE3/0/5(上行)、HGE4/0/4(上行)、HGE5/0/4(上行)、XGE6/2/2(上行)、XGE6/2/3(上行)、XGE6/2/4(上行)、XGE6/2/5(上行)、XGE6/2/6(上行)、XGE6/2/7(上行)、XGE7/2/2(上行)、XGE7/2/3(上行)、XGE7/2/4(上行)、XGE7/2/5(上行)、XGE6/1/20(下行)、XGE6/2/10(下行)、XGE6/2/11(下行)、XGE6/2/12(下行)、XGE6/2/13(下行)、XGE6/2/14(下行)、XGE6/2/15(下行)、XGE6/2/16(下行)、XGE6/2/17(下行)、XGE6/2/18(下行)、XGE6/2/19(下行)、XGE6/2/20(下行)、XGE7/2/10(下行)、XGE7/2/11(下行)、XGE7/2/12(下行)、XGE7/2/13(下行)、XGE7/2/14(下行)、XGE7/2/15(下行)、XGE7/2/16(下行)、XGE7/2/17(下行)、XGE7/2/18(下行)、XGE7/2/19(下行)、XGE7/2/8(下行)、XGE7/2/9(下行)、HGE2/0/1(互联)、HGE3/0/1(互联)、HGE4/0/1(互联)、HGE5/0/1(互联)、XGE6/2/1(互联)、XGE7/2/1(互联)

## 四、整体结论

**不通过（存在发现项）**

请按上述发现项人工复核后再执行操作。
