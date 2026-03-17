# Chocolate Factory – FairCom Edge Data Simulator

A Python-based simulator that generates time-series sensor data for a large-scale
chocolate manufacturing facility and writes it to [FairCom Edge](https://www.faircom.com/edge)
via its JSON API. Data can alternatively be exported to JSON or CSV files without any
FairCom dependency.

## Files

| File | Purpose |
|---|---|
| `config.py` | Sensor definitions, simulation parameters, and FairCom connection defaults |
| `generate_data.py` | Data generator — schema setup, backfill, live stream, and file export |
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
pip install requests
```

`requests` is only needed when writing to FairCom Edge. JSON and CSV export work without it.

## Quick start

```bash
# 1. Start FairCom Edge
docker compose up -d

# 2. Create the schema and seed the sensor registry (interactive — prompts for credentials)
python3 generate_data.py --mode setup

# 3. Same as above, using all defaults non-interactively
python3 generate_data.py --mode setup --yes

# 4. Backfill 30 minutes of historical data and push to FairCom (default behavior)
python3 generate_data.py

# 5. Backfill to JSON files (no FairCom connection required)
python3 generate_data.py --output json

# 6. Backfill to CSV files
python3 generate_data.py --output csv

# 7. Backfill a custom time range
python3 generate_data.py --seconds 7200

# 8. Stream live data to FairCom Edge
python3 generate_data.py --mode stream
```

## Connection settings

The script prompts for connection details when FairCom is needed. Defaults are read from
the top of `config.py`:

```python
FAIRCOM_HOST     = "localhost"
FAIRCOM_PORT     = 8080
FAIRCOM_DB       = "chocolate_factory"
FAIRCOM_USER     = "admin"
FAIRCOM_PASSWORD = "ADMIN"
```

Connection parameters can also be passed directly on the command line:

```bash
python3 generate_data.py --host 192.168.1.50 --user admin --yes
```

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
