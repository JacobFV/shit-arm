"""Slower, more robust probe. Opens once per baud, waits for CH343 to settle."""
import time
import serial

PORT = "/dev/cu.usbmodem5B140318401"
BAUDS = [1_000_000, 115_200, 500_000, 57_600, 9_600]

print("=== passive listen (2s each, 1s between) ===")
for baud in BAUDS:
    for attempt in range(3):
        try:
            s = serial.Serial(PORT, baud, timeout=0.2)
            time.sleep(2.0)
            n = s.in_waiting
            data = s.read(min(n, 400)) if n else b""
            s.close()
            printable = data.decode("ascii", errors="replace") if data else ""
            print(f"  {baud:>8}: {n} bytes  {printable!r}")
            break
        except Exception as e:
            if attempt == 2:
                print(f"  {baud:>8}: error {e}")
            else:
                time.sleep(1.0)
    time.sleep(1.0)
