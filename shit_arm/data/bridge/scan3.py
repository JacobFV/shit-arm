"""Exhaustive Feetech bus scan: every documented baud, both protocols, full ID range."""
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140318401"
# Feetech STS/SMS/SCS supported bauds (per official docs)
BAUDS = [1_000_000, 500_000, 250_000, 128_000, 115_200, 76_800, 57_600, 38_400, 19_200, 9_600]

for baud in BAUDS:
    port = PortHandler(PORT)
    if not port.openPort():
        print(f"{baud:>8}: open failed")
        continue
    port.setBaudRate(baud)
    time.sleep(0.4)
    all_hits = {}
    for proto in (0, 1):  # 0 = STS/SMS, 1 = SCS
        pk = PacketHandler(proto)
        for sid in range(0, 254):
            _, comm, _ = pk.ping(port, sid)
            if comm == COMM_SUCCESS:
                all_hits.setdefault(sid, []).append(proto)
    port.closePort()
    if all_hits:
        print(f"{baud:>8}: hits={all_hits}")
    else:
        print(f"{baud:>8}: -")
    time.sleep(0.6)
