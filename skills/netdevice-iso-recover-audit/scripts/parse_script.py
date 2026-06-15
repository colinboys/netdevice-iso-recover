#!/usr/bin/env python3
"""parse_script.py — 解析隔离/恢复操作脚本，提取接口的 shutdown / undo shutdown 操作。

支持的厂家（按厂家分发）：
  - huawei  ：VRP V800（已实现：interface / shutdown / undo shutdown、// 段注释）
  - zte     ：占位（待实现；中兴常用 no shutdown 而非 undo shutdown）
  - h3c     ：占位（待实现；华三 Comware V7 与华为风格类似）
  - ruijie  ：占位（待实现；锐捷常用 no shutdown）

输出：JSON 数组，按脚本中出现顺序，每个元素：
  {
    "line_no":     原脚本 1-based 行号
    "iface":       操作的接口名
    "op":          "shutdown" | "undo_shutdown"
    "section":     顶层注释（"//..."），无则 null
    "raw":         原始行
  }

使用：
  python3 parse_script.py <script> --vendor huawei

注意：「no shutdown」在最终输出里统一归一为 "undo_shutdown"，便于上游
稽核（audit.py）按同一份「op ∈ {shutdown, undo_shutdown}」做语义比较。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


# ---------- 通用正则 ----------

IFACE_RE = re.compile(r"^\s*interface\s+(.+?)\s*$", re.IGNORECASE)

# 区分三种「与关闭端口相关」的命令，避免短路误判
_RE_SHUTDOWN = re.compile(r"^\s*shutdown\s*$", re.IGNORECASE)
_RE_UNDO_SHUTDOWN = re.compile(r"^\s*undo\s+shutdown\s*$", re.IGNORECASE)
_RE_NO_SHUTDOWN = re.compile(r"^\s*no\s+shutdown\s*$", re.IGNORECASE)

# 顶层段注释（//...）— VRP 风格
SECTION_COMMENT_RE = re.compile(r"^\s*//\s*(?P<text>.+?)\s*$")


def _normalize_iface(name: str) -> str:
    """归一化接口名用于比较：去多余空白、保留单个空格、不改变大小写。

    注意：保留原始大小写以兼容『Eth-trunk 2』与『Eth-Trunk2』两种写法，
    比较时在调用方做大小写不敏感处理。
    """
    return " ".join(name.split())


def _classify_shutdown_line(line: str) -> Optional[str]:
    """把当前行映射为 shutdown/undo_shutdown；命中不到返回 None。"""
    if _RE_UNDO_SHUTDOWN.match(line):
        return "undo_shutdown"
    if _RE_NO_SHUTDOWN.match(line):
        # Cisco / 中兴 / 锐捷风格的 no shutdown，归一为 undo_shutdown
        return "undo_shutdown"
    if _RE_SHUTDOWN.match(line):
        return "shutdown"
    return None


# ---------- 华为 VRP（已实现） ----------

def parse_huawei(text: str) -> List[Dict[str, Any]]:
    """华为 VRP 风格的隔离/恢复脚本解析。

    识别要点：
      - `interface <ifname>` 进入接口上下文
      - `shutdown` / `undo shutdown` 记录为 op
      - 顶层 `//` 注释作为「section」分段提示
      - `#`、`!` 开头的行视为注释
      - `system-view` / `commit` / `save` / `quit` 等控制命令忽略
    """
    ops: List[Dict[str, Any]] = []
    current_iface: Optional[str] = None
    current_section: Optional[str] = None

    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")

        # 顶层注释：//开头，且行首没有更深的缩进
        m = SECTION_COMMENT_RE.match(line)
        if m and not line.startswith(("  //", "\t//")):
            current_section = m.group("text").strip()
            current_iface = None  # 注释也会重置 current_iface，与 VRP 行为一致
            continue

        # 注释行：# 或 ! 开头
        if line.lstrip().startswith(("#", "!")):
            continue

        m_iface = IFACE_RE.match(line)
        if m_iface:
            current_iface = _normalize_iface(m_iface.group(1))
            continue

        if current_iface is None:
            # 等待进入 interface 段
            continue

        op = _classify_shutdown_line(line)
        if op is None:
            # 其它命令（commit / save / quit / system-view 等）忽略
            continue

        ops.append({
            "line_no": idx,
            "iface": current_iface,
            "op": op,
            "section": current_section,
            "raw": line.strip(),
        })

    return ops


# ---------- 中兴（占位） ----------

def parse_zte(text: str) -> List[Dict[str, Any]]:
    """中兴 ZXR10 / ROSNG 隔离/恢复脚本解析（占位）。"""
    raise NotImplementedError(
        "中兴（zte）隔离/恢复脚本解析尚未实现。\n"
        "实现前请先在 references/parser-zte.md 补充『configure terminal / interface / shutdown / no shutdown』等样例，"
        "再在本文件实现 parse_zte()。\n"
        "提示：中兴常用『shutdown』/『no shutdown』而非『undo shutdown』，"
        "no shutdown 已在 _classify_shutdown_line 中归一为 undo_shutdown。"
    )


# ---------- 华三（占位） ----------

def parse_h3c(text: str) -> List[Dict[str, Any]]:
    """华三 Comware V7 隔离/恢复脚本解析（占位）。"""
    raise NotImplementedError(
        "华三（h3c）隔离/恢复脚本解析尚未实现。\n"
        "实现前请先在 references/parser-h3c.md 补充『system-view / interface / shutdown / undo shutdown』等样例，"
        "再在本文件实现 parse_h3c()。\n"
        "提示：华三语法与华为 VRP 高度相似，可优先复用 parse_huawei() 作为参考实现，"
        "并按需调整段注释 / 控制命令的识别。"
    )


# ---------- 锐捷（占位） ----------

def parse_ruijie(text: str) -> List[Dict[str, Any]]:
    """锐捷 RGOS 隔离/恢复脚本解析（占位）。"""
    raise NotImplementedError(
        "锐捷（ruijie）隔离/恢复脚本解析尚未实现。\n"
        "实现前请先在 references/parser-ruijie.md 补充『configure terminal / interface / shutdown / no shutdown』等样例，"
        "再在本文件实现 parse_ruijie()。\n"
        "提示：锐捷常用『shutdown』/『no shutdown』而非『undo shutdown』；"
        "接口名常含空格（如『GigabitEthernet 0/1』），IFACE_RE 的非贪婪匹配已能容忍此情形。"
    )


# ---------- 调度器 ----------

PARSERS: Dict[str, Callable[[str], List[Dict[str, Any]]]] = {
    "huawei": parse_huawei,
    "zte": parse_zte,
    "h3c": parse_h3c,
    "ruijie": parse_ruijie,
}


def parse_script(text: str, vendor: str = "huawei") -> List[Dict[str, Any]]:
    """按厂家分发的脚本解析入口。

    为保持向后兼容，未传 vendor 时默认按 huawei 处理（与改造前一致）。
    """
    key = (vendor or "huawei").lower()
    if key not in PARSERS:
        raise ValueError(
            f"未知厂商 {vendor!r}；当前支持：{', '.join(PARSERS.keys())}"
        )
    return PARSERS[key](text)


# ---------- CLI ----------

def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="解析隔离/恢复脚本中的接口操作")
    parser.add_argument("path", help="脚本文件路径")
    parser.add_argument(
        "--vendor",
        default="huawei",
        choices=sorted(PARSERS.keys()),
        help="设备厂家（默认 huawei）；中兴/华三/锐捷目前为占位，会抛 NotImplementedError",
    )
    parser.add_argument("--indent", type=int, default=2, help="JSON 缩进")
    args = parser.parse_args(list(argv) if argv is not None else None)

    text = Path(args.path).read_text(encoding="utf-8", errors="replace")
    ops = parse_script(text, args.vendor)
    json.dump(ops, sys.stdout, ensure_ascii=False, indent=args.indent)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
