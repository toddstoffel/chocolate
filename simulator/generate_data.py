"""
Chocolate Factory – FairCom Edge Setup and Data Backfill

Mirrors what a factory user would do when onboarding FairCom Edge:
  1. Start FairCom Edge and the Modbus device simulator.
  2. "Connect to the sensor" – create a Modbus input in FairCom Edge that
     points at the simulator.  FairCom auto-creates the sensor_readings
     integration table and begins polling immediately.
  3. Backfill that same integration table with realistic historical data so
     dashboards and queries have a populated dataset from day one.

Usage:
    # Connect FairCom Edge to the Modbus simulator (auto-creates sensor_readings)
    python generate_data.py --mode setup

    # Backfill 30 minutes of historical data into the integration tables
    python generate_data.py

    # Backfill a custom time window
    python generate_data.py --seconds 7200

    # Dump to JSON files instead of sending to FairCom
    python generate_data.py --output json

    # Stream live data directly to FairCom (mirrors what the Modbus connector
    # writes, one snapshot per poll interval)
    python generate_data.py --mode stream
"""

import argparse
import csv
import getpass
import json
import math
import os
import random
import struct
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

from simulator.config import (
    SENSORS,
    FAIRCOM_DB,
    FAIRCOM_USER,
    FAIRCOM_PASSWORD,
    BACKFILL_SECONDS,
    DEFAULT_INTERVAL,
    ANOMALY_PROBABILITY,
    DRIFT_PROBABILITY,
    MODBUS_CONNECT_HOST,
    MODBUS_PORT,
    MODBUS_UNIT_ID,
)

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _as_float32(v: float) -> float:
    """Quantize v to IEEE 754 single-precision, matching Modbus 32-bit register precision."""
    return struct.unpack('f', struct.pack('f', v))[0]


class SensorState:
    """Tracks per-sensor drift and anomaly state."""

    def __init__(self, sensor_def: dict):
        self.sensor = sensor_def
        self.drift = 0.0
        self.drift_rate = 0.0
        self.drifting = False

    def generate_value(self, t: float) -> float | int | bool:
        s = self.sensor
        sp = s["setpoint"]

        # Bool sensors: random failure with low probability
        if s["dtype"] == "bool":
            return 0 if random.random() < 0.002 else 1

        # Evolve drift
        if self.drifting:
            self.drift += self.drift_rate
            if abs(self.drift) > (s["high_limit"] - s["low_limit"]) * 0.3:
                self.drifting = False
                self.drift *= 0.5
        elif random.random() < DRIFT_PROBABILITY:
            self.drifting = True
            self.drift_rate = random.choice([-1, 1]) * s["noise_std"] * 0.05

        # Base value with noise
        noise = random.gauss(0, s["noise_std"]) if s["noise_std"] > 0 else 0
        value = sp + noise + self.drift

        # Inject occasional anomaly
        if random.random() < ANOMALY_PROBABILITY:
            direction = random.choice([-1, 1])
            spike = direction * s["noise_std"] * random.uniform(5, 12)
            value += spike

        # Subtle sinusoidal process oscillation (simulates PID cycling)
        period = random.uniform(120, 300)  # seeded per call is fine for fake data
        value += s["noise_std"] * 0.3 * math.sin(2 * math.pi * t / period)

        if s["dtype"] == "int":
            return max(int(round(value)), 0)
        return _as_float32(value)


# ─── FairCom Edge API calls ───────────────────────────────────────────────────

_auth_token: str | None = None
_base_url: str = ""
_db: str = ""


def faircom_connect(base_url: str, user: str, password: str, db: str) -> bool:
    """Authenticate with FairCom Edge and store the session token and connection details."""
    global _auth_token, _base_url, _db
    if requests is None:
        print("ERROR: 'requests' library is required for FairCom mode.  pip install requests")
        sys.exit(1)
    _base_url = base_url
    _db = db
    url = f"{base_url}/api/admin"
    payload = {
        "api": "admin",
        "action": "createSession",
        "params": {"username": user, "password": password},
    }
    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        _auth_token = data.get("authToken")
        if not _auth_token:
            print(f"  Login failed: {data.get('errorMessage', 'unknown')}")
            return False
        return True
    except requests.RequestException as exc:
        print(f"  Connection error: {exc}")
        return False


