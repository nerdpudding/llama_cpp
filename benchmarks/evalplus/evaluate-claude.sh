#!/usr/bin/env bash
# evaluate-claude.sh — Run evalplus evaluation on Claude-generated solutions.
#
# Usage:
#   ./evaluate-claude.sh bench-opus4.6-thinking
#   ./evaluate-claude.sh bench-opus4.6
#   ./evaluate-claude.sh              # evaluates both if they exist
#
# Prerequisites:
#   - Solutions JSONL must exist in results/<bench-id>/humaneval/
#   - Docker must be running (evaluation uses ganler/evalplus sandbox)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

evaluate_model() {
    local bench_id="$1"
    local model_dir="$RESULTS_DIR/$bench_id/humaneval"

    # Find the solutions JSONL
    local jsonl
    jsonl=$(find "$model_dir" -name "*.jsonl" ! -name "*.raw.jsonl" ! -name "*_part*" 2>/dev/null | head -1)

    if [[ -z "$jsonl" ]]; then
        echo "ERROR: No solutions JSONL found in $model_dir"
        return 1
    fi

    echo "=== Evaluating $bench_id ==="
    echo "Solutions: $jsonl"
    echo ""

    # Run evalplus evaluation in Docker sandbox
    $VENV_PYTHON -m evalplus.evaluate \
        --samples "$jsonl" \
        --dataset humaneval \
        --parallel 8 \
        2>&1 | tee "$RESULTS_DIR/$bench_id/evaluation.log"

    echo ""
    echo "Done: $bench_id"
    echo "Results: $RESULTS_DIR/$bench_id/"
    echo ""
}

# Determine which models to evaluate
if [[ $# -gt 0 ]]; then
    MODELS=("$@")
else
    MODELS=()
    for d in bench-opus4.6-thinking bench-opus4.6; do
        if [[ -d "$RESULTS_DIR/$d/humaneval" ]]; then
            MODELS+=("$d")
        fi
    done
fi

if [[ ${#MODELS[@]} -eq 0 ]]; then
    echo "No Claude benchmark results found. Run the humaneval-solver agent first."
    exit 1
fi

for model in "${MODELS[@]}"; do
    evaluate_model "$model"
done

echo "=== Generating report ==="
cd "$SCRIPT_DIR"
$VENV_PYTHON generate-report.py
