#!/usr/bin/env python3
"""parse_trunks.py — 解析聚合口与成员物理口映射关系。

支持的厂家：
  - huawei（默认；VRP V800，display interface brief）
  - h3c（Comware V7，display link-aggregation verbose）

中兴、锐捷为占位。

输出：JSON 对象
  {
    "trunks": {
      "<Eth-Trunk N>": ["<物理口1>", "<物理口2>", ...],
      ...
    },
    "standalone_phys": ["<未加入聚合的物理口1>", ...]
  }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Iterable


# 已知的「逻辑/虚拟」接口前缀，解析时跳过
LOGICAL_PREFIXES = (
    "LoopBack",
    "MEth",
    "NULL",
    "Vlanif",
    "VInterface",
    "Tunnel",
    "VBDIF",
    "Vbdif",
    "Nve",
    "Dialer",
    "InLoopBack",
    "Register-Tunnel",
    "Virtual-Template",
    "Cellular",
    "Aux",
    "Console",
    "Bridge-Aggregation",  # 华三风格，独立检查
    "Route-Aggregation",   # 华三风格，独立检查
    "AggregatePort",       # 锐捷风格，独立检查
)

# 描述接口名后可能出现的速率后缀，例如 (100G)、(10G)
RATE_SUFFIX = re.compile(r"\([0-9A-Za-z]+\)\s*$")

# 描述行尾的 *down、^down 等状态标记
STATE_SUFFIX = re.compile(r"(\*down|\^down|\(s\)|\(l\)|\(b\)|\(c\)|\(p\)|\(ld\)|\(mf\)|\(sd\)|\(e\)|\(B\)|\(E\)|\(d\))\s*$")


def _strip_bom(s: str) -> str:
    return s.lstrip("\ufeff")


def _is_logical(name: str) -> bool:
    return any(name.startswith(p) for p in LOGICAL_PREFIXES)


def _clean_iface(name: str) -> str:
    """去掉速率后缀、状态后缀，保留可比较的接口名。"""
    n = name.strip()
    n = RATE_SUFFIX.sub("", n)
    n = STATE_SUFFIX.sub("", n).strip()
    return n


def parse_huawei(text: str) -> Dict[str, object]:
    if "Aggregate Interface:" in text and "Loadsharing Type:" in text:
        return parse_link_aggregation_verbose(text)

    trunks: Dict[str, List[str]] = {}
    standalone: List[str] = []
    seen_phys: Set[str] = set()

    lines = text.splitlines()
    # 找到表头行
    header_idx = None
    for i, raw in enumerate(lines):
        line = _strip_bom(raw).lstrip()
        if line.startswith("Interface") and "PHY" in line:
            header_idx = i
            break
    if header_idx is None:
        return {"trunks": trunks, "standalone_phys": standalone}

    current_trunk: str | None = None

    for raw in lines[header_idx + 1:]:
        if not raw.strip():
            # 空行：可能结束当前聚合口描述
            current_trunk = None
            continue

        # 行首空白判断缩进
        leading = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if not stripped:
            continue

        # 取第一列（接口名）
        first_col = stripped.split()[0]
        name = _clean_iface(first_col)
        if not name or _is_logical(name):
            current_trunk = None
            continue

        is_indented = leading >= 2  # 成员口缩进

        if is_indented and current_trunk is not None:
            trunks.setdefault(current_trunk, []).append(name)
            seen_phys.add(name)
        else:
            # 顶层接口
            lower = name.lower()
            if lower.startswith("eth-trunk") or lower.startswith("bridge-aggregation") \
                    or lower.startswith("route-aggregation") or lower.startswith("aggregateport") \
                    or lower.startswith("ap"):
                current_trunk = name
                trunks.setdefault(current_trunk, [])
            else:
                # 独立物理口
                current_trunk = None
                if name not in seen_phys:
                    standalone.append(name)
                    seen_phys.add(name)

    return {"trunks": trunks, "standalone_phys": standalone}


def parse_link_aggregation_verbose(text: str) -> Dict[str, object]:
    """解析 `display link-aggregation verbose` 聚合口成员。

    典型段落：
      Aggregate Interface: Route-Aggregation1
      Local:
        Port                Status ...
        HGE2/0/1            S ...
      Remote:

    只采集 Local 段下的成员端口；Remote 段为对端 Actor 信息，不应纳入本端成员。
    """
    trunks: Dict[str, List[str]] = {}
    current_trunk: str | None = None
    in_local = False
    seen_members: Set[str] = set()

    for raw in text.splitlines():
        line = _strip_bom(raw).rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        m = re.match(r"^Aggregate Interface:\s+(.+?)\s*$", stripped, re.IGNORECASE)
        if m:
            current_trunk = _clean_iface(m.group(1))
            trunks.setdefault(current_trunk, [])
            in_local = False
            continue

        if current_trunk is None:
            continue
        if stripped.startswith("Local:"):
            in_local = True
            continue
        if stripped.startswith("Remote:"):
            in_local = False
            continue
        if not in_local:
            continue
        if stripped.startswith("Port ") or stripped.startswith("Port\t"):
            continue

        first_col = stripped.split()[0]
        name = _clean_iface(first_col)
        if not name or name in ("Port",):
            continue
        trunks.setdefault(current_trunk, []).append(name)
        seen_members.add(name)

    # verbose 输出只描述聚合口，未加入聚合的独立物理口无法从该命令可靠获得。
    return {"trunks": trunks, "standalone_phys": []}


def parse_trunks(text: str, vendor: str) -> Dict[str, object]:
    vendor = vendor.lower()
    if vendor in ("huawei", "h3c"):
        return parse_huawei(text)
    raise NotImplementedError(
        f"厂商 {vendor!r} 的聚合口解析尚未实现，请先在 references/parser-{vendor}.md 补充样例。"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="解析聚合口-物理口映射")
    parser.add_argument("path", help="接口摘要文件路径")
    parser.add_argument("--vendor", default="huawei", help="厂商（默认 huawei）")
    parser.add_argument("--indent", type=int, default=2, help="JSON 缩进")
    args = parser.parse_args(list(argv) if argv is not None else None)

    text = Path(args.path).read_text(encoding="utf-8", errors="replace")
    data = parse_trunks(text, args.vendor)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
