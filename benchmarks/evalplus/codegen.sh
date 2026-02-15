#!/usr/bin/env bash
# =============================================================================
# codegen.sh — Code generation for local models via llama.cpp API
#
# Starts the model server, runs code generation, stops the server.
# Called by benchmark.sh (which generates .env beforehand).
#
# Uses evalplus.codegen by default. When a system prompt is provided
# (5th argument), uses codegen-custom.py instead (evalplus doesn't
# support system prompts).
#
# Usage:
#   ./codegen.sh <model-id> <model-name> <results-dir> <project-dir> [system-prompt] [max-tokens]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
CUSTOM_CODEGEN="$SCRIPT_DIR/codegen-custom.py"

MODEL_ID="${1:?Usage: $0 <model-id> <model-name> <results-dir> <project-dir> [system-prompt] [max-tokens]}"
MODEL_NAME="${2:?Usage: $0 <model-id> <model-name> <results-dir> <project-dir> [system-prompt] [max-tokens]}"
RESULTS_DIR="${3:?Usage: $0 <model-id> <model-name> <results-dir> <project-dir> [system-prompt] [max-tokens]}"
PROJECT_DIR="${4:?Usage: $0 <model-id> <model-name> <results-dir> <project-dir> [system-prompt] [max-tokens]}"
SYSTEM_PROMPT="${5:-}"
MAX_TOKENS="${6:-4096}"

COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
HEALTH_URL="http://localhost:8080/health"
HEALTH_TIMEOUT=600  # 10 minutes — large models need time to load

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# --- Health check -------------------------------------------------------------

wait_for_health() {
    local elapsed=0

    log "Waiting for server health (timeout: ${HEALTH_TIMEOUT}s)..."

    while (( elapsed < HEALTH_TIMEOUT )); do
        local state
        state=$(docker inspect --format='{{.State.Status}}' llama-server 2>/dev/null || echo "missing")
        if [[ "$state" != "running" ]]; then
            log "Container stopped unexpectedly. Recent logs:"
            docker compose -f "$COMPOSE_FILE" logs --tail=30 2>/dev/null || true
            return 1
        fi

        if curl -sf "$HEALTH_URL" &>/dev/null; then
            log "Server is ready."
            return 0
        fi

        sleep 5
        elapsed=$((elapsed + 5))
    done

    log "Timeout after ${HEALTH_TIMEOUT}s. Recent logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail=20 2>/dev/null || true
    return 1
}

# --- Main ---------------------------------------------------------------------

OUTPUT_DIR="$RESULTS_DIR/$MODEL_ID"
mkdir -p "$OUTPUT_DIR"

# Start container
log "Starting container for $MODEL_NAME..."
docker compose -f "$COMPOSE_FILE" up -d

# Wait for health
if ! wait_for_health; then
    log "Server failed to start — aborting"
    docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true
    exit 1
fi

# Run code generation
codegen_ok=true

if [[ -n "$SYSTEM_PROMPT" ]]; then
    # Custom codegen with system prompt (evalplus doesn't support system prompts)
    log "Running custom codegen (system prompt: $SYSTEM_PROMPT)..."
    "$VENV_PYTHON" "$CUSTOM_CODEGEN" \
        --model-name "$MODEL_NAME" \
        --system-prompt "$SYSTEM_PROMPT" \
        --max-tokens "$MAX_TOKENS" \
        --output-dir "$OUTPUT_DIR" \
        2>&1 | tee "$OUTPUT_DIR/codegen.log"
else
    # Standard evalplus codegen (no system prompt needed)
    log "Running evalplus codegen..."
    "$VENV_DIR/bin/evalplus.codegen" \
        --model "$MODEL_NAME" \
        --dataset humaneval \
        --base-url http://localhost:8080/v1 \
        --backend openai \
        --greedy \
        --root "$OUTPUT_DIR" \
        2>&1 | tee "$OUTPUT_DIR/codegen.log"
fi

rc=${PIPESTATUS[0]}
if [[ $rc -ne 0 ]]; then
    log "Code generation failed (exit code $rc)"
    codegen_ok=false
fi

# Stop container
log "Stopping container..."
docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true

if [[ "$codegen_ok" == false ]]; then
    exit 1
fi

log "Code generation complete: $OUTPUT_DIR"
