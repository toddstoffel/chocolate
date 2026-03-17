"""
Chocolate Factory – Fake Data Generator for FairCom Edge

Generates realistic time-series sensor data for a chocolate bar
manufacturing line and publishes it to FairCom Edge via its REST/JSON API.

Usage:
    # Live streaming mode (pushes data every second)
    python generate_data.py --mode stream

    # Backfill historical data (default: 1 hour)
    python generate_data.py --mode backfill --seconds 3600

    # Dump to JSON files instead of sending to FairCom
    python generate_data.py --mode backfill --output json

    # Dump to CSV files
    python generate_data.py --mode backfill --output csv
"""

import argparse
import csv
import getpass
import json
import math
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

from config import (
    SENSORS,
    LINE_SEGMENTS,
    FAIRCOM_BASE_URL,
    FAIRCOM_DB,
    FAIRCOM_USER,
    FAIRCOM_PASSWORD,
    BACKFILL_SECONDS,
    DEFAULT_INTERVAL,
    ANOMALY_PROBABILITY,
    DRIFT_PROBABILITY,
    BATCH_DURATION_SECONDS,
    BATCH_PREFIX,
)

# ─── Helpers ───────────────────────────────────────────────────────────────────

def make_batch_id(batch_num: int) -> str:
    return f"{BATCH_PREFIX}-{batch_num:06d}"


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
        return round(value, 4)


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


def ensure_table(table_name: str, columns: list[dict]):
    """Create a table in FairCom Edge if it doesn't exist."""
    payload = {
        "api": "db",
        "action": "createTable",
        "params": {
            "databaseName": _db,
            "tableName": table_name,
            "fields": columns,
        },
    }
    result = faircom_api("db", payload, ok_codes={4021, 4022})
    if result is not None:
        print(f"  Table '{table_name}': OK")


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

READINGS_TABLE = "sensor_readings"
ALARMS_TABLE = "sensor_alarms"
BATCHES_TABLE = "batch_log"
SENSORS_TABLE = "sensor_registry"

# FairCom auto-adds a bigint 'id' primary key to every table.
# varchar fields require a separate 'length' property.
READINGS_COLUMNS = [
    {"name": "timestamp",  "type": "timestamp"},
    {"name": "tag",        "type": "varchar", "length": 64},
    {"name": "value",      "type": "float"},
    {"name": "unit",       "type": "varchar", "length": 16},
    {"name": "segment",    "type": "varchar", "length": 32},
    {"name": "batch_id",   "type": "varchar", "length": 32},
    {"name": "quality",    "type": "smallint"},
]

ALARMS_COLUMNS = [
    {"name": "timestamp",   "type": "timestamp"},
    {"name": "tag",         "type": "varchar", "length": 64},
    {"name": "value",       "type": "float"},
    {"name": "limit_type",  "type": "varchar", "length": 8},
    {"name": "limit_value", "type": "float"},
    {"name": "batch_id",    "type": "varchar", "length": 32},
]

BATCHES_COLUMNS = [
    {"name": "batch_id",     "type": "varchar", "length": 32},
    {"name": "start_time",   "type": "timestamp"},
    {"name": "end_time",     "type": "timestamp"},
    {"name": "product_code", "type": "varchar", "length": 32},
    {"name": "status",       "type": "varchar", "length": 16},
]

REGISTRY_COLUMNS = [
    {"name": "tag",          "type": "varchar", "length": 64},
    {"name": "description",  "type": "varchar", "length": 128},
    {"name": "unit",         "type": "varchar", "length": 16},
    {"name": "segment",      "type": "varchar", "length": 32},
    {"name": "setpoint",     "type": "float"},
    {"name": "low_limit",    "type": "float"},
    {"name": "high_limit",   "type": "float"},
    {"name": "dtype",        "type": "varchar", "length": 8},
    {"name": "interval_sec", "type": "float"},
]

PRODUCT_CODES = ["DARK-70", "DARK-85", "MILK-CLASSIC", "MILK-HAZELNUT", "WHITE-VANILLA"]


