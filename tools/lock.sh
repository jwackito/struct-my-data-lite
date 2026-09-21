#!/usr/bin/env bash
# Regenerate requirements.txt as a hash-pinned lock.
#
# Usage: tools/lock.sh
#
# Strategy: install requirements.in in a throwaway venv inside the dev app
# container, freeze the exact transitive tree, download every artifact and
# record its sha256. The result installs with:
#   pip install --require-hashes -r requirements.txt
#
# This avoids pip-compile's resolver backtracking on the large transitive tree
# while staying fully reproducible (exact versions + hashes).
set -euo pipefail

cd "$(dirname "$0")/.."
CONTAINER="${SMD_CONTAINER:-structmydata-app-1}"

echo "==> Building lock inside $CONTAINER"
docker exec "$CONTAINER" sh -c '
  set -e
  rm -rf /tmp/lockgen && mkdir -p /tmp/lockgen
  python -m venv /tmp/lockgen/venv
  /tmp/lockgen/venv/bin/pip install -q --upgrade pip
  /tmp/lockgen/venv/bin/pip install -q -r /app/requirements.in
  /tmp/lockgen/venv/bin/pip freeze > /tmp/lockgen/freeze.txt
  mkdir -p /tmp/lockgen/wheels
  /tmp/lockgen/venv/bin/pip download -q --no-deps -r /tmp/lockgen/freeze.txt -d /tmp/lockgen/wheels
'

docker cp tools/gen_lock.py "$CONTAINER:/tmp/lockgen/gen_lock.py"
docker exec "$CONTAINER" python /tmp/lockgen/gen_lock.py
docker exec "$CONTAINER" sh -c "cat /tmp/lockgen/requirements.lock" > requirements.txt

echo "==> Wrote requirements.txt"
head -4 requirements.txt
