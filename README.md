# Chocolate Factory – FairCom Edge Demo

A complete chocolate factory IoT demo built on [FairCom Edge](https://www.faircom.com/edge). It includes a Modbus TCP simulator that exposes 3,982 plant-floor sensors as holding registers, a data backfill tool that pre-loads ~90,000 rows of realistic historical data, and a Docker Compose setup that brings the whole stack up in a single command.

## Architecture

```
  modbus_simulator.py          FairCom Edge              ./data/
  ─────────────────────        ──────────────────────     ──────────────────
  Modbus TCP server       ←→   Modbus connector       →   17 integration tables
  (3,982 sensors as            (polls per-segment          (one per line segment)
   holding registers)           intervals, stores
                                readings continuously)
  generate_data.py    ─────────────────────────────────►  same integration tables
  (setup + bulk backfill via JSON API)
```

FairCom Edge runs in Docker and stores all data in `./data/` (a local bind mount). The `./data/` directory is gitignored and distributed separately — when it is present, `docker compose up` starts with all historical data already loaded.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python 3.9+
- A FairCom Edge license file (place it in `./license/` as `ctsrvr<serial>.lic`)

Install Python dependencies (no virtual environment required):

```bash
pip install pymodbus>=3.0 requests
```

## Quick start

```bash
# 1. Start FairCom Edge (loads pre-seeded data if ./data/ is present)
docker compose up -d

# 2. (First run only) Create the 17 integration tables and connect to the simulator
python generate_data.py --mode setup -y

# 3. (Optional) Bulk-backfill ~90k rows of historical data
python generate_data.py --mode backfill --seconds 10600 --row-delay 0 -y

# 4. Start the live Modbus TCP simulator on port 5020
python modbus_simulator.py
```

FairCom Edge's REST API and Explorer are available at **http://localhost:8080** (admin / ADMIN).

## Files

| File | Purpose |
|---|---|
| `config.py` | All 3,982 sensor definitions, per-sensor polling intervals, and connection defaults |
| `generate_data.py` | Schema setup, historical backfill, and live streaming via FairCom JSON API |
| `modbus_simulator.py` | Async Modbus TCP server — each sensor refreshes at its own realistic interval |
| `check_state.py` | Prints live row counts for all 17 integration tables |
| `docker-compose.yml` | Runs FairCom Edge with bind-mounted `./data/`, `./config/`, and `./libs/` |
| `Dockerfile` | Builds a licensed image — removes the eval license baked into the base image |
| `requirements.txt` | Python dependencies |

## Sensor coverage (3,982 tags)

Sensors are generated in `config.py` across 17 line segments and all shared plant systems.

| Segment | Description | Tags |
|---|---|---|
| `tempering` | 13 tempering machines × 22 zones — temps, speed, viscosity, power | 286 |
| `cooling_tunnel` | 5 tunnels × 18 zones × fan/belt/temp/humidity per zone | 1,235 |
| `depositing` | Chocolate temp, vacuum, pressure, pump speed per depositor | 65 |
| `demolding` | Vibration, cylinder pressure, belt speed, motor health | 39 |
| `inspection` | Vision system pass/fail, weight, date-code check (0.5 s polling) | 78 |
| `packaging` | Bar count, label/date OK, film tension, rejects, sealer temp | 104 |
| `mixing_conching` | 24 conching vessels — temp, torque, speed, vibration, power | 120 |
| `refining` | 16 ball mills — inlet/outlet temp, pressure, speed, power | 160 |
| `roasting` | 6 roasters — drum/bean/exhaust temp, gas flow, moisture, vibration | 48 |
| `ingredient_dosing` | 10 dosing weighers — batch weight, feed rate, belt speed | 244 |
| `utilities` | 8 compressors, 4 boilers, 12 chilled-water circuits, 4 compressed-air systems | 440 |
| `hvac` | 50 AHUs — supply/return temp, humidity, fan speed, filter ΔP | 330 |
| `cold_storage` | 12 cold rooms + 4 freezers — multi-point temp, door, defrost, refrigerant | 120 |
| `energy` | 150 sub-meters — active power (kW), cumulative energy (kWh), power factor | 450 |
| `environmental` | 80 zones — temperature, humidity, CO₂ | 195 |
| `water_treatment` | 4 RO units, 4 process water tanks — flow, pH, TDS, conductivity | 32 |
| `palletizing` | 6 palletizers — cycle rate, arm torque/speed, gripper vacuum, pallet weight | 36 |
| **Total** | | **3,982** |

## Polling intervals

Each sensor is assigned a realistic polling interval in `config.py` based on its function:

| Interval | Sensor types |
|---|---|
| 0.5 s | Inspection pass/fail, label and date-code checks |
| 1 s | Critical tempering temps, depositor vacuum/pressure, weight checks |
| 2 s | Vibration (X/Y/Z), current |
| 5 s | Flow, pressure, speed, power, valve position, door status |
| 10 s | General temperatures, humidity, fan speed, environmental, power factor |
| 30 s | Level, bearing temps, filter ΔP, batch weight, pH |
| 60 s | Viscosity, TDS, cumulative energy (kWh) |

The Modbus simulator ticks at 100 ms and refreshes each register only when its interval elapses. FairCom Edge connector poll rates match the fastest sensor in each segment.

## Modbus register layout

Each sensor occupies two consecutive 16-bit holding registers encoding an IEEE 754 float32 value in ABCD (big-endian) byte order — matching FairCom Edge's `"modbusRegisterType": "ieeefloat32ABCD"` setting.

| Sensor index | Register addresses |
|---|---|
| 0 | 0, 1 |
| 1 | 2, 3 |
| i | i×2, i×2+1 |

## Simulation model

Each sensor generates values using a per-sensor setpoint with the following applied on top:

- Gaussian noise scaled by a per-sensor `noise_std`
- Slow random drift that self-corrects over time
- Low-probability anomaly spikes (controlled by `ANOMALY_PROBABILITY` in `config.py`)
- Subtle sinusoidal oscillation to simulate PID cycling

## Distributing the demo

The `./data/` folder (FairCom's binary DB files, ~900 MB) is gitignored. To share a seeded demo:

1. Stop the container: `docker compose stop`
2. Zip the project folder including `./data/`
3. Recipient unzips and runs `docker compose up -d` — data loads immediately

No setup or backfill scripts needed on the receiving end.
