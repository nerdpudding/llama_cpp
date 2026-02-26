# TODO 26 February

## Priority 1: Qwen3.5 Model Onboarding

Plan: `claude_plans/qwen3_5_onboarding_plan.md`

Three Qwen3.5 models to onboard using `/add-model` skill for each:
- Qwen3.5-122B-A10B UD-Q4_K_XL (68.4 GB) — MoE, replaces GPT-OSS
- Qwen3.5-35B-A3B UD-Q6_K_XL (30.3 GB) — MoE, replaces Qwen3-Next
- Qwen3.5-27B UD-Q8_K_XL (32.4 GB) — Dense, replaces Qwen3-Coder-Next

### Progress
- [x] Phase 1: Evaluate — architecture, quant selection, sizing done
- [x] Phase 2: Download — all three models downloaded
- [x] Phase 3: Create production profiles — all three added to models.conf
- [x] Phase 4: Find sampler settings — Qwen3.5 family (thinking model, documented)
- [x] Phase 5: Test with 262K context
  - 35B-A3B: ~120 t/s, 3 graph splits — excellent
  - 122B-A10B: ~18 t/s, 65 graph splits — works, RAM tight
  - 27B dense: CUDA crash on inference — needs investigation
- [x] Phase 6: Create bench profiles — all three added
- [x] Phase 7: Run EvalPlus HumanEval+ benchmarks (35B + 122B done, 27B blocked)
  - 122B-A10B: 97.6% HumanEval, 94.5% HumanEval+ (#2 overall, behind Claude only)
  - 35B-A3B: 95.1% HumanEval, 90.9% HumanEval+ (ties Qwen3-Coder-Next at 4x speed)
- [x] Phase 8: Update documentation (doc-keeper) — in progress
- [x] Post-onboarding: retirement decisions made (see below)

### Retirement decisions
Models retired from active use (bench data and REPORT.md preserved):
- **GPT-OSS 120B** (61 GB) — outclassed by Qwen3.5-122B (94.5% vs 87.2% HE+, similar speed)
- **Qwen3-Coder-Next** (57 GB) — matched by Qwen3.5-35B (90.9% HE+ each, 120 vs 33 t/s)
- **Qwen3-Next-80B-A3B** (53 GB) — replaced by Qwen3.5-122B (94.5% vs 93.9% HE+)

Active lineup going forward:
- GLM-4.7 Flash Q4 (~147 t/s) — fast daily driver
- GLM-4.7 Flash Q8 (~112 t/s) — higher quality daily driver
- **Qwen3.5-35B-A3B Q6** (~120 t/s) — fast thinking model, coding, agentic
- **Qwen3.5-122B-A10B Q4** (~18 t/s) — quality king, deep reasoning
- Qwen3.5-27B Q8 — pending (CUDA crash investigation)

### Remaining work
- [ ] Document benchmark findings and retirement decisions across all docs
- [ ] Investigate Qwen3.5-27B CUDA crash (multi-GPU dense model issue)
- [ ] Once 27B works: test + benchmark + add to comparison

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
- **Note:** upstream update may also fix the Qwen3.5-27B CUDA crash

### API integration with external tools (defer)
- Connect Continue.dev, aider, OpenClaw, etc. to the local server
- Depends on local Claude Code integration being stable first
- Low priority — defer to a future session
