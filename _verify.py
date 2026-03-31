import requests, json

BASE = "http://localhost:8080"

r = requests.post(BASE + "/api/admin", json={
    "api": "admin", "action": "createSession",
    "params": {"username": "admin", "password": "ADMIN"}
})
token = r.json()["authToken"]

segments = [
    "tempering", "cooling_tunnel", "depositing", "demolding", "inspection",
    "packaging", "mixing_conching", "refining", "roasting", "ingredient_dosing",
    "utilities", "hvac", "cold_storage", "energy", "environmental",
    "water_treatment", "palletizing"
]


def sql(q):
    r2 = requests.post(BASE + "/api/db", json={
        "api": "db", "action": "runSqlStatements", "authToken": token,
        "params": {"databaseName": "faircom", "sqlStatements": [q]}
    })
    rxn = r2.json().get("result", {}).get("reactions", [{}])[0]
    return rxn.get("rows", {}).get("data", [])


print(f"  {'Segment':<22} {'Rows':>6}  {'Backfill':>9}  {'Live':>6}")
print("  " + "-" * 48)
total = 0
for seg in segments:
    rows = sql(f"SELECT COUNT(*) AS cnt FROM {seg}")
    cnt = rows[0]["cnt"] if rows else 0
    total += cnt
    bf = min(cnt, 31)
    live = max(cnt - 31, 0)
    print(f"  {seg:<22} {cnt:>6}  {bf:>9}  {live:>6}")
print("  " + "-" * 48)
print(f"  {'TOTAL':<22} {total:>6}")

# Sample payload from palletizing (oldest backfill row)
print()
print("--- Sample backfill source_payload (palletizing row 1) ---")
rows = sql("SELECT source_payload FROM palletizing")
if rows:
    hex_val = rows[0]["source_payload"]
    decoded = json.loads(bytes.fromhex(hex_val).decode("utf-8"))
    keys = list(decoded.keys())
    print(f"  Sensor count : {len(keys) - 1}")   # exclude create_ts
    print(f"  Key ordering : {keys[:3]} ... {keys[-2:]} (last=create_ts: {keys[-1]})")
    sample_key = keys[0]
    print(f"  Sample value : {sample_key} = {decoded[sample_key]}  (float32 precision)")
    print(f"  create_ts    : {decoded.get('create_ts', 'MISSING')}")