def create_schema():
    """Create all tables and seed the sensor registry."""
    # Create database first
    faircom_api("db", {
        "api": "db",
        "action": "createDatabase",
        "params": {"databaseName": _db},
    }, ok_codes={4021, 4022})

    ensure_table(READINGS_TABLE, READINGS_COLUMNS)
    ensure_table(ALARMS_TABLE, ALARMS_COLUMNS)
    ensure_table(BATCHES_TABLE, BATCHES_COLUMNS)
    ensure_table(SENSORS_TABLE, REGISTRY_COLUMNS)

    # Seed sensor registry
    registry_rows = []
    for s in SENSORS:
        registry_rows.append({
            "tag": s["tag"],
            "description": s["desc"],
            "unit": s["unit"],
            "segment": s["segment"],
            "setpoint": s["setpoint"],
            "low_limit": s["low_limit"],
            "high_limit": s["high_limit"],
            "dtype": s["dtype"],
            "interval_sec": s.get("interval", DEFAULT_INTERVAL),
        })
    insert_rows(SENSORS_TABLE, registry_rows)
    print(f"  ✓ sensor_registry  {len(registry_rows):,} sensors seeded")
    print("Schema creation complete.\n")


# ─── Data generation engine ───────────────────────────────────────────────────

def generate_readings(start_time: datetime, end_time: datetime):
    """Yield (timestamp, tag, value, unit, segment, batch_id, quality) tuples."""
    states = {s["tag"]: SensorState(s) for s in SENSORS}
    intervals = {s["tag"]: s.get("interval", DEFAULT_INTERVAL) for s in SENSORS}
    next_fire = {tag: 0.0 for tag in states}

    total_seconds = (end_time - start_time).total_seconds()
    batch_num = 1
    batch_start = 0.0
    batch_id = make_batch_id(batch_num)
    batches = []

    t = 0.0
    min_interval = min(intervals.values())

    while t <= total_seconds:
        ts = start_time + timedelta(seconds=t)
        ts_str = str(int(ts.timestamp()))

        # batch management
        if t - batch_start >= BATCH_DURATION_SECONDS:
            batches.append({
                "batch_id": batch_id,
                "start_time": str(int((start_time + timedelta(seconds=batch_start)).timestamp())),
                "end_time": ts_str,
                "product_code": random.choice(PRODUCT_CODES),
                "status": "completed",
            })
            batch_num += 1
            batch_start = t
            batch_id = make_batch_id(batch_num)

        for tag, state in states.items():
            if t < next_fire[tag]:
                continue
            next_fire[tag] = t + intervals[tag]

            value = state.generate_value(t)
            s = state.sensor

            # Determine quality flag
            quality = 0
            if s["dtype"] == "float":
                if value < s["low_limit"] or value > s["high_limit"]:
                    quality = 2
                elif (
                    value < s["low_limit"] + s["noise_std"] * 2
                    or value > s["high_limit"] - s["noise_std"] * 2
                ):
                    quality = 1

            yield {
                "timestamp": ts_str,
                "tag": tag,
                "value": float(value),
                "unit": s["unit"],
                "segment": s["segment"],
                "batch_id": batch_id,
                "quality": quality,
            }

        t += min_interval

    # Close final batch
    batches.append({
        "batch_id": batch_id,
        "start_time": str(int((start_time + timedelta(seconds=batch_start)).timestamp())),
        "end_time": str(int(end_time.timestamp())),
        "product_code": random.choice(PRODUCT_CODES),
        "status": "in_progress",
    })

    return batches


