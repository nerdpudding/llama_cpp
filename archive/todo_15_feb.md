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

### 2. Test alles samen (fair postprocessing + separation of concerns) — DONE
- [x] Smoke test bench-glm-flash-q4
- [x] Pipeline werkt (codegen → postprocess → evaluate → report)
- [x] Full benchmark run draait nu met --all

### 3. Na succesvolle test — DONE
- [x] Archiveer `PLAN_fair_postprocessing_benchmark.md` → `archive/`
- [x] Archiveer `PLAN_separation_of_concerns.md` → `archive/`

### 4. GPU layer optimalisatie bench profielen — DONE
- [x] Alle bench profiles geoptimaliseerd en getest (zie testlijst)
- [x] GPU strategy docs aangemaakt (gpu-strategy-guide.md, lessons_learned.md)
- [x] gpu-optimizer agent aangemaakt en alle agents bijgewerkt
- [x] Test resultaten gedocumenteerd in docs/bench-test-results.md
- [x] Q6K (non-UD) verwijderd, UD varianten volstaan
- [x] Full benchmark run gestart (~all, loopt nu)

### 5. Productie profiles reviewen — overgeheveld naar todo_16_feb.md

## Profile test status

### Bench profiles

| Profile | Strategy | Split | Status |
|---------|----------|-------|--------|
| `bench-glm-flash-q4` | A (4090 only) | 47/47 GPU | OK — ~140 t/s |
| `bench-glm-flash-q8` | C (beide GPUs) | 35+12=47/47 | OK — ~105 t/s (37+10 getest: trager, 53 splits) |
| `bench-gpt-oss-120b` | D (GPU+CPU) | 13+5=18/36 | OK — ~22 t/s (13+6 OOM op CUDA1) |
| `bench-qwen3-coder-ud-q5` | D (GPU+CPU) | 19+9=28/48 | OK — ~30 t/s (was 18+8 ~29 t/s) |
| `bench-qwen3-coder-ud-q6` | D (GPU+CPU) | 16+8=24/48 | OK — ~24 t/s (17+8 OOM, CUDA1 96%) |
| `bench-qwen3-coder-q6k` | — | — | VERWIJDERD (UD varianten volstaan) |

### Productie profiles

| Profile | Strategy | Split | Status |
|---------|----------|-------|--------|
| `glm-flash-q4` | A (4090 only) | all GPU | Werkt, niet gereviewd |
| `glm-flash-q8` | ? | ? | Werkt, niet gereviewd |
| `gpt-oss-120b` | D (GPU+CPU) | 12+4=16/36 | Werkt, niet gereviewd |
| `qwen3-coder` | D (GPU+CPU) | 13+6=19/48 | Werkt, niet gereviewd |
| `qwen3-coder-q5` | D (GPU+CPU) | 15+7=22/48 | Werkt, niet gereviewd |
| `qwen3-coder-q6k` | — | — | VERWIJDERD (UD varianten volstaan) |
