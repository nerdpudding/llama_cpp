# TODO 15 februari

## Volgorde

### 1. Implementeer PLAN_separation_of_concerns — DONE
- [x] `bench-client.conf` aanmaken (GPT-OSS system prompt + MAX_TOKENS defaults)
- [x] `codegen-custom.py` schrijven (lokale API met system prompt + max_tokens)
- [x] `codegen.sh` aanpassen (kies evalplus vs custom codegen)
- [x] `benchmark.sh` aanpassen (parse bench-client.conf, patch evalplus max_tokens)
- [x] models.conf comments toevoegen ("dit is server config")
- [x] README.md updaten (server vs client config uitleg)
- [x] benchmarks/evalplus/README.md updaten (bench-client.conf docs, MAX_TOKENS, reasoning-format)

### 2. Test alles samen (fair postprocessing + separation of concerns) — IN PROGRESS
- [x] Smoke test: `./benchmark.sh bench-glm-flash-q4` (loopt nu)
- [ ] Controleer: postprocessor stript GLM correct
- [ ] Controleer: evaluate + report werken in nieuwe pipeline
- [ ] Draai `./benchmark.sh bench-gpt-oss-120b` (test system prompt pad)
- [ ] Controleer: "Running custom codegen (system prompt: Reasoning: high)" in log
- [ ] Controleer: delete/skip/quit prompt werkt
- [ ] Draai resterende modellen
- [ ] Controleer: REPORT.md genereert correct met alle modellen
- [ ] Draai Claude benchmark apart (als gewenst)

### 3. Na succesvolle test
- [ ] Archiveer `PLAN_fair_postprocessing_benchmark.md` → `archive/`
- [ ] Archiveer `PLAN_separation_of_concerns.md` → `archive/`
- [ ] Controleer alle README's en docs op accuraatheid
- [ ] Commit

### 4. GPU layer optimalisatie bench profielen — NOT STARTED
Zie `claude_plans/PLAN_bench_gpu_optimization.md`
- [ ] Handmatige test: GPT-OSS + Reasoning: high, meet response lengtes
- [ ] Bench profiles toevoegen aan start.sh model picker
- [ ] CTX_SIZE verlagen naar 8192 voor alle bench profiles
- [ ] GLM Q4/Q8 testen of ze op 4090-only passen
- [ ] Layer splits optimaliseren voor GPT-OSS en Qwen3
- [ ] OOM test per model via start.sh
- [ ] models.conf bench profiles updaten
- [ ] Full benchmark run met geoptimaliseerde profiles
