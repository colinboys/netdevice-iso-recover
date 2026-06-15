---
name: netdevice-iso-recover-audit
description: 网络设备（华为/中兴/华三/锐捷）整机隔离与恢复脚本的安全性稽核。适用于版本升级、设备隔离更换等需要「先安全关闭全部端口、再安全恢复入网」的场景。当用户提供一个包含 LLDP 邻居摘要、聚合口-物理口映射、隔离脚本、恢复脚本的目录时，本 skill 会对脚本中的端口关闭/恢复顺序、完整性、准确性进行自动稽核，输出可作为审计证据的 Markdown 报告。支持的设备类型以 DCGW（S-RT/E-RT）为首，其它类型（业务 EOR / 各 TOR / 防火墙 / CE / 负载均衡）以占位方式保留扩展点。触发词：网络设备稽核、隔离脚本稽核、恢复脚本稽核、整机隔离、shutdown 顺序稽核、DCGW 稽核。
---

# 网络设备整机隔离/恢复脚本安全性稽核

## 概述

针对版本升级、设备隔离更换等场景，对网络设备的整机隔离与恢复脚本进行安全性稽核：

- 按 LLDP 邻居 + 聚合口映射，对本端物理端口做 **上行 / 下行 / 互联 / 剩余** 分类。
- 对照设备类型预定义的 **隔离顺序（上行→下行→互联）** 与 **恢复顺序（互联→上行→下行）**，检查脚本中 `shutdown` / `undo shutdown` 的执行顺序、覆盖范围与重复操作。
- 输出含原始数据、推导依据、逐端口合法性标注的 Markdown 稽核报告，可直接作为审计证据。

> 当前已完整实现的设备类型：**DCGW**（S-RT / E-RT）。其他类型（业务 EOR / 管理 EOR / 业务 TOR / 管理 TOR / 防火墙 / CE / 负载均衡 …）已建立占位规则与扩展入口。

## 适用场景

- 提交给变更委员会前，对现网设备整机隔离/恢复脚本做合规性检查。
- 跨厂家（华为/中兴/华三/锐捷）设备统一稽核流程。
- 在执行自动化下发前，作为最后一道安全闸。

## 不适用场景

- 设备日常单端口 shutdown / 端口级策略调整。
- 路由器进程级、协议级（OSPF/BGP）变更。
- 物理链路故障定位。

## 通用原则

| 操作 | 推荐顺序 |
| ---- | -------- |
| **隔离（shutdown）** | 先断「上行」（离开现网）→ 再断「下行」（脱离业务）→ 最后断「互联」（脱离对端设备） |
| **恢复（undo shutdown）** | 先开「互联」（先和对端打通）→ 再开「上行」（重新接入外网）→ 最后开「下行」（恢复业务流量） |

> 顺序背后的逻辑：隔离时由外向内收敛，恢复时由内向外开放，保证任意瞬间不会出现「孤立半边」的不一致状态。

### 防火墙主备子顺序（v6，DCGW 已实现）

在 DCGW / CMNET CE 等同时连接多对防火墙的设备上，上行 + 下行段内还需要再细分主备子顺序，避免混淆同一对防火墙内的关闭顺序。v6 将检查粒度从「类型分组」细化为「每对防火墙」独立检查，并新增 S-FW 数字接近度配对算法。

| 适用段 | 操作 | 对内子顺序 |
| --- | --- | --- |
| 上行 + 下行 | **隔离** | 先关闭所有连接**备防火墙**的本端端口，再关闭所有连接**主防火墙**的本端端口 |
| 上行 + 下行 | **恢复** | 先打开所有连接**主防火墙**的本端端口，再打开所有连接**备防火墙**的本端端口 |

**作用域（重要）**：

- 该子顺序对「**上行 + 下行**」段内的防火墙端口生效。
- 「互联」与「剩余」段内的防火墙端口（理论场景）**不应用**子顺序，仍按大类骨架处理。
- 跨大类的隔离 / 恢复骨架仍是「上行 → 下行 → 互联」。

**分组粒度**：按**防火墙对（fw_pair_id）**逐对独立检查，**跨对顺序自由**。例如 DCGW 上行同时连 S-FW 对和 CBN 对时，S-FW 对和 CBN 对之间可以交错出现，只要每对**内部**子顺序正确即可。

