#!/usr/bin/env python3
"""audit.py — 网络设备整机隔离/恢复脚本安全性稽核主入口。

支持的设备类型：
  - DCGW（已实现：上行/下行/互联分类 + 隔离/恢复顺序）

其他设备类型当前为「占位」，调用本脚本时若设备类型非 DCGW，会输出明确提示。

工作流（与 SKILL.md 步骤 6 对应）：
  1. 解析 LLDP
  2. 解析聚合口-物理口映射
  3. 识别设备类型
  4. 对每个本端物理口分类（上行/下行/互联/剩余）
  5. 解析隔离/恢复脚本
  6. 对比预期顺序与实际顺序，稽核完整性、准确性
  7. 输出 Markdown 稽核报告

用法：
  python3 audit.py \\
      --device-name NFV-D-HNZJI-02A-1801-AE02-S-RT-01 \\
      --device-type DCGW \\
      --vendor huawei \\
      --lldp <...> \\
      --trunks <...> \\
      --isolate-script <...> \\
      --recover-script <...> \\
      --output report.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# 允许从脚本所在目录直接 import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_lldp import parse_lldp  # noqa: E402
from parse_trunks import parse_trunks  # noqa: E402
from parse_script import parse_script  # noqa: E402


# ---------- 设备类型 → 端口分类规则 ----------

# DCGW 上行：对端设备名包含以下任一关键字
# 变更记录：v2 起 M-EOR（管理 EOR）从下行调整为上行
DCGW_UPLINK_KEYWORDS = ("CBN", "PC-CMNET", "N-RT", "NETNMS", "NETCN", "NETBOSS", "S-FW", "M-FW", "M-EOR")
DCGW_DOWNLINK_KEYWORDS = ("S-EOR", "LB")
DCGW_INTERCONNECT_KEYWORDS = ("S-RT", "E-RT")


@dataclass
class PortRule:
    uplink: Sequence[str]
    downlink: Sequence[str]
    interconnect: Sequence[str]


RULES: Dict[str, PortRule] = {
    "DCGW": PortRule(
        uplink=DCGW_UPLINK_KEYWORDS,
        downlink=DCGW_DOWNLINK_KEYWORDS,
        interconnect=DCGW_INTERCONNECT_KEYWORDS,
    ),
}


# ---------- 设备类型 → 隔离/恢复顺序 ----------

# v5：跨大类顺序仍以「上行/下行/互联」为骨架；主备子顺序在 audit_order
# 内部、对「上行」/「下行」两段内的防火墙端口作额外检查（不进入
# expected_order）。互联 / 剩余段内的防火墙端口不应用子顺序。
ISO_ORDER: Dict[str, List[str]] = {
    "DCGW": ["上行", "下行", "互联"],
}
REC_ORDER: Dict[str, List[str]] = {
    "DCGW": ["互联", "上行", "下行"],
}


# ---------- 防火墙主备识别（v5） ----------

# 视为「防火墙类」的对端设备名关键字；与 references/device-types.md 对齐：
#   - 业务业支防火墙：`S-FW`
#   - 网管防火墙：    `M-FW`
#   - CMNET 防火墙：  `S-FW` 或 `C-FW`（与业务业支防火墙同名同关键字，靠 LLDP 进一步区分）
#   - 广电防火墙：    `CBN`（例：`YDCBN-FW`）
#
# 注意：`PC-CMNET` 与 `N-RT` 是 CMNET CE（出口路由器）的关键字，
# 不是防火墙关键字，**不要**列入此处。
FW_KEYWORDS_FOR_MASTER_BACKUP: Tuple[str, ...] = (
    "S-FW",  # 业务业支防火墙 / CMNET 防火墙
    "M-FW",  # 网管防火墙
    "C-FW",  # CMNET 防火墙
    "CBN",   # 广电防火墙
)

# 主备子顺序**按防火墙类型分组**检查。同类防火墙内部遵守「隔离 / 恢复
# 都是「先主后备」；不同类防火墙之间顺序自由。
# 顺序越具体（越不普适）越靠前，方便 _fw_type_from_neighbor_dev 取最具体的命中。
FW_TYPE_KEYWORDS: Tuple[str, ...] = ("C-FW", "CBN", "M-FW", "S-FW")

# 主 / 备防火墙设备名的默认后缀
FW_MASTER_SUFFIX = "-01"
FW_BACKUP_SUFFIX = "-02"


# ---------- 数据结构 ----------

@dataclass
class LLDPEntry:
    local_intf: str
    neighbor_dev: str
    neighbor_intf: str
    exptime: Optional[int]

    @classmethod
    def from_dict(cls, d: Dict) -> "LLDPEntry":
        return cls(
            local_intf=d["local_intf"],
            neighbor_dev=d["neighbor_dev"],
            neighbor_intf=d["neighbor_intf"],
            exptime=d.get("exptime"),
        )


@dataclass
class PortInfo:
    """本端端口的分类信息。

    v6：category 仍为 4 大类（上行 / 下行 / 互联 / 剩余），主备信息
    通过独立的 fw_role 和 fw_pair_id 字段携带，**不**作为 category 的子分类。
    主备子顺序的检查粒度为「每对防火墙」，在 audit_order 内部对「上行」/
    「下行」两段内的防火墙端口作额外检查（不进入 expected_order）。
    """
    name: str
    category: str  # 上行 / 下行 / 互联 / 剩余
    neighbor_dev: Optional[str] = None
    neighbor_intf: Optional[str] = None
    trunk: Optional[str] = None  # 所属聚合口（如有）
    fw_role: Optional[str] = None  # "主" / "备" / None（仅防火墙端口有值）
    fw_pair_id: Optional[str] = None  # "Pair-1" / "Pair-2" / ... / None（仅配对成功的防火墙端口有值）


@dataclass
class ScriptOp:
    line_no: int
    iface: str
    op: str
    section: Optional[str]
    raw: str

    @classmethod
    def from_dict(cls, d: Dict) -> "ScriptOp":
        return cls(
            line_no=d["line_no"],
            iface=d["iface"],
            op=d["op"],
            section=d.get("section"),
            raw=d.get("raw", ""),
        )


@dataclass
class TrunkData:
    trunks: Dict[str, List[str]] = field(default_factory=dict)
    standalone_phys: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict) -> "TrunkData":
        return cls(
            trunks=dict(d.get("trunks", {})),
            standalone_phys=list(d.get("standalone_phys", [])),
        )

    def phys_to_trunk(self) -> Dict[str, str]:
        m: Dict[str, str] = {}
        for trunk, members in self.trunks.items():
            for m_ in members:
                m[m_] = trunk
        return m


# ---------- 设备类型识别 ----------

DEVICE_TYPE_KEYWORDS: List[Tuple[str, str]] = [
    # (设备类型, 关键字)
    ("业务 TOR", "S-TOR"),
    ("管理 TOR", "M-TOR"),
    ("存储 TOR", "ST-TOR"),
    ("硬件管理 TOR", "DM-TOR"),
    ("业务 EOR", "S-EOR"),
    ("管理 EOR", "M-EOR"),
    ("存储 EOR", "ST-EOR"),
    ("负载均衡", "LB"),
    ("网管 CE", "NETNMS"),
    ("业务 CE", "NETCN"),
    ("业支 CE", "NETBOSS"),
    ("CMNET CE", "PC-CMNET"),
    ("CMNET CE", "N-RT"),
    ("广电防火墙", "CBN"),
    # 注：S-FW 由 LLDP 二次判定
    ("DCGW", "S-RT"),
    ("DCGW", "E-RT"),
]


def detect_device_type(sysname: str) -> str:
    name = sysname or ""
    for dev_type, kw in DEVICE_TYPE_KEYWORDS:
        if kw in name:
            return dev_type
    return "未知"


# ---------- 端口分类 ----------

def classify_port(
    local_intf: str,
    neighbor_dev: str,
    rule: PortRule,
) -> str:
    """对单个本端物理口做上/下/互联/剩余分类。"""
    nb = neighbor_dev or ""
    for kw in rule.uplink:
        if kw in nb:
            return "上行"
    for kw in rule.downlink:
        if kw in nb:
            return "下行"
    for kw in rule.interconnect:
        if kw in nb:
            return "互联"
    return "剩余"


# ---------- 防火墙主备识别（v5） ----------

def is_firewall_device(neighbor_dev: str) -> bool:
    """判断对端设备是否为防火墙类。

    v4：仅按 `FW_KEYWORDS_FOR_MASTER_BACKUP` 中的关键字识别；
    `PC-CMNET` / `N-RT` 是 CMNET 路由器（CE）的关键字，不是防火墙，已从
    该常量中移除。
    """
    nb = neighbor_dev or ""
    return any(kw in nb for kw in FW_KEYWORDS_FOR_MASTER_BACKUP)


def detect_fw_master_backup(lldp: List[LLDPEntry]) -> Dict[str, str]:
    """识别 LLDP 中的主备防火墙。

    规则（与 port-classification-dcgw.md 对齐）：
      - 对端防火墙设备名以 -01 结尾 → 主
      - 以 -02 结尾 → 备
      - 仅在 -01 / -02 **成对出现** 时才记录；否则该防火墙不标记主备。

    返回：{neighbor_dev: "主" / "备"}。
    """
    fw_devs = {e.neighbor_dev for e in lldp if is_firewall_device(e.neighbor_dev)}
    masters = {d for d in fw_devs if d.endswith(FW_MASTER_SUFFIX)}
    backups = {d for d in fw_devs if d.endswith(FW_BACKUP_SUFFIX)}
    result: Dict[str, str] = {}
    if masters and backups:
        for d in masters:
            result[d] = "主"
        for d in backups:
            result[d] = "备"
    return result


def detect_unpaired_firewalls(lldp: List[LLDPEntry]) -> List[str]:
    """检测未配对的防火墙设备名，用于在发现项中提示人工确认。

    例：LLDP 中只出现 -01、未出现 -02（或反之），会返回该防火墙名。
    """
    fw_devs = {e.neighbor_dev for e in lldp if is_firewall_device(e.neighbor_dev)}
    has_master = any(d.endswith(FW_MASTER_SUFFIX) for d in fw_devs)
    has_backup = any(d.endswith(FW_BACKUP_SUFFIX) for d in fw_devs)
    unpaired: List[str] = []
    if not (has_master and has_backup):
        for d in sorted(fw_devs):
            if d.endswith(FW_MASTER_SUFFIX) and not has_backup:
                unpaired.append(d)
            elif d.endswith(FW_BACKUP_SUFFIX) and not has_master:
                unpaired.append(d)
    return unpaired


# ---------- 防火墙对配对算法（v6） ----------

# v6.1：放宽前缀匹配。原 v6 仅识别 (AE|AF)，但实际 DCGW 拓扑中备机
# S-FW 经常使用 AD / AC 等其它两位大写字母前缀（如
# `NFV-D-HNGZ-14A-3203-AD14-S-FW-02`），导致配对失败、v6 子顺序检查不触发。
# 现在改为任意 2 位大写字母。
_S_FW_NUM_RE = re.compile(r"[A-Z]{2}(\d+)-S-FW-(\d+)")


def _extract_s_fw_number(dev_name: str) -> Optional[int]:
    """从 S-FW 设备名中提取数字标识。

    格式：<任意 2 位大写字母><数字>-S-FW-<01|02>
    例如：NFV-D-HNZJI-02A-1801-AE09-S-FW-01 → 数字 = 9
          NFV-D-HNZJI-02A-1801-AF04-S-FW-02 → 数字 = 4
          NFV-D-HNGZ-14A-3203-AD14-S-FW-02 → 数字 = 14 （v6.1 起也识别）

    返回：int 或 None（不是 S-FW 格式时）
    """
    m = _S_FW_NUM_RE.search(dev_name)
    if m:
        return int(m.group(1))
    return None


def detect_fw_pairs(lldp: List[LLDPEntry]) -> Dict[str, Tuple[str, str]]:
    """检测 LLDP 中的防火墙对（fw_pair_id → (master_dev, backup_dev)）。

    v6 算法：
    - M-FW / CBN / C-FW：按 -01/-02 后缀直接配对（同类型内）
    - S-FW：按数字接近度两两配对（见 port-classification-dcgw.md v6 说明）

    返回：{fw_pair_id: (master_dev, backup_dev)}
    例如：
      {
        "Pair-S-FW-1": ("NFV-D-HNZJI-02A-1801-AE09-S-FW-01", "NFV-D-HNZJI-02A-1801-AF08-S-FW-02"),
        "Pair-S-FW-2": ("NFV-D-HNZJI-02A-1801-AE04-S-FW-01", "NFV-D-HNZJI-02A-1801-AF04-S-FW-02"),
        "Pair-CBN-1": ("NFV-D-HNZJI-02A-1801-AE15-YDCBN-FW-01", "NFV-D-HNZJI-02A-1801-AF14-YDCBN-FW-02"),
      }
    """
    fw_entries = [e for e in lldp if is_firewall_device(e.neighbor_dev)]
    if not fw_entries:
        return {}

    # v6.1：先按设备名去重。同一台防火墙可能出现在多个 Eth-Trunk 的
    # 成员口 LLDP 中，不去重的话后续按 -01/-02 配对会得到「同一对多对」
    # 的重复结果。
    unique_fw_devs: List[str] = []
    seen_fw: Set[str] = set()
    for e in fw_entries:
        if e.neighbor_dev not in seen_fw:
            unique_fw_devs.append(e.neighbor_dev)
            seen_fw.add(e.neighbor_dev)

    # Step 1: 按类型分流
    mfw_cbn_cfw_devs: List[str] = []
    sfw_devs: List[Tuple[str, int, str]] = []  # (dev_name, number, role)

    for nb in unique_fw_devs:
        if "M-FW" in nb or "CBN" in nb or "C-FW" in nb:
            mfw_cbn_cfw_devs.append(nb)
        elif "S-FW" in nb:
            num = _extract_s_fw_number(nb)
            if num is not None:
                role = "主" if nb.endswith(FW_MASTER_SUFFIX) else "备"
                sfw_devs.append((nb, num, role))

    pairs: Dict[str, Tuple[str, str]] = {}
    pair_counter = {"S-FW": 1, "M-FW": 1, "C-FW": 1, "CBN": 1}

    # Step 2: M-FW / CBN / C-FW 按 -01/-02 直接配对
    for kw in ("M-FW", "CBN", "C-FW"):
        devs = [d for d in mfw_cbn_cfw_devs if kw in d]
        masters = sorted([d for d in devs if d.endswith(FW_MASTER_SUFFIX)])
        backups = sorted([d for d in devs if d.endswith(FW_BACKUP_SUFFIX)])
        for master in masters:
            for backup in backups:
                pair_id = f"Pair-{kw}-{pair_counter[kw]}"
                pairs[pair_id] = (master, backup)
                pair_counter[kw] += 1
                break  # 每个 master 只配一个 backup

    # Step 3: S-FW 按数字接近度配对
    if sfw_devs:
        # 按数字分组
        by_number: Dict[int, List[Tuple[str, str]]] = {}  # number -> [(dev, role), ...]
        for dev, num, role in sfw_devs:
            by_number.setdefault(num, []).append((dev, role))

        # 先处理数字完全相同的组（一定能配对）
        paired_devs: Set[str] = set()
        for num in sorted(by_number.keys()):
            group = by_number[num]
            masters_in_group = [d for d, r in group if r == "主"]
            backups_in_group = [d for d, r in group if r == "备"]
            for master in masters_in_group:
                for backup in backups_in_group:
                    pair_id = f"Pair-S-FW-{pair_counter['S-FW']}"
                    pairs[pair_id] = (master, backup)
                    pair_counter["S-FW"] += 1
                    paired_devs.add(master)
                    paired_devs.add(backup)
                    break

        # 处理跨组配对（数字不同但接近）—— 只配剩余的未配对设备
        remaining = [(d, num, r) for d, num, r in sfw_devs if d not in paired_devs]
        if remaining:
            # 按数字排序后贪心配对：每个 -01 与数字最接近的 -02 配对
            masters_remaining = sorted([(d, num) for d, num, r in remaining if r == "主"], key=lambda x: x[1])
            backups_remaining = sorted([(d, num) for d, num, r in remaining if r == "备"], key=lambda x: x[1])

            for master, master_num in masters_remaining:
                if not backups_remaining:
                    break
                # 找数字最接近的 backup
                best_backup = min(backups_remaining, key=lambda x: abs(x[1] - master_num))
                pair_id = f"Pair-S-FW-{pair_counter['S-FW']}"
                pairs[pair_id] = (master, best_backup[0])
                pair_counter["S-FW"] += 1
                backups_remaining.remove(best_backup)

    return pairs


def detect_fw_master_backup_v6(lldp: List[LLDPEntry]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """识别 LLDP 中的主备防火墙 + 防火墙对映射（v6 版本）。

    返回：
      - fw_role_map: {neighbor_dev: "主" / "备"}
      - fw_pair_map: {neighbor_dev: fw_pair_id}
    """
    pairs = detect_fw_pairs(lldp)
    fw_role_map: Dict[str, str] = {}
    fw_pair_map: Dict[str, str] = {}

    for pair_id, (master, backup) in pairs.items():
        fw_role_map[master] = "主"
        fw_role_map[backup] = "备"
        fw_pair_map[master] = pair_id
        fw_pair_map[backup] = pair_id

    return fw_role_map, fw_pair_map


def classify_port_with_fw_role(
    local_intf: str,
    neighbor_dev: str,
    rule: PortRule,
    fw_role: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """对单个本端物理口做 (大类, fw_role) 分类。

    v5 设计：
      - category 保持 4 大类（上行 / 下行 / 互联 / 剩余），不再展开 subcategory。
      - fw_role 与 category **正交**：fw_role 描述主备角色，在 category=上行
        或 category=下行 且对端为防火墙时影响隔离/恢复子顺序。
    """
    cat = classify_port(local_intf, neighbor_dev, rule)
    return cat, fw_role


# ---------- 核心稽核 ----------

@dataclass
class AuditReport:
    device_name: str
    device_type: str
    vendor: str
    port_table: List[PortInfo]
    trunks: TrunkData
    isolate_ops: List[ScriptOp]
    recover_ops: List[ScriptOp]
    isolate_findings: List[str]
    recover_findings: List[str]
    isolate_expected_order: List[str]
    recover_expected_order: List[str]
    overall: str  # 通过 / 不通过 / 仅供人工复核

    def to_markdown(self) -> str:
        return render_markdown(self)


def build_port_table(
    lldp: List[LLDPEntry],
    trunks: TrunkData,
    rule: PortRule,
) -> List[PortInfo]:
    """构造本端物理口 → 分类信息表。"""
    # v6：先识别防火墙对，填到 fw_role_map 和 fw_pair_map
    fw_role_map, fw_pair_map = detect_fw_master_backup_v6(lldp)

    phys_to_trunk = trunks.phys_to_trunk()
    by_name: Dict[str, PortInfo] = {}

    # 1) 从 LLDP 入手
    for e in lldp:
        if e.local_intf in by_name:
            continue
        fw_role = fw_role_map.get(e.neighbor_dev)
        fw_pair_id = fw_pair_map.get(e.neighbor_dev)
        cat, role = classify_port_with_fw_role(
            e.local_intf, e.neighbor_dev, rule, fw_role=fw_role,
        )
        by_name[e.local_intf] = PortInfo(
            name=e.local_intf,
            category=cat,
            neighbor_dev=e.neighbor_dev,
            neighbor_intf=e.neighbor_intf,
            trunk=phys_to_trunk.get(e.local_intf),
            fw_role=role,
            fw_pair_id=fw_pair_id,
        )

    # 2) 聚合口成员口但未出现在 LLDP 中：继承聚合口分类
    for trunk, members in trunks.trunks.items():
        for m in members:
            if m in by_name:
                continue
            # 聚合口本身的分类以「该聚合口任意一个成员口」的对端为准
            sample_neighbor_dev = None
            sample_neighbor_intf = None
            sample_fw_role = None
            sample_fw_pair_id = None
            for e in lldp:
                if e.local_intf in members:
                    sample_neighbor_dev = e.neighbor_dev
                    sample_neighbor_intf = e.neighbor_intf
                    sample_fw_role = fw_role_map.get(e.neighbor_dev)
                    sample_fw_pair_id = fw_pair_map.get(e.neighbor_dev)
                    break
            cat, role = classify_port_with_fw_role(
                m, sample_neighbor_dev or "", rule, fw_role=sample_fw_role,
            )
            by_name[m] = PortInfo(
                name=m,
                category=cat,
                neighbor_dev=sample_neighbor_dev,
                neighbor_intf=sample_neighbor_intf,
                trunk=trunk,
                fw_role=role,
                fw_pair_id=sample_fw_pair_id,
            )

    # 3) 独立物理口但未出现在 LLDP 中：归为「剩余」
    for phys in trunks.standalone_phys:
        if phys in by_name:
            continue
        by_name[phys] = PortInfo(
            name=phys,
            category="剩余",
            neighbor_dev=None,
            neighbor_intf=None,
            trunk=None,
            fw_role=None,
        )

    # 4) 按大类排序：上行 → 下行 → 互联 → 剩余；同名按接口名字典序
    order = {"上行": 0, "下行": 1, "互联": 2, "剩余": 3}
    return sorted(
        by_name.values(),
        key=lambda p: (order.get(p.category, 99), p.name),
    )


def _canon_iface(name: str) -> str:
    """归一化接口名用于比较：去所有空白、保留原始大小写。"""
    return "".join(name.split())


_TRUNK_NUM_RE = re.compile(r"(\d+)\s*$")

_TRUNK_PREFIXES = (
    "eth-trunk", "bridge-aggregation", "route-aggregation",
    "aggregateport", "port-channel",
)


def _is_trunk_name(name: str) -> bool:
    """判断接口名是否为聚合口名。仅在此处返回 True 时才进入 trunk-ID 匹配路径。

    为什么必须先判聚合口：50|100GE1/0/4、GigabitEthernet4/0/6 等物理口
    末尾也有数字， 若不加拦截，会跟 Eth-Trunk4/Eth-Trunk6 错误碰撞。
    """
    s = _canon_iface(name).lower()
    if s.startswith("ap") and len(s) > 2 and s[2].isdigit():
        return True
    return any(s.startswith(p) for p in _TRUNK_PREFIXES)


def _trunk_id(name: str) -> Optional[str]:
    """从聚合口名中提取末尾的数字 ID。

        Eth-Trunk12  -> 12
        Eth-trunk 2  -> 2
        Bridge-Aggregation 5 -> 5
        GigabitEthernet4/0/6  -> None（不是聚合口）
    """
    if not _is_trunk_name(name):
        return None
    s = name.strip()
    s_compact = _canon_iface(s)
    m = _TRUNK_NUM_RE.search(s_compact)
    if m:
        return m.group(1)
    toks = s.split()
    for t in reversed(toks):
        if t.isdigit():
            return t
    return None


def _op_to_category(iface: str, port_table: List[PortInfo], trunks: TrunkData) -> str:
    """把脚本里出现的接口名翻译为 4 大类（上行/下行/互联/剩余）。

    匹配顺序：
      1) 精确匹配（去空白、大小写不敏感）
      2) 聚合口 ID 匹配（脚本写『Eth-trunk 2』、聚合口键为『Eth-Trunk2』）

    返回「混合：X+Y」表示同一聚合口成员跨大类（需人工复核）。
    """
    iface_norm = iface.strip()
    canon = _canon_iface(iface_norm).lower()
    # 1) 物理口
    for p in port_table:
        if _canon_iface(p.name).lower() == canon:
            return p.category
    # 2) 聚合口 — 名称直接匹配
    for trunk, members in trunks.trunks.items():
        if _canon_iface(trunk).lower() == canon:
            cats = {p.category for p in port_table if p.name in members}
            if len(cats) == 1:
                return next(iter(cats))
            if not cats:
                return "剩余"
            return "混合：" + "+".join(sorted(cats))
    # 3) 聚合口 — ID 匹配
    if _is_trunk_name(iface_norm):
        iface_tid = _trunk_id(iface_norm)
        if iface_tid is not None:
            for trunk, members in trunks.trunks.items():
                if _trunk_id(trunk) == iface_tid:
                    cats = {p.category for p in port_table if p.name in members}
                    if len(cats) == 1:
                        return next(iter(cats))
                    if not cats:
                        return "剩余"
                    return "混合：" + "+".join(sorted(cats))
    return "未知"


def _op_to_fw_role(iface: str, port_table: List[PortInfo], trunks: TrunkData) -> Optional[str]:
    """把脚本里出现的接口名翻译为 fw_role（"主" / "备" / None）。

    v4 新增：与 _op_to_category 平行的辅助函数，仅用于 audit_order 的
    「主备子顺序」检查。聚合口成员跨主备时返回 "混合：主+备"。
    """
    iface_norm = iface.strip()
    canon = _canon_iface(iface_norm).lower()
    # 1) 物理口
    for p in port_table:
        if _canon_iface(p.name).lower() == canon:
            return p.fw_role
    # 2) 聚合口 — 名称直接匹配
    for trunk, members in trunks.trunks.items():
        if _canon_iface(trunk).lower() == canon:
            roles = {p.fw_role for p in port_table if p.name in members and p.fw_role}
            if len(roles) == 1:
                return next(iter(roles))
            if not roles:
                return None
            return "混合：" + "+".join(sorted(roles))
    # 3) 聚合口 — ID 匹配
    if _is_trunk_name(iface_norm):
        iface_tid = _trunk_id(iface_norm)
        if iface_tid is not None:
            for trunk, members in trunks.trunks.items():
                if _trunk_id(trunk) == iface_tid:
                    roles = {p.fw_role for p in port_table if p.name in members and p.fw_role}
                    if len(roles) == 1:
                        return next(iter(roles))
                    if not roles:
                        return None
                    return "混合：" + "+".join(sorted(roles))
    return None


def _fw_type_from_neighbor_dev(neighbor_dev: str) -> Optional[str]:
    """根据对端设备名判断防火墙类型关键字（'C-FW' / 'CBN' / 'M-FW' / 'S-FW'）。

    v5 设计：按 `FW_TYPE_KEYWORDS` 顺序取最具体的命中（C-FW / CBN / M-FW 优先于 S-FW）。
    业务业支防火墙与 CMNET 防火墙都用 S-FW 命名，本函数不区分这两种
    业务角色，只做关键字层面分组（同类 S-FW 走同一组）。
    """
    nb = neighbor_dev or ""
    for kw in FW_TYPE_KEYWORDS:
        if kw in nb:
            return kw
    return None


def _op_to_fw_pair_id(iface: str, port_table: List[PortInfo], trunks: TrunkData) -> Optional[str]:
    """把脚本里出现的接口名翻译为 fw_pair_id（"Pair-1" / "Pair-2" / ... / None）。

    v6 新增：与 _op_to_fw_role 平行。聚合口成员跨对时返回 "混合：X+Y"。
    非防火墙接口（fw_pair_id=None）返回 None。
    """
    iface_norm = iface.strip()
    canon = _canon_iface(iface_norm).lower()
    # 1) 物理口
    for p in port_table:
        if _canon_iface(p.name).lower() == canon:
            return p.fw_pair_id
    # 2) 聚合口 — 名称直接匹配
    for trunk, members in trunks.trunks.items():
        if _canon_iface(trunk).lower() == canon:
            pair_ids = {p.fw_pair_id for p in port_table if p.name in members and p.fw_pair_id}
            if len(pair_ids) == 1:
                return next(iter(pair_ids))
            if not pair_ids:
                return None
            return "混合：" + "+".join(sorted(pair_ids))
    # 3) 聚合口 — ID 匹配
    if _is_trunk_name(iface_norm):
        iface_tid = _trunk_id(iface_norm)
        if iface_tid is not None:
            for trunk, members in trunks.trunks.items():
                if _trunk_id(trunk) == iface_tid:
                    pair_ids = {p.fw_pair_id for p in port_table if p.name in members and p.fw_pair_id}
                    if len(pair_ids) == 1:
                        return next(iter(pair_ids))
                    if not pair_ids:
                        return None
                    return "混合：" + "+".join(sorted(pair_ids))
    return None


def _op_to_fw_type(iface: str, port_table: List[PortInfo], trunks: TrunkData) -> Optional[str]:
    """把脚本里出现的接口名翻译为防火墙类型（S-FW / M-FW / C-FW / CBN / None）。

    v5 新增：与 _op_to_fw_role 平行。聚合口成员跨类型时返回 "混合：X+Y"。
    非防火墙接口（fw_role=None）返回 None。
    """
    iface_norm = iface.strip()
    canon = _canon_iface(iface_norm).lower()
    # 1) 物理口
    for p in port_table:
        if _canon_iface(p.name).lower() == canon:
            if not p.fw_role:
                return None
            return _fw_type_from_neighbor_dev(p.neighbor_dev or "")
    # 2) 聚合口 — 名称直接匹配
    for trunk, members in trunks.trunks.items():
        if _canon_iface(trunk).lower() == canon:
            types: Set[str] = set()
            for p in port_table:
                if p.name in members and p.fw_role:
                    t = _fw_type_from_neighbor_dev(p.neighbor_dev or "")
                    if t:
                        types.add(t)
            if len(types) == 1:
                return next(iter(types))
            if not types:
                return None
            return "混合：" + "+".join(sorted(types))
    # 3) 聚合口 — ID 匹配
    if _is_trunk_name(iface_norm):
        iface_tid = _trunk_id(iface_norm)
        if iface_tid is not None:
            for trunk, members in trunks.trunks.items():
                if _trunk_id(trunk) == iface_tid:
                    types = set()
                    for p in port_table:
                        if p.name in members and p.fw_role:
                            t = _fw_type_from_neighbor_dev(p.neighbor_dev or "")
                            if t:
                                types.add(t)
                    if len(types) == 1:
                        return next(iter(types))
                    if not types:
                        return None
                    return "混合：" + "+".join(sorted(types))
    return None


def audit_order(
    ops: List[ScriptOp],
    port_table: List[PortInfo],
    trunks: TrunkData,
    expected_order: List[str],
    unpaired_firewalls: Optional[List[str]] = None,
    direction: str = "isolate",
) -> List[str]:
    """按 expected_order 检查 ops 的实际顺序，输出发现项。

    v5：
      - expected_order 是 4 大类序列（["上行", "下行", "互联"] 等）。
      - 主备子顺序**按防火墙类型分组**检查：
          - 适用段：上行 + 下行（v4 仅上行，v5 修正：CMNET CE 等设备的
            防火墙端口在「下行」段，也要走子顺序）。
          - 同类防火墙内部（按关键字 S-FW / M-FW / C-FW / CBN 分组）：
              隔离与恢复都「**先主后备**」（主在前、备在后）。
          - 不同类防火墙之间顺序自由。
        例子（隔离脚本，上行段同时连多对防火墙）：
            [业务业支-主, 业务业支-备, 广电-主, 广电-备, 业务业支-主, 业务业支-备, ...]
            只要业务业支内部「先主后备」、广电内部「先主后备」即可，业务业支和
            广电之间谁先谁后都允许。

    direction 取值：
      - "isolate"：隔离（上行 → 下行 → 互联）
      - "recover"：恢复（互联 → 上行 → 下行）

    unpaired_firewalls：从 LLDP 推导出的未配对防火墙列表。
    """
    findings: List[str] = []
    if not ops:
        findings.append("脚本中未识别到任何 shutdown/undo shutdown 操作，请人工复核脚本是否完整。")
        if unpaired_firewalls:
            findings.append(
                "未配对防火墙（需人工确认主备关系）：" + "、".join(unpaired_firewalls)
            )
        return findings

    # 翻译为大类序列 + fw_role 序列 + fw_type 序列
    # v5：fw_type 用于「按类型分组」的主备子顺序检查。
    actual_seq: List[Tuple[int, str, str, Optional[str], Optional[str]]] = []  # (line_no, iface, cat, role, ftype)
    for op in ops:
        cat = _op_to_category(op.iface, port_table, trunks)
        role = _op_to_fw_role(op.iface, port_table, trunks)
        ftype = _op_to_fw_type(op.iface, port_table, trunks) if role else None
        actual_seq.append((op.line_no, op.iface, cat, role, ftype))

    # 检查 1：大类顺序 + 非预期分类（去重）
    cat_only = [c for _, _, c, _, _ in actual_seq]
    unexpected_cats: Set[str] = set()
    for c in cat_only:
        if c not in expected_order:
            unexpected_cats.add(c)
    for c in sorted(unexpected_cats):
        if c == "未知":
            findings.append(
                "存在脚本中操作但未在 LLDP / 聚合口数据中出现的接口，请人工核对拓扑与脚本是否一致。"
            )
        elif c == "剩余":
            findings.append(
                "脚本中操作的接口在 LLDP 中被归为「剩余」分类（拓扑上无法判定上 / 下 / 互联），"
                "需人工确认这些接口在隔离 / 恢复中是否真的不应处理。"
            )
        elif c.startswith("混合"):
            findings.append(
                f"存在跨多分类的聚合口：{c}，脚本仅关闭聚合口本身可能不够，需人工复核。"
            )
        else:
            findings.append(f"存在未识别分类的接口：{c}，请人工复核。")

    # 大类顺序检查：仅记录「出现的实际大类序列」是否与期望顺序一致。
    seen_so_far: List[str] = []
    first_seen_cat: Optional[str] = None
    for _line_no, _iface, c, _, _ in actual_seq:
        if c in expected_order:
            if first_seen_cat is None:
                first_seen_cat = c
            if not seen_so_far or seen_so_far[-1] != c:
                seen_so_far.append(c)
    if first_seen_cat is not None and first_seen_cat != expected_order[0]:
        findings.append(
            f"顺序异常：脚本起始分类为 {first_seen_cat}，但期望从 {expected_order[0]} 开始，"
            f"期望顺序：{ '→'.join(expected_order) }。"
        )
    for i in range(1, len(seen_so_far)):
        if expected_order.index(seen_so_far[i]) < expected_order.index(seen_so_far[i - 1]):
            findings.append(
                f"顺序异常：脚本中期望分类出现顺序为 { '→'.join(seen_so_far) }，"
                f"与期望顺序 { '→'.join(expected_order) } 不一致。"
            )
            break

    # v6：防火墙主备子顺序（按对检查）
    # 适用段：上行 + 下行
    # 分组粒度：按防火墙对（fw_pair_id）逐对独立检查
    # 隔离子顺序：所有备边端口操作在前，所有主边端口操作在后
    # 恢复子顺序：所有主边端口操作在前，所有备边端口操作在后
    # 跨对顺序自由。

    # 构建 fw_pair_id → [(line_no, iface, role), ...] 的映射
    fw_pair_ops: Dict[str, List[Tuple[int, str, str]]] = {}
    for ln, iface, cat, role, ftype in actual_seq:
        if cat in ("上行", "下行") and role in ("主", "备"):
            # 通过 iface 查找对应的 fw_pair_id
            pair_id = _op_to_fw_pair_id(iface, port_table, trunks)
            if pair_id:
                fw_pair_ops.setdefault(pair_id, []).append((ln, iface, role))

    for pair_id, ops_in_pair in fw_pair_ops.items():
        # 按行号排序（确保按脚本中出现的顺序）
        ops_in_pair.sort(key=lambda x: x[0])

        # v6.2：构造「建议的正常顺序」—— 在异常发现项中补充列出
        # 该对在本脚本中应有的正确顺序（用本脚本中实际出现的接口 +
        # 行号），便于审计人员据此直接调整脚本，不停留在抽象描述。
        # 隔离：先全部备，再全部主；恢复：先全部主，再全部备。
        backups_in_pair = sorted(
            [(ln, iface) for ln, iface, role in ops_in_pair if role == "备"],
            key=lambda x: x[0],
        )
        masters_in_pair = sorted(
            [(ln, iface) for ln, iface, role in ops_in_pair if role == "主"],
            key=lambda x: x[0],
        )

        if direction == "isolate":
            # 隔离：所有备边端口必须在所有主边端口之前
            # 一旦出现第一个主，后续不能再出现备
            first_master_line: Optional[int] = None
            backup_after_master: List[Tuple[int, str]] = []
            for ln, iface, role in ops_in_pair:
                if role == "备":
                    if first_master_line is not None:
                        backup_after_master.append((ln, iface))
                elif role == "主" and first_master_line is None:
                    first_master_line = ln
            if backup_after_master:
                lines = ", ".join(f"行 {ln}({iface})" for ln, iface in backup_after_master)
                # 期望（建议）的正常顺序：先全部备、再全部主
                expected_parts: List[str] = []
                if backups_in_pair:
                    backup_list = "、".join(
                        f"行 {ln}({iface})" for ln, iface in backups_in_pair
                    )
                    expected_parts.append(f"先全部备边端口（{backup_list}）")
                if masters_in_pair:
                    master_list = "、".join(
                        f"行 {ln}({iface})" for ln, iface in masters_in_pair
                    )
                    expected_parts.append(f"再全部主边端口（{master_list}）")
                expected_str = "，".join(expected_parts)
                findings.append(
                    f"防火墙对 {pair_id} 主备子顺序异常：隔离应「先全部备边端口再全部主边端口」，"
                    f"但 {lines} 出现在主防火墙操作之后。"
                    f"建议的正常操作顺序：{expected_str}。"
                )
        elif direction == "recover":
            # 恢复：所有主边端口必须在所有备边端口之前
            # 一旦出现第一个备，后续不能再出现主
            first_backup_line: Optional[int] = None
            master_after_backup: List[Tuple[int, str]] = []
            for ln, iface, role in ops_in_pair:
                if role == "主":
                    if first_backup_line is not None:
                        master_after_backup.append((ln, iface))
                elif role == "备" and first_backup_line is None:
                    first_backup_line = ln
            if master_after_backup:
                lines = ", ".join(f"行 {ln}({iface})" for ln, iface in master_after_backup)
                # 期望（建议）的正常顺序：先全部主、再全部备
                expected_parts: List[str] = []
                if masters_in_pair:
                    master_list = "、".join(
                        f"行 {ln}({iface})" for ln, iface in masters_in_pair
                    )
                    expected_parts.append(f"先全部主边端口（{master_list}）")
                if backups_in_pair:
                    backup_list = "、".join(
                        f"行 {ln}({iface})" for ln, iface in backups_in_pair
                    )
                    expected_parts.append(f"再全部备边端口（{backup_list}）")
                expected_str = "，".join(expected_parts)
                findings.append(
                    f"防火墙对 {pair_id} 主备子顺序异常：恢复应「先全部主边端口再全部备边端口」，"
                    f"但 {lines} 出现在备防火墙操作之后。"
                    f"建议的正常操作顺序：{expected_str}。"
                )

    # 未配对防火墙提示
    if unpaired_firewalls:
        findings.append(
            "未配对防火墙（需人工确认主备关系，主备子顺序未生效）："
            + "、".join(unpaired_firewalls)
        )

    # 检查 2：聚合口与成员口不能重复关闭
    seen_trunks: Set[str] = set()  # 存的 key 是 _trunk_id
    seen_phys: Set[str] = set()
    phys_to_trunk = trunks.phys_to_trunk()
    for op in ops:
        # 只有「看起来是聚合口」的名字才走 trunk-ID 去重
        is_trunk = _is_trunk_name(op.iface)
        trunk_match: Optional[str] = None
        tid = _trunk_id(op.iface) if is_trunk else None
        if tid is not None:
            for trunk, members in trunks.trunks.items():
                if _trunk_id(trunk) == tid:
                    trunk_match = trunk
                    break
        if trunk_match is not None:
            if tid in seen_trunks:
                findings.append(
                    f"聚合口 {op.iface} 重复操作（行 {op.line_no}），请确认是否有冗余命令。"
                )
            seen_trunks.add(tid or "")
            for m in trunks.trunks[trunk_match]:
                if _canon_iface(m).lower() in seen_phys:
                    findings.append(
                        f"成员口 {m} 在聚合口 {trunk_match} 之外被重复操作。"
                    )
        else:
            # 检查是否命中成员口或独立物理口
            canon = _canon_iface(op.iface).lower()
            matched_member: Optional[str] = None
            for phys, trunk in phys_to_trunk.items():
                if _canon_iface(phys).lower() == canon:
                    matched_member = phys
                    break
            if matched_member is not None:
                trunk = phys_to_trunk[matched_member]
                trunk_tid = _trunk_id(trunk) or ""
                if trunk_tid in seen_trunks:
                    findings.append(
                        f"成员口 {op.iface} 已被其所属聚合口 {trunk} 覆盖（行 {op.line_no}），疑似重复。"
                    )
                seen_phys.add(canon)
            else:
                if canon in seen_phys:
                    findings.append(f"独立物理口 {op.iface} 重复操作。")
                seen_phys.add(canon)

    # 检查 3：完整性 — 期望关闭的物理口是否都覆盖
    #    v4：仍按 p.category 判定（subcategory 已移除），主备子分类不参与覆盖判定
    expected_ports = [p for p in port_table if p.category in expected_order]
    covered: Set[str] = set()
    for op in ops:
        canon = _canon_iface(op.iface).lower()
        # 优先按 ID 匹配聚合口
        tid = _trunk_id(op.iface)
        matched_trunk = None
        if tid is not None:
            for trunk in trunks.trunks:
                if _trunk_id(trunk) == tid:
                    matched_trunk = trunk
                    break
        if matched_trunk is not None:
            for m in trunks.trunks[matched_trunk]:
                covered.add(_canon_iface(m).lower())
        else:
            covered.add(canon)
    missing = [p for p in expected_ports if _canon_iface(p.name).lower() not in covered]
    if missing:
        findings.append(
            "缺少以下应操作的端口（不在脚本内）：" +
            "、".join(f"{p.name}({p.category})" for p in missing)
        )

    return findings


def _annotate_ops_legality(ops: List[ScriptOp], port_table: List[PortInfo],
                           trunks: TrunkData, expected_order: List[str]) -> List[Tuple[ScriptOp, str, str, str]]:
    """为每条 op 给出 (op, 期望分类, 实际分类, 合法性) 的元组列表。

    v4：使用 4 大类（上行 / 下行 / 互联 / 剩余）做顺序比对。
    主备子顺序的合法性由 audit_order 额外报出，不在每行 op 上展开。

    合法性 = 『通过』/『异常：xxx』。
    """
    results: List[Tuple[ScriptOp, str, str, str]] = []
    last_idx = -1
    last_cat: Optional[str] = None
    for i, op in enumerate(ops):
        actual = _op_to_category(op.iface, port_table, trunks)
        if actual in expected_order:
            cur_idx = expected_order.index(actual)
            # 期望顺序中的分类。last_idx 为 -1 表示还没遇到任何期望分类
            # 的接口，此时出现的分类是哪个，就以哪个为“起企”。
            if last_idx < 0:
                # 首条 op 决定起企位置。若其不是第一个期望分类，标记为起企违反
                if cur_idx > 0:
                    legality = (
                        f"异常：期望起始分类 {expected_order[0]}，"
                        f"但首条 op 为 {actual}（顺序 {cur_idx+1}/{len(expected_order)}）"
                    )
                else:
                    legality = "通过"
                last_idx = cur_idx
                last_cat = actual
            elif cur_idx < last_idx:
                legality = (
                    f"异常：违反期望顺序。"
                    f"前面已出现 {last_cat}（{last_idx+1}/{len(expected_order)}），"
                    f"本 op 为 {actual}（{cur_idx+1}/{len(expected_order)}）"
                )
            else:
                legality = "通过"
                if cur_idx > last_idx:
                    last_idx = cur_idx
                    last_cat = actual
            expected_cat = actual
        elif actual in ("未知",):
            legality = "异常：接口未在 LLDP/聚合口数据中出现"
            expected_cat = "—"
        elif "混合" in actual:
            legality = f"异常：聚合口成员跨多分类（{actual}）"
            expected_cat = "—"
        elif actual == "剩余":
            legality = "异常：接口在剩余分类，需人工确认是否应关闭/恢复"
            expected_cat = "剩余"
        else:
            legality = f"异常：未知分类 {actual}"
            expected_cat = "—"
        results.append((op, expected_cat, actual, legality))
    return results


def _md_cell(value: Optional[str], *, code: bool = False, default: str = "-") -> str:
    """把任意值安全地写入 Markdown 表格单元格。

    关键点：华为路由器的 50|100GE 接口名本身就含 | 字符。如果不处理，
    Markdown 渲染器会把它当作新的列边界，导致整行错位、表格断成两半。

    这里同时做两件事保证跨渲染器一致：
      1) | → \\|    （GFM/CommonMark 支持反斜杠转义）
      2) code=True 时再包一层反引号代码片段（CommonMark 规范保证代码片段内的 |
         不会被识别为列分隔符，作为 \\| 不被识别时的兜底）

    None / 空串统一渲染为占位符（默认 "-"），避免空单元格被部分渲染器
    折叠。
    """
    if value is None or str(value) == "":
        return default
    text = str(value).replace("|", "\\|")
    if code:
        text = f"`{text}`"
    return text


def render_markdown(r: AuditReport) -> str:
    out: List[str] = []
    out.append("# 网络设备整机隔离/恢复脚本安全性稽核报告\n")
    out.append(f"- 被稽核设备：`{_md_cell(r.device_name)}`")
    out.append(f"- 设备类型：**{_md_cell(r.device_type)}**")
    out.append(f"- 设备厂家：{_md_cell(r.vendor)}")
    out.append("")

    out.append("## 一、LLDP 端口分类（带聚合口关联）\n")
    out.append("| 本端物理口 | 对端设备 | 对端接口 | 所属聚合口 | 端口分类 | 主备 | 防火墙对 |")
    out.append("| --- | --- | --- | --- | --- | --- | --- |")
    for p in r.port_table:
        out.append(
            "| " + " | ".join([
                _md_cell(p.name, code=True),
                _md_cell(p.neighbor_dev),
                _md_cell(p.neighbor_intf, code=True),
                _md_cell(p.trunk, code=True),
                f"**{_md_cell(p.category)}**",
                _md_cell(p.fw_role) if p.fw_role else "-",
                _md_cell(p.fw_pair_id) if p.fw_pair_id else "-",
            ]) + " |"
        )
    out.append("")

    out.append("## 二、隔离脚本稽核\n")
    out.append(f"**期望顺序**：{' → '.join(_md_cell(o) for o in r.isolate_expected_order) if r.isolate_expected_order else '（未配置）'}")
    out.append("")
    if r.isolate_ops:
        out.append("| 序号 | 行号 | 接口 | 操作 | 期望分类 | 实际分类 | 合法性 |")
        out.append("| --- | --- | --- | --- | --- | --- | --- |")
        for i, (op, exp, act, leg) in enumerate(
            _annotate_ops_legality(r.isolate_ops, r.port_table, r.trunks, r.isolate_expected_order), 1
        ):
            out.append(
                "| " + " | ".join([
                    str(i),
                    str(op.line_no),
                    _md_cell(op.iface, code=True),
                    _md_cell(op.op),
                    _md_cell(exp),
                    _md_cell(act),
                    _md_cell(leg),
                ]) + " |"
            )
    else:
        out.append("> 脚本中未识别到任何 shutdown 操作。")
    out.append("")
    if r.isolate_findings:
        out.append("**发现项**：")
        for f in r.isolate_findings:
            out.append(f"- {f}")
    else:
        out.append("**发现项**：无")
    out.append("")

    out.append("## 三、恢复脚本稽核\n")
    out.append(f"**期望顺序**：{' → '.join(_md_cell(o) for o in r.recover_expected_order) if r.recover_expected_order else '（未配置）'}")
    out.append("")
    if r.recover_ops:
        out.append("| 序号 | 行号 | 接口 | 操作 | 期望分类 | 实际分类 | 合法性 |")
        out.append("| --- | --- | --- | --- | --- | --- | --- |")
        for i, (op, exp, act, leg) in enumerate(
            _annotate_ops_legality(r.recover_ops, r.port_table, r.trunks, r.recover_expected_order), 1
        ):
            out.append(
                "| " + " | ".join([
                    str(i),
                    str(op.line_no),
                    _md_cell(op.iface, code=True),
                    _md_cell(op.op),
                    _md_cell(exp),
                    _md_cell(act),
                    _md_cell(leg),
                ]) + " |"
            )
    else:
        out.append("> 脚本中未识别到任何 undo shutdown 操作。")
    out.append("")
    if r.recover_findings:
        out.append("**发现项**：")
        for f in r.recover_findings:
            out.append(f"- {f}")
    else:
        out.append("**发现项**：无")
    out.append("")

    out.append("## 四、整体结论\n")
    out.append(f"**{_md_cell(r.overall)}**\n")
    if r.isolate_findings or r.recover_findings:
        out.append("请按上述发现项人工复核后再执行操作。")
    else:
        out.append("脚本与拓扑一致，可按顺序执行。")
    out.append("")

    return "\n".join(out)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="网络设备整机隔离/恢复脚本安全性稽核")
    parser.add_argument("--device-name", required=True, help="被稽核设备的本端名称（sysname）")
    parser.add_argument("--device-type", default="",
                        help="设备类型（DCGW/业务EOR/...），留空则按名称自动识别")
    parser.add_argument("--vendor", default="huawei", help="设备厂家（默认 huawei）")
    parser.add_argument("--lldp", required=True, help="LLDP 邻居摘要文件")
    parser.add_argument("--trunks", required=True, help="聚合口-物理口映射文件（display interface brief）")
    parser.add_argument("--isolate-script", required=True, help="整机隔离脚本")
    parser.add_argument("--recover-script", required=True, help="整机恢复脚本")
    parser.add_argument("--output", "-o", default="-", help="报告输出路径（默认 stdout）")
    args = parser.parse_args(list(argv) if argv is not None else None)

    dev_type = args.device_type.strip() or detect_device_type(args.device_name)
    lldp_text = Path(args.lldp).read_text(encoding="utf-8", errors="replace")
    trunks_text = Path(args.trunks).read_text(encoding="utf-8", errors="replace")
    iso_text = Path(args.isolate_script).read_text(encoding="utf-8", errors="replace")
    rec_text = Path(args.recover_script).read_text(encoding="utf-8", errors="replace")

    lldp = [LLDPEntry.from_dict(r) for r in parse_lldp(lldp_text, args.vendor)]
    trunks = TrunkData.from_dict(parse_trunks(trunks_text, args.vendor))

    if dev_type not in RULES:
        msg = (
            f"设备类型 {dev_type!r} 暂未实现稽核规则。\n"
            "请先在 references/port-classification-others.md 中补充该类型的上/下/互联规则，\n"
            "并在 references/isolation-order.md 中定义隔离/恢复顺序。\n"
            "本稽核器支持：{}".format(", ".join(RULES.keys()))
        )
        sys.stderr.write(msg + "\n")
        rule = PortRule(uplink=(), downlink=(), interconnect=())
        port_table = build_port_table(lldp, trunks, rule)
        iso_ops = [ScriptOp.from_dict(d) for d in parse_script(iso_text, args.vendor)]
        rec_ops = [ScriptOp.from_dict(d) for d in parse_script(rec_text, args.vendor)]
        report = AuditReport(
            device_name=args.device_name,
            device_type=dev_type,
            vendor=args.vendor,
            port_table=port_table,
            trunks=trunks,
            isolate_ops=iso_ops,
            recover_ops=rec_ops,
            isolate_findings=[msg],
            recover_findings=[],
            isolate_expected_order=[],
            recover_expected_order=[],
            overall="仅供人工复核（设备类型未实现）",
        )
        md = report.to_markdown()
        if args.output == "-":
            sys.stdout.write(md)
        else:
            Path(args.output).write_text(md, encoding="utf-8")
        return 0

    rule = RULES[dev_type]
    expected_iso = ISO_ORDER[dev_type]
    expected_rec = REC_ORDER[dev_type]

    port_table = build_port_table(lldp, trunks, rule)

    # v3：未配对防火墙检测
    unpaired = detect_unpaired_firewalls(lldp)

    iso_ops = [ScriptOp.from_dict(d) for d in parse_script(iso_text, args.vendor)]
    rec_ops = [ScriptOp.from_dict(d) for d in parse_script(rec_text, args.vendor)]

    iso_findings = audit_order(
        iso_ops, port_table, trunks, expected_iso,
        unpaired_firewalls=unpaired, direction="isolate",
    )
    rec_findings = audit_order(
        rec_ops, port_table, trunks, expected_rec,
        unpaired_firewalls=unpaired, direction="recover",
    )

    overall = "通过"
    if iso_findings or rec_findings:
        overall = "不通过（存在发现项）"

    report = AuditReport(
        device_name=args.device_name,
        device_type=dev_type,
        vendor=args.vendor,
        port_table=port_table,
        trunks=trunks,
        isolate_ops=iso_ops,
        recover_ops=rec_ops,
        isolate_findings=iso_findings,
        recover_findings=rec_findings,
        isolate_expected_order=expected_iso,
        recover_expected_order=expected_rec,
        overall=overall,
    )

    md = report.to_markdown()
    if args.output == "-":
        sys.stdout.write(md)
    else:
        Path(args.output).write_text(md, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