def faircom_api(endpoint: str, payload: dict, ok_codes: set = frozenset()) -> dict | None:
    """POST to FairCom Edge JSON action API."""
    if requests is None:
        print("ERROR: 'requests' library is required for FairCom mode.  pip install requests")
        sys.exit(1)
    if _auth_token is None:
        print("ERROR: Not authenticated. Call faircom_connect() first.")
        return None
    url = f"{_base_url}/api/{endpoint}"
    payload["authToken"] = _auth_token
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        error_code = data.get("errorCode", -1)
        if error_code != 0 and error_code not in ok_codes:
            action = payload.get("action", "?")
            print(f"  FairCom Error [{error_code}] ({action}): {data.get('errorMessage', 'unknown')}")
            return None
        return data
    except requests.RequestException as exc:
        print(f"  FairCom API error ({endpoint}): {exc}")
        return None


# Build a stable lookup: segment → [(global_sensor_index, sensor_dict), ...]
# Ordered by appearance in SENSORS so register addresses are deterministic.
_SEGMENT_SENSORS: dict[str, list[tuple[int, dict]]] = {}
for _i, _s in enumerate(SENSORS):
    _SEGMENT_SENSORS.setdefault(_s["segment"], []).append((_i, _s))


def setup_modbus_connectors(modbus_server: str = None, modbus_port: int = None):
    """Create one Modbus input (and integration table) per line segment.

    Each input maps only the sensors belonging to that segment.  Register
    addresses are the global sensor index × 2, matching the simulator layout.
    FairCom Edge auto-creates each integration table and begins polling.
    """
    server = modbus_server or MODBUS_CONNECT_HOST
    port   = modbus_port   or MODBUS_PORT

    # Remove old single-input if it still exists
    faircom_api("hub", {
        "api": "hub", "action": "deleteInput",
        "params": {"inputName": "modbus_simulator"},
    }, ok_codes=frozenset(range(12000, 12100)))

    # Delete old sensor_readings integration table
    faircom_api("hub", {
        "api": "hub", "action": "deleteIntegrationTables",
        "params": {"databaseName": _db, "tableNames": ["sensor_readings"]},
    }, ok_codes=frozenset(range(12000, 12100)))

    created = 0
    for seg_name, sensor_list in _SEGMENT_SENSORS.items():
        # Idempotent – delete the input if it already exists
        faircom_api("hub", {
            "api": "hub", "action": "deleteInput",
            "params": {"inputName": seg_name},
        }, ok_codes=frozenset(range(12000, 12100)))

        property_map = [
            {
                "propertyPath":       s["tag"],
                "modbusDataAccess":   "holdingregister",
                "modbusDataAddress":  i * 2,       # global register address
                "modbusUnitId":       MODBUS_UNIT_ID,
                "modbusDataLen":      2,
                "modbusRegisterType": "ieeefloat32ABCD",
            }
            for i, s in sensor_list
        ]

        result = faircom_api("hub", {
            "api": "hub",
            "action": "createInput",
            "params": {
                "inputName":   seg_name,
                "serviceName": "modbus",
                "settings": {
                    "modbusProtocol":                    "TCP",
                    "modbusServer":                      server,
                    "modbusServerPort":                  port,
                    "dataCollectionIntervalMilliseconds": max(500, int(
                        min(s.get("interval", DEFAULT_INTERVAL) for _, s in sensor_list) * 1000
                    )),
                    "propertyMapList":                   property_map,
                },
                "databaseName": _db,
                "tableName":    seg_name,
            },
        })
        if result is not None:
            print(f"  [{seg_name}]  {len(sensor_list)} sensors → table '{seg_name}'")
            created += 1

    print(f"  {created}/{len(_SEGMENT_SENSORS)} segment inputs created")
    print(f"  FairCom Edge will poll {server}:{port} (per-segment fastest interval used)")


def insert_rows(table_name: str, rows: list[dict]):
    """Bulk insert rows into a FairCom Edge table."""
    if not rows:
        return
    payload = {
        "api": "db",
        "action": "insertRecords",
        "params": {
            "databaseName": _db,
            "tableName": table_name,
            "dataFormat": "objects",
            "sourceData": rows,
        },
    }
    result = faircom_api("db", payload)
    if result:
        return result.get("data", {}).get("rowsInserted", len(rows))
    return 0


