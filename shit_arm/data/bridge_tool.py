from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BAUD = 1_000_000
DEFAULT_ID_RANGE = "1-20"
DEFAULT_FULL_ID_RANGE = "0-253"

ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED = 46
ADDR_PRESENT_POS = 56
ADDR_PRESENT_LOAD = 60
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMP = 63
ADDR_OPERATING_MODE = 33
ADDR_LOCK = 55

JOINT_NAMES = {
    1: "shoulder_pan",
    2: "shoulder_lift",
    3: "elbow_flex",
    4: "wrist_flex",
    5: "wrist_roll",
    6: "gripper",
}

DEMO_AMPLITUDE = {
    1: 250,
    2: 120,
    3: 150,
    4: 200,
    5: 250,
    6: 200,
}


@dataclass(frozen=True)
class ServoStatus:
    sid: int
    position: int | None = None
    voltage: float | None = None
    temperature: int | None = None
    load: int | None = None
    mode: int | None = None
    lock: int | None = None
    torque_enabled: int | None = None
    model: int | None = None
    protocol: int = 0


class ServoBus:
    def __init__(self, port_path: str, baud: int = BAUD, protocol: int = 0, settle: float = 0.3):
        scservo = _load_scservo()
        self.port_path = port_path
        self.baud = baud
        self.protocol = protocol
        self.comm_success = scservo.COMM_SUCCESS
        self.port = scservo.PortHandler(port_path)
        if not self.port.openPort():
            raise RuntimeError(f"failed to open {port_path}")
        if not self.port.setBaudRate(baud):
            self.close()
            raise RuntimeError(f"failed to set baud {baud} on {port_path}")
        time.sleep(settle)
        self.packet = scservo.PacketHandler(protocol)

    def close(self) -> None:
        try:
            self.port.closePort()
        except Exception:
            pass

    def __enter__(self) -> ServoBus:
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def ping(self, sid: int) -> int | None:
        model, comm, _err = self.packet.ping(self.port, sid)
        return model if comm == self.comm_success else None

    def read1(self, sid: int, addr: int) -> int | None:
        value, comm, _err = self.packet.read1ByteTxRx(self.port, sid, addr)
        return value if comm == self.comm_success else None

    def read2(self, sid: int, addr: int) -> int | None:
        value, comm, _err = self.packet.read2ByteTxRx(self.port, sid, addr)
        return value if comm == self.comm_success else None

    def write1(self, sid: int, addr: int, value: int) -> None:
        self.packet.write1ByteTxRx(self.port, sid, addr, value)

    def write2(self, sid: int, addr: int, value: int) -> None:
        self.packet.write2ByteTxRx(self.port, sid, addr, value)


