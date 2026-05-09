"""Probe the serial port at common baud rates: listen for any stream, then try Feetech ping."""
import time
import serial
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140318401"
BAUDS = [1_000_000, 500_000, 115_200, 57_600, 9_600, 38_400, 250_000]

print("=== passive listen (1.5s each) ===")
for baud in BAUDS:
    try:
        s = serial.Serial(PORT, baud, timeout=0.1)
        time.sleep(1.5)
        n = s.in_waiting
        data = s.read(min(n, 200)) if n else b""
        s.close()
        if data:
            printable = data.decode("ascii", errors="replace")
            print(f"  {baud:>8}: {n} bytes -> {printable!r}")
        else:
            print(f"  {baud:>8}: silent")
    except Exception as e:
        print(f"  {baud:>8}: error {e}")

print("\n=== feetech ping sweep (ids 1..12) ===")
for baud in BAUDS:
    port = PortHandler(PORT)
    packet = PacketHandler(0)
    if not port.openPort():
        print(f"  {baud}: open failed")
        continue
    port.setBaudRate(baud)
    hits = []
    for sid in range(1, 13):
        _, comm, _ = packet.ping(port, sid)
        if comm == COMM_SUCCESS:
            hits.append(sid)
    port.closePort()
    print(f"  {baud:>8}: hits={hits}")
