# 华为（VRP）LLDP / 接口采集数据格式

> 本文件描述华为数通设备（NE/AR/S 系列，VRP V800）通过数通 CLI 采集的原始数据格式。`scripts/parse_lldp.py` 与 `scripts/parse_trunks.py` 已实现华为格式的解析。

## LLDP 邻居摘要（`display lldp neighbor brief`）

### 原始示例

```
Local Intf                     Neighbor Dev         Neighbor Intf        Exptime (sec)
--------------------------------------------------------------------------------------
50|100GE1/0/0                  GDZJI-NETCN02-CE05-ZTEM60008S cgei-0/0/0/2                    93
GigabitEthernet4/0/0           GDZJI-NETBOSS-CE01-ZTEM60008S xgei-0/0/0/5                   105
```

### 字段说明

- 列以**单个或多个空格**分隔（典型 2+ 个空格），脚本会做空白规整。
- 第一行表头可能以 `﻿`（BOM）开头，解析时需忽略。
- 分隔线 `----...` 需跳过。
- 字段数为 4：`Local Intf`、`Neighbor Dev`、`Neighbor Intf`、`Exptime (sec)`。
- 邻居设备名称可能包含空格以外的字符；典型为 `设备名-厂家-型号-编号` 形式。
- 本端接口命名遵循 VRP 规范：`50|100GE<slot>/<subslot>/<port>`、`100GE<slot>/<subslot>/<port>`、`GigabitEthernet<slot>/<subslot>/<port>` 等。

### 解析逻辑

1. 跳过空行、分隔线与表头。
2. 按连续空白字符切分。
3. 取前 4 列：本地接口、对端设备、对端接口、TTL。
4. 对端设备名做 `strip()` 即可。
5. **要求对端接口**的列可能因表格对齐而出现尾巴的额外空白，无影响。

## 接口摘要（`display interface brief`）

### 原始示例（节选）

```
Interface                   PHY   Protocol  InUti OutUti   inErrors  outErrors
50|100GE1/0/4(100G)         up    down      1.32%  1.27%          0          0
Eth-Trunk1                  up    down      0.01%  0.01%          0          0
  50|100GE1/1/0(100G)       up    up        0.01%  0.01%          0          0
  50|100GE2/1/0(100G)       up    up        0.01%  0.01%          0          0
Eth-Trunk2                  up    down      0.15%  0.29%          0          0
  GigabitEthernet4/0/5(10G) up    up        0.15%  0.29%          0          0
```

### 字段说明

- 前若干行为图例（`PHY:`、`*down:`、`(l):` 等），需跳过直到出现 `Interface ... PHY ...` 表头。
- 接口名可能携带速率后缀（如 `50|100GE1/0/4(100G)`），需去掉 `(<rate>)` 部分。
- 缩进的物理口（行首有空格）从属于上方最近的非缩进聚合口；缩进深度以「行首空白」识别。
- `LoopBack*`、`MEth*`、`NULL*`、`Vlanif*` 等逻辑接口不参与稽核。
- `HP-GE*` 是华为早期模块化接口，按物理口处理。

### 解析逻辑

1. 跳过图例区。
2. 找到表头行后开始解析。
3. 接口名正则：剥离 `(...)`、`*down` 等后缀。
4. 用行首空白（≥2 个空格）判断是否成员口；非空白的为聚合口或独立物理口。
5. 维护「当前聚合口」栈：成员口压入栈顶聚合口，直到下一个非缩进口出现。

## 隔离/恢复脚本（手工编写）

华为 VRP 风格的脚本片段示例：

```
system-view
interface Eth-trunk 2
shutdown
#
interface 50|100GE1/0/4
shutdown
#
commit
quit
save
y
```

`scripts/parse_script.py` 的 `parse_huawei()`（**已实现**）可识别以下要素：

- `interface <ifname>` 段。
- `shutdown` / `undo shutdown` 操作。
- 注释行（`//`、`#`、`!`）。
- `commit`、`save`、`y` 等控制命令不视为接口操作。
- 段注释 `//关闭上行接口`、`//关闭下行接口` 等可作为分类提示，但**不作为权威分类依据**——以 LLDP + 聚合口推导出的真实分类为准。

> CLI 调用：`python3 scripts/parse_script.py <script> --vendor huawei`（默认 vendor 即 huawei，可省略）。

## 待扩展提示

- `display trunk membership` / `display eth-trunk` 也是聚合口信息来源，可在 `parse_trunks.py` 中扩展。
- `display lldp neighbor`（详细模式）包含更多字段，本稽核暂未使用。

## 报告渲染注意事项：接口名中的 `|` 字符

华为 CE/NE 系列路由器的 `50GE / 100GE / 50|100GE` 自协商接口名中**本身带 `|`** 字符（例如 `50|100GE1/0/0`、`50|100GE1/0/2`）。在稽核报告中把这类接口名原样拼到 Markdown 表格行里时，`|` 会被 GFM 解析为新的列边界，导致：

- 行内出现多余空列
- 整行单元格数与表头不一致
- 渲染时列错位、表格被截断

`scripts/audit.py` 中的 `render_markdown()` 已经做了双层防御：

1. **表格单元格统一过 `_md_cell()`**：把所有 `|` 转义为 `\|`（GFM/CommonMark 反斜杠转义）。
2. **接口名额外用反引号包成代码片段**：CommonMark 规范保证代码片段内的 `|` 不会被识别为列分隔符，作为 `\|` 不被识别时的兜底。

新接入厂家或新增接口前缀时，如果设备名可能含 `|`（如未来出现 `100|200GE` 这类速率档位拼接），仍可复用 `_md_cell()`，不需要再改渲染逻辑。
