"""Move the partial arm (port ...40801) -- whichever servos respond."""
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140340801"
BAUD = 1_000_000
ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED    = 46
ADDR_PRESENT_POS   = 56

JOINT_NAMES = {
    1: "shoulder_pan", 2: "shoulder_lift", 3: "elbow_flex",
    4: "wrist_flex",   5: "wrist_roll",    6: "gripper",
}

port = PortHandler(PORT)
port.openPort(); port.setBaudRate(BAUD); time.sleep(0.5)
pk = PacketHandler(0)

home = {}
for sid, name in JOINT_NAMES.items():
    _, comm, _ = pk.ping(port, sid)
    if comm == COMM_SUCCESS:
        pos, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
        home[sid] = pos
        print(f"  ok  id={sid} {name:14s} home={pos}")
    else:
        print(f"  -- id={sid} {name:14s} not responding (skip)")

if not home:
    port.closePort(); raise SystemExit("no servos to move")

for sid in home:
    pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, 500)
    pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)

try:
    for sid in home:
        print(f"\n>>> moving id={sid} ({JOINT_NAMES[sid]}) — watch this joint")
        for off in (+300, -300, 0):
            tgt = max(0, min(4095, home[sid] + off))
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, tgt)
            time.sleep(1.0)
finally:
    for sid in home:
        pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
    port.closePort()
    print("\ndone, torque off.")
