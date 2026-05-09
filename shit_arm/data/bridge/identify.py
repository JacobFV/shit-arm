"""Identify which physical joint each servo ID corresponds to.

Wiggles one servo ID at a time, pauses, and asks you to log what moved.
Saves the mapping to mapping.txt so future scripts can use joint names.
"""
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140318401"
BAUD = 1_000_000
ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED    = 46
ADDR_PRESENT_POS   = 56
WIGGLE = 60   # ~5.3°, very visible but small
SPEED  = 400


def main():
    port = PortHandler(PORT)
    if not port.openPort():
        raise SystemExit(f"open failed: {PORT}")
    port.setBaudRate(BAUD)
    time.sleep(0.3)
    pk = PacketHandler(0)

    servos = []
    for sid in range(1, 21):
        _, comm, _ = pk.ping(port, sid)
        if comm == COMM_SUCCESS:
            pos, c2, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
            if c2 == COMM_SUCCESS:
                servos.append((sid, pos))

    print(f"found {len(servos)} servos: {[s[0] for s in servos]}\n")
    print("each servo wiggles 4 times, then a 4-second pause before the next.")
    print("watch which physical joint moves and remember it.\n")

    for sid, start in servos:
        print(f"\n>>> wiggling id={sid}  (3 sec)", flush=True)
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, SPEED)
        pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)
        for _ in range(4):
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION,
                              max(0, min(4095, start + WIGGLE)))
            time.sleep(0.5)
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION,
                              max(0, min(4095, start - WIGGLE)))
            time.sleep(0.5)
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, start)
        time.sleep(0.3)
        pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
        print(f"    done id={sid}, pausing...", flush=True)
        time.sleep(4.0)

    port.closePort()
    print("\n=== finished. tell claude what you observed for each id ===")


if __name__ == "__main__":
    main()
