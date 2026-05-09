"""Demo for the 3 working SO-101 servos: health, smooth wave, solo flair, free mode."""
import math
import sys
import time
from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS

PORT = "/dev/cu.usbmodem5B140318401"
BAUD = 1_000_000

# STS3215 control table
ADDR_TORQUE_ENABLE   = 40
ADDR_GOAL_POSITION   = 42
ADDR_GOAL_TIME       = 44
ADDR_GOAL_SPEED      = 46
ADDR_PRESENT_POS     = 56
ADDR_PRESENT_SPEED   = 58
ADDR_PRESENT_LOAD    = 60
ADDR_PRESENT_VOLTAGE = 62
ADDR_PRESENT_TEMP    = 63

WAVE_AMPL_TICKS = 150     # ~13 degrees: still small enough to be safe near unknown limits
WAVE_PERIOD     = 4.0     # seconds per cycle
WAVE_CYCLES     = 3
SOLO_AMPL       = 200
FREE_SECONDS    = 12


def banner(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def health(pk, port, sid):
    pos, _, _   = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
    volt, _, _  = pk.read1ByteTxRx(port, sid, ADDR_PRESENT_VOLTAGE)
    temp, _, _  = pk.read1ByteTxRx(port, sid, ADDR_PRESENT_TEMP)
    load, _, _  = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_LOAD)
    return pos, volt / 10.0, temp, load


def main():
    port = PortHandler(PORT)
    if not port.openPort():
        sys.exit(f"open failed: {PORT}")
    port.setBaudRate(BAUD)
    time.sleep(0.3)
    pk = PacketHandler(0)

    # discover
    servos = []
    for sid in range(1, 21):
        _, comm, _ = pk.ping(port, sid)
        if comm == COMM_SUCCESS:
            servos.append(sid)
    if not servos:
        port.closePort()
        sys.exit("no servos found")

    banner(f"health check ({len(servos)} servos)")
    home = {}
    for sid in servos:
        pos, v, t, load = health(pk, port, sid)
        home[sid] = pos
        print(f"  id={sid:>2}  pos={pos:>4}  volts={v:>4.1f}V  temp={t:>2}°C  load={load}")

    # set slow speed and enable torque
    for sid in servos:
        pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, 600)  # mid speed
        pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 1)

    try:
        # --- 1. coordinated sinusoidal wave ---
        banner("coordinated wave: all servos breathing together")
        steps_per_second = 30
        total_steps = int(WAVE_PERIOD * WAVE_CYCLES * steps_per_second)
        t0 = time.time()
        for k in range(total_steps):
            phase = 2 * math.pi * (k / steps_per_second) / WAVE_PERIOD
            offset = int(WAVE_AMPL_TICKS * math.sin(phase))
            for sid in servos:
                target = max(0, min(4095, home[sid] + offset))
                pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, target)
            time.sleep(max(0, (k + 1) / steps_per_second - (time.time() - t0)))

        # return home
        for sid in servos:
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, home[sid])
        time.sleep(0.8)

        # --- 2. solo flair: each servo does a swing on its own ---
        banner("solo flair: each servo moves on its own")
        for sid in servos:
            print(f"  -- id={sid} --")
            for offset in (+SOLO_AMPL, -SOLO_AMPL, +SOLO_AMPL // 2, 0):
                target = max(0, min(4095, home[sid] + offset))
                pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, target)
                time.sleep(0.7)

        # --- 3. speed showcase on first servo ---
        sid = servos[0]
        banner(f"speed showcase on id={sid}: slow then snappy")
        for label, speed in (("slow", 200), ("medium", 800), ("snappy", 2000)):
            print(f"  {label} (speed={speed})")
            pk.write2ByteTxRx(port, sid, ADDR_GOAL_SPEED, speed)
            for offset in (+SOLO_AMPL, -SOLO_AMPL, 0):
                target = max(0, min(4095, home[sid] + offset))
                pk.write2ByteTxRx(port, sid, ADDR_GOAL_POSITION, target)
                time.sleep(0.9)

        # --- 4. free mode: torque off, stream live positions ---
        banner(f"free mode: torque off for {FREE_SECONDS}s — move the arm by hand")
        for sid in servos:
            pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
        end = time.time() + FREE_SECONDS
        while time.time() < end:
            line = "  "
            for sid in servos:
                pos, _, _ = pk.read2ByteTxRx(port, sid, ADDR_PRESENT_POS)
                deg = (pos - 2048) * 360.0 / 4096.0  # signed degrees from center
                line += f"id{sid}={pos:>4} ({deg:+6.1f}°)   "
            print(line, end="\r", flush=True)
            time.sleep(0.05)
        print()

    finally:
        banner("disabling torque")
        for sid in servos:
            pk.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, 0)
        port.closePort()
        print("done.")


if __name__ == "__main__":
    main()
