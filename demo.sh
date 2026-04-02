#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
SEED_DIR="$SCRIPT_DIR/data_seed"

# Kill any leftover Modbus simulator from a previous run
if lsof -ti :5020 > /dev/null 2>&1; then
  echo "=== Stopping previous Modbus simulator on port 5020 ==="
  kill $(lsof -ti :5020) 2>/dev/null || true
  sleep 1
fi

# Stop the container so we can safely reset data
docker compose -f docker/docker-compose.yml down 2>/dev/null || true

# Restore seeded data to a clean state
if [[ -d "$SEED_DIR" ]]; then
  echo "=== Restoring data/ from seed snapshot ==="
  rm -rf "$DATA_DIR"
  cp -a "$SEED_DIR" "$DATA_DIR"
else
  echo "ERROR: No data_seed/ directory found. Run prepare_seed.py first." >&2
  exit 1
fi
echo ""

echo "=== Starting FairCom Edge container ==="
docker compose -f docker/docker-compose.yml up -d --quiet-pull
echo ""

echo "=== Waiting for FairCom Edge to be ready ==="
until curl -sf http://localhost:8080 > /dev/null 2>&1; do
  sleep 2
done
echo "FairCom Edge is up."
echo ""

echo "=== Starting Modbus simulator (background) ==="
python3 -m simulator.modbus_simulator &
MODBUS_PID=$!
sleep 2
echo ""

echo "=== Connecting FairCom Edge to the Modbus simulator ==="
python3 -m simulator.generate_data --mode setup -y
echo ""

echo "Demo is running. Modbus simulator PID: $MODBUS_PID"
echo "  FairCom Edge:  http://localhost:8080  (admin / ADMIN)"
echo "  Press Ctrl+C to stop."
echo ""

# Keep the script alive; clean up on exit
trap "kill $MODBUS_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait $MODBUS_PID
