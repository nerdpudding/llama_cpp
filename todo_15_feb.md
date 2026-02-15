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

### 4. GPU layer optimalisatie bench profielen — IN PROGRESS
Zie `claude_plans/PLAN_bench_gpu_optimization.md`
- [x] Handmatige test: GPT-OSS + Reasoning: high, meet response lengtes (max ~3,300 tokens)
- [x] CTX_SIZE verlagen naar 10240 voor alle bench profiles
- [x] GLM Q4 getest: past op 4090-only (Strategy A), ~140 t/s
- [x] GLM Q8 split aangemaakt (Strategy C, 35+12, beide GPUs)
- [x] GPT-OSS split geoptimaliseerd (13+5=18/36, was 12+5)
- [x] Qwen3 splits berekend (Q5: 18+8, Q6/Q6K: 16+7)
- [x] GPU strategy docs aangemaakt (gpu-strategy-guide.md, lessons_learned.md)
- [x] gpu-optimizer agent aangemaakt en alle agents bijgewerkt
- [ ] Bench profiles testen (zie testlijst hieronder)
- [ ] Na tests: productie profiles reviewen
- [ ] Full benchmark run met geoptimaliseerde profiles

## Profile test status

### Bench profiles

| Profile | Strategy | Split | Status |
|---------|----------|-------|--------|
| `bench-glm-flash-q4` | A (4090 only) | 47/47 GPU | OK — ~140 t/s |
| `bench-glm-flash-q8` | C (beide GPUs) | 35+12=47/47 | OK — ~105 t/s (37+10 getest: trager, 53 splits) |
| `bench-gpt-oss-120b` | D (GPU+CPU) | 13+5=18/36 | ONGETEST (was 12+5) |
| `bench-qwen3-coder-ud-q5` | D (GPU+CPU) | 18+8=26/48 | ONGETEST |
| `bench-qwen3-coder-ud-q6` | D (GPU+CPU) | 16+7=23/48 | ONGETEST |
| `bench-qwen3-coder-q6k` | D (GPU+CPU) | 16+7=23/48 | ONGETEST |

### Productie profiles

| Profile | Strategy | Split | Status |
|---------|----------|-------|--------|
| `glm-flash-q4` | A (4090 only) | all GPU | Werkt, niet gereviewd |
| `glm-flash-q8` | ? | ? | Werkt, niet gereviewd |
| `gpt-oss-120b` | D (GPU+CPU) | 12+4=16/36 | Werkt, niet gereviewd |
| `qwen3-coder` | D (GPU+CPU) | 13+6=19/48 | Werkt, niet gereviewd |
| `qwen3-coder-q5` | D (GPU+CPU) | 15+7=22/48 | Werkt, niet gereviewd |
| `qwen3-coder-q6k` | D (GPU+CPU) | 13+6=19/48 | Werkt, niet gereviewd |
