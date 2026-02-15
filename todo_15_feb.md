# TODO 15 februari

## Volgorde

### 1. Implementeer PLAN_separation_of_concerns
- [x] `bench-client.conf` aanmaken (GPT-OSS system prompt)
- [x] `codegen-custom.py` schrijven (lokale API met system prompt)
- [x] `codegen.sh` aanpassen (kies evalplus vs custom codegen)
- [x] `benchmark.sh` aanpassen (parse bench-client.conf)
- [x] models.conf comments toevoegen ("dit is server config")
- [x] README.md updaten (server vs client config uitleg)
- [x] benchmarks/evalplus/README.md updaten (bench-client.conf docs)

### 2. Test alles samen (fair postprocessing + separation of concerns)
- [ ] Verwijder alle bestaande benchmark resultaten
- [ ] Draai `./benchmark.sh --local` voor alle 6 local modellen
- [ ] Controleer: postprocessor stript GLM/GPT-OSS correct, Qwen3 ongewijzigd
- [ ] Controleer: GPT-OSS gebruikt system prompt uit bench-client.conf
- [ ] Controleer: overwrite/skip/quit prompt werkt
- [ ] Controleer: REPORT.md genereert correct met alle modellen
- [ ] Draai Claude benchmark apart (als gewenst)

### 3. Na succesvolle test
- [ ] Archiveer `PLAN_fair_postprocessing_benchmark.md` → `archive/`
- [ ] Archiveer `PLAN_separation_of_concerns.md` → `archive/`
- [ ] Controleer alle README's en docs op accuraatheid
- [ ] Commit

### 4. Later: GPU layer optimalisatie bench profielen
- [ ] Bereken VRAM vrijgekomen door 16K vs productie context
- [ ] Pas layer splits aan voor bench profielen
- [ ] Test per model op OOM
- [ ] Update models.conf bench profielen als stabiel
