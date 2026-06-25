#!/usr/bin/env python3
"""parse_lldp.py — 解析 LLDP 邻居摘要。

支持的厂家：
  - huawei（默认；VRP V800，display lldp neighbor brief）
  - h3c（Comware V7，display lldp neighbor-information list）

中兴、锐捷为占位，需要时再扩展。

输出：JSON 数组，每个元素包含
  {
    "local_intf":   本端物理口（已 strip）
    "neighbor_dev": 对端设备名
    "neighbor_intf": 对端接口
    "exptime":      TTL（秒；解析失败时为 None）
  }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Any, Tuple


def _strip_bom(s: str) -> str:
    return s.lstrip("\ufeff")


def _is_separator(line: str) -> bool:
    return bool(re.match(r"^[\s-]+$", line)) and "-" in line


_INTF_PREFIXES = (
    "TenGigabitEthernet",
    "XGigabitEthernet",
    "HundredGigE",
    "TwentyFiveGigE",
    "Ten-GigabitEthernet",
    "GigabitEthernet",
    "FastEthernet",
    "xgei", "cgei", "gei", "xei",
    "50|100GE", "100GE", "40GE", "25GE", "10GE", "GE",
    "Eth-Trunk", "Bridge-Aggregation", "Route-Aggregation", "Port-Channel",
    "BVI", "Loopback",
)


def _split_neighbor_middle(middle: str) -> Tuple[str, str]:
    """拆分『对端设备 + 对端接口』合并的字符串。

    启发式（按优先级）：
      1) 从右向左扫描，找到首个以已知接口前缀开头的 token；该 token 及
         其之后所有 token 作为对端接口，其余作为对端设备名。
         这一规则同时覆盖华为、中兴、华三、锐捷：
           - Huawei: 50|100GE1/0/0, 100GE5/0/0, 10GE2/0/7
           - H3C:    Ten-GigabitEthernet6/0/20
           - ZTE:    cgei-0/0/0/2, xgei-0/0/0/5
           - Ruijie: TenGigabitEthernet 1/0/2（最后一个 token 无前缀、
                     倒数第二个才是接口名）
      2) 退化：取最右 token 作为对端接口。
    """
    toks = middle.split()
    if not toks:
        return "", ""
    for i in range(len(toks) - 1, -1, -1):
        for prefix in _INTF_PREFIXES:
            if toks[i].startswith(prefix):
                return " ".join(toks[:i]), " ".join(toks[i:])
    return " ".join(toks[:-1]), toks[-1]


def parse_huawei(text: str) -> List[Dict[str, Any]]:
    if "Nbr system name" in text and "Nbr chassis ID" in text:
        return parse_neighbor_information_list(text)

    rows: List[Dict[str, Any]] = []
    for raw in text.splitlines():
        line = _strip_bom(raw).rstrip()
        if not line.strip():
            continue
        if _is_separator(line):
            continue
        # 跳过表头
        if line.lstrip().lower().startswith("local intf"):
            continue
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 4:
            local_intf = parts[0]
            neighbor_dev = parts[1]
            neighbor_intf = parts[2]
            exptime = parts[3]
        elif len(parts) == 3:
            # 形如：`GigabitEthernet4/0/6  WTT... TenGigabitEthernet 1/0/2  99`
            # parts[1] 把『对端设备 + 对端接口』合在一起，需要二次拆分
            local_intf = parts[0]
            neighbor_dev, neighbor_intf = _split_neighbor_middle(parts[1])
            exptime = parts[2]
        else:
            # 退化为单空白切分
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            local_intf = parts[0]
            exptime = parts[-1]
            neighbor_dev, neighbor_intf = _split_neighbor_middle(" ".join(parts[1:-1]))
        exptime_val: Any
        try:
            exptime_val = int(exptime)
        except (TypeError, ValueError):
            exptime_val = None
        rows.append({
            "local_intf": local_intf,
            "neighbor_dev": neighbor_dev.strip(),
            "neighbor_intf": neighbor_intf.strip(),
            "exptime": exptime_val,
        })
    return rows


def parse_neighbor_information_list(text: str) -> List[Dict[str, Any]]:
    """解析 `display lldp neighbor-information list` 表格。

    该格式列为：LocalIf / Nbr chassis ID / Nbr port ID / Nbr system name。
    和 `neighbor brief` 相比，对端设备名在最后一列，而不是第二列。
    """
    rows: List[Dict[str, Any]] = []
    in_table = False
    for raw in text.splitlines():
        line = _strip_bom(raw).rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("LocalIf") and "Nbr system name" in stripped:
            in_table = True
            continue
        if not in_table:
            continue

        parts = re.split(r"\s{2,}", stripped)
        if len(parts) < 4:
            continue
        local_intf, _chassis_id, neighbor_intf, neighbor_dev = parts[:4]
        rows.append({
            "local_intf": local_intf.strip(),
            "neighbor_dev": neighbor_dev.strip(),
            "neighbor_intf": neighbor_intf.strip(),
            "exptime": None,
        })
    return rows


def parse_lldp(text: str, vendor: str) -> List[Dict[str, Any]]:
    vendor = vendor.lower()
    if vendor in ("huawei", "h3c"):
        return parse_huawei(text)
    raise NotImplementedError(
        f"厂商 {vendor!r} 的 LLDP 解析尚未实现，请先在 references/parser-{vendor}.md 补充样例。"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="解析 LLDP 邻居摘要")
    parser.add_argument("path", help="LLDP 摘要文件路径")
    parser.add_argument("--vendor", default="huawei", help="厂商（默认 huawei）")
    parser.add_argument("--indent", type=int, default=2, help="JSON 缩进")
    args = parser.parse_args(list(argv) if argv is not None else None)

    text = Path(args.path).read_text(encoding="utf-8", errors="replace")
    rows = parse_lldp(text, args.vendor)
    json.dump(rows, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