**防火墙对配对规则（v6 新增）**：

| 对端防火墙类型 | 配对方式 |
| --- | --- |
| M-FW / CBN / C-FW | 按 `-01`（主）/ `-02`（备）后缀直接配对 |
| S-FW | 按设备名中数字接近度两两配对（详见下方算法） |

**S-FW 数字接近度配对算法**：
- 提取设备名中的数字标识（格式：**任意 2 位大写字母** + `<数字>` + `-S-FW-<01|02>`，正则 `r"[A-Z]{2}(\d+)-S-FW-(\d+)"`）
 - v6.1 起放宽前缀匹配：原 v6 仅识别 `(AE|AF)`，但实际 DCGW 拓扑中备机 S-FW 经常使用 AD / AC 等其它两位大写字母前缀（如 `NFV-D-HNGZ-14A-3203-AD14-S-FW-02`、`NFV-D-HNZJI-01A-1805-AC03-S-FW-01`），只识别 AE/AF 会导致配对失败、v6 子顺序检查不触发
- 按数字相同或接近将 S-FW 设备分组，组内 `-01` 与 `-02` 配对
- 例如：`AE09-S-FW-01` + `AF08-S-FW-02`（差值1）配对，`AE04-S-FW-01` + `AF04-S-FW-02`（差值0）配对，`AE15-S-FW-01` + `AD14-S-FW-02`（差值1）配对
- 详细算法见 `references/port-classification-dcgw.md` 的「防火墙对配对算法（v6）」章节

**子顺序（v6：对内严格，跨对自由）**：

| 操作 | 对内子顺序 |
| --- | --- |
| **隔离** | 先全部备边端口，再全部主边端口（一旦主出现，后续不能再有备） |
| **恢复** | 先全部主边端口，再全部备边端口（一旦备出现，后续不能再有主） |

> 隔离与恢复采用**相反**的子顺序：
> - 隔离「**先全部备边端口，再全部主边端口**」：先断「备」使业务短暂走单「主」、再断「主」，避免「主备同时断开」导致业务真空。
> - 恢复「**先全部主边端口，再全部备边端口**」：先开「主」使业务先恢复主路径、再开「备」补回热备，避免「备先开」时业务单边承担后又双主短暂不一致。

**发现项要求（v6.2）**：当检测到某防火墙对的主备子顺序异常时，**除了指出「哪些接口出现在错误的角色后面」之外，还必须额外列出该对在本脚本中应有的「建议正常操作顺序」**（用本脚本中实际出现的接口 + 行号给出，例如「先全部备边端口（行 12(Eth-Trunk6)、行 15(Eth-Trunk9)），再全部主边端口（行 8(Eth-Trunk5)、行 22(Eth-Trunk20)）」）。理由：

- 抽象描述「应先备后主」不足以让审计人员直接调整脚本；列出该对在本脚本中**具体**应有的行号顺序后，审计人员可以据此直接重排脚本。
- 跨对顺序自由（v6 放宽约束）下，列出「先全部备、再全部主」的总顺序即可，不需要限定两对之间的先后。

实现位置：`scripts/audit.py` 的 `audit_order()` 内、对每对 `pair_id` 处理 `backup_after_master` / `master_after_backup` 时构造。

**主备识别规则**：对端防火墙设备名以 `-01` 结尾视为**主**，`-02` 结尾视为**备**。仅在 LLDP 中 `-01` / `-02` **成对出现**时才触发；未成对时 `fw_role` 为 `None`，不参与子顺序检查，并在发现项中提示人工确认。

- 防火墙关键字（与 `references/device-types.md` 对齐）：`S-FW`（业务业支 / CMNET 防火墙）、`M-FW`（网管防火墙）、`C-FW`（CMNET 防火墙）、`CBN`（广电防火墙）。
- **不**列入防火墙关键字：`PC-CMNET`、`N-RT`——这两者是 CMNET CE（出口路由器）的关键字，**不是**防火墙。
- 详细判定与边缘 case 详见 `references/port-classification-dcgw.md` 的「防火墙主备识别（v6）」章节与 `references/isolation-order.md` 的 DCGW 段。

