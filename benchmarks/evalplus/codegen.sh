#!/usr/bin/env bash
# =============================================================================
# codegen.sh — Code generation for local models via llama.cpp API
#
# Starts the model server, runs evalplus code generation, stops the server.
# Called by benchmark.sh (which generates .env beforehand).
#
# Usage:
#   ./codegen.sh <model-id> <model-name> <results-dir> <project-dir>
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

MODEL_ID="${1:?Usage: $0 <model-id> <model-name> <results-dir> <project-dir>}"
MODEL_NAME="${2:?Usage: $0 <model-id> <model-name> <results-dir> <project-dir>}"
RESULTS_DIR="${3:?Usage: $0 <model-id> <model-name> <results-dir> <project-dir>}"
PROJECT_DIR="${4:?Usage: $0 <model-id> <model-name> <results-dir> <project-dir>}"

COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
HEALTH_URL="http://localhost:8080/health"
HEALTH_TIMEOUT=600  # 10 minutes — large models need time to load
EVALPLUS_DOCKER="ganler/evalplus:latest"

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

# Run evalplus codegen
log "Running code generation..."
codegen_ok=true
"$VENV_DIR/bin/evalplus.codegen" \
    --model "$MODEL_NAME" \
    --dataset humaneval \
    --base-url http://localhost:8080/v1 \
    --backend openai \
    --greedy \
    --root "$OUTPUT_DIR" \
    2>&1 | tee "$OUTPUT_DIR/codegen.log"

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
