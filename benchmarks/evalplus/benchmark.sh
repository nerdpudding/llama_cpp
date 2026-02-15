#!/usr/bin/env bash
# =============================================================================
# benchmark.sh — EvalPlus HumanEval+ benchmark runner
#
# Main entry point for running benchmarks. Orchestrates:
#   codegen → postprocess → evaluate → report
#
# Usage:
#   ./benchmark.sh --local                  # All local models (llama.cpp)
#   ./benchmark.sh --all                    # All models (local + Claude)
#   ./benchmark.sh bench-glm-flash-q4       # Specific model(s)
#   ./benchmark.sh --report                 # Regenerate report only
#   ./benchmark.sh --list                   # List available profiles
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONF="$PROJECT_DIR/models.conf"
RESULTS_DIR="$SCRIPT_DIR/results"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# Sub-scripts
CODEGEN_SCRIPT="$SCRIPT_DIR/codegen.sh"
POSTPROCESS_SCRIPT="$SCRIPT_DIR/postprocess-solutions.py"
EVALUATE_SCRIPT="$SCRIPT_DIR/evaluate.sh"
REPORT_SCRIPT="$SCRIPT_DIR/generate-report.py"
CLAUDE_SCRIPT="$SCRIPT_DIR/run-claude-benchmark.py"
REFERENCE_FILE="$SCRIPT_DIR/reference-scores.json"

# Client config (system prompts etc. — separate from server config in models.conf)
CLIENT_CONF="$SCRIPT_DIR/bench-client.conf"

# Claude benchmark model IDs (not in models.conf)
CLAUDE_MODELS=("bench-opus4.6-thinking" "bench-opus4.6")

# --- INI parser ---------------------------------------------------------------

declare -a SECTION_IDS=()
declare -A CONFIG=()

parse_conf() {
    local section=""
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        if [[ "$line" =~ ^\[([a-zA-Z0-9_.-]+)\]$ ]]; then
            section="${BASH_REMATCH[1]}"
            SECTION_IDS+=("$section")
            continue
        fi
        if [[ -n "$section" && "$line" == *=* ]]; then
            local key="${line%%=*}"
            local value="${line#*=}"
            CONFIG["${section}.${key}"]="$value"
        fi
    done < "$CONF"
}

get() { echo "${CONFIG["${1}.${2}"]:-}"; }

# --- Client config parser (bench-client.conf) --------------------------------

declare -A CLIENT_CONFIG=()

parse_client_conf() {
    [[ ! -f "$CLIENT_CONF" ]] && return 0
    local section=""
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        if [[ "$line" =~ ^\[([a-zA-Z0-9_.-]+)\]$ ]]; then
            section="${BASH_REMATCH[1]}"
            continue
        fi
        if [[ -n "$section" && "$line" == *=* ]]; then
            local key="${line%%=*}"
            local value="${line#*=}"
            CLIENT_CONFIG["${section}.${key}"]="$value"
        fi
    done < "$CLIENT_CONF"
}

get_client() { echo "${CLIENT_CONFIG["${1}.${2}"]:-}"; }

die() { echo "ERROR: $*" >&2; exit 1; }

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# --- Helpers ------------------------------------------------------------------

get_bench_ids() {
    local ids=()
    for id in "${SECTION_IDS[@]}"; do
        [[ "$id" == bench-* ]] && ids+=("$id")
    done
    echo "${ids[@]}"
}

is_claude_model() {
    local id="$1"
    for cm in "${CLAUDE_MODELS[@]}"; do
        [[ "$id" == "$cm" ]] && return 0
    done
    return 1
}

list_profiles() {
    echo "Available benchmark profiles:"
    echo ""
    echo "  Local models (from models.conf):"
    for id in "${SECTION_IDS[@]}"; do
        [[ "$id" != bench-* ]] && continue
        local name; name=$(get "$id" NAME)
        local model; model=$(get "$id" MODEL)
        echo "    $id  —  $name"
    done
    echo ""
    echo "  Claude models (via Claude Code CLI):"
    for cm in "${CLAUDE_MODELS[@]}"; do
        echo "    $cm"
    done
    echo ""
}

# --- Prerequisite checks -----------------------------------------------------

check_prerequisites() {
    if [[ ! -d "$VENV_DIR" ]]; then
        die "Python venv not found at $VENV_DIR
Run setup first:
  cd $SCRIPT_DIR
  uv venv
  source .venv/bin/activate
  uv pip install evalplus"
    fi
    if ! "$VENV_PYTHON" -c "import evalplus" 2>/dev/null; then
        die "evalplus not installed in $VENV_DIR
Run: source $VENV_DIR/bin/activate && uv pip install evalplus"
    fi
}

check_docker() {
    if ! command -v docker &>/dev/null; then
        die "docker not found. Install Docker first."
    fi
    if ! docker info &>/dev/null 2>&1; then
        die "Docker daemon is not running."
    fi
}

