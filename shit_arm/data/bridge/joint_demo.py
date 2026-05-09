"""Joint-named demo for the alive servos.

Mapping (dual-arm SO-101 on a single bus):
    id=1 -> follower shoulder pan
    id=6 -> follower gripper
    id=7 -> leader   shoulder pan
    id=8 -> leader   shoulder lift
"""
import math
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140318401"
BAUD = 1_000_000

ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED    = 46
ADDR_PRESENT_POS   = 56

JOINTS = {
    1: "follower.shoulder_pan",
    6: "follower.gripper",
    7: "leader.shoulder_pan",
    8: "leader.shoulder_lift",
}


def open_bus():
    port = PortHandler(PORT)
    if not port.openPort():
        raise SystemExit(f"open failed: {PORT}")
    port.setBaudRate(BAUD)
    time.sleep(0.3)
    return port, PacketHandler(0)


def banner(s):
    print("\n" + "=" * 60 + f"\n  {s}\n" + "=" * 60)


def main():
    port, pk = open_bus()

    home = {}
    for sid, name in JOINTS.items():
        _, comm, _ = pk.ping(port, sid)
        if comm != COMM_SUCCESS:
            print(f"  [skip] {name} (id={sid}) not responding")
            continue
        pos, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
        home[sid] = pos
        print(f"  ok  {name:30s} id={sid} home={pos}")

    if not home:
        port.closePort()
        return

    for sid in home:
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, 600)
        pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)

    try:
        # 1. mirror the shoulders
        if 1 in home and 7 in home:
            banner("mirror: follower & leader shoulder pans move opposite")
            steps = 90
            for k in range(steps):
                phase = 2 * math.pi * k / steps * 2  # 2 cycles
                off = int(250 * math.sin(phase))
                pk.write2ByteTxRx(port, 1, ADDR_GOAL_POSITION,
                                  max(0, min(4095, home[1] + off)))
                pk.write2ByteTxRx(port, 7, ADDR_GOAL_POSITION,
                                  max(0, min(4095, home[7] - off)))
                time.sleep(0.04)
            pk.write2ByteTxRx(port, 1, ADDR_GOAL_POSITION, home[1])
            pk.write2ByteTxRx(port, 7, ADDR_GOAL_POSITION, home[7])
            time.sleep(0.6)

        # 2. leader shoulder-lift bow
        if 8 in home:
            banner("leader bow: shoulder-lift dips and rises")
            for off in (-200, +0, -300, +0):
                pk.write2ByteTxRx(port, 8, ADDR_GOAL_POSITION,
                                  max(0, min(4095, home[8] + off)))
                time.sleep(0.9)

        # 3. gripper pulses
        if 6 in home:
            banner("follower gripper: open / close pulses")
            for _ in range(3):
                pk.write2ByteTxRx(port, 6, ADDR_GOAL_POSITION,
                                  max(0, min(4095, home[6] + 250)))
                time.sleep(0.5)
                pk.write2ByteTxRx(port, 6, ADDR_GOAL_POSITION,
                                  max(0, min(4095, home[6] - 250)))
                time.sleep(0.5)
            pk.write2ByteTxRx(port, 6, ADDR_GOAL_POSITION, home[6])
            time.sleep(0.5)

        # 4. all-together finale
        banner("finale: all alive joints sweep in sync")
        steps = 80
        for k in range(steps):
            phase = 2 * math.pi * k / steps
            off = int(180 * math.sin(phase))
            for sid in home:
                pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION,
                                  max(0, min(4095, home[sid] + off)))
            time.sleep(0.04)
        for sid in home:
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, home[sid])
        time.sleep(0.8)

    finally:
        for sid in home:
            pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
        port.closePort()
        print("\ndone, torque off.")


if __name__ == "__main__":
    main()
