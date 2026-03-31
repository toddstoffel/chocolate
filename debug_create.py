import sys, json, requests
sys.path.insert(0, '.')
import config
import generate_data as gd

gd.faircom_connect(
    'http://localhost:8080',
    config.FAIRCOM_USER,
    config.FAIRCOM_PASSWORD,
    config.FAIRCOM_DB
)

def raw_api(endpoint, payload):
    payload['authToken'] = gd._auth_token
    r = requests.post(gd._base_url + f'/api/{endpoint}', json=payload, timeout=10)
    return r.json()

for tbl in ('batch_log', 'sensor_alarms', 'sensor_readings', 'sensor_registry'):
    res = raw_api('db', {
        'api': 'query', 'action': 'sql',
        'params': {
            'databaseName': 'faircom',
            'query': f'SELECT COUNT(*) AS cnt FROM {tbl}',
        }
    })
    err = res.get('errorCode', 0)
    if err:
        # fallback: try getRecordsByTable without dataFormat
        res2 = raw_api('db', {
            'api': 'db', 'action': 'getRecordsByTable',
            'params': {'databaseName': 'faircom', 'tableName': tbl}
        })
        err2 = res2.get('errorCode', 0)
        if err2:
            print(f"{tbl:25} ERROR [{err2}]: {res2.get('errorMessage','')}")
        else:
            rows = res2.get('result', {}).get('data', [])
            print(f"{tbl:25} ~{len(rows)} rows (partial response)")
    else:
        data = res.get('result', {}).get('data', [])
        cnt = data[0].get('cnt', '?') if data else '?'
        print(f"{tbl:25} {cnt} rows")