def add_bridge_subparser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser("bridge", help="Run low-level Feetech/SO-101 hardware bring-up tools.")
    configure_parser(parser)
    return parser


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(dest="bridge_command", required=True)

    scan = subparsers.add_parser("scan", help="Ping servo IDs and optionally read current positions.")
    _add_common_scan_args(scan)
    scan.add_argument("--read-position", action=argparse.BooleanOptionalAction, default=True)
    scan.set_defaults(func=_cmd_scan)

    health = subparsers.add_parser("health", help="Read position, voltage, temperature, and load.")
    _add_port_args(health)
    health.add_argument("--ids", default=DEFAULT_ID_RANGE)
    health.add_argument("--baud", type=int, default=BAUD)
    health.add_argument("--protocol", type=int, default=0)
    health.set_defaults(func=_cmd_health)

    probe = subparsers.add_parser("probe", help="Passively listen at common baud rates, then ping IDs.")
    probe.add_argument("--port", required=True)
    probe.add_argument("--bauds", default="1000000,500000,250000,115200,57600,38400,9600")
    probe.add_argument("--ids", default="1-12")
    probe.add_argument("--seconds", type=float, default=1.5)
    probe.set_defaults(func=_cmd_probe)

    wiggle = subparsers.add_parser("wiggle", help="Move one or more servos by a small relative offset.")
    wiggle.add_argument("--port", required=True)
    wiggle.add_argument("--ids", default=DEFAULT_ID_RANGE)
    wiggle.add_argument("--baud", type=int, default=BAUD)
    wiggle.add_argument("--protocol", type=int, default=0)
    wiggle.add_argument("--ticks", type=int, default=60)
    wiggle.add_argument("--speed", type=int, default=400)
    wiggle.add_argument("--repeats", type=int, default=3)
    wiggle.add_argument("--dwell", type=float, default=0.5)
    wiggle.add_argument("--torque-off", action=argparse.BooleanOptionalAction, default=True)
    wiggle.set_defaults(func=_cmd_wiggle)

    torque = subparsers.add_parser("torque", help="Enable or disable torque for responding servos.")
    torque.add_argument("--port", required=True)
    torque.add_argument("--ids", default=DEFAULT_ID_RANGE)
    torque.add_argument("--baud", type=int, default=BAUD)
    torque.add_argument("--protocol", type=int, default=0)
    torque_state = torque.add_mutually_exclusive_group(required=True)
    torque_state.add_argument("--enable", action="store_true")
    torque_state.add_argument("--disable", action="store_true")
    torque.set_defaults(func=_cmd_torque)

    identify = subparsers.add_parser("identify", help="Wiggle each responding servo with a pause for visual mapping.")
    identify.add_argument("--port", required=True)
    identify.add_argument("--ids", default=DEFAULT_ID_RANGE)
    identify.add_argument("--baud", type=int, default=BAUD)
    identify.add_argument("--protocol", type=int, default=0)
    identify.add_argument("--ticks", type=int, default=60)
    identify.add_argument("--speed", type=int, default=400)
    identify.add_argument("--pause", type=float, default=4.0)
    identify.set_defaults(func=_cmd_identify)

    demo = subparsers.add_parser("demo", help="Run a named SO-101 servo movement demo.")
    demo.add_argument("--port", required=True)
    demo.add_argument("--ids", default="1-6")
    demo.add_argument("--baud", type=int, default=BAUD)
    demo.add_argument("--protocol", type=int, default=0)
    demo.add_argument("--speed", type=int, default=500)
    demo.add_argument("--profile", choices=["single-joints", "wave", "full"], default="full")
    demo.add_argument("--torque-off", action=argparse.BooleanOptionalAction, default=True)
    demo.set_defaults(func=_cmd_demo)

    verify = subparsers.add_parser("verify-move", help="Command a move and poll position/load to prove motion.")
    verify.add_argument("--port", required=True)
    verify.add_argument("--id", type=int, default=1)
    verify.add_argument("--baud", type=int, default=BAUD)
    verify.add_argument("--protocol", type=int, default=0)
    verify.add_argument("--ticks", type=int, default=600)
    verify.add_argument("--speed", type=int, default=400)
    verify.add_argument("--seconds", type=float, default=3.0)
    verify.set_defaults(func=_cmd_verify_move)

    aruco = subparsers.add_parser("aruco-tags", help="Generate printable ArUco tags at physical size.")
    aruco.add_argument("--out", type=Path, default=Path("aruco_sheet.png"))
    aruco.add_argument("--tag-size-mm", type=float, default=40.0)
    aruco.add_argument("--dpi", type=int, default=300)
    aruco.add_argument("--ids", default="0-5")
    aruco.set_defaults(func=_cmd_aruco_tags)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shit-arm-bridge")
    configure_parser(parser)
    args = parser.parse_args(argv)
    return args.func(args)


def scan_servos(
    port_path: str,
    *,
    baud: int = BAUD,
    ids: Iterable[int] = range(1, 21),
    protocol: int = 0,
    read_position: bool = True,
) -> list[ServoStatus]:
    statuses: list[ServoStatus] = []
    with ServoBus(port_path, baud=baud, protocol=protocol) as bus:
        for sid in ids:
            model = bus.ping(sid)
            if model is None:
                continue
            position = bus.read2(sid, ADDR_PRESENT_POS) if read_position else None
            statuses.append(ServoStatus(sid=sid, model=model, position=position, protocol=protocol))
    return statuses


def read_health(port_path: str, *, baud: int = BAUD, ids: Iterable[int] = range(1, 21), protocol: int = 0) -> list[ServoStatus]:
    statuses: list[ServoStatus] = []
    with ServoBus(port_path, baud=baud, protocol=protocol) as bus:
        for sid in ids:
            model = bus.ping(sid)
            if model is None:
                continue
            voltage = bus.read1(sid, ADDR_PRESENT_VOLTAGE)
            statuses.append(
                ServoStatus(
                    sid=sid,
                    model=model,
                    position=bus.read2(sid, ADDR_PRESENT_POS),
                    voltage=voltage / 10.0 if voltage is not None else None,
                    temperature=bus.read1(sid, ADDR_PRESENT_TEMP),
                    load=bus.read2(sid, ADDR_PRESENT_LOAD),
                    mode=bus.read1(sid, ADDR_OPERATING_MODE),
                    lock=bus.read1(sid, ADDR_LOCK),
                    torque_enabled=bus.read1(sid, ADDR_TORQUE_ENABLE),
                    protocol=protocol,
                )
            )
    return statuses


