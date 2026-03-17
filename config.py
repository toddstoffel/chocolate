"""
Configuration for the Chocolate Factory data simulator.
Defines all sensor definitions, line segments, and FairCom Edge connection settings.
"""

# ─── FairCom Edge connection ───────────────────────────────────────────────────
FAIRCOM_HOST = "localhost"
FAIRCOM_PORT = 8080
FAIRCOM_BASE_URL = f"http://{FAIRCOM_HOST}:{FAIRCOM_PORT}"
FAIRCOM_DB = "chocolate_factory"
FAIRCOM_USER = "admin"
FAIRCOM_PASSWORD = "ADMIN"

# ─── Simulation parameters ─────────────────────────────────────────────────────
# How many seconds of historical data to backfill on first run
BACKFILL_SECONDS = 1800  # 30 minutes
# Interval between readings in seconds
DEFAULT_INTERVAL = 60.0  # 1 reading per sensor per minute
# Probability of an anomaly on any given reading (per sensor)
ANOMALY_PROBABILITY = 0.003
# Probability of a minor drift starting on any given reading
DRIFT_PROBABILITY = 0.01

# ─── Batch settings ────────────────────────────────────────────────────────────
BATCH_DURATION_SECONDS = 600  # each chocolate batch ~ 10 min
BATCH_PREFIX = "BATCH"

# ─── Line segments ─────────────────────────────────────────────────────────────
LINE_SEGMENTS = [
    "bean_intake",
    "roasting",
    "winnowing_grinding",
    "refining",
    "mixing_conching",
    "ingredient_dosing",
    "tempering",
    "depositing",
    "cooling_tunnel",
    "demolding",
    "inspection",
    "packaging",
    "palletizing",
    "cold_storage",
    "utilities",
    "hvac",
    "energy",
    "environmental",
    "water_treatment",
]

# ─── Sensor definitions ────────────────────────────────────────────────────────
# Each sensor dict has:
#   tag        – unique tag name (like a PLC tag)
#   desc       – human-readable description
#   unit       – engineering unit
#   segment    – which line segment it belongs to
#   setpoint   – nominal target value
#   noise_std  – standard deviation of normal Gaussian noise
#   low_limit  – alarm low
#   high_limit – alarm high
#   dtype      – "float" | "int" | "bool"
#   interval   – override sample interval (seconds), defaults to DEFAULT_INTERVAL


def _s(tag, desc, unit, segment, setpoint, noise_std, low_limit, high_limit,
       dtype="float", interval=None):
    d = dict(tag=tag, desc=desc, unit=unit, segment=segment,
             setpoint=setpoint, noise_std=noise_std,
             low_limit=low_limit, high_limit=high_limit, dtype=dtype)
    if interval is not None:
        d["interval"] = interval
    return d


