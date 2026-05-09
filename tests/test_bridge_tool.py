from __future__ import annotations

import argparse

from shit_arm.data import bridge_tool


def test_parse_ids_accepts_ranges_and_lists() -> None:
    assert bridge_tool._parse_ids("1-3,6,3") == [1, 2, 3, 6]


def test_bridge_subparser_registers_commands_without_hardware_imports() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    bridge_tool.add_bridge_subparser(subparsers)

    args = parser.parse_args(["bridge", "scan", "--port", "/dev/null"])

    assert args.command == "bridge"
    assert args.bridge_command == "scan"
    assert args.port == ["/dev/null"]