# ─── Schema creation ──────────────────────────────────────────────────────────


def create_schema(modbus_server: str = None, modbus_port: int = None):
    """Create one Modbus input + integration table per line segment.

    FairCom Edge auto-creates each integration table and begins polling the
    Modbus simulator immediately after each createInput call.
    """
    setup_modbus_connectors(modbus_server, modbus_port)
    print("Setup complete.")


# ─── Data generation engine ───────────────────────────────────────────────────

def generate_snapshots(start_time: datetime, end_time: datetime):
    """Yield (ts_str, snapshot_dict) tuples, one per DEFAULT_INTERVAL tick.

    Mirrors real PLC / Modbus holding-register behaviour: each sensor value
    is regenerated only when its own polling interval elapses and held at the
    last reading between updates — exactly what FairCom Edge would collect.
    """
    states      = {s["tag"]: SensorState(s) for s in SENSORS}
    current     = {s["tag"]: float(states[s["tag"]].generate_value(0.0)) for s in SENSORS}
    next_update = {s["tag"]: 0.0 for s in SENSORS}
    total_s = (end_time - start_time).total_seconds()
    t = 0.0

    while t <= total_s:
        ts     = start_time + timedelta(seconds=t)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        for s in SENSORS:
            tag = s["tag"]
            if t >= next_update[tag]:
                current[tag]     = float(states[tag].generate_value(t))
                next_update[tag] = t + s.get("interval", DEFAULT_INTERVAL)

        yield ts_str, dict(current)
        t += DEFAULT_INTERVAL


def _sql(query: str) -> dict:
    """Execute a SQL statement via runSqlStatements and return the first reaction."""
    result = faircom_api("db", {
        "api": "db",
        "action": "runSqlStatements",
        "params": {"databaseName": _db, "sqlStatements": [query]},
    })
    if result is None:
        return {}
    return result.get("result", {}).get("reactions", [{}])[0]


