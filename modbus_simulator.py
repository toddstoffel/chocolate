"""
Chocolate Factory Modbus TCP Simulator for FairCom Edge

Runs a Modbus TCP server that exposes every chocolate-factory sensor
as a pair of holding registers (32-bit IEEE 754 float, ABCD byte order).
This simulates a factory PLC device.  FairCom Edge's built-in Modbus
connector polls this server and stores data into integration tables.

Typical workflow:
  1. docker compose up -d                     # start FairCom Edge
  2. python modbus_simulator.py               # start this device simulator
  3. python generate_data.py --mode setup     # connect FairCom to this device
                                              # (creates integration tables)
  4. python generate_data.py --mode backfill  # backfill historical data
  FairCom Edge then polls this simulator live at the configured interval.

Register layout (holding registers, unit-id 1):
  Sensor at index  i  → registers  [ i*2,  i*2+1 ]  (IEEE 754 float32 ABCD)

Usage:
    python modbus_simulator.py
    python modbus_simulator.py --port 5020
    python modbus_simulator.py --update-interval 0.5

Requirements:
    pip install pymodbus>=3.0
"""

import argparse
import asyncio
import math
import random
import struct
import sys
import time

try:
    from pymodbus.server import StartAsyncTcpServer
    from pymodbus.datastore import (
        ModbusSequentialDataBlock,
        ModbusServerContext,
    )
    # ModbusSlaveContext was renamed to ModbusDeviceContext in pymodbus 3.12
    try:
        from pymodbus.datastore import ModbusDeviceContext as ModbusSlaveContext
    except ImportError:
        from pymodbus.datastore import ModbusSlaveContext
except ImportError:
    print("ERROR: pymodbus is required.  Install with:  pip install pymodbus>=3.0")
    sys.exit(1)

from config import (
    SENSORS,
    ANOMALY_PROBABILITY,
    DRIFT_PROBABILITY,
    MODBUS_HOST,
    MODBUS_PORT,
    MODBUS_UNIT_ID,
)
from generate_data import SensorState

# ─── Register mapping ──────────────────────────────────────────────────────────
# Each sensor → 2 consecutive 16-bit holding registers (IEEE 754 float32)
NUM_REGISTERS = len(SENSORS) * 2    # total 16-bit words needed
TAG_TO_ADDR: dict[str, int] = {s["tag"]: i * 2 for i, s in enumerate(SENSORS)}




# ─── Float ↔ register encoding ─────────────────────────────────────────────────

def float_to_registers(value: float) -> tuple[int, int]:
    """Pack a float32 into two big-endian 16-bit unsigned ints."""
    packed = struct.pack(">f", float(value))
    hi = struct.unpack(">H", packed[0:2])[0]
    lo = struct.unpack(">H", packed[2:4])[0]
    return hi, lo


def registers_to_float(hi: int, lo: int) -> float:
    """Decode two big-endian 16-bit unsigned ints back to float32."""
    return struct.unpack(">f", struct.pack(">HH", hi, lo))[0]


# ─── Register updater ──────────────────────────────────────────────────────────

async def update_registers(context: ModbusServerContext, base_interval: float):
    """Update Modbus holding registers; each sensor refreshes at its own interval."""
    states      = {s["tag"]: SensorState(s) for s in SENSORS}
    last_update = {s["tag"]: -s.get("interval", base_interval) for s in SENSORS}
    t0   = time.time()
    tick = 0.1  # 100 ms base tick — precise enough for 0.5 s inspection sensors

    print(f"  Modbus registers updating (per-sensor intervals, {NUM_REGISTERS} registers, {len(SENSORS)} sensors)")
    while True:
        t     = time.time() - t0
        slave = context[0x00]

        for i, sensor in enumerate(SENSORS):
            tag = sensor["tag"]
            iv  = sensor.get("interval", base_interval)
            if t - last_update[tag] >= iv:
                value = states[tag].generate_value(t)
                hi, lo = float_to_registers(value)
                addr   = i * 2
                slave.setValues(3, addr,     [hi])   # high word
                slave.setValues(3, addr + 1, [lo])   # low  word
                last_update[tag] = t

        await asyncio.sleep(tick)


# ─── Main ──────────────────────────────────────────────────────────────────────

async def run(args):
    # Build Modbus datastore — add 10 padding registers so the last sensor
    # read (address + length) never hits the exact block boundary, which
    # causes pymodbus to return exception code 2 (ILLEGAL_DATA_ADDRESS).
    block   = ModbusSequentialDataBlock(0, [0] * (NUM_REGISTERS + 10))
    slave   = ModbusSlaveContext(hr=block)
    context = ModbusServerContext(devices=slave, single=True)

    tasks = [
        asyncio.create_task(update_registers(context, args.update_interval)),
    ]

    # Start Modbus TCP server (blocks until cancelled)
    print(f"Starting Modbus TCP server on {args.host}:{args.port}  (unit-id {MODBUS_UNIT_ID})")
    print(f"  {len(SENSORS)} sensors  |  {NUM_REGISTERS} holding registers")
    print("  Run  python generate_data.py --mode setup     to connect FairCom Edge to this device.")
    print("  Run  python generate_data.py --mode backfill  to populate historical data.")
    print("  Press Ctrl+C to stop.\n")

    server_task = asyncio.create_task(
        StartAsyncTcpServer(context, address=(args.host, args.port))
    )
    tasks.append(server_task)

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nShutting down simulator …")
        for t in tasks:
            t.cancel()


def main():
    parser = argparse.ArgumentParser(
        description="Chocolate Factory Modbus TCP Simulator for FairCom Edge"
    )
    parser.add_argument("--host", default=MODBUS_HOST, help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=MODBUS_PORT, help=f"TCP port (default: {MODBUS_PORT})")
    parser.add_argument("--update-interval", type=float, default=1.0,
                        help="Seconds between Modbus register updates (default: 1)")
    args = parser.parse_args()

    print("=" * 60)
    print("  CHOCOLATE FACTORY MODBUS TCP SIMULATOR")
    print("=" * 60)

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nDone.")


if __name__ == "__main__":
    main()
