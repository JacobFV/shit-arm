from __future__ import annotations

import argparse
from pathlib import Path

from shit_arm.app import build_mock_context
from shit_arm.control.runner import ModeRunner
from shit_arm.modes import mode_names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shit-arm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("modes", help="List available operating modes.")

    run_parser = subparsers.add_parser("run", help="Run a mode against mock hardware.")
    run_parser.add_argument("mode", choices=mode_names())
    run_parser.add_argument("--ticks", type=int, default=1)
    run_parser.add_argument("--hz", type=float, default=10.0)
    run_parser.add_argument("--record", action="store_true")
    run_parser.add_argument("--run-root", type=Path, default=Path("runs"))
    run_parser.add_argument("--replay-path", type=Path)
    run_parser.add_argument("--label")
    run_parser.add_argument("--target-bin")
    run_parser.add_argument("--confirmed", action="store_true")
    run_parser.add_argument("--min-confidence", type=float, default=None)
    run_parser.add_argument("--speed-scale", type=float, default=None)
    run_parser.add_argument("--assistance-level", type=int, default=None)

    args = parser.parse_args(argv)
    if args.command == "modes":
        for name in mode_names():
            print(name)
        return 0

    context = build_mock_context(record=args.record or args.mode in {"record", "teach"}, run_root=args.run_root)
    if args.replay_path:
        context.options["replay_path"] = str(args.replay_path)
    if args.label:
        context.options["label"] = args.label
    if args.target_bin:
        context.options["target_bin"] = args.target_bin
    if args.confirmed:
        context.options["confirmed"] = True
    if args.min_confidence is not None:
        context.options["min_confidence"] = args.min_confidence
    if args.speed_scale is not None:
        context.options["speed_scale"] = args.speed_scale
    if args.assistance_level is not None:
        context.options["assistance_level"] = args.assistance_level

    result = ModeRunner(context).run(args.mode, ticks=args.ticks, hz=args.hz)
    print(f"mode={args.mode} ticks={result.ticks} last_command={result.last_command.kind.value} reason={result.last_command.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