def wiggle_servos(
    port_path: str,
    *,
    ids: Iterable[int],
    baud: int = BAUD,
    protocol: int = 0,
    ticks: int = 60,
    speed: int = 400,
    repeats: int = 3,
    dwell: float = 0.5,
    torque_off: bool = True,
) -> list[ServoStatus]:
    with ServoBus(port_path, baud=baud, protocol=protocol) as bus:
        home = _responding_positions(bus, ids)
        for sid in home:
            bus.write2(sid, ADDR_GOAL_SPEED, speed)
            bus.write1(sid, ADDR_TORQUE_ENABLE, 1)
        try:
            for sid, start in home.items():
                print(f"\n>>> wiggling id={sid} {JOINT_NAMES.get(sid, '')} start={start}", flush=True)
                for _ in range(repeats):
                    for offset in (ticks, -ticks):
                        bus.write2(sid, ADDR_GOAL_POSITION, _clamp_tick(start + offset))
                        time.sleep(dwell)
                bus.write2(sid, ADDR_GOAL_POSITION, start)
                time.sleep(dwell)
        finally:
            if torque_off:
                for sid in home:
                    bus.write1(sid, ADDR_TORQUE_ENABLE, 0)
        return [ServoStatus(sid=sid, position=pos, protocol=protocol) for sid, pos in home.items()]


def _cmd_scan(args: argparse.Namespace) -> int:
    for port_path in args.port:
        for baud in _parse_int_list(args.bauds):
            for protocol in _parse_int_list(args.protocols):
                print(f"\n=== {port_path} baud={baud} protocol={protocol} ===")
                try:
                    statuses = scan_servos(
                        port_path,
                        baud=baud,
                        ids=_parse_ids(args.ids),
                        protocol=protocol,
                        read_position=args.read_position,
                    )
                except Exception as exc:
                    print(f"error: {exc}")
                    continue
                if not statuses:
                    print("no servos responded")
                    continue
                for status in statuses:
                    pos = f" pos={status.position}" if status.position is not None else ""
                    print(f"id={status.sid:>3} model=0x{status.model:04x}{pos}")
    return 0


def _cmd_health(args: argparse.Namespace) -> int:
    for port_path in args.port:
        print(f"\n=== {port_path} ===")
        try:
            statuses = read_health(port_path, baud=args.baud, ids=_parse_ids(args.ids), protocol=args.protocol)
        except Exception as exc:
            print(f"error: {exc}")
            continue
        if not statuses:
            print("no servos responded")
            continue
        for status in statuses:
            print(
                f"id={status.sid:>2} pos={_fmt(status.position):>4} "
                f"volts={_fmt(status.voltage):>4} temp={_fmt(status.temperature):>3} "
                f"load={_fmt(status.load):>5} torque={_fmt(status.torque_enabled)} "
                f"mode={_fmt(status.mode)} lock={_fmt(status.lock)}"
            )
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    serial = _load_serial()
    bauds = _parse_int_list(args.bauds)
    print("=== passive listen ===")
    for baud in bauds:
        try:
            stream = serial.Serial(args.port, baud, timeout=0.1)
            time.sleep(args.seconds)
            pending = stream.in_waiting
            data = stream.read(min(pending, 400)) if pending else b""
            stream.close()
            printable = data.decode("ascii", errors="replace") if data else ""
            print(f"{baud:>8}: {pending} bytes {printable!r}")
        except Exception as exc:
            print(f"{baud:>8}: error {exc}")
        time.sleep(0.2)

    print("\n=== ping sweep ===")
    for baud in bauds:
        try:
            statuses = scan_servos(args.port, baud=baud, ids=_parse_ids(args.ids), read_position=False)
            print(f"{baud:>8}: hits={[status.sid for status in statuses]}")
        except Exception as exc:
            print(f"{baud:>8}: error {exc}")
    return 0


def _cmd_wiggle(args: argparse.Namespace) -> int:
    statuses = wiggle_servos(
        args.port,
        ids=_parse_ids(args.ids),
        baud=args.baud,
        protocol=args.protocol,
        ticks=args.ticks,
        speed=args.speed,
        repeats=args.repeats,
        dwell=args.dwell,
        torque_off=args.torque_off,
    )
    if not statuses:
        print("no servos responded")
    return 0