check_no_running_container() {
    local state
    state=$(docker inspect --format='{{.State.Status}}' llama-server 2>/dev/null || true)
    if [[ "$state" == "running" ]]; then
        die "Container 'llama-server' is already running. Stop it first:
  docker compose -f $PROJECT_DIR/docker-compose.yml down"
    fi
}

check_model_file() {
    local id="$1"
    local model; model=$(get "$id" MODEL)
    local full_path="$PROJECT_DIR/models/$model"
    if [[ ! -f "$full_path" ]]; then
        log "WARNING: Model file not found: $full_path — skipping $id"
        return 1
    fi
    return 0
}

# --- Existing data handling ---------------------------------------------------

check_existing_results() {
    local model_id="$1"
    local model_dir="$RESULTS_DIR/$model_id/humaneval"

    # No existing data — proceed
    if [[ ! -d "$model_dir" ]]; then
        return 0
    fi

    # Check if there are actual JSONL files
    local jsonl_count
    jsonl_count=$(find "$model_dir" -name "*.jsonl" ! -name "*.raw.jsonl" 2>/dev/null | wc -l)
    if [[ "$jsonl_count" -eq 0 ]]; then
        return 0
    fi

    echo ""
    echo "Results already exist for $model_id."
    echo "  [o] Overwrite (delete existing, run fresh)"
    echo "  [s] Skip this model"
    echo "  [q] Quit"
    read -rp "Choice [o/s/q]: " choice

    case "$choice" in
        o|O)
            log "Deleting existing results for $model_id..."
            rm -rf "$RESULTS_DIR/$model_id"
            return 0
            ;;
        s|S)
            return 1
            ;;
        q|Q)
            log "Quitting."
            exit 0
            ;;
        *)
            log "Invalid choice. Skipping $model_id."
            return 1
            ;;
    esac
}

# --- .env generation ---------------------------------------------------------

generate_env() {
    local id="$1"
    local model; model=$(get "$id" MODEL)
    local ctx; ctx=$(get "$id" CTX_SIZE)
    local ngl; ngl=$(get "$id" N_GPU_LAYERS)
    local fit; fit=$(get "$id" FIT)
    local extra; extra=$(get "$id" EXTRA_ARGS)

    {
        echo "# Generated by benchmark.sh — $(get "$id" NAME)"
        echo "# Section: [$id] from models.conf"
        echo ""
        [[ -n "$model" ]] && echo "MODEL=$model"
        [[ -n "$ctx" ]]   && echo "CTX_SIZE=$ctx"
        [[ -n "$ngl" ]]   && echo "N_GPU_LAYERS=$ngl"
        [[ -n "$fit" ]]   && echo "FIT=$fit"
        [[ -n "$extra" ]] && echo "EXTRA_ARGS=$extra"
    } > "$PROJECT_DIR/.env"
}

# --- Pipeline steps -----------------------------------------------------------

run_codegen_local() {
    local model_id="$1"
    local model_name; model_name=$(get "$model_id" NAME)
    local sys_prompt; sys_prompt=$(get_client "$model_id" SYSTEM_PROMPT)

    generate_env "$model_id"
    "$CODEGEN_SCRIPT" "$model_id" "$model_name" "$RESULTS_DIR" "$PROJECT_DIR" "$sys_prompt"
}

run_codegen_claude() {
    local model_id="$1"

    if [[ "$model_id" == "bench-opus4.6-thinking" ]]; then
        "$VENV_PYTHON" "$CLAUDE_SCRIPT" --thinking
    else
        "$VENV_PYTHON" "$CLAUDE_SCRIPT"
    fi
}

run_postprocess() {
    local model_id="$1"
    log "Post-processing $model_id..."
    "$VENV_PYTHON" "$POSTPROCESS_SCRIPT" "$RESULTS_DIR/$model_id/"
}

run_evaluate() {
    local model_id="$1"
    "$EVALUATE_SCRIPT" "$model_id" "$RESULTS_DIR" "$VENV_PYTHON"
}

run_report() {
    log "Generating comparison report..."
    "$VENV_PYTHON" "$REPORT_SCRIPT" \
        --results-dir "$RESULTS_DIR" \
        --reference "$REFERENCE_FILE"
}

# --- Main pipeline for a single model ----------------------------------------

run_model() {
    local model_id="$1"

    # Check for existing results
    if ! check_existing_results "$model_id"; then
        log "Skipping $model_id"
        return 2  # skipped
    fi

    # Step 1: Code generation
    if is_claude_model "$model_id"; then
        log "=== Codegen: $model_id (Claude) ==="
        if ! run_codegen_claude "$model_id"; then
            log "Codegen failed for $model_id"
            return 1
        fi
    else
        if ! check_model_file "$model_id"; then
            return 2  # skipped (no model file)
        fi
        log "=== Codegen: $model_id (local) ==="
        if ! run_codegen_local "$model_id"; then
            log "Codegen failed for $model_id"
            return 1
        fi
    fi

    # Step 2: Post-process (always, all models)
    log "=== Post-process: $model_id ==="
    run_postprocess "$model_id" || log "Post-processing warning (non-fatal)"

    # Step 3: Evaluate
    log "=== Evaluate: $model_id ==="
    if ! run_evaluate "$model_id"; then
        log "Evaluation failed for $model_id"
        return 1
    fi

    return 0
}

