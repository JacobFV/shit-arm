"""Careful Feetech ping at multiple bauds. Single open per baud, full ID sweep."""
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140318401"
BAUDS = [1_000_000, 500_000, 115_200, 250_000, 57_600]

for baud in BAUDS:
    port = PortHandler(PORT)
    if not port.openPort():
        print(f"{baud}: open failed")
        continue
    port.setBaudRate(baud)
    time.sleep(0.5)
    packet = PacketHandler(0)
    hits = []
    for sid in range(0, 254):
        _, comm, _ = packet.ping(port, sid)
        if comm == COMM_SUCCESS:
            hits.append(sid)
    port.closePort()
    print(f"{baud}: hits={hits}")
    time.sleep(1.0)
