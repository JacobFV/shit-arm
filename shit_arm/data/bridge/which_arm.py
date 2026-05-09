"""Wiggle the shoulder pan on each port so you can tell which arm is on which port."""
import time
import sys
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORTS = [
    "/dev/cu.usbmodem5B140339331",
    "/dev/cu.usbmodem5B140340801",
]
BAUD = 1_000_000
ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED    = 46
ADDR_PRESENT_POS   = 56


def wiggle(path, sid, label):
    port = PortHandler(path)
    if not port.openPort():
        print(f"{path}: open failed"); return
    port.setBaudRate(BAUD); time.sleep(0.3)
    pk = PacketHandler(0)
    _, comm, _ = pk.ping(port, sid)
    if comm != COMM_SUCCESS:
        print(f"{path}: id={sid} not responding"); port.closePort(); return
    pos, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
    pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, 400)
    pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)
    print(f"\n>>> {label}: wiggling id={sid} on {path} for 4 sec — watch which arm moves")
    for _ in range(4):
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, max(0, min(4095, pos + 80)))
        time.sleep(0.5)
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, max(0, min(4095, pos - 80)))
        time.sleep(0.5)
    pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, pos); time.sleep(0.3)
    pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
    port.closePort()


# Port 1 has all 6 servos — wiggle id=1 (shoulder pan)
wiggle(PORTS[0], 1, f"PORT A ({PORTS[0]})")
print("    ...pause 3s...")
time.sleep(3.0)
# Port 2 missing 1 and 3 — wiggle id=2 (shoulder lift) since it has it
wiggle(PORTS[1], 2, f"PORT B ({PORTS[1]})")
print("\ndone. tell claude which physical arm moved for each.")