# =============================================================================
# Main
# =============================================================================

[[ ! -f "$CONF" ]] && die "Config file not found: $CONF"

parse_conf
parse_client_conf

# Collect bench-* model IDs from models.conf
local_bench_ids=()
for id in "${SECTION_IDS[@]}"; do
    [[ "$id" == bench-* ]] && local_bench_ids+=("$id")
done

# Parse arguments
selected_ids=()
do_report=false
include_claude=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all|-a)
            selected_ids=("${local_bench_ids[@]}")
            include_claude=true
            shift
            ;;
        --local|-l)
            selected_ids=("${local_bench_ids[@]}")
            shift
            ;;
        --report|-r)
            do_report=true
            shift
            ;;
        --list)
            list_profiles
            exit 0
            ;;
        --help|-h)
            echo "Usage: $0 [options] [model-id ...]"
            echo ""
            echo "Options:"
            echo "  --all, -a      Run all models (local + Claude)"
            echo "  --local, -l    Run all local models (no Claude)"
            echo "  --report, -r   Regenerate report from existing results"
            echo "  --list         List available benchmark profiles"
            echo "  --help, -h     Show this help"
            echo ""
            echo "Examples:"
            echo "  $0 --local                          # All local models"
            echo "  $0 --all                            # All models including Claude"
            echo "  $0 bench-glm-flash-q4               # Single model"
            echo "  $0 bench-glm-flash-q4 bench-gpt-oss-120b  # Multiple models"
            echo "  $0 bench-opus4.6-thinking            # Claude model only"
            echo "  $0 --report                          # Report only"
            exit 0
            ;;
        -*)
            die "Unknown option: $1. Use --help for usage."
            ;;
        *)
            # Validate model ID (local or Claude)
            found=false
            for id in "${local_bench_ids[@]}"; do
                if [[ "$id" == "$1" ]]; then
                    selected_ids+=("$1")
                    found=true
                    break
                fi
            done
            if [[ "$found" == false ]]; then
                for cm in "${CLAUDE_MODELS[@]}"; do
                    if [[ "$cm" == "$1" ]]; then
                        selected_ids+=("$1")
                        include_claude=false  # already included explicitly
                        found=true
                        break
                    fi
                done
            fi
            if [[ "$found" == false ]]; then
                echo "Error: Unknown benchmark profile '$1'" >&2
                echo ""
                list_profiles >&2
                exit 1
            fi
            shift
            ;;
    esac
done

# Report-only mode
if [[ "$do_report" == true && ${#selected_ids[@]} -eq 0 ]]; then
    check_prerequisites
    run_report
    exit 0
fi

# No arguments — show help
if [[ ${#selected_ids[@]} -eq 0 && "$include_claude" == false ]]; then
    echo "No models selected. Use --local, --all, or specify model IDs."
    echo "Run '$0 --help' for usage."
    exit 1
fi

# Add Claude models if --all was used
if [[ "$include_claude" == true ]]; then
    for cm in "${CLAUDE_MODELS[@]}"; do
        selected_ids+=("$cm")
    done
fi

# Full run: prerequisites
check_prerequisites

# Check docker only if we have local models
has_local=false
for id in "${selected_ids[@]}"; do
    if ! is_claude_model "$id"; then
        has_local=true
        break
    fi
done

if [[ "$has_local" == true ]]; then
    check_docker
    check_no_running_container
fi

mkdir -p "$RESULTS_DIR"

# Summary counters
total=0
passed=0
failed=0
skipped=0

log "Starting benchmark: ${#selected_ids[@]} model(s)"
log "Models: ${selected_ids[*]}"
echo ""

for model_id in "${selected_ids[@]}"; do
    total=$((total + 1))
    echo "================================================================"
    log "[$total/${#selected_ids[@]}] $model_id"
    echo "================================================================"

    rc=0
    run_model "$model_id" || rc=$?

    case $rc in
        0) passed=$((passed + 1)) ;;
        1) failed=$((failed + 1)) ;;
        2) skipped=$((skipped + 1)) ;;
    esac

    echo ""
done

# Summary
echo "================================================================"
log "Benchmark complete"
log "  Total: $total | Passed: $passed | Failed: $failed | Skipped: $skipped"
echo "================================================================"

# Generate report if any results exist
if [[ $passed -gt 0 ]] || [[ "$do_report" == true ]]; then
    echo ""
    run_report || log "Report generation failed (non-fatal)"
fi