def _cmd_torque(args: argparse.Namespace) -> int:
    value = 1 if args.enable else 0
    with ServoBus(args.port, baud=args.baud, protocol=args.protocol) as bus:
        home = _responding_positions(bus, _parse_ids(args.ids))
        if not home:
            print("no servos responded")
            return 0
        for sid in home:
            bus.write1(sid, ADDR_TORQUE_ENABLE, value)
            print(f"id={sid:>2} torque={'on' if value else 'off'}")
    return 0


def _cmd_identify(args: argparse.Namespace) -> int:
    ids = _parse_ids(args.ids)
    with ServoBus(args.port, baud=args.baud, protocol=args.protocol) as bus:
        home = _responding_positions(bus, ids)
    if not home:
        print("no servos responded")
        return 0
    print(f"found {len(home)} servos: {list(home)}")
    for sid in home:
        wiggle_servos(
            args.port,
            ids=[sid],
            baud=args.baud,
            protocol=args.protocol,
            ticks=args.ticks,
            speed=args.speed,
            repeats=4,
            dwell=0.5,
            torque_off=True,
        )
        print(f"done id={sid}; pausing {args.pause}s", flush=True)
        time.sleep(args.pause)
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    ids = _parse_ids(args.ids)
    with ServoBus(args.port, baud=args.baud, protocol=args.protocol) as bus:
        home = _responding_positions(bus, ids)
        if not home:
            print("no servos responded")
            return 0
        for sid, pos in home.items():
            print(f"ok id={sid} {JOINT_NAMES.get(sid, ''):14s} home={pos}")
            bus.write2(sid, ADDR_GOAL_SPEED, args.speed)
            bus.write1(sid, ADDR_TORQUE_ENABLE, 1)
        try:
            if args.profile in {"single-joints", "full"}:
                _demo_single_joints(bus, home)
            if args.profile in {"wave", "full"}:
                _demo_wave(bus, home)
        finally:
            if args.torque_off:
                for sid in home:
                    bus.write1(sid, ADDR_TORQUE_ENABLE, 0)
    return 0


def _cmd_verify_move(args: argparse.Namespace) -> int:
    with ServoBus(args.port, baud=args.baud, protocol=args.protocol) as bus:
        sid = args.id
        if bus.ping(sid) is None:
            print(f"id={sid} did not respond")
            return 1
        voltage = bus.read1(sid, ADDR_PRESENT_VOLTAGE)
        status = ServoStatus(
            sid=sid,
            position=bus.read2(sid, ADDR_PRESENT_POS),
            voltage=voltage / 10.0 if voltage is not None else None,
            temperature=bus.read1(sid, ADDR_PRESENT_TEMP),
            load=bus.read2(sid, ADDR_PRESENT_LOAD),
            mode=bus.read1(sid, ADDR_OPERATING_MODE),
            lock=bus.read1(sid, ADDR_LOCK),
            torque_enabled=bus.read1(sid, ADDR_TORQUE_ENABLE),
            protocol=args.protocol,
        )
        print(
            f"id={sid} before mode={_fmt(status.mode)} lock={_fmt(status.lock)} "
            f"torque={_fmt(status.torque_enabled)} volts={_fmt(status.voltage)} "
            f"temp={_fmt(status.temperature)} pos={_fmt(status.position)}"
        )
        start = bus.read2(sid, ADDR_PRESENT_POS)
        if start is None:
            print("could not read start position")
            return 1
        bus.write2(sid, ADDR_GOAL_SPEED, args.speed)
        bus.write1(sid, ADDR_TORQUE_ENABLE, 1)
        target = _clamp_tick(start + args.ticks)
        bus.write2(sid, ADDR_GOAL_POSITION, target)
        print(f"commanded goal={target}; polling for {args.seconds}s")
        t0 = time.time()
        while time.time() - t0 < args.seconds:
            pos = bus.read2(sid, ADDR_PRESENT_POS)
            load = bus.read2(sid, ADDR_PRESENT_LOAD)
            delta = "" if pos is None else f" delta={pos - start:+d}"
            print(f"t={time.time() - t0:4.1f}s pos={_fmt(pos)}{delta} load={_fmt(load)}")
            time.sleep(0.3)
        bus.write2(sid, ADDR_GOAL_POSITION, start)
        time.sleep(1.0)
        print(f"after return pos={_fmt(bus.read2(sid, ADDR_PRESENT_POS))}")
        bus.write1(sid, ADDR_TORQUE_ENABLE, 0)
    return 0