def run_backfill(seconds: int, output: str):
    """Generate historical data and either push to FairCom or save to files."""
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(seconds=seconds)

    print(f"Generating {seconds}s of backfill data  ({start_time} → {end_time})")
    print(f"  Sensors: {len(SENSORS)}")
    print()

    if output == "faircom":
        create_schema()

    readings = []
    alarms = []
    batches = []

    gen = generate_readings(start_time, end_time)

    # generate_readings is a generator that also returns batches at the end
    # We need to collect all readings
    for row in gen:
        readings.append(row)
        # Check for alarm
        if row["quality"] == 2:
            sensor_def = next(s for s in SENSORS if s["tag"] == row["tag"])
            limit_type = "high" if row["value"] > sensor_def["high_limit"] else "low"
            limit_val = (
                sensor_def["high_limit"]
                if limit_type == "high"
                else sensor_def["low_limit"]
            )
            alarms.append({
                "timestamp": row["timestamp"],
                "tag": row["tag"],
                "value": row["value"],
                "limit_type": limit_type,
                "limit_value": limit_val,
                "batch_id": row["batch_id"],
            })

    # generate_readings returns batches via StopIteration value
    # Re-generate batch info
    batch_num = 1
    batch_start_t = start_time
    while batch_start_t < end_time:
        batch_end_t = min(batch_start_t + timedelta(seconds=BATCH_DURATION_SECONDS), end_time)
        status = "completed" if batch_end_t < end_time else "in_progress"
        batches.append({
            "batch_id": make_batch_id(batch_num),
            "start_time": str(int(batch_start_t.timestamp())),
            "end_time": str(int(batch_end_t.timestamp())),
            "product_code": random.choice(PRODUCT_CODES),
            "status": status,
        })
        batch_num += 1
        batch_start_t = batch_end_t

    print(f"\n  Generated {len(readings):,} readings, {len(alarms):,} alarms, {len(batches)} batches")

    if output == "faircom":
        # Bulk insert readings with live progress
        chunk_size = 5000
        total_readings = len(readings)
        num_chunks = max(1, (total_readings + chunk_size - 1) // chunk_size)
        for idx, i in enumerate(range(0, total_readings, chunk_size), 1):
            insert_rows(READINGS_TABLE, readings[i : i + chunk_size])
            so_far = min(i + chunk_size, total_readings)
            print(
                f"  sensor_readings  chunk {idx}/{num_chunks}  "
                f"({so_far:,} / {total_readings:,} rows)",
                end="\r", flush=True,
            )
        print(f"  sensor_readings  {total_readings:,} rows inserted  ✓" + " " * 20)
        insert_rows(ALARMS_TABLE, alarms)
        print(f"  sensor_alarms    {len(alarms):,} rows inserted  ✓")
        insert_rows(BATCHES_TABLE, batches)
        print(f"  batch_log        {len(batches):,} rows inserted  ✓")
        print("\nBackfill complete – data is in FairCom Edge.")

    elif output == "json":
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)
        with open(out_dir / "sensor_readings.json", "w") as f:
            json.dump(readings, f, indent=2)
        with open(out_dir / "sensor_alarms.json", "w") as f:
            json.dump(alarms, f, indent=2)
        with open(out_dir / "batch_log.json", "w") as f:
            json.dump(batches, f, indent=2)
        with open(out_dir / "sensor_registry.json", "w") as f:
            registry = []
            for s in SENSORS:
                registry.append({
                    "tag": s["tag"],
                    "description": s["desc"],
                    "unit": s["unit"],
                    "segment": s["segment"],
                    "setpoint": s["setpoint"],
                    "low_limit": s["low_limit"],
                    "high_limit": s["high_limit"],
                    "dtype": s["dtype"],
                    "interval_sec": s.get("interval", DEFAULT_INTERVAL),
                })
            json.dump(registry, f, indent=2)
        print(f"\nFiles written to {out_dir.resolve()}/")

    elif output == "csv":
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)

        with open(out_dir / "sensor_readings.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(readings[0].keys()))
            w.writeheader()
            w.writerows(readings)

        if alarms:
            with open(out_dir / "sensor_alarms.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(alarms[0].keys()))
                w.writeheader()
                w.writerows(alarms)

        with open(out_dir / "batch_log.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(batches[0].keys()))
            w.writeheader()
            w.writerows(batches)

        print(f"\nCSV files written to {out_dir.resolve()}/")


def run_stream():
    """Stream live data to FairCom Edge in real time."""
    create_schema()

    states = {s["tag"]: SensorState(s) for s in SENSORS}
    intervals = {s["tag"]: s.get("interval", DEFAULT_INTERVAL) for s in SENSORS}
    last_fire = {tag: 0.0 for tag in states}

    batch_num = 1
    batch_id = make_batch_id(batch_num)
    batch_start = time.time()

    print("Streaming live data to FairCom Edge.  Ctrl+C to stop.\n")
    t0 = time.time()

    try:
        while True:
            now = time.time()
            elapsed = now - t0
            ts_str = str(int(now))

            # Batch rollover
            if now - batch_start >= BATCH_DURATION_SECONDS:
                insert_rows(BATCHES_TABLE, [{
                    "batch_id": batch_id,
                    "start_time": str(int(batch_start)),
                    "end_time": ts_str,
                    "product_code": random.choice(PRODUCT_CODES),
                    "status": "completed",
                }])
                batch_num += 1
                batch_id = make_batch_id(batch_num)
                batch_start = now

            readings_batch = []
            alarms_batch = []

            for tag, state in states.items():
                if elapsed - last_fire[tag] < intervals[tag]:
                    continue
                last_fire[tag] = elapsed

                value = state.generate_value(elapsed)
                s = state.sensor
                quality = 0
                if s["dtype"] == "float":
                    if value < s["low_limit"] or value > s["high_limit"]:
                        quality = 2
                    elif (
                        value < s["low_limit"] + s["noise_std"] * 2
                        or value > s["high_limit"] - s["noise_std"] * 2
                    ):
                        quality = 1

                row = {
                    "timestamp": ts_str,
                    "tag": tag,
                    "value": float(value),
                    "unit": s["unit"],
                    "segment": s["segment"],
                    "batch_id": batch_id,
                    "quality": quality,
                }
                readings_batch.append(row)

                if quality == 2:
                    limit_type = "high" if value > s["high_limit"] else "low"
                    alarms_batch.append({
                        "timestamp": ts_str,
                        "tag": tag,
                        "value": float(value),
                        "limit_type": limit_type,
                        "limit_value": s["high_limit"] if limit_type == "high" else s["low_limit"],
                        "batch_id": batch_id,
                    })

            if readings_batch:
                insert_rows(READINGS_TABLE, readings_batch)
            if alarms_batch:
                insert_rows(ALARMS_TABLE, alarms_batch)

            count_str = f"{len(readings_batch)} readings"
            if alarms_batch:
                count_str += f", {len(alarms_batch)} alarms"
            print(f"  [{ts_str}] {batch_id}  {count_str}")

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
    parser.add_argument("--host",     default=None, help="FairCom Edge hostname (default: localhost)")
    parser.add_argument("--port",     type=int, default=None, help="FairCom Edge HTTP port (default: 8080)")
    parser.add_argument("--user",     default=None, help="FairCom username")
    parser.add_argument("--password", default=None, help="FairCom password")
    parser.add_argument("--db",       default=None, help="FairCom database name")
    parser.add_argument("--yes", "-y", action="store_true", help="Accept all defaults non-interactively")
    args = parser.parse_args()

    print("=" * 60)
    print("  CHOCOLATE FACTORY DATA SIMULATOR")
    print("  FairCom Edge Edition")
    print("=" * 60)
    print()

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
        print(f"\nConnecting to {base_url} …\n")
        print(f"  Authenticating as '{user}' … ", end="", flush=True)
        if not faircom_connect(base_url, user, password, db):
            print("✗")
            print("  Is the container running?  docker compose up -d")
            sys.exit(1)
        print("✓\n")

    if args.mode == "setup":
        create_schema()
    elif args.mode == "backfill":
        run_backfill(args.seconds, args.output)
    elif args.mode == "stream":
        run_stream()


if __name__ == "__main__":
    main()