def _build_sensors():
    sensors = []

    # ── 13 PRODUCTION LINES ───────────────────────────────────────────────────
    # Each line: tempering (10) + cooling tunnel 18 zones (59) + depositor (5)
    #            + demolding (3) + inspection (6) + packaging (8)
    #            + 5 inter-stage conveyor segments (4 each = 20) = 111 per line
    for line in range(1, 14):
        L = f"L{line:02d}"

        # Tempering machine – 10 sensors
        sensors += [
            _s(f"{L}_TEMP_TCZ1_IN",   f"Line {line} tempering melt inlet",         "degC", "tempering", 50.0, 0.30, 48.0, 52.0),
            _s(f"{L}_TEMP_TCZ1_OUT",  f"Line {line} tempering zone 1 outlet",      "degC", "tempering", 27.0, 0.20, 25.5, 28.5),
            _s(f"{L}_TEMP_TCZ2_OUT",  f"Line {line} tempering zone 2 re-heat",     "degC", "tempering", 31.5, 0.15, 30.5, 32.5),
            _s(f"{L}_TEMP_TCZ3_OUT",  f"Line {line} tempering working temp",       "degC", "tempering", 32.0, 0.10, 31.0, 33.0),
            _s(f"{L}_TEMP_MOLD_IR",   f"Line {line} mold surface IR temp",         "degC", "tempering", 30.0, 0.50, 28.0, 33.0),
            _s(f"{L}_FLOW_CHOC",      f"Line {line} chocolate mass flow",          "kg/min","tempering", 45.0, 1.50, 35.0, 55.0),
            _s(f"{L}_PRES_PUMP",      f"Line {line} chocolate pump pressure",      "bar",  "tempering",  3.5, 0.20,  2.0,  5.0),
            _s(f"{L}_TEMP_WATER_IN",  f"Line {line} tempering water jacket in",    "degC", "tempering", 15.0, 0.30, 12.0, 18.0),
            _s(f"{L}_TEMP_WATER_OUT", f"Line {line} tempering water jacket out",   "degC", "tempering", 22.0, 0.40, 18.0, 26.0),
            _s(f"{L}_HUMID_HALL",     f"Line {line} production hall humidity",     "%RH",  "tempering", 45.0, 2.00, 30.0, 55.0, interval=5.0),
        ]

        # Cooling tunnel – 18 zones, 3 sensors per zone + 5 shared = 59
        for z in range(1, 19):
            sp = max(5.0, 15.0 - (z - 1) * 0.4)
            sensors += [
                _s(f"{L}_COOL_Z{z:02d}_AIR",  f"Line {line} cool tunnel zone {z} air temp",     "degC", "cooling_tunnel", sp,      0.40, sp - 3.0, sp + 3.0),
                _s(f"{L}_COOL_Z{z:02d}_PROD", f"Line {line} cool tunnel zone {z} product temp", "degC", "cooling_tunnel", sp + 4,  0.50, sp + 1.0, sp + 7.0),
                _s(f"{L}_COOL_Z{z:02d}_RH",   f"Line {line} cool tunnel zone {z} humidity",     "%RH",  "cooling_tunnel", 40.0,    2.00, 25.0,     60.0),
            ]
        sensors += [
            _s(f"{L}_COOL_CONV_SPD",    f"Line {line} cooling conveyor speed",          "m/min", "cooling_tunnel",  2.5, 0.05,  1.5,  3.5),
            _s(f"{L}_COOL_REFRIG_PRES", f"Line {line} chiller refrigerant pressure",    "bar",   "cooling_tunnel",  4.2, 0.15,  3.0,  5.5),
            _s(f"{L}_COOL_SUPPLY_TEMP", f"Line {line} chiller supply coolant temp",     "degC",  "cooling_tunnel",  5.0, 0.30,  2.0,  8.0),
            _s(f"{L}_COOL_VIB_CONV",    f"Line {line} cooling conveyor vibration",      "mm/s",  "cooling_tunnel",  1.8, 0.20,  0.0,  5.0, interval=2.0),
            _s(f"{L}_COOL_AIR_FLOW",    f"Line {line} cooling tunnel air flow",         "m/min", "cooling_tunnel",  1.2, 0.10,  0.5,  2.5),
        ]

        # Depositor – 5 sensors
        sensors += [
            _s(f"{L}_DEP_VAC",       f"Line {line} depositor vacuum",             "mbar",  "depositing", -50.0, 3.0, -80.0, -20.0),
            _s(f"{L}_DEP_TEMP_CHOC", f"Line {line} depositor chocolate temp",     "degC",  "depositing",  31.0, 0.2,  29.5,  32.5),
            _s(f"{L}_DEP_LVL",       f"Line {line} depositor hopper level",       "%",     "depositing",  60.0, 8.0,  10.0,  95.0),
            _s(f"{L}_DEP_PRES",      f"Line {line} depositor nozzle pressure",    "bar",   "depositing",   1.5, 0.1,   0.8,   2.5),
            _s(f"{L}_DEP_SPEED",     f"Line {line} depositor drive speed",        "RPM",   "depositing",  50.0, 2.0,  20.0,  80.0),
        ]

        # Demolding – 3 sensors
        sensors += [
            _s(f"{L}_DEM_VIB",  f"Line {line} demolding vibrator amplitude", "mm/s", "demolding", 8.0, 0.5,  4.0, 12.0),
            _s(f"{L}_DEM_CONV", f"Line {line} demolding conveyor speed",     "m/min","demolding", 3.0, 0.1,  1.5,  5.0),
            _s(f"{L}_DEM_TEMP", f"Line {line} demolding mold temperature",   "degC", "demolding",18.0, 0.5, 14.0, 23.0),
        ]

        # Inspection – 6 sensors
        sensors += [
            _s(f"{L}_INS_WEIGHT",  f"Line {line} checkweigher weight",       "g",     "inspection", 100.0, 0.8, 95.0, 105.0, interval=0.5),
            _s(f"{L}_INS_COLOR_L", f"Line {line} vision L* lightness",       "L*",    "inspection",  32.0, 1.0, 27.0,  37.0, interval=0.5),
            _s(f"{L}_INS_SHAPE",   f"Line {line} vision shape score",        "score", "inspection",  95.0, 2.0, 80.0, 100.0, interval=0.5),
            _s(f"{L}_INS_METAL",   f"Line {line} metal detector pass",       "",      "inspection",   1.0, 0.0,  0.0,   1.0, dtype="bool", interval=0.5),
            _s(f"{L}_INS_XRAY",    f"Line {line} X-ray void score",          "score", "inspection",  98.0, 1.0, 85.0, 100.0, interval=0.5),
            _s(f"{L}_INS_THICK",   f"Line {line} product thickness (laser)", "mm",    "inspection",   8.5, 0.1,  8.0,   9.0, interval=0.5),
        ]

        # Packaging – 8 sensors
        sensors += [
            _s(f"{L}_PKG_BARS_MIN",  f"Line {line} bars per minute",        "bars/min","packaging", 120.0, 5.0,  80.0, 150.0, dtype="int"),
            _s(f"{L}_PKG_LABEL_OK",  f"Line {line} label scan pass",        "",        "packaging",   1.0, 0.0,   0.0,   1.0, dtype="bool", interval=0.5),
            _s(f"{L}_PKG_SERVO_TQ",  f"Line {line} wrapper servo torque",   "Nm",      "packaging",   8.0, 0.5,   4.0,  12.0),
            _s(f"{L}_PKG_SERVO_SPD", f"Line {line} wrapper servo speed",    "RPM",     "packaging", 300.0,10.0, 150.0, 450.0),
            _s(f"{L}_PKG_REJECTS",   f"Line {line} reject count",           "count",   "packaging",   0.0, 0.0,   0.0,  50.0, dtype="int", interval=5.0),
            _s(f"{L}_PKG_FILM_TENS", f"Line {line} film web tension",       "N",       "packaging",  12.0, 0.5,   8.0,  18.0),
            _s(f"{L}_PKG_SEAL_TEMP", f"Line {line} heat-seal jaw temp",     "degC",    "packaging", 140.0, 2.0, 130.0, 155.0),
            _s(f"{L}_PKG_INDATE_OK", f"Line {line} inkjet date code verify","",        "packaging",   1.0, 0.0,   0.0,   1.0, dtype="bool", interval=0.5),
        ]

        # Inter-stage conveyors – 5 segments × 4 sensors = 20
        for sq, seg_name in [
            ("PRETEMP",   "pre-tempering"),
            ("POSTTEMP",  "post-tempering"),
            ("INTERCOOL", "inter-cooling"),
            ("POSTCOOL",  "post-cooling"),
            ("PREPKG",    "pre-packaging"),
        ]:
            sensors += [
                _s(f"{L}_CONV_{sq}_SPD",   f"Line {line} {seg_name} conveyor speed",     "m/min","cooling_tunnel", 1.5, 0.05, 0.5, 3.0),
                _s(f"{L}_CONV_{sq}_VIB",   f"Line {line} {seg_name} conveyor vibration", "mm/s", "cooling_tunnel", 1.5, 0.20, 0.0, 5.0, interval=2.0),
                _s(f"{L}_CONV_{sq}_CURR",  f"Line {line} {seg_name} motor current",      "A",    "cooling_tunnel", 4.5, 0.30, 1.0, 8.0),
                _s(f"{L}_CONV_{sq}_BTEMP", f"Line {line} {seg_name} bearing temp",       "degC", "cooling_tunnel",45.0, 2.00,30.0,75.0),
            ]

    # ── CONCHING VESSELS (24) – 5 sensors each = 120 ─────────────────────────
    for v in range(1, 25):
        V = f"CONCHE{v:02d}"
        sensors += [
            _s(f"{V}_TEMP",   f"Conche {v} chocolate mass temp", "degC",         "mixing_conching",  55.0, 0.5,  50.0,  65.0),
            _s(f"{V}_TORQUE", f"Conche {v} motor torque",        "Nm",           "mixing_conching", 120.0, 5.0,  80.0, 180.0),
            _s(f"{V}_SPD",    f"Conche {v} motor speed",         "RPM",          "mixing_conching",  60.0, 1.0,  40.0,  80.0),
            _s(f"{V}_VIB",    f"Conche {v} motor vibration",     "mm/s",         "mixing_conching",   2.5, 0.3,   0.0,   7.0, interval=2.0),
            _s(f"{V}_POWER",  f"Conche {v} motor power draw",    "kW",           "mixing_conching",  18.5, 1.0,   5.0,  30.0),
        ]

    # ── BALL MILLS / REFINERS (16) – 6 sensors each = 96 ────────────────────
    for m in range(1, 17):
        M = f"MILL{m:02d}"
        sensors += [
            _s(f"{M}_TEMP_IN",  f"Mill {m} inlet temperature",   "degC", "refining",  45.0, 1.0, 38.0,  55.0),
            _s(f"{M}_TEMP_OUT", f"Mill {m} outlet temperature",  "degC", "refining",  60.0, 1.5, 50.0,  75.0),
            _s(f"{M}_PRES",     f"Mill {m} hydraulic pressure",  "bar",  "refining",  80.0, 3.0, 60.0, 100.0),
            _s(f"{M}_SPD",      f"Mill {m} drum speed",          "RPM",  "refining",  45.0, 1.0, 30.0,  60.0),
            _s(f"{M}_POWER",    f"Mill {m} motor power",         "kW",   "refining",  55.0, 3.0, 30.0,  80.0),
            _s(f"{M}_VIB",      f"Mill {m} vibration",           "mm/s", "refining",   3.0, 0.4,  0.0,   8.0, interval=2.0),
        ]

    # ── ROASTERS (6) – 8 sensors each = 48 ──────────────────────────────────
    for r in range(1, 7):
        R = f"ROAST{r:01d}"
        sensors += [
            _s(f"{R}_TEMP_DRUM",    f"Roaster {r} drum temperature",    "degC", "roasting", 130.0, 2.0, 115.0, 145.0),
            _s(f"{R}_TEMP_BEAN",    f"Roaster {r} bean product temp",   "degC", "roasting", 120.0, 3.0, 105.0, 135.0),
            _s(f"{R}_TEMP_EXHAUST", f"Roaster {r} exhaust gas temp",    "degC", "roasting", 155.0, 5.0, 130.0, 180.0),
            _s(f"{R}_SPD_DRUM",     f"Roaster {r} drum rotation speed", "RPM",  "roasting",   8.0, 0.2,   4.0,  12.0),
            _s(f"{R}_GAS_FLOW",     f"Roaster {r} gas burner flow",     "m3/h", "roasting",  12.0, 0.5,   5.0,  20.0),
            _s(f"{R}_HUMID_OUT",    f"Roaster {r} outlet moisture",     "%RH",  "roasting",   3.0, 0.5,   1.0,   7.0),
            _s(f"{R}_VIB",          f"Roaster {r} drum vibration",      "mm/s", "roasting",   2.0, 0.3,   0.0,   6.0, interval=2.0),
            _s(f"{R}_POWER",        f"Roaster {r} motor power",         "kW",   "roasting",  22.0, 1.5,  10.0,  35.0),
        ]

    # ── INGREDIENT STORAGE ────────────────────────────────────────────────────
    # Sugar silos (12) – 4 sensors each = 48
    for i in range(1, 13):
        T = f"SUGAR_SILO{i:02d}"
        sensors += [
            _s(f"{T}_LVL",   f"Sugar silo {i} level",           "%",     "ingredient_dosing", 70.0, 5.0, 10.0, 95.0),
            _s(f"{T}_TEMP",  f"Sugar silo {i} temperature",     "degC",  "ingredient_dosing", 22.0, 1.0, 15.0, 35.0),
            _s(f"{T}_HUMID", f"Sugar silo {i} humidity",        "%RH",   "ingredient_dosing", 30.0, 3.0, 10.0, 55.0),
            _s(f"{T}_FLOW",  f"Sugar silo {i} discharge flow",  "kg/min","ingredient_dosing", 12.0, 0.4,  8.0, 18.0),
        ]
    # Cocoa butter tanks (10) – 5 sensors each = 50
    for i in range(1, 11):
        T = f"COBUT_TANK{i:02d}"
        sensors += [
            _s(f"{T}_LVL",  f"Cocoa butter tank {i} level",    "%",     "ingredient_dosing", 65.0, 4.0, 10.0, 95.0),
            _s(f"{T}_TEMP", f"Cocoa butter tank {i} temp",     "degC",  "ingredient_dosing", 45.0, 0.5, 40.0, 55.0),
            _s(f"{T}_FLOW", f"Cocoa butter tank {i} flow",     "kg/min","ingredient_dosing",  8.5, 0.3,  5.0, 12.0),
            _s(f"{T}_PRES", f"Cocoa butter tank {i} pressure", "bar",   "ingredient_dosing",  0.8,0.05,  0.2,  2.0),
            _s(f"{T}_VIS",  f"Cocoa butter tank {i} viscosity","mPas",  "ingredient_dosing", 30.0, 2.0, 15.0, 80.0),
        ]
    # Cocoa mass tanks (8) – 5 sensors each = 40
    for i in range(1, 9):
        T = f"COMASS_TANK{i:02d}"
        sensors += [
            _s(f"{T}_LVL",  f"Cocoa mass tank {i} level",    "%",     "ingredient_dosing", 60.0, 5.0, 10.0, 95.0),
            _s(f"{T}_TEMP", f"Cocoa mass tank {i} temp",     "degC",  "ingredient_dosing", 55.0, 0.5, 48.0, 65.0),
            _s(f"{T}_FLOW", f"Cocoa mass tank {i} flow",     "kg/min","ingredient_dosing",  7.0, 0.4,  4.0, 12.0),
            _s(f"{T}_PRES", f"Cocoa mass tank {i} pressure", "bar",   "ingredient_dosing",  1.0,0.08,  0.3,  2.5),
            _s(f"{T}_STIR", f"Cocoa mass tank {i} agitator", "RPM",   "ingredient_dosing", 25.0, 1.0, 10.0, 40.0),
        ]
    # Milk powder silos (8) – 4 sensors each = 32
    for i in range(1, 9):
        T = f"MILKPWD_SILO{i:02d}"
        sensors += [
            _s(f"{T}_LVL",   f"Milk powder silo {i} level",    "%",    "ingredient_dosing", 65.0, 5.0, 10.0, 95.0),
            _s(f"{T}_TEMP",  f"Milk powder silo {i} temp",     "degC", "ingredient_dosing", 20.0, 1.0, 15.0, 30.0),
            _s(f"{T}_HUMID", f"Milk powder silo {i} humidity", "%RH",  "ingredient_dosing", 20.0, 2.0,  5.0, 40.0),
            _s(f"{T}_FLOW",  f"Milk powder silo {i} flow",     "kg/min","ingredient_dosing", 5.0, 0.2,  2.0,  8.0),
        ]
    # Lecithin tanks (4) – 3 sensors each = 12
    for i in range(1, 5):
        T = f"LECITHIN_TK{i:01d}"
        sensors += [
            _s(f"{T}_LVL",  f"Lecithin tank {i} level", "%",    "ingredient_dosing", 50.0, 5.0, 10.0, 90.0),
            _s(f"{T}_TEMP", f"Lecithin tank {i} temp",  "degC", "ingredient_dosing", 60.0, 1.0, 50.0, 75.0),
            _s(f"{T}_FLOW", f"Lecithin tank {i} flow",  "kg/h", "ingredient_dosing",  0.8,0.05,  0.2,  2.0),
        ]
    # Flavor / vanilla tanks (4) – 3 sensors each = 12
    for i in range(1, 5):
        T = f"FLAVOR_TK{i:01d}"
        sensors += [
            _s(f"{T}_LVL",  f"Flavor tank {i} level", "%",    "ingredient_dosing", 45.0, 5.0, 10.0, 90.0),
            _s(f"{T}_TEMP", f"Flavor tank {i} temp",  "degC", "ingredient_dosing", 22.0, 1.0, 15.0, 35.0),
            _s(f"{T}_FLOW", f"Flavor tank {i} flow",  "kg/h", "ingredient_dosing",  0.2,0.02, 0.05,  0.5),
        ]

    # ── UTILITIES ─────────────────────────────────────────────────────────────
    # Refrigeration compressors (8) – 7 sensors each = 56
    for i in range(1, 9):
        C = f"REFRIG_COMP{i:02d}"
        sensors += [
            _s(f"{C}_SUCT_PRES",  f"Refrig compressor {i} suction pressure",  "bar",  "utilities",  4.2, 0.15,  3.0,  6.0),
            _s(f"{C}_DISCH_PRES", f"Refrig compressor {i} discharge pressure", "bar",  "utilities", 15.0, 0.50, 12.0, 18.0),
            _s(f"{C}_CURR",       f"Refrig compressor {i} motor current",      "A",    "utilities", 85.0, 3.00, 30.0,120.0),
            _s(f"{C}_TEMP_OIL",   f"Refrig compressor {i} oil temperature",    "degC", "utilities", 55.0, 2.00, 40.0, 75.0),
            _s(f"{C}_VIB",        f"Refrig compressor {i} vibration",          "mm/s", "utilities",  2.5, 0.30,  0.0,  7.0, interval=2.0),
            _s(f"{C}_POWER",      f"Refrig compressor {i} power",              "kW",   "utilities", 45.0, 3.00, 15.0, 75.0),
            _s(f"{C}_SUPERHEAT",  f"Refrig compressor {i} superheat",          "K",    "utilities",  8.0, 0.50,  4.0, 15.0),
        ]
    # Boilers (4) – 10 sensors each = 40
    for i in range(1, 5):
        B = f"BOILER{i:02d}"
        sensors += [
            _s(f"{B}_STEAM_PRES", f"Boiler {i} steam pressure",       "bar",   "utilities",  10.0, 0.30,  8.0, 12.0),
            _s(f"{B}_STEAM_TEMP", f"Boiler {i} steam temperature",    "degC",  "utilities", 180.0, 2.00,170.0,195.0),
            _s(f"{B}_WATER_LVL",  f"Boiler {i} water level",          "%",     "utilities",  65.0, 2.00, 30.0, 90.0),
            _s(f"{B}_GAS_FLOW",   f"Boiler {i} gas burner flow",      "m3/h",  "utilities",  18.0, 1.00,  5.0, 30.0),
            _s(f"{B}_FLUE_TEMP",  f"Boiler {i} flue gas temperature", "degC",  "utilities", 160.0, 5.00,130.0,200.0),
            _s(f"{B}_FEED_FLOW",  f"Boiler {i} feedwater flow",       "L/min", "utilities",  42.0, 2.00, 20.0, 65.0),
            _s(f"{B}_COND_TEMP",  f"Boiler {i} condensate return",    "degC",  "utilities",  80.0, 3.00, 60.0,100.0),
            _s(f"{B}_O2_FLUE",    f"Boiler {i} flue O2 content",      "%",     "utilities",   3.5, 0.30,  1.5,  7.0),
            _s(f"{B}_TDS",        f"Boiler {i} TDS in boiler water",  "ppm",   "utilities",1500.0,50.00,500.0,2500.0),
            _s(f"{B}_POWER",      f"Boiler {i} pump and fan power",   "kW",    "utilities",  12.0, 1.00,  5.0, 20.0),
        ]
    # Chilled water circuits (12) – 6 sensors each = 72
    for i in range(1, 13):
        CW = f"CHW_CIRC{i:02d}"
        sensors += [
            _s(f"{CW}_SUPPLY_T", f"Chilled water {i} supply temp",   "degC",  "utilities",   6.0, 0.30,  3.0, 10.0),
            _s(f"{CW}_RETURN_T", f"Chilled water {i} return temp",   "degC",  "utilities",  12.0, 0.40,  8.0, 16.0),
            _s(f"{CW}_FLOW",     f"Chilled water {i} flow rate",     "L/min", "utilities", 250.0,10.00,100.0,400.0),
            _s(f"{CW}_DP",       f"Chilled water {i} diff pressure", "bar",   "utilities",   0.6, 0.05,  0.2,  1.2),
            _s(f"{CW}_PUMP_PWR", f"Chilled water {i} pump power",   "kW",    "utilities",  18.0, 1.00,  5.0, 30.0),
            _s(f"{CW}_VALVE",    f"Chilled water {i} valve position","%",     "utilities",  60.0, 5.00,  0.0,100.0),
        ]
    # Compressed air systems (4) – 8 sensors each = 32
    for i in range(1, 5):
        CA = f"CAIR_COMP{i:01d}"
        sensors += [
            _s(f"{CA}_PRES",     f"Compressed air {i} header pressure",    "bar",  "utilities",  7.0, 0.20,  5.5,  8.5),
            _s(f"{CA}_DEW_PT",   f"Compressed air {i} dew point",          "degC", "utilities",-20.0, 1.00,-40.0, -5.0),
            _s(f"{CA}_FLOW",     f"Compressed air {i} flow",               "m3/h", "utilities",120.0,10.00, 40.0,200.0),
            _s(f"{CA}_TEMP",     f"Compressed air {i} after-cooler outlet","degC", "utilities", 35.0, 2.00, 22.0, 50.0),
            _s(f"{CA}_OIL_PPM",  f"Compressed air {i} oil content",        "ppm",  "utilities",  0.1, 0.05,  0.0,  1.0),
            _s(f"{CA}_POWER",    f"Compressed air {i} motor power",        "kW",   "utilities", 55.0, 3.00, 20.0, 90.0),
            _s(f"{CA}_VIB",      f"Compressed air {i} vibration",          "mm/s", "utilities",  2.0, 0.30,  0.0,  6.0, interval=2.0),
            _s(f"{CA}_CURR",     f"Compressed air {i} motor current",      "A",    "utilities", 90.0, 4.00, 30.0,130.0),
        ]

    # ── HVAC – 50 Air Handling Units, 5 sensors each = 250 ───────────────────
    for i in range(1, 51):
        A = f"AHU{i:02d}"
        sensors += [
            _s(f"{A}_SUPPLY_T",  f"AHU {i} supply air temperature",       "degC", "hvac", 18.0, 0.5, 14.0, 24.0),
            _s(f"{A}_RETURN_T",  f"AHU {i} return air temperature",       "degC", "hvac", 23.0, 0.5, 18.0, 28.0),
            _s(f"{A}_SUPPLY_RH", f"AHU {i} supply air humidity",          "%RH",  "hvac", 45.0, 2.0, 30.0, 60.0),
            _s(f"{A}_FAN_SPD",   f"AHU {i} supply fan speed",             "RPM",  "hvac",900.0,20.0,300.0,1500.0),
            _s(f"{A}_FILTER_DP", f"AHU {i} filter differential pressure", "Pa",   "hvac",120.0,10.0, 30.0, 350.0),
        ]

    # ── COLD STORAGE – 12 cold rooms (8 sensors each = 96) ───────────────────
    for i in range(1, 13):
        CR = f"COLDROOM{i:02d}"
        sensors += [
            _s(f"{CR}_TEMP1",    f"Cold room {i} temp sensor 1",    "degC", "cold_storage",   4.0, 0.30,  1.0,  8.0),
            _s(f"{CR}_TEMP2",    f"Cold room {i} temp sensor 2",    "degC", "cold_storage",   4.0, 0.40,  1.0,  8.0),
            _s(f"{CR}_TEMP3",    f"Cold room {i} temp sensor 3",    "degC", "cold_storage",   4.0, 0.40,  1.0,  8.0),
            _s(f"{CR}_HUMID",    f"Cold room {i} humidity",         "%RH",  "cold_storage",  75.0, 3.00, 55.0, 90.0),
            _s(f"{CR}_DOOR",     f"Cold room {i} door status",      "",     "cold_storage",   0.0, 0.00,  0.0,  1.0, dtype="bool"),
            _s(f"{CR}_EVAP_T",   f"Cold room {i} evaporator temp",  "degC", "cold_storage",  -5.0, 0.50,-10.0,  2.0),
            _s(f"{CR}_DEFROST",  f"Cold room {i} defrost power",    "kW",   "cold_storage",   0.0, 0.00,  0.0, 12.0),
            _s(f"{CR}_REF_PRES", f"Cold room {i} refrig low pres",  "bar",  "cold_storage",   2.5, 0.20,  1.5,  4.5),
        ]
    # 4 freezers – 6 sensors each = 24
    for i in range(1, 5):
        FZ = f"FREEZER{i:02d}"
        sensors += [
            _s(f"{FZ}_TEMP1",  f"Freezer {i} temp sensor 1",  "degC", "cold_storage", -22.0, 0.5,-26.0,-18.0),
            _s(f"{FZ}_TEMP2",  f"Freezer {i} temp sensor 2",  "degC", "cold_storage", -22.0, 0.5,-26.0,-18.0),
            _s(f"{FZ}_HUMID",  f"Freezer {i} humidity",       "%RH",  "cold_storage",  60.0, 3.0, 40.0, 80.0),
            _s(f"{FZ}_DOOR",   f"Freezer {i} door status",    "",     "cold_storage",   0.0, 0.0,  0.0,  1.0, dtype="bool"),
            _s(f"{FZ}_EVAP_T", f"Freezer {i} evaporator temp","degC", "cold_storage", -30.0, 0.8,-38.0,-24.0),
            _s(f"{FZ}_POWER",  f"Freezer {i} compressor power","kW",  "cold_storage",  12.0, 1.0,  5.0, 22.0),
        ]

    # ── ELECTRICAL ENERGY METERING – 150 sub-meters, 3 sensors each = 450 ───
    energy_areas = (
        [f"LINE{i:02d}"      for i in range(1, 14)] +
        [f"CONCHE{i:02d}"    for i in range(1, 25)] +
        [f"MILL{i:02d}"      for i in range(1, 17)] +
        [f"ROAST{i:01d}"     for i in range(1, 7)]  +
        [f"RCOMP{i:02d}"     for i in range(1, 9)]  +
        [f"AHU_BANK{i:02d}"  for i in range(1, 11)] +
        [f"LIGHTING{i:02d}"  for i in range(1, 11)] +
        [f"MISC{i:02d}"      for i in range(1, 21)] +
        [f"HVAC{i:02d}"      for i in range(1, 16)] +
        [f"COLD{i:02d}"      for i in range(1, 9)]  +
        [f"INGRED{i:02d}"    for i in range(1, 10)] +
        [f"UTIL{i:02d}"      for i in range(1, 9)]  +
        ["SITE_MAIN", "SITE_BACKUP", "SITE_SOLAR", "SITE_XFMR1", "SITE_XFMR2"]
    )
    for area in energy_areas[:150]:
        E = f"PWR_{area}"
        sensors += [
            _s(f"{E}_KW",  f"Power meter {area} active power", "kW",   "energy",  50.0, 5.0,  0.0, 500.0),
            _s(f"{E}_KWH", f"Power meter {area} energy total", "kWh",  "energy",   0.0, 0.0,  0.0, 1e6, interval=60.0),
            _s(f"{E}_PF",  f"Power meter {area} power factor", "",     "energy",  0.92,0.02,  0.7,   1.0),
        ]

    # ── MOTOR HEALTH – 187 motors, 4 sensors each = 748 ─────────────────────
    # (vibration X/Y/Z + bearing temperature per motor)
    motor_tags = (
        [(f"L{l:02d}_PUMP{p:01d}", "tempering")      for l in range(1, 14) for p in range(1, 4)] +
        [(f"L{l:02d}_FAN{f:01d}",  "cooling_tunnel") for l in range(1, 14) for f in range(1, 5)] +
        [(f"UTIL_PUMP{i:02d}",     "utilities")       for i in range(1, 31)] +
        [(f"GRIND_MTR{i:02d}",     "refining")        for i in range(1, 17)] +
        [(f"HVAC_FAN{i:02d}",      "hvac")            for i in range(1, 21)] +
        [(f"MISC_MTR{i:02d}",      "utilities")       for i in range(1, 31)]
    )
    for tag_pfx, seg in motor_tags:
        sensors += [
            _s(f"{tag_pfx}_VX",   f"{tag_pfx} vibration X-axis",   "mm/s", seg,  2.0, 0.3, 0.0,  8.0, interval=2.0),
            _s(f"{tag_pfx}_VY",   f"{tag_pfx} vibration Y-axis",   "mm/s", seg,  2.0, 0.3, 0.0,  8.0, interval=2.0),
            _s(f"{tag_pfx}_VZ",   f"{tag_pfx} vibration Z-axis",   "mm/s", seg,  1.5, 0.2, 0.0,  6.0, interval=2.0),
            _s(f"{tag_pfx}_BTEMP",f"{tag_pfx} bearing temperature","degC", seg, 45.0, 2.0,25.0, 85.0),
        ]

    # ── ENVIRONMENTAL MONITORING – 80 room points, 3 sensors each = 240 ─────
    env_rooms = (
        [f"PROD_{x}"   for x in ["A1","A2","A3","B1","B2","B3","C1","C2"]] +
        [f"TEMPER{i}"  for i in range(1, 6)]  +
        [f"COOLING{i}" for i in range(1, 6)]  +
        [f"DEP{i}"     for i in range(1, 5)]  +
        [f"PKG{i}"     for i in range(1, 9)]  +
        [f"STORE{i}"   for i in range(1, 9)]  +
        [f"LAB{i}"     for i in range(1, 5)]  +
        [f"OFFICE{i}"  for i in range(1, 5)]  +
        [f"UTIL{i}"    for i in range(1, 9)]  +
        [f"ROAST{i}"   for i in range(1, 7)]  +
        [f"INTAKE{i}"  for i in range(1, 5)]  +
        ["EXTERNAL"]
    )
    for room in env_rooms[:80]:
        R = f"ENV_{room}"
        sensors += [
            _s(f"{R}_TEMP",  f"Env temp — {room}",     "degC", "environmental", 22.0, 0.5, 15.0,  35.0, interval=5.0),
            _s(f"{R}_HUMID", f"Env humidity — {room}", "%RH",  "environmental", 50.0, 3.0, 25.0,  75.0, interval=5.0),
            _s(f"{R}_CO2",   f"Env CO2 — {room}",      "ppm",  "environmental",450.0,30.0,300.0,1200.0, interval=10.0),
        ]

    # ── WATER TREATMENT – 4 RO units (5 each=20) + 4 tanks (3 each=12) = 32 ─
    for i in range(1, 5):
        WT = f"RO_UNIT{i:01d}"
        sensors += [
            _s(f"{WT}_INLET_COND", f"RO unit {i} inlet conductivity",    "uS/cm","water_treatment",300.0,20.0, 50.0, 600.0),
            _s(f"{WT}_PERM_COND",  f"RO unit {i} permeate conductivity", "uS/cm","water_treatment",  8.0, 1.0,  1.0,  30.0),
            _s(f"{WT}_PRES_FEED",  f"RO unit {i} feed pressure",         "bar",  "water_treatment",  5.0, 0.3,  3.0,   8.0),
            _s(f"{WT}_FLOW_PERM",  f"RO unit {i} permeate flow",         "L/min","water_treatment", 80.0, 5.0, 30.0, 140.0),
            _s(f"{WT}_RECOVERY",   f"RO unit {i} recovery rate",         "%",    "water_treatment", 75.0, 2.0, 60.0,  90.0),
        ]
    for i in range(1, 5):
        WT = f"WATER_TK{i:01d}"
        sensors += [
            _s(f"{WT}_LVL",  f"Process water tank {i} level", "%",    "water_treatment", 70.0, 5.0, 15.0, 95.0),
            _s(f"{WT}_TEMP", f"Process water tank {i} temp",  "degC", "water_treatment", 18.0, 1.0, 10.0, 30.0),
            _s(f"{WT}_PH",   f"Process water tank {i} pH",    "",     "water_treatment",  7.0, 0.1,  6.5,  8.5),
        ]

    # ── PALLETIZERS (6) – 6 sensors each = 36 ────────────────────────────────
    for i in range(1, 7):
        P = f"PALLETIZER{i:01d}"
        sensors += [
            _s(f"{P}_CYCLE",   f"Palletizer {i} cycles per min",   "count",  "palletizing",  6.0, 0.3,  2.0, 10.0),
            _s(f"{P}_ARM_TQ",  f"Palletizer {i} arm servo torque", "Nm",     "palletizing", 45.0, 3.0, 20.0, 80.0),
            _s(f"{P}_ARM_SPD", f"Palletizer {i} arm speed",        "deg/s",  "palletizing",180.0,10.0, 50.0,300.0),
            _s(f"{P}_GRIP_VAC",f"Palletizer {i} gripper vacuum",   "mbar",   "palletizing",-60.0, 5.0,-90.0,-30.0),
            _s(f"{P}_PAL_WT",  f"Palletizer {i} pallet weight",    "kg",     "palletizing",400.0,20.0,  0.0,600.0),
            _s(f"{P}_UPTIME",  f"Palletizer {i} uptime flag",      "",       "palletizing",  1.0, 0.0,  0.0,  1.0, dtype="bool"),
        ]

    # ── INLINE DOSING WEIGHERS (10) – 5 sensors each = 50 ────────────────────
    for i in range(1, 11):
        W = f"WGHR{i:02d}"
        sensors += [
            _s(f"{W}_WEIGHT",   f"Dosing weigher {i} instantaneous weight", "kg",    "ingredient_dosing", 25.0, 0.5, 10.0, 50.0),
            _s(f"{W}_BATCH_WT", f"Dosing weigher {i} batch total weight",   "kg",    "ingredient_dosing",500.0, 2.0,400.0,600.0),
            _s(f"{W}_RATE",     f"Dosing weigher {i} feed rate",            "kg/min","ingredient_dosing", 12.0, 0.4,  8.0, 18.0),
            _s(f"{W}_SPEED",    f"Dosing weigher {i} belt speed",           "m/min", "ingredient_dosing",  1.5, 0.1,  0.5,  3.0),
            _s(f"{W}_TENSION",  f"Dosing weigher {i} belt tension",         "N",     "ingredient_dosing", 80.0, 3.0, 50.0,120.0),
        ]

    return sensors