## 工作流

按以下步骤顺序执行；任一步骤失败都应停止并向用户反馈。

### 0) 模型自检（非阻塞）

检查当前模型能力；低能力模型会给出「建议切换」提示，但**不阻断**执行。

### 1) 收集输入并识别厂家

要求用户提供一个**目录**，目录内至少包含以下文件（命名建议以设备本端名做前缀）：

| 文件 | 说明 |
| ---- | ---- |
| `*display lldp neighbor brief*` | 设备 `display lldp neighbor brief` 的原始输出 |
| `*display interface brief*` | 设备 `display interface brief` 的原始输出（含聚合口成员） |
| `*-隔离脚本.txt` | 整机隔离操作脚本 |
| `*-恢复脚本.txt` | 整机恢复操作脚本 |

判定厂家：优先看 LLDP 摘要表头格式与接口名风格（华为 `50|100GE` / `Eth-Trunk`，华三 `Bridge-Aggregation`，中兴 `cgei-`/`xgei-`，锐捷 `AggregatePort`）。不确定时向用户确认。

### 2) 解析 LLDP 邻居

读取 `references/parser-<vendor>.md` 中对应厂家的格式说明，然后调用脚本：

```bash
python3 scripts/parse_lldp.py "<lldp 文件>" --vendor huawei
```

华为已实现。中兴/华三/锐捷为占位，需先补充样例。

输出 JSON 数组，每条包含 `local_intf`（本端物理口）、`neighbor_dev`（对端设备名）、`neighbor_intf`（对端接口）、`exptime`（TTL）。

### 3) 解析聚合口-物理口映射

读取同一 `references/parser-<vendor>.md` 的接口段，调用：

```bash
python3 scripts/parse_trunks.py "<interface brief 文件>" --vendor huawei
```

输出 JSON 对象：

```json
{
  "trunks": {
    "Eth-Trunk1": ["50|100GE1/1/0", "50|100GE2/1/0", "..."],
    "Eth-Trunk2": ["GigabitEthernet4/0/5", "GigabitEthernet5/0/5"]
  },
  "standalone_phys": ["GigabitEthernet0/0/0", "..."]
}
```

### 4) 识别设备类型

参考 `references/device-types.md`，按设备本端名称（sysname 或文件名中的设备名）匹配关键字。

- 命中 `S-RT` / `E-RT` → **DCGW**
- 命中 `S-EOR` → 业务 EOR
- 命中 `M-EOR` → 管理 EOR
- … 详见设备类型表
- 命中 `S-FW` 时，**必须**结合 LLDP 邻居进一步区分：若对端含 `PC-CMNET` / `N-RT` 则是 CMNET 防火墙，否则是业务业支防火墙。

未命中时输出「未知」，并提示用户。

### 5) 端口分类（上行/下行/互联/剩余）

按设备类型加载对应规则文件：

| 设备类型 | 规则文件 |
| -------- | -------- |
| DCGW | `references/port-classification-dcgw.md`（已实现） |
| 其他 | `references/port-classification-others.md`（占位） |

**关键约束**：聚合口的上/下/互联属性继承自其任意一个成员物理口的 LLDP 邻居；未出现在 LLDP 中的成员口跟随该聚合口分类。

### 6) 稽核脚本顺序

加载设备类型的隔离/恢复顺序：

| 设备类型 | 隔离顺序 | 恢复顺序 |
| -------- | -------- | -------- |
| DCGW | 上行 → 下行 → 互联 | 互联 → 上行 → 下行 |
| 其他 | 占位（待补） | 占位（待补） |

详见 `references/isolation-order.md`。

解析隔离/恢复脚本：

```bash
python3 scripts/parse_script.py "<隔离脚本>" --vendor huawei
python3 scripts/parse_script.py "<恢复脚本>" --vendor huawei
```

> `parse_script.py` 已按厂家分发：当前已实现 `huawei`；`zte` / `h3c` / `ruijie` 均为占位（以 `NotImplementedError` 拒绝），需在 `references/parser-<vendor>.md` 补齐样例后实现对应 `parse_<vendor>()` 函数。CLI 会校验 `--vendor` 取值，避免静默默认。
>
> 调度约定：`no shutdown`（Cisco 风格，中兴/锐捷常见）在最终输出里统一归一为 `undo_shutdown`，与上游 `audit.py` 的 op 语义保持一致。

