"""Scan both ports, report voltage + temp for every responding servo."""
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORTS = [
    "/dev/cu.usbmodem5B140339331",
    "/dev/cu.usbmodem5B140340801",
]
BAUD = 1_000_000
ADDR_PRESENT_POS     = 56
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMP    = 63

for path in PORTS:
    print(f"\n=== {path} ===")
    try:
        port = PortHandler(path)
        if not port.openPort():
            print("  open failed"); continue
        port.setBaudRate(BAUD); time.sleep(0.6)
        pk = PacketHandler(0)
        any_hit = False
        for sid in range(1, 13):
            _, comm, _ = pk.ping(port, sid)
            if comm != COMM_SUCCESS:
                continue
            any_hit = True
            pos, _, _  = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
            volt, _, _ = pk.read1ByteTxRx(port, sid, ADDR_PRESENT_VOLTAGE)
            temp, _, _ = pk.read1ByteTxRx(port, sid, ADDR_PRESENT_TEMP)
            print(f"  id={sid:>2}  pos={pos:>4}  volts={volt/10:.1f}V  temp={temp}°C")
        if not any_hit:
            print("  no servos responded")
        port.closePort()
    except Exception as e:
        print(f"  error: {e}")
    time.sleep(0.5)