def run_backfill(seconds: int, output: str, segment: str | None = None,
                 row_delay: float = 2.0):
    """Generate historical data and either push to FairCom or save to files.

    Args:
        seconds:    How many seconds of history to generate.
        output:     'faircom', 'json', or 'csv'.
        segment:    If given, only backfill the named segment (e.g. 'cold_storage').
                    Useful for targeted testing.  None means all segments.
        row_delay:  Seconds to sleep between inserting each time-slot row (faircom
                    mode only).  Each slot inserts one row per segment so the outer
                    create_ts is spread over ``row_delay * num_snapshots`` seconds,
                    making the backfill data usable in time-series charts.
                    Default: 2.0 s (31 snapshots × 2 s ≈ 62 s total).
                    Use 0 for the legacy bulk-insert behaviour.
    """
    end_time   = datetime.now(timezone.utc)
    start_time = end_time - timedelta(seconds=seconds)

    # Filter to the requested segment(s)
    if segment:
        if segment not in _SEGMENT_SENSORS:
            print(f"ERROR: segment '{segment}' not found.  Known: {sorted(_SEGMENT_SENSORS)}")
            return
        seg_items = {segment: _SEGMENT_SENSORS[segment]}
    else:
        seg_items = _SEGMENT_SENSORS

    num_segs = len(seg_items)
    sensor_count = sum(len(v) for v in seg_items.values())
    print(f"Generating {seconds}s of backfill data  ({start_time} → {end_time})")
    print(f"  Segments: {num_segs}  |  Sensors: {sensor_count}")
    print()

    all_snapshots: list[tuple[str, dict]] = []
    for ts_str, snap in generate_snapshots(start_time, end_time):
        all_snapshots.append((ts_str, snap))

    total = len(all_snapshots)
    print(f"  Generated {total:,} snapshots")

    if output == "faircom":
        # Build per-segment tag lists once.
        seg_tags = {seg_name: [s["tag"] for _, s in sensor_list]
                    for seg_name, sensor_list in seg_items.items()}

        if row_delay > 0:
            # ── Trickle mode ────────────────────────────────────────────────
            # Insert ONE row per segment per time-slot, then sleep row_delay
            # seconds.  This ensures each backfill row receives a distinct
            # server-side create_ts, making the data usable in time-series
            # charts without requiring a 30-minute wait.
            est_secs = total * row_delay
            print(f"  Trickle mode: {total} slots × {row_delay}s delay ≈ {est_secs:.0f}s total")
            print(f"  Inserting across {num_segs} segment(s) …\n")
            seg_failed = {seg_name: 0 for seg_name in seg_items}
            for slot_idx, (ts_str, snap) in enumerate(all_snapshots, 1):
                for seg_name, tags in seg_tags.items():
                    row = {"error": False,
                           "source_payload": {"create_ts": ts_str,
                                              **{t: snap[t] for t in tags}}}
                    ok = insert_rows(seg_name, [row])
                    if not ok:
                        seg_failed[seg_name] += 1
                pct = slot_idx / total * 100
                print(f"  Slot {slot_idx:>3}/{total}  ({pct:.0f}%)  ts={ts_str}",
                      end="\r", flush=True)
                if slot_idx < total:
                    time.sleep(row_delay)
            print()  # clear the progress line
            for seg_name in seg_items:
                failed = seg_failed[seg_name]
                status = "✗" if failed else "✓"
                print(f"  {seg_name:<25} {total:,} rows  {status}")
        else:
            # ── Bulk mode (legacy) ───────────────────────────────────────────
            chunk_size = 500
            for seg_name, tags in seg_tags.items():
                # Include create_ts inside source_payload so historical time is
                # preserved.  (The outer create_ts column is auto-set to insertion
                # time by FairCom and cannot be overridden via the HTTP API.)
                rows = [
                    {"error": False,
                     "source_payload": {"create_ts": ts_str, **{t: snap[t] for t in tags}}}
                    for ts_str, snap in all_snapshots
                ]
                failed = 0
                num_chunks = max(1, (total + chunk_size - 1) // chunk_size)
                for idx, i in enumerate(range(0, total, chunk_size), 1):
                    ok = insert_rows(seg_name, rows[i: i + chunk_size])
                    if not ok:
                        failed += len(rows[i: i + chunk_size])
                    print(f"  {seg_name:<25} chunk {idx}/{num_chunks}", end="\r", flush=True)
                status = "✗" if failed else "✓"
                print(f"  {seg_name:<25} {total:,} rows  {status}" + " " * 10)
        print("\nBackfill complete – data is in FairCom Edge.")

    elif output == "json":
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)
        for seg_name, sensor_list in seg_items.items():
            tags = [s["tag"] for _, s in sensor_list]
            data = [{"create_ts": ts, "source_payload": {"create_ts": ts, **{t: snap[t] for t in tags}}}
                    for ts, snap in all_snapshots]
            with open(out_dir / f"{seg_name}.json", "w") as f:
                json.dump(data, f, indent=2)
        print(f"\nJSON files written to {out_dir.resolve()}/")

    elif output == "csv":
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)
        for seg_name, sensor_list in seg_items.items():
            tags = [s["tag"] for _, s in sensor_list]
            rows = [{"create_ts": ts, **{t: snap[t] for t in tags}}
                    for ts, snap in all_snapshots]
            with open(out_dir / f"{seg_name}.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        print(f"\nCSV files written to {out_dir.resolve()}/")



def run_stream():
    """Stream live data to FairCom Edge in real time (one snapshot per interval)."""
    states = {s["tag"]: SensorState(s) for s in SENSORS}

    print("Streaming live data to FairCom Edge.  Ctrl+C to stop.\n")
    t0 = time.time()

    try:
        while True:
            now     = time.time()
            elapsed = now - t0
            ts_str  = datetime.utcfromtimestamp(now).strftime("%Y-%m-%dT%H:%M:%S")

            snapshot = {s["tag"]: float(states[s["tag"]].generate_value(elapsed)) for s in SENSORS}

            for seg_name, sensor_list in _SEGMENT_SENSORS.items():
                tags = [s["tag"] for _, s in sensor_list]
                insert_rows(seg_name, [{"source_payload": {"create_ts": ts_str,
                                                           **{t: snapshot[t] for t in tags}}}])

            print(f"  [{ts_str}]  {len(_SEGMENT_SENSORS)} segments ({len(snapshot)} sensors)")

            time.sleep(DEFAULT_INTERVAL)

    except KeyboardInterrupt:
        print("\n\nStreaming stopped.")


# ─── CLI ───────────────────────────────────────────────────────────────────────

def prompt(label: str, default: str, secret: bool = False) -> str:
    """Prompt the user for a value, showing the default. Hidden input for secrets."""
    display_default = "****" if secret else default
    prompt_str = f"  {label} [{display_default}]: "
    if secret:
        value = getpass.getpass(prompt_str)
    else:
        value = input(prompt_str).strip()
    return value if value else default


def main():
    parser = argparse.ArgumentParser(
        description="Chocolate Factory data simulator for FairCom Edge"
    )
    parser.add_argument(
        "--mode",
        choices=["setup", "backfill", "stream"],
        default="backfill",
        help="setup = create schema only; backfill = generate historical data; stream = real-time",
    )
    parser.add_argument(
        "--output",
        choices=["faircom", "json", "csv"],
        default="faircom",
        help="Where to send generated data (default: faircom)",
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=BACKFILL_SECONDS,
        help=f"Seconds of historical data to backfill (default: {BACKFILL_SECONDS})",
    )
    parser.add_argument("--host",          default=None, help="FairCom Edge hostname (default: localhost)")
    parser.add_argument("--port",          type=int, default=None, help="FairCom Edge HTTP port (default: 8080)")
    parser.add_argument("--modbus-server", default=None, help="Modbus device hostname (default: from config)")
    parser.add_argument("--modbus-port",   type=int, default=None, help="Modbus device TCP port (default: from config)")
    parser.add_argument("--user",     default=None, help="FairCom username")
    parser.add_argument("--password", default=None, help="FairCom password")
    parser.add_argument("--db",       default=None, help="FairCom database name")
    parser.add_argument(
        "--segment",
        default=None,
        help="Backfill only this segment (e.g. cold_storage). Default: all segments",
    )
    parser.add_argument(
        "--row-delay",
        type=float,
        default=2.0,
        dest="row_delay",
        help=(
            "Seconds to sleep between time-slot rows during backfill (faircom mode).\n"
            "  2.0 (default) → 31 rows × 2 s ≈ 62 s total, timestamps spread naturally.\n"
            "  60.0           → real-time cadence (one row per minute, ~31 min total).\n"
            "  0              → legacy bulk insert (all rows get the same create_ts).\n"
        ),
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Accept all defaults non-interactively")
    args = parser.parse_args()

    needs_faircom = args.mode in ("setup", "stream") or (
        args.mode == "backfill" and args.output == "faircom"
    )

    if needs_faircom:
        if args.yes:
            host     = args.host     or "localhost"
            port     = args.port     or 8080
            user     = args.user     or FAIRCOM_USER
            password = args.password or FAIRCOM_PASSWORD
            db       = args.db       or FAIRCOM_DB
        else:
            print("Press Enter to accept the default value shown in brackets.\n")
            host     = args.host     or prompt("Host",     "localhost")
            port     = int(args.port or prompt("Port",     "8080"))
            user     = args.user     or prompt("Username", FAIRCOM_USER)
            password = args.password or prompt("Password", FAIRCOM_PASSWORD, secret=True)
            db       = args.db       or prompt("Database", FAIRCOM_DB)

        base_url = f"http://{host}:{port}"
        print(f"Connecting to {base_url} …")
        print(f"\n  Authenticating as '{user}' … ", end="", flush=True)
        if not faircom_connect(base_url, user, password, db):
            print("✗")
            print("  Is the container running?  docker compose up -d")
            sys.exit(1)
        print("✓")

    if args.mode == "setup":
        create_schema(
            modbus_server=args.modbus_server or MODBUS_CONNECT_HOST,
            modbus_port=args.modbus_port or MODBUS_PORT,
        )
    elif args.mode == "backfill":
        run_backfill(args.seconds, args.output, segment=args.segment,
                     row_delay=args.row_delay)
    elif args.mode == "stream":
        run_stream()


if __name__ == "__main__":
    main()
