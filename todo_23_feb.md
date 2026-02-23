# TODO 23 February

## Model switching and dashboard decoupling

Goal: switch models without leaving the dashboard, like Ollama but with our
optimized per-model GPU configs. Each model has its own FIT-based GPU placement
config in `models.conf` — the wrapper makes this feel simple to use.

### Requirements
- [x] Make a plan: research current dashboard/container coupling, explore
      options (llama-server load/unload API vs container restart), define
      requirements, write implementation plan
- [x] Implement model switching
- [x] Decouple dashboard from container lifecycle (survives model switches)
- [x] Test manually: switch between models from dashboard, verify GPU
      placement and speed are correct per model

### Design constraints
- Each model has its own context size, FIT GPU placement, and sampler config
  in `models.conf` — switching must apply the full profile, not just the
  model file
- Dashboard must stay running during switches and show loading progress
- Solution must also support switching via API (for future integration
  with Claude Code, agents, and other tools that call the local server)

## Not this session (but keep in mind)

### API integration with external tools
- Connect Claude Code, Continue.dev, aider, etc. to the local server
- Depends on model switching working well — an agent should be able to
  request a specific model and have it loaded automatically
- Defer to a future session, but the model switching design must not
  block this

## Ongoing

### llama.cpp upstream merge
- Waiting for `ggml_set_inplace` → `ggml_set` fix to merge into master
- Running patched `ed4837891` locally
- Check: https://github.com/ggml-org/llama.cpp/issues/19816
- Note: patch is no longer load-bearing — migrated to FIT auto (no `-ot`)

## Completed today

### FIT auto migration (2026-02-23)
- [x] Discovered `N_GPU_LAYERS=99` in Dockerfile/docker-compose prevented FIT
      from working — FIT OOM'd because it tried to put 99 layers on GPU
- [x] Changed `N_GPU_LAYERS=auto` in Dockerfile and docker-compose.yml
- [x] Converted ALL models.conf profiles from `-ot` GPU splits to FIT auto
      (removed FIT=off, N_GPU_LAYERS=99, all `-ot` GPU device assignments)
- [x] Tested Qwen3-Next with FIT auto at 262K: 32.9 t/s (vs 26.5 t/s), 55 graph splits (vs 136)
- [x] Updated all documentation to reflect new GPU strategy

### FIT_TARGET tuning for asymmetric GPU setup (2026-02-23)
- [x] Discovered `FIT_TARGET` per-device is important for asymmetric GPU setups
      (CUDA0 dedicated, CUDA1 shares with display)
- [x] Set `FIT_TARGET=128,1024` as default in `docker-compose.yml`
      (128 MiB margin for CUDA0, 1024 MiB for CUDA1/display)
- [x] Final measured speeds after tuning:
      - GLM Q4: ~147 t/s (was ~140)
      - GLM Q8: ~112 t/s, 5 graph splits (was ~105 t/s, 33 splits)
      - GPT-OSS 120B: ~22 t/s (was ~21 t/s)
      - Qwen3-Coder-Next: ~33 t/s (was ~28 t/s)
      - Qwen3-Next: ~33 t/s (was ~27 t/s)
- [x] Updated README, ROADMAP, gpu-strategy-guide, known_issue doc, lessons_learned,
      client-settings, gpu-optimizer agent, docker-compose.example.yml
