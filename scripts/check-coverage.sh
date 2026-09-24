#!/usr/bin/env bash
# Coverage ratchet (CI-002): measure, then fail if coverage fell more than
# TOLERANCE points below the recorded baseline.
#
# Why a ratchet and not a target: an invented "80%" is a number nobody chose and
# nothing defends. A ratchet makes the real figure visible and monotone — the
# baseline can only be raised deliberately, in the commit that closes the gap.
#
# The baseline lives in .coverage-baseline (the SSOT for the number); this script
# only reads it and applies the tolerance, so the value is not restated — and
# therefore cannot drift — across the Makefile, the workflow and the docs.
#
# Portable: bash and zsh, no jq, no GNU-only flags beyond grep -E.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASELINE_FILE="$ROOT/.coverage-baseline"
TOLERANCE=2

if [ ! -f "$BASELINE_FILE" ]; then
  echo "check-coverage: $BASELINE_FILE is missing — the ratchet cannot be computed" >&2
  exit 1
fi

# First line that is a bare number; the file's comments are free-form prose.
baseline="$(grep -m1 -oE '^[0-9]+(\.[0-9]+)?' "$BASELINE_FILE" || true)"
if [ -z "$baseline" ]; then
  echo "check-coverage: no baseline number found in $BASELINE_FILE" >&2
  exit 1
fi

floor="$(awk -v b="$baseline" -v t="$TOLERANCE" 'BEGIN { printf "%.2f", b - t }')"

printf '  coverage ....... baseline %s%%, floor %s%% (baseline - %s)\n' \
  "$baseline" "$floor" "$TOLERANCE"

cd "$ROOT"
poetry run pytest \
  --no-header --tb=short -W ignore::DeprecationWarning \
  -m "not e2e" \
  --cov=garsync --cov-report=term \
  --cov-fail-under="$floor"
