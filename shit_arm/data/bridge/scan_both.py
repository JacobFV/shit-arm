"""Scan both USB-modem ports for Feetech servos at 1 Mbaud, tolerant of port flaps."""
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORTS = [
    "/dev/cu.usbmodem5B140339331",
    "/dev/cu.usbmodem5B140340801",
]
BAUD = 1_000_000
ADDR_PRESENT_POS = 56


def scan(path):
    try:
        port = PortHandler(path)
        if not port.openPort():
            print("  open failed"); return
        port.setBaudRate(BAUD)
        time.sleep(1.0)  # longer settle
        pk = PacketHandler(0)
        hits = []
        for sid in range(0, 254):
            try:
                _, comm, _ = pk.ping(port, sid)
                if comm == COMM_SUCCESS:
                    pos, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
                    hits.append((sid, pos))
            except Exception as e:
                print(f"  [error at id={sid}: {e}]")
                break
        try:
            port.closePort()
        except Exception:
            pass
        if hits:
            for sid, pos in hits:
                print(f"  id={sid:>2}  pos={pos}")
        else:
            print("  no servos responded")
    except Exception as e:
        print(f"  fatal: {e}")


for path in PORTS:
    print(f"\n=== {path} ===")
    scan(path)
    time.sleep(1.0)
