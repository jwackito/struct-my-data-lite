#!/usr/bin/env bash
# Regenerate a hash-pinned lock file from a requirements input.
#
# Usage: tools/lock.sh [requirements-input]
#
# Default input: requirements.in. The output is the input path with .in -> .txt
# (requirements.in -> requirements.txt, requirements-saas.in ->
# requirements-saas.txt).
#
# Strategy: install the input in a throwaway venv inside the dev app
# container, freeze the exact transitive tree, download every artifact and
# record its sha256. The result installs with:
#   pip install --require-hashes -r <output>
#
# This avoids pip-compile's resolver backtracking on the large transitive tree
# while staying fully reproducible (exact versions + hashes).
set -euo pipefail

cd "$(dirname "$0")/.."
CONTAINER="${SMD_CONTAINER:-structmydata-app-1}"
INPUT="${1:-requirements.in}"
OUTPUT="${INPUT%.in}.txt"

echo "==> Building lock for $INPUT inside $CONTAINER"
docker exec -e INPUT="$INPUT" "$CONTAINER" sh -c '
  set -e
  rm -rf /tmp/lockgen && mkdir -p /tmp/lockgen
  python -m venv /tmp/lockgen/venv
  /tmp/lockgen/venv/bin/pip install -q --upgrade pip
  /tmp/lockgen/venv/bin/pip install -q -r "/app/$INPUT"
  /tmp/lockgen/venv/bin/pip freeze > /tmp/lockgen/freeze.txt
  mkdir -p /tmp/lockgen/wheels
  /tmp/lockgen/venv/bin/pip download -q --no-deps -r /tmp/lockgen/freeze.txt -d /tmp/lockgen/wheels
'

docker cp tools/gen_lock.py "$CONTAINER:/tmp/lockgen/gen_lock.py"
docker exec "$CONTAINER" python /tmp/lockgen/gen_lock.py
docker exec "$CONTAINER" sh -c "cat /tmp/lockgen/requirements.lock" > "$OUTPUT"

echo "==> Wrote $OUTPUT"
head -4 "$OUTPUT"
