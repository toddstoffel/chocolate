# Chocolate Factory – FairCom Edge Demo

A realistic chocolate factory IoT demo built on [FairCom Edge](https://www.faircom.com/edge). A Modbus TCP simulator exposes 3,982 plant-floor sensors as holding registers, FairCom Edge polls them into 17 integration tables, and a pre-seeded dataset lets you start exploring immediately.

## Quick start

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the demo (starts FairCom Edge, restores seed data, launches the Modbus simulator)
./demo.sh
```

FairCom Edge is available at **http://localhost:8080** (admin / ADMIN).

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python 3.9+
- [Git LFS](https://git-lfs.github.com/) (the `data_seed/` directory is stored with LFS)

After cloning, pull the LFS files if they weren't fetched automatically:

```bash
git lfs pull
```

## Project structure

```
├── demo.sh                  # One-command demo launcher
├── requirements.txt         # Python dependencies
├── docker/
│   ├── Dockerfile           # Optional custom FairCom Edge image
│   └── docker-compose.yml   # Container + volume mounts
├── simulator/
│   ├── config.py            # 3,982 sensor definitions and connection settings
│   ├── generate_data.py     # Schema setup, backfill, and live streaming
│   ├── modbus_simulator.py  # Async Modbus TCP server
│   └── check_state.py       # Prints row counts for all integration tables
├── config/                  # FairCom Edge server configuration
├── data/                    # Working data directory (bind-mounted into Docker)
├── data_seed/               # Pre-seeded snapshot (5,000 rows/table, stored in LFS)
└── libs/                    # FairCom Edge integration libraries
```

## How the demo works

```
  simulator/                   FairCom Edge              data/
  ──────────────────           ──────────────────────     ──────────────────
  Modbus TCP server       ←→   Modbus connector       →   17 integration tables
  (3,982 sensors as            (polls per-segment          (one per line segment)
   holding registers)           intervals, stores
                                readings continuously)
```

1. **`demo.sh`** stops any previous run, restores `data/` from the `data_seed/` snapshot (so every run starts with exactly 5,000 rows per table), starts FairCom Edge, launches the Modbus simulator, and connects FairCom Edge to it.
2. **FairCom Edge** runs in Docker with `data/`, `config/`, and `libs/` bind-mounted.
3. **The Modbus simulator** refreshes each sensor at its own realistic polling interval. FairCom Edge polls and stores readings continuously.

## Sensor coverage (3,982 tags)

Sensors are defined in `simulator/config.py` across 17 line segments and all shared plant systems.

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

Each sensor is assigned a realistic polling interval based on its function:

| Interval | Sensor types |
|---|---|
| 0.5 s | Inspection pass/fail, label and date-code checks |
| 1 s | Critical tempering temps, depositor vacuum/pressure, weight checks |
| 2 s | Vibration (X/Y/Z), current |
| 5 s | Flow, pressure, speed, power, valve position, door status |
| 10 s | General temperatures, humidity, fan speed, environmental, power factor |
| 30 s | Level, bearing temps, filter ΔP, batch weight, pH |
| 60 s | Viscosity, TDS, cumulative energy (kWh) |

## Modbus register layout

Each sensor occupies two consecutive 16-bit holding registers encoding an IEEE 754 float32 value in ABCD (big-endian) byte order — matching FairCom Edge's `"modbusRegisterType": "ieeefloat32ABCD"` setting.

| Sensor index | Register addresses |
|---|---|
| 0 | 0, 1 |
| 1 | 2, 3 |
| i | i×2, i×2+1 |

## Simulation model

Each sensor generates values using a per-sensor setpoint with:

- Gaussian noise scaled by a per-sensor `noise_std`
- Slow random drift that self-corrects over time
- Low-probability anomaly spikes (controlled by `ANOMALY_PROBABILITY` in `simulator/config.py`)
- Subtle sinusoidal oscillation to simulate PID cycling

## Distributing the demo

The `./data/` folder (FairCom's binary DB files, ~900 MB) is gitignored. To share a seeded demo:

1. Stop the container: `docker compose stop`
2. Zip the project folder including `./data/`
3. Recipient unzips and runs `docker compose up -d` — data loads immediately

No setup or backfill scripts needed on the receiving end.
