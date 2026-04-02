"""
Chocolate Factory – FairCom Edge state check
Run with:  python check_state.py
"""
import requests, json

BASE = 'http://localhost:8080'

r = requests.post(f'{BASE}/api/admin', json={
    'api': 'admin', 'action': 'createSession',
    'params': {'username': 'admin', 'password': 'ADMIN'}
}, timeout=10)
tok = r.json()['authToken']
print("FairCom Edge  ✓  connected\n")

# Registered inputs
r2 = requests.post(f'{BASE}/api/hub', json={
    'api': 'hub', 'action': 'listInputs', 'params': {}, 'authToken': tok
}, timeout=10)
inputs = r2.json().get('result', {}).get('data', [])
print(f"Inputs ({len(inputs)}): {inputs or 'none'}\n")

# Integration tables (user-created only)
r3 = requests.post(f'{BASE}/api/hub', json={
    'api': 'hub', 'action': 'listIntegrationTables', 'params': {}, 'authToken': tok
}, timeout=10)
user_tables = [t['tableName'] for t in r3.json().get('result', {}).get('data', [])
               if not t['tableName'].startswith('mqtt_')]
print(f"Integration tables ({len(user_tables)}):")

# Row count per table
for tbl in sorted(user_tables):
    r4 = requests.post(f'{BASE}/api/db', json={
        'api': 'db', 'action': 'getRecordsUsingSQL',
        'params': {'databaseName': 'faircom', 'sql': f'SELECT COUNT(*) AS cnt FROM {tbl}'},
        'authToken': tok
    }, timeout=10)
    d = r4.json()
    result_data = d.get('result', {}).get('data', [])
    rows = result_data if isinstance(result_data, list) else result_data.get('rows', [])
    cnt = rows[0].get('cnt', '?') if rows else f'ERR {d.get("errorCode")}'
    print(f"  {tbl:<30} {cnt} rows")

