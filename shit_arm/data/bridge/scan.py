"""Scan the Feetech bus for connected servos and print their current positions."""
import sys
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140318401"
BAUD = 1_000_000
ADDR_PRESENT_POSITION = 56  # STS/SCS series

port = PortHandler(PORT)
packet = PacketHandler(0)  # protocol 0 = STS/SMS/SCS

if not port.openPort():
    sys.exit(f"failed to open {PORT}")
if not port.setBaudRate(BAUD):
    sys.exit(f"failed to set baud {BAUD}")

print(f"scanning ids 1..20 on {PORT} @ {BAUD}...")
found = []
for sid in range(1, 21):
    model, comm, err = packet.ping(port, sid)
    if comm == COMM_SUCCESS:
        pos, comm2, err2 = packet.read2ByteTxRx(port, sid, ADDR_PRESENT_POSITION)
        print(f"  id {sid:2d}  model=0x{model:04x}  position={pos}")
        found.append((sid, pos))

if not found:
    print("no servos responded. check power, baud, wiring.")
else:
    print(f"\nfound {len(found)} servo(s)")

port.closePort()