SENSORS = [
    # ── TEMPERING CHAIN (the crown jewel of chocolate data) ─────────────────
    {
        "tag": "TEMP_TCZ1_IN",
        "desc": "Tempering Zone 1 inlet temperature (melt)",
        "unit": "degC",
        "segment": "tempering",
        "setpoint": 50.0,
        "noise_std": 0.3,
        "low_limit": 48.0,
        "high_limit": 52.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_TCZ1_OUT",
        "desc": "Tempering Zone 1 outlet temperature",
        "unit": "degC",
        "segment": "tempering",
        "setpoint": 27.0,
        "noise_std": 0.2,
        "low_limit": 25.5,
        "high_limit": 28.5,
        "dtype": "float",
    },
    {
        "tag": "TEMP_TCZ2_OUT",
        "desc": "Tempering Zone 2 outlet (re-heat)",
        "unit": "degC",
        "segment": "tempering",
        "setpoint": 31.5,
        "noise_std": 0.15,
        "low_limit": 30.5,
        "high_limit": 32.5,
        "dtype": "float",
    },
    {
        "tag": "TEMP_TCZ3_OUT",
        "desc": "Tempering Zone 3 outlet (working temp)",
        "unit": "degC",
        "segment": "tempering",
        "setpoint": 32.0,
        "noise_std": 0.1,
        "low_limit": 31.0,
        "high_limit": 33.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_MOLD_IR",
        "desc": "Mold surface temperature (IR sensor)",
        "unit": "degC",
        "segment": "tempering",
        "setpoint": 30.0,
        "noise_std": 0.5,
        "low_limit": 28.0,
        "high_limit": 33.0,
        "dtype": "float",
    },
    {
        "tag": "FLOW_CHOC_MASS",
        "desc": "Chocolate mass flow rate",
        "unit": "kg/min",
        "segment": "tempering",
        "setpoint": 45.0,
        "noise_std": 1.5,
        "low_limit": 35.0,
        "high_limit": 55.0,
        "dtype": "float",
    },
    {
        "tag": "PRES_CHOC_PUMP",
        "desc": "Chocolate pump discharge pressure",
        "unit": "bar",
        "segment": "tempering",
        "setpoint": 3.5,
        "noise_std": 0.2,
        "low_limit": 2.0,
        "high_limit": 5.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_TEMPER_WATER_IN",
        "desc": "Tempering water jacket inlet temp",
        "unit": "degC",
        "segment": "tempering",
        "setpoint": 15.0,
        "noise_std": 0.3,
        "low_limit": 12.0,
        "high_limit": 18.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_TEMPER_WATER_OUT",
        "desc": "Tempering water jacket outlet temp",
        "unit": "degC",
        "segment": "tempering",
        "setpoint": 22.0,
        "noise_std": 0.4,
        "low_limit": 18.0,
        "high_limit": 26.0,
        "dtype": "float",
    },
    # ── COOLING TUNNEL ──────────────────────────────────────────────────────
    {
        "tag": "TEMP_COOL_Z1",
        "desc": "Cooling tunnel zone 1 air temperature",
        "unit": "degC",
        "segment": "cooling_tunnel",
        "setpoint": 15.0,
        "noise_std": 0.4,
        "low_limit": 12.0,
        "high_limit": 18.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_COOL_Z2",
        "desc": "Cooling tunnel zone 2 air temperature",
        "unit": "degC",
        "segment": "cooling_tunnel",
        "setpoint": 10.0,
        "noise_std": 0.3,
        "low_limit": 7.0,
        "high_limit": 13.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_COOL_Z3",
        "desc": "Cooling tunnel zone 3 air temperature",
        "unit": "degC",
        "segment": "cooling_tunnel",
        "setpoint": 12.0,
        "noise_std": 0.3,
        "low_limit": 9.0,
        "high_limit": 15.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_COOL_PRODUCT_EXIT",
        "desc": "Product temperature at tunnel exit",
        "unit": "degC",
        "segment": "cooling_tunnel",
        "setpoint": 18.0,
        "noise_std": 0.5,
        "low_limit": 15.0,
        "high_limit": 22.0,
        "dtype": "float",
    },
    {
        "tag": "HUMID_COOL_TUNNEL",
        "desc": "Cooling tunnel humidity",
        "unit": "%RH",
        "segment": "cooling_tunnel",
        "setpoint": 40.0,
        "noise_std": 2.0,
        "low_limit": 25.0,
        "high_limit": 55.0,
        "dtype": "float",
    },
    {
        "tag": "SPD_COOL_CONVEYOR",
        "desc": "Cooling tunnel conveyor speed",
        "unit": "m/min",
        "segment": "cooling_tunnel",
        "setpoint": 2.5,
        "noise_std": 0.05,
        "low_limit": 1.5,
        "high_limit": 3.5,
        "dtype": "float",
    },
    {
        "tag": "PRES_CHILLER_REFRIG",
        "desc": "Chiller refrigerant suction pressure",
        "unit": "bar",
        "segment": "cooling_tunnel",
        "setpoint": 4.2,
        "noise_std": 0.15,
        "low_limit": 3.0,
        "high_limit": 5.5,
        "dtype": "float",
    },
    {
        "tag": "TEMP_CHILLER_SUPPLY",
        "desc": "Chiller supply coolant temperature",
        "unit": "degC",
        "segment": "cooling_tunnel",
        "setpoint": 5.0,
        "noise_std": 0.3,
        "low_limit": 2.0,
        "high_limit": 8.0,
        "dtype": "float",
    },
    # ── INGREDIENT DOSING ───────────────────────────────────────────────────
    {
        "tag": "FLOW_SUGAR",
        "desc": "Sugar dosing flow rate",
        "unit": "kg/min",
        "segment": "ingredient_dosing",
        "setpoint": 12.0,
        "noise_std": 0.4,
        "low_limit": 10.0,
        "high_limit": 14.0,
        "dtype": "float",
    },
    {
        "tag": "FLOW_COCOA_BUTTER",
        "desc": "Cocoa butter dosing flow rate",
        "unit": "kg/min",
        "segment": "ingredient_dosing",
        "setpoint": 8.5,
        "noise_std": 0.3,
        "low_limit": 7.0,
        "high_limit": 10.0,
        "dtype": "float",
    },
    {
        "tag": "FLOW_MILK_SOLIDS",
        "desc": "Milk solids dosing flow rate",
        "unit": "kg/min",
        "segment": "ingredient_dosing",
        "setpoint": 5.0,
        "noise_std": 0.2,
        "low_limit": 4.0,
        "high_limit": 6.0,
        "dtype": "float",
    },
    {
        "tag": "LVL_SUGAR_HOPPER",
        "desc": "Sugar hopper level",
        "unit": "%",
        "segment": "ingredient_dosing",
        "setpoint": 70.0,
        "noise_std": 5.0,
        "low_limit": 15.0,
        "high_limit": 95.0,
        "dtype": "float",
    },
    {
        "tag": "LVL_COCOA_BUTTER_TANK",
        "desc": "Cocoa butter holding tank level",
        "unit": "%",
        "segment": "ingredient_dosing",
        "setpoint": 65.0,
        "noise_std": 4.0,
        "low_limit": 10.0,
        "high_limit": 95.0,
        "dtype": "float",
    },
    {
        "tag": "WEIGHT_MIXING_VESSEL",
        "desc": "Mixing vessel load cell weight",
        "unit": "kg",
        "segment": "ingredient_dosing",
        "setpoint": 500.0,
        "noise_std": 5.0,
        "low_limit": 50.0,
        "high_limit": 750.0,
        "dtype": "float",
    },
    # ── MIXING / CONCHING ───────────────────────────────────────────────────
    {
        "tag": "TORQUE_CONCHE",
        "desc": "Conche motor torque",
        "unit": "Nm",
        "segment": "mixing_conching",
        "setpoint": 120.0,
        "noise_std": 5.0,
        "low_limit": 80.0,
        "high_limit": 180.0,
        "dtype": "float",
    },
    {
        "tag": "SPD_CONCHE",
        "desc": "Conche motor speed",
        "unit": "RPM",
        "segment": "mixing_conching",
        "setpoint": 60.0,
        "noise_std": 1.0,
        "low_limit": 40.0,
        "high_limit": 80.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_CONCHE",
        "desc": "Conche chocolate mass temperature",
        "unit": "degC",
        "segment": "mixing_conching",
        "setpoint": 55.0,
        "noise_std": 0.5,
        "low_limit": 50.0,
        "high_limit": 65.0,
        "dtype": "float",
    },
    {
        "tag": "VIB_CONCHE_MOTOR",
        "desc": "Conche motor vibration (RMS velocity)",
        "unit": "mm/s",
        "segment": "mixing_conching",
        "setpoint": 2.5,
        "noise_std": 0.3,
        "low_limit": 0.0,
        "high_limit": 7.0,
        "dtype": "float",
    },
    # ── DEPOSITING ──────────────────────────────────────────────────────────
    {
        "tag": "VAC_DEPOSITOR",
        "desc": "Depositor vacuum pressure",
        "unit": "mbar",
        "segment": "depositing",
        "setpoint": -50.0,
        "noise_std": 3.0,
        "low_limit": -80.0,
        "high_limit": -20.0,
        "dtype": "float",
    },
    {
        "tag": "TEMP_DEPOSITOR_CHOC",
        "desc": "Chocolate temperature at depositor",
        "unit": "degC",
        "segment": "depositing",
        "setpoint": 31.0,
        "noise_std": 0.2,
        "low_limit": 29.5,
        "high_limit": 32.5,
        "dtype": "float",
    },
    {
        "tag": "LVL_DEPOSITOR_HOPPER",
        "desc": "Depositor hopper fill level",
        "unit": "%",
        "segment": "depositing",
        "setpoint": 60.0,
        "noise_std": 8.0,
        "low_limit": 10.0,
        "high_limit": 95.0,
        "dtype": "float",
    },
    # ── INSPECTION / QUALITY ────────────────────────────────────────────────
    {
        "tag": "WEIGHT_CHECKWEIGHER",
        "desc": "Finished bar checkweigher weight",
        "unit": "g",
        "segment": "inspection",
        "setpoint": 100.0,
        "noise_std": 0.8,
        "low_limit": 95.0,
        "high_limit": 105.0,
        "dtype": "float",
        "interval": 0.5,
    },
    {
        "tag": "VISION_BAR_COLOR_L",
        "desc": "Vision system bar color (L* lightness)",
        "unit": "L*",
        "segment": "inspection",
        "setpoint": 32.0,
        "noise_std": 1.0,
        "low_limit": 27.0,
        "high_limit": 37.0,
        "dtype": "float",
        "interval": 0.5,
    },
    {
        "tag": "VISION_BAR_SHAPE_SCORE",
        "desc": "Vision system bar shape conformity score",
        "unit": "score",
        "segment": "inspection",
        "setpoint": 95.0,
        "noise_std": 2.0,
        "low_limit": 80.0,
        "high_limit": 100.0,
        "dtype": "float",
        "interval": 0.5,
    },
    {
        "tag": "METAL_DETECT_CLEAR",
        "desc": "Metal detector pass (1=clear, 0=reject)",
        "unit": "",
        "segment": "inspection",
        "setpoint": 1,
        "noise_std": 0,
        "low_limit": 0,
        "high_limit": 1,
        "dtype": "bool",
        "interval": 0.5,
    },
    {
        "tag": "XRAY_VOID_SCORE",
        "desc": "X-ray void/inclusion detection score",
        "unit": "score",
        "segment": "inspection",
        "setpoint": 98.0,
        "noise_std": 1.0,
        "low_limit": 85.0,
        "high_limit": 100.0,
        "dtype": "float",
        "interval": 0.5,
    },
    # ── ENVIRONMENTAL ───────────────────────────────────────────────────────
    {
        "tag": "HUMID_PRODUCTION",
        "desc": "Production hall humidity",
        "unit": "%RH",
        "segment": "tempering",
        "setpoint": 45.0,
        "noise_std": 2.0,
        "low_limit": 30.0,
        "high_limit": 55.0,
        "dtype": "float",
        "interval": 5.0,
    },
    {
        "tag": "TEMP_AMBIENT_PROD",
        "desc": "Production hall ambient temperature",
        "unit": "degC",
        "segment": "tempering",
        "setpoint": 22.0,
        "noise_std": 0.5,
        "low_limit": 18.0,
        "high_limit": 26.0,
        "dtype": "float",
        "interval": 5.0,
    },
    {
        "tag": "CO2_STORAGE",
        "desc": "Storage area CO2 level",
        "unit": "ppm",
        "segment": "palletizing",
        "setpoint": 450.0,
        "noise_std": 30.0,
        "low_limit": 300.0,
        "high_limit": 1000.0,
        "dtype": "float",
        "interval": 10.0,
    },
    {
        "tag": "DUST_PARTICULATE",
        "desc": "Dust particulate monitor",
        "unit": "mg/m3",
        "segment": "ingredient_dosing",
        "setpoint": 1.2,
        "noise_std": 0.3,
        "low_limit": 0.0,
        "high_limit": 5.0,
        "dtype": "float",
        "interval": 5.0,
    },
    # ── PACKAGING LINE ──────────────────────────────────────────────────────
    {
        "tag": "CNT_BARS_PER_MIN",
        "desc": "Bars per minute (photoelectric counter)",
        "unit": "bars/min",
        "segment": "packaging",
        "setpoint": 120,
        "noise_std": 5,
        "low_limit": 80,
        "high_limit": 150,
        "dtype": "int",
    },
    {
        "tag": "PKG_LABEL_SCAN_OK",
        "desc": "Label barcode scan pass (1=OK, 0=fail)",
        "unit": "",
        "segment": "packaging",
        "setpoint": 1,
        "noise_std": 0,
        "low_limit": 0,
        "high_limit": 1,
        "dtype": "bool",
        "interval": 0.5,
    },
    {
        "tag": "SERVO_WRAPPER_TORQUE",
        "desc": "Wrapper servo motor torque",
        "unit": "Nm",
        "segment": "packaging",
        "setpoint": 8.0,
        "noise_std": 0.5,
        "low_limit": 4.0,
        "high_limit": 12.0,
        "dtype": "float",
    },
    {
        "tag": "SERVO_WRAPPER_SPEED",
        "desc": "Wrapper servo motor speed",
        "unit": "RPM",
        "segment": "packaging",
        "setpoint": 300.0,
        "noise_std": 10.0,
        "low_limit": 150.0,
        "high_limit": 450.0,
        "dtype": "float",
    },
    {
        "tag": "CNT_REJECTS",
        "desc": "Cumulative reject count (resets per batch)",
        "unit": "count",
        "segment": "packaging",
        "setpoint": 0,
        "noise_std": 0,
        "low_limit": 0,
        "high_limit": 50,
        "dtype": "int",
        "interval": 5.0,
    },
    # ── MOTORS / CONVEYORS (vibration & predictive maintenance) ─────────────
    {
        "tag": "VIB_CONV_MAIN",
        "desc": "Main conveyor motor vibration (RMS)",
        "unit": "mm/s",
        "segment": "cooling_tunnel",
        "setpoint": 1.8,
        "noise_std": 0.2,
        "low_limit": 0.0,
        "high_limit": 5.0,
        "dtype": "float",
        "interval": 2.0,
    },
    {
        "tag": "VIB_PUMP_CHOC",
        "desc": "Chocolate pump vibration (RMS)",
        "unit": "mm/s",
        "segment": "tempering",
        "setpoint": 2.0,
        "noise_std": 0.25,
        "low_limit": 0.0,
        "high_limit": 6.0,
        "dtype": "float",
        "interval": 2.0,
    },
    {
        "tag": "SPD_CONV_MAIN_ENC",
        "desc": "Main conveyor encoder speed",
        "unit": "m/min",
        "segment": "cooling_tunnel",
        "setpoint": 2.5,
        "noise_std": 0.03,
        "low_limit": 1.0,
        "high_limit": 4.0,
        "dtype": "float",
    },
]


SENSORS = _build_sensors()
