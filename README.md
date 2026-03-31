# Chocolate Factory – FairCom Edge Modbus Simulator

A Python-based Modbus TCP simulator and data backfill tool for
[FairCom Edge](https://www.faircom.com/edge). The simulator exposes 3,982
chocolate-factory sensors as Modbus holding registers so that FairCom Edge's
native Modbus connector can collect and store live data into integration tables
automatically. `generate_data.py` creates the integration table schema and
backfills those tables with realistic historical sensor data.

## Architecture

```
  modbus_simulator.py          FairCom Edge              FairCom Edge DB
  ─────────────────────        ──────────────────────     ──────────────────
  Modbus TCP server       ←→   Modbus connector       →   integration tables
  (3,982 sensors as            (polls registers,           sensor_readings
   holding registers)           stores readings)            sensor_alarms
                                                            batch_log
  generate_data.py    ─────────────────────────────────►   sensor_registry
  (schema setup + backfill via JSON API)
```

## Files

| File | Purpose |
|---|---|
| `config.py` | Sensor definitions, simulation parameters, and FairCom connection defaults |
| `generate_data.py` | Creates integration table schema, backfills historical data, file export |
| `modbus_simulator.py` | Modbus TCP server — exposes all sensors as IEEE 754 float32 holding registers |
| `docker-compose.yml` | Runs FairCom Edge locally with a persistent data volume |

## Sensor coverage (3,982 tags)

Sensors are generated programmatically in `config.py` across 13 production lines and all
shared plant systems.

| Area | Detail | Tags |
|---|---|---|
| 13 Production lines | Tempering, 18-zone cooling tunnel, depositing, demolding, inspection, packaging, 5 conveyors | 1,443 |
| 24 Conching vessels | Temperature, torque, speed, vibration, power | 120 |
| 16 Ball mills / refiners | Inlet/outlet temp, pressure, speed, power, vibration | 96 |
| 6 Roasters | Drum/bean/exhaust temp, drum speed, gas flow, moisture, vibration, power | 48 |
| Ingredient storage | 12 sugar silos, 10 cocoa butter tanks, 8 cocoa mass tanks, 8 milk powder silos, lecithin & flavor tanks | 194 |
| Utilities | 8 refrigeration compressors, 4 boilers, 12 chilled water circuits, 4 compressed air systems | 200 |
| 50 AHUs | Supply/return air temp, humidity, fan speed, filter differential pressure | 250 |
| 12 cold rooms + 4 freezers | Multi-point temp, humidity, door status, evaporator temp, defrost, refrigerant pressure | 120 |
| 150 electrical sub-meters | Active power (kW), cumulative energy (kWh), power factor | 450 |
| 187 motors | Vibration X/Y/Z and bearing temperature | 748 |
| 80 environmental points | Temperature, humidity, CO2 per room/zone | 240 |
| Water treatment | 4 RO units, 4 process water tanks | 32 |
| 6 palletizers | Cycle rate, arm torque/speed, gripper vacuum, pallet weight | 36 |
| 10 dosing weighers | Instantaneous weight, batch total, feed rate, belt speed/tension | 50 |
| **Total** | | **3,982** |

## Requirements

```bash
pip install pymodbus>=3.0 requests
```

`requests` is only needed when connecting to FairCom Edge. JSON and CSV export work without it.
`pymodbus` is only needed to run the Modbus simulator.

## Quick start

```bash
# 1. Start FairCom Edge
docker compose up -d

# 2. Create integration tables and seed the sensor registry
python3 generate_data.py --mode setup

# 3. Backfill 30 minutes of historical data into the integration tables (default)
python3 generate_data.py

# 4. Start the Modbus TCP simulator
python3 modbus_simulator.py

# 5. In FairCom Edge Explorer, configure a Modbus connector:
#    - Host: localhost (or host.docker.internal from inside docker)  Port: 502
#    - Register type: ieeefloat32ABCD   Data length: 2   Unit ID: 1
#    - Sensor i → address i*2  (see modbus_simulator.py for the full mapping)
#    Alternatively, run the helper to register the first 100 sensors automatically:
python3 modbus_simulator.py --setup-connector
```

### File export (no FairCom required)

```bash
# Backfill to JSON files
python3 generate_data.py --output json

# Backfill to CSV files
python3 generate_data.py --output csv

# Backfill a custom time range
python3 generate_data.py --seconds 7200
```

## Connection settings

Defaults are read from the top of `config.py`:

```python
FAIRCOM_HOST     = "localhost"
FAIRCOM_PORT     = 8080
FAIRCOM_DB       = "faircom"
FAIRCOM_USER     = "admin"
FAIRCOM_PASSWORD = "ADMIN"
```

Connection parameters can also be passed on the command line:

```bash
python3 generate_data.py --host 192.168.1.50 --user admin --yes
```

## Modbus register layout

Each sensor occupies two consecutive 16-bit holding registers encoding an IEEE 754
float32 value in ABCD (big-endian) byte order — matching FairCom Edge's
`"modbusRegisterType": "ieeefloat32ABCD"` setting.

| Sensor index | Register addresses |
|---|---|
| 0 | 0, 1 |
| 1 | 2, 3 |
| i | i×2, i×2+1 |

## Database schema

| Table | Description |
|---|---|
| `sensor_readings` | Time-series readings — timestamp, tag, value, unit, segment, batch_id, quality |
| `sensor_alarms` | Records when a reading exceeds a sensor's configured high or low limit |
| `batch_log` | Batch start/end times, product code, and status |
| `sensor_registry` | Metadata for all 3,982 tags — setpoint, limits, units, sample interval, data type |

All timestamps are stored as Unix epoch integers (seconds since 1970-01-01 UTC).

## Simulation behavior

Readings are generated using per-sensor setpoints with the following noise model applied
on top:

- Gaussian noise scaled by a per-sensor `noise_std`
- Random slow drift that self-corrects over time
- Low-probability anomaly spikes (configurable via `ANOMALY_PROBABILITY` in `config.py`)
- Subtle sinusoidal oscillation to simulate PID cycling behavior

Quality flags: `0` = good, `1` = suspect (within 2 sigma of a limit), `2` = alarm (outside limit).

Batch IDs roll over every `BATCH_DURATION_SECONDS` (default: 10 minutes). Readings carry
the batch ID active at the time they were generated.
