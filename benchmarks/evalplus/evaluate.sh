#!/usr/bin/env bash
# =============================================================================
# evaluate.sh — Run evalplus evaluation on generated solutions
#
# Works for all models (local and Claude). Finds the JSONL file in the
# model's results directory and runs evalplus.evaluate.
#
# Usage:
#   ./evaluate.sh <model-id> <results-dir> <venv-python>
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODEL_ID="${1:?Usage: $0 <model-id> <results-dir> <venv-python>}"
RESULTS_DIR="${2:-$SCRIPT_DIR/results}"
VENV_PYTHON="${3:-$SCRIPT_DIR/.venv/bin/python}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

MODEL_DIR="$RESULTS_DIR/$MODEL_ID/humaneval"

if [[ ! -d "$MODEL_DIR" ]]; then
    echo "ERROR: No humaneval/ directory found for $MODEL_ID"
    echo "Expected: $MODEL_DIR"
    exit 1
fi

# Find solutions JSONL (exclude backups and parts)
JSONL=$(find "$MODEL_DIR" -name "*.jsonl" ! -name "*.raw.jsonl" ! -name "*_part*" 2>/dev/null | head -1)

if [[ -z "$JSONL" ]]; then
    echo "ERROR: No solutions JSONL found in $MODEL_DIR"
    exit 1
fi

log "Evaluating $MODEL_ID"
log "Solutions: $JSONL"

$VENV_PYTHON -m evalplus.evaluate \
    --samples "$JSONL" \
    --dataset humaneval \
    --parallel 8 \
    2>&1 | tee "$RESULTS_DIR/$MODEL_ID/evaluation.log"

rc=${PIPESTATUS[0]}
if [[ $rc -ne 0 ]]; then
    log "Evaluation failed for $MODEL_ID (exit code $rc)"
    exit 1
fi

log "Evaluation complete: $MODEL_ID"
