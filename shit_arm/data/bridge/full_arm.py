"""Full 6-joint demo on the fully-working SO-101 arm (port ...39331).

Each joint moves on its own first (so you can confirm it's alive),
then a coordinated wave with all 6 joints together.
"""
import math
import sys
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140339331"
BAUD = 1_000_000

ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED    = 46
ADDR_PRESENT_POS   = 56

JOINT_NAMES = {
    1: "shoulder_pan",
    2: "shoulder_lift",
    3: "elbow_flex",
    4: "wrist_flex",
    5: "wrist_roll",
    6: "gripper",
}

# per-joint sweep amplitude (ticks). Smaller for shoulder-lift/elbow which carry weight.
AMPLITUDE = {
    1: 250,
    2: 120,
    3: 150,
    4: 200,
    5: 250,
    6: 200,
}
SPEED = 500


def main():
    port = PortHandler(PORT)
    if not port.openPort():
        sys.exit(f"open failed: {PORT}")
    port.setBaudRate(BAUD)
    time.sleep(0.5)
    pk = PacketHandler(0)

    home = {}
    for sid, name in JOINT_NAMES.items():
        _, comm, _ = pk.ping(port, sid)
        if comm == COMM_SUCCESS:
            pos, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
            home[sid] = pos
            print(f"  ok  id={sid} {name:14s} home={pos}")
        else:
            print(f"  -- id={sid} {name:14s} NOT RESPONDING")

    if not home:
        port.closePort()
        sys.exit("no servos found")

    for sid in home:
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, SPEED)
        pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)

    try:
        # 1. each joint solo
        for sid, name in JOINT_NAMES.items():
            if sid not in home:
                continue
            print(f"\n>>> moving {name} (id={sid})")
            amp = AMPLITUDE[sid]
            for off in (+amp, -amp, 0):
                target = max(0, min(4095, home[sid] + off))
                pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, target)
                time.sleep(0.9)

        # 2. coordinated wave
        print("\n>>> coordinated wave (all joints, 2 cycles)")
        steps = 120
        for k in range(steps):
            phase = 2 * math.pi * k / steps * 2
            for sid in home:
                amp = AMPLITUDE[sid]
                off = int(amp * math.sin(phase + sid * 0.4))  # phase offset per joint
                pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION,
                                  max(0, min(4095, home[sid] + off)))
            time.sleep(0.04)

        # return home
        print("\n>>> returning home")
        for sid in home:
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, home[sid])
        time.sleep(1.0)

    finally:
        for sid in home:
            pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
        port.closePort()
        print("\ndone, torque off (arm goes limp).")


if __name__ == "__main__":
    main()
