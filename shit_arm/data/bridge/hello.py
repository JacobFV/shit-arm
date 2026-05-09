"""Hello world for the SO-101 / Feetech STS3215 bus.

Detects responding servos, then wiggles each one by a tiny relative offset
and returns it to its starting position. Slow speed, small range -- safe
even without knowing the calibration.
"""
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140318401"
BAUD = 1_000_000

ADDR_TORQUE_ENABLE   = 40
ADDR_GOAL_POSITION   = 42
ADDR_GOAL_SPEED      = 46
ADDR_PRESENT_POS     = 56

WIGGLE_TICKS = 30   # ~2.6 degrees on STS3215 (4096 ticks / 360 deg)
SLOW_SPEED   = 300  # raw units; very slow
DWELL        = 1.0  # seconds between waypoints


def main():
    port = PortHandler(PORT)
    if not port.openPort():
        raise SystemExit(f"open failed: {PORT}")
    port.setBaudRate(BAUD)
    time.sleep(0.3)
    pk = PacketHandler(0)

    print(f"scanning ids 1..20 at {BAUD} baud...")
    servos = []
    for sid in range(1, 21):
        _, comm, _ = pk.ping(port, sid)
        if comm == COMM_SUCCESS:
            pos, c2, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
            if c2 == COMM_SUCCESS:
                servos.append((sid, pos))
                print(f"  id={sid:>2}  present_position={pos}")

    if not servos:
        port.closePort()
        raise SystemExit("no servos responded")

    print("\nenabling torque + setting slow speed...")
    for sid, _ in servos:
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, SLOW_SPEED)
        pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)

    try:
        for sid, start in servos:
            print(f"\n-- wiggling id={sid} (start={start}) --")
            for offset in (+WIGGLE_TICKS, -WIGGLE_TICKS, 0):
                target = max(0, min(4095, start + offset))
                pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, target)
                print(f"   goto {target}")
                time.sleep(DWELL)
    finally:
        print("\ndisabling torque (arm goes limp)...")
        for sid, _ in servos:
            pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
        port.closePort()
        print("done.")


if __name__ == "__main__":
    main()