def _cmd_aruco_tags(args: argparse.Namespace) -> int:
    cv2, np, image_mod = _load_aruco_deps()
    Image, ImageDraw, ImageFont = image_mod.Image, image_mod.ImageDraw, image_mod.ImageFont
    tag_px = _mm_to_px(args.tag_size_mm, args.dpi)
    quiet_px = _mm_to_px(5, args.dpi)
    label_h = _mm_to_px(8, args.dpi)
    cell_w = tag_px + 2 * quiet_px
    cell_h = tag_px + 2 * quiet_px + label_h
    tag_ids = list(_parse_ids(args.ids))
    cols = 2
    rows = (len(tag_ids) + cols - 1) // cols
    page = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(page)
    aruco = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", _mm_to_px(3, args.dpi))
    except OSError:
        font = ImageFont.load_default()
    for index, tag_id in enumerate(tag_ids):
        row, col = divmod(index, cols)
        marker = cv2.aruco.generateImageMarker(aruco, tag_id, tag_px)
        marker_image = Image.fromarray(np.asarray(marker)).convert("RGB")
        x = col * cell_w + quiet_px
        y = row * cell_h + quiet_px
        page.paste(marker_image, (x, y))
        draw.text((x, y + tag_px + _mm_to_px(2, args.dpi)), f"id={tag_id} ({args.tag_size_mm:g}mm)", fill="black", font=font)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    page.save(args.out, dpi=(args.dpi, args.dpi))
    print(f"wrote {args.out}")
    return 0


def _add_port_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--port", action="append", required=True, help="Serial port. Repeat for multiple ports.")


def _add_common_scan_args(parser: argparse.ArgumentParser) -> None:
    _add_port_args(parser)
    parser.add_argument("--ids", default=DEFAULT_FULL_ID_RANGE)
    parser.add_argument("--bauds", default=str(BAUD))
    parser.add_argument("--protocols", default="0")


def _responding_positions(bus: ServoBus, ids: Iterable[int]) -> dict[int, int]:
    home: dict[int, int] = {}
    for sid in ids:
        if bus.ping(sid) is None:
            continue
        pos = bus.read2(sid, ADDR_PRESENT_POS)
        if pos is not None:
            home[sid] = pos
    return home


def _demo_single_joints(bus: ServoBus, home: dict[int, int]) -> None:
    for sid, start in home.items():
        print(f"\n>>> moving {JOINT_NAMES.get(sid, f'id={sid}')}")
        amplitude = DEMO_AMPLITUDE.get(sid, 120)
        for offset in (amplitude, -amplitude, 0):
            bus.write2(sid, ADDR_GOAL_POSITION, _clamp_tick(start + offset))
            time.sleep(0.9)


def _demo_wave(bus: ServoBus, home: dict[int, int]) -> None:
    import math

    print("\n>>> coordinated wave")
    steps = 120
    for step in range(steps):
        phase = 2 * math.pi * step / steps * 2
        for sid, start in home.items():
            amp = min(DEMO_AMPLITUDE.get(sid, 120), 180)
            bus.write2(sid, ADDR_GOAL_POSITION, _clamp_tick(start + int(amp * math.sin(phase))))
        time.sleep(0.04)
    for sid, start in home.items():
        bus.write2(sid, ADDR_GOAL_POSITION, start)
    time.sleep(0.8)


def _parse_ids(value: str) -> range | list[int]:
    ids: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(piece) for piece in part.split("-", 1))
            ids.extend(range(start, end + 1))
        else:
            ids.append(int(part))
    return sorted(set(ids))


def _parse_int_list(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _clamp_tick(value: int) -> int:
    return max(0, min(4095, value))


def _fmt(value: object) -> str:
    return "-" if value is None else str(value)


def _mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm * dpi / 25.4))


def _load_scservo():
    try:
        import scservo_sdk
    except ImportError as exc:
        raise RuntimeError("scservo_sdk is required for bridge hardware commands; install the Feetech/SCServo SDK") from exc
    return scservo_sdk


def _load_serial():
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial is required for `bridge probe`; install pyserial") from exc
    return serial


def _load_aruco_deps():
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("opencv-contrib-python, numpy, and pillow are required for `bridge aruco-tags`") from exc

    class ImageModule:
        pass

    image_mod = ImageModule()
    image_mod.Image = Image
    image_mod.ImageDraw = ImageDraw
    image_mod.ImageFont = ImageFont
    return cv2, np, image_mod


if __name__ == "__main__":
    raise SystemExit(main())
