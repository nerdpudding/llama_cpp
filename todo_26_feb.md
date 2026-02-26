# TODO 26 February

## Priority 1: Qwen3.5 Model Onboarding

Plan: `claude_plans/qwen3_5_onboarding_plan.md`

Three Qwen3.5 models to onboard using `/add-model` skill for each:
- Qwen3.5-122B-A10B UD-Q4_K_XL (68.4 GB) — MoE, replaces GPT-OSS
- Qwen3.5-35B-A3B UD-Q6_K_XL (30.3 GB) — MoE, replaces Qwen3-Next
- Qwen3.5-27B UD-Q8_K_XL (32.4 GB) — Dense, replaces Qwen3-Coder-Next

### Progress
- [x] Phase 1: Evaluate — architecture, quant selection, sizing done
- [ ] Phase 2: Download — user downloading recommended quants
- [ ] Phase 3: Create production profiles (gpu-optimizer, per model)
- [ ] Phase 4: Find sampler settings (Qwen3.5 family)
- [ ] Phase 5: Test with full 262K context (per model, verify load + speed)
- [ ] Phase 6: Create bench profiles (per model)
- [ ] Phase 7: Run EvalPlus HumanEval+ benchmarks (all three + full comparison)
- [ ] Phase 8: Update documentation (doc-keeper)
- [ ] Post-onboarding: decide which old models to retire (save disk space)

## Priority 2: Carry-over from 24 Feb

### Claude-local hands-on testing
- [ ] Extensive hands-on testing of claude-local — use it for real tasks, try
      different models (including the new Qwen3.5 models), explore edge cases.
      Findings and ideas feed into roadmap and future improvements.

### llama.cpp upstream merge
- Waiting for `ggml_set_inplace` -> `ggml_set` fix to merge into master
- Running patched `ed4837891` locally
- Check: https://github.com/ggml-org/llama.cpp/issues/19816
- Note: patch is no longer load-bearing — migrated to FIT auto (no `-ot`)
- **Action:** check if upstream has merged the fix; if so, rebuild

### API integration with external tools (defer)
- Connect Continue.dev, aider, OpenClaw, etc. to the local server
- Depends on local Claude Code integration being stable first
- Low priority — defer to a future session