逐条检查：

1. **顺序**：按期望顺序，第一个分类出现后再出现更早分类 → 顺序异常。
2. **冗余**：聚合口与其成员口同时出现在脚本中 → 重复操作。
3. **覆盖**：期望关闭的物理口是否都在脚本中（按物理口粒度核对，聚合口视为覆盖其成员）。
4. **意外**：脚本中出现未在 LLDP/聚合口数据中出现的接口。

### 7) 输出稽核报告

调用主入口脚本生成报告：

```bash
python3 scripts/audit.py \
  --device-name "NFV-D-HNZJI-02A-1801-AE02-S-RT-01" \
  --device-type DCGW \
  --vendor huawei \
  --lldp "..." \
  --trunks "..." \
  --isolate-script "..." \
  --recover-script "..." \
  --output report.md
```

报告使用 `assets/report-template.md` 模板（脚本内置），必须包含：

1. **LLDP 原始信息表** —— 增加「所属聚合口」「端口分类」「主备」「防火墙对」列，作为分类依据。
2. **隔离/恢复脚本逐端口标注** —— 列出脚本中每个接口的期望分类与实际分类，标注合法性。
3. **整体结论** —— 通过 / 不通过 / 仅供人工复核。

## 资源索引

### scripts/（可直接执行）

- `parse_lldp.py` — 解析 LLDP 邻居摘要（华为已实现）
- `parse_trunks.py` — 解析聚合口-物理口映射（华为已实现）
- `parse_script.py` — 解析隔离/恢复脚本中的 `shutdown` / `undo shutdown`
- `audit.py` — 主入口，串联全流程并生成 Markdown 报告

### references/（按需加载）

- `device-types.md` — 设备类型识别表与关键字冲突处理
- `port-classification-dcgw.md` — DCGW 上/下/互联分类规则（已实现）
- `port-classification-others.md` — 其他设备类型端口分类（占位）
- `isolation-order.md` — 各设备类型的隔离/恢复顺序
- `parser-huawei.md` — 华为 LLDP / 接口摘要 / 脚本格式说明
- `parser-zte.md` — 中兴格式（占位）
- `parser-h3c.md` — 华三格式（占位）
- `parser-ruijie.md` — 锐捷格式（占位）

### assets/

- `report-template.md` — 稽核报告 Markdown 模板（已被 `audit.py` 内置；可手工润色时参考）

## 扩展指引

新增设备类型时：

1. 在 `references/` 中创建 `port-classification-<类型>.md`，定义上行/下行/互联关键字。
2. 在 `references/isolation-order.md` 中追加该类型的隔离/恢复顺序。
3. 在 `scripts/audit.py` 的 `RULES` / `ISO_ORDER` / `REC_ORDER` 中各加一行配置。

> 如果该类型设备也存在「同时连接主备防火墙」的场景，可复用 DCGW 的「防火墙主备子顺序（v6）」思路：
> - 不要把主备子分类加入 `ISO_ORDER` / `REC_ORDER`（跨大类的骨架不应被拆细）。
> - 在 `audit_order` 内部、对「上行」段内的 `fw_role` 作额外检查，参考 `audit.py` 中现有的「v6：防火墙主备子顺序（按对检查）」段。
> - 分类时调用 `detect_fw_master_backup_v6()` + `classify_port_with_fw_role()`，把主备结果写入 `PortInfo.fw_role` 和 `PortInfo.fw_pair_id`。

新增厂家时：

1. 在 `references/parser-<vendor>.md` 中贴样例数据并解释字段。
2. 在 `scripts/parse_lldp.py`、`scripts/parse_trunks.py`、`scripts/parse_script.py` 中各加一个 `parse_<vendor>()` 函数。
3. 在三者的 dispatch 中各增加一条分支（`parse_script.py` 已在 `PARSERS` 字典中预留了 zte/h3c/ruijie 三个 key，等你把占位的 `raise NotImplementedError` 换成真实实现即可）。
