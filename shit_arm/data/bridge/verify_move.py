"""Command a move and read back to verify the servo actually moved."""
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140339331"
BAUD = 1_000_000
ADDR_TORQUE_ENABLE   = 40
ADDR_GOAL_POSITION   = 42
ADDR_GOAL_SPEED      = 46
ADDR_PRESENT_POS     = 56
ADDR_PRESENT_LOAD    = 60
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMP    = 63
ADDR_OPERATING_MODE  = 33
ADDR_LOCK            = 55

port = PortHandler(PORT)
port.openPort(); port.setBaudRate(BAUD); time.sleep(0.5)
pk = PacketHandler(0)

sid = 1  # shoulder_pan -- big, easy to see
mode, _, _   = pk.read1ByteTxRx(port, sid, ADDR_OPERATING_MODE)
lock, _, _   = pk.read1ByteTxRx(port, sid, ADDR_LOCK)
te, _, _     = pk.read1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE)
volt, _, _   = pk.read1ByteTxRx(port, sid, ADDR_PRESENT_VOLTAGE)
temp, _, _   = pk.read1ByteTxRx(port, sid, ADDR_PRESENT_TEMP)
start, _, _  = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)

print(f"id={sid} BEFORE  mode={mode} lock={lock} torque_en={te} "
      f"volts={volt/10:.1f} temp={temp}°C pos={start}")

print("\nenabling torque, setting speed=400, commanding +600 ticks...")
pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, 400)
pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)
time.sleep(0.2)
te2, _, _ = pk.read1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE)
print(f"  torque_enable readback after write: {te2}")

target = max(0, min(4095, start + 600))
pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, target)

# poll position for 3 seconds
print(f"\ncommanded goal={target}, polling present_position for 3s:")
t0 = time.time()
while time.time() - t0 < 3.0:
    pos, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
    load, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_LOAD)
    delta = pos - start
    print(f"  t={time.time()-t0:4.1f}s  pos={pos}  delta={delta:+d}  load={load}")
    time.sleep(0.3)

# return home
pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, start)
time.sleep(1.5)
end, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
print(f"\nAFTER return: pos={end} (started at {start})")

pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
port.closePort()
