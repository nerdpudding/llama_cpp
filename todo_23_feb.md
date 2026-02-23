# TODO 23 February

## Model switching and dashboard decoupling

Goal: switch models without leaving the dashboard, like Ollama but with our
optimized per-model GPU configs. The wrapper should make the complex `-ot`
setup feel simple to use.

### Requirements
- [ ] Make a plan: research current dashboard/container coupling, explore
      options (llama-server load/unload API vs container restart), define
      requirements, write implementation plan
- [ ] Implement model switching
- [ ] Decouple dashboard from container lifecycle (survives model switches)
- [ ] Test manually: switch between models from dashboard, verify GPU
      placement and speed are correct per model

### Design constraints
- Each model has its own `-ot` regex, context size, and GPU layer config
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
