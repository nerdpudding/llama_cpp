# Plan: Fair post-processing for all benchmark models

**Status: IMPLEMENTED — awaiting full test run**

## Afgerond

- [x] `postprocess-solutions.py` aangemaakt en getest op bestaande data
- [x] Pipeline herstructurering: `benchmark.sh` → `codegen.sh` → `postprocess-solutions.py` → `evaluate.sh`
- [x] Oude scripts verwijderd (`run-benchmark.sh`, `evaluate-claude.sh`)
- [x] System prompt verbeterd in `run-claude-benchmark.py`
- [x] `bench-glm-flash` hernoemd naar `bench-glm-flash-q8`
- [x] Overwrite/skip/quit prompt (nu delete/skip/quit)
- [x] README.md bijgewerkt

## Nog te doen

- [ ] Volledige clean run met alle modellen (smoke test GLM Q4 loopt nu)
- [ ] Verifiëren dat postprocessor + evaluate + report correct werken in nieuwe pipeline
- [ ] Na succesvolle test: archiveer dit plan naar `archive/`

### Testresultaten postprocessor

| Model | Origineel | Na postprocessing | Schoon? |
|-------|-----------|-------------------|---------|
| GLM Q4 | 164x `<think>` + markdown fences | Alles gestript | Ja |
| GLM Q8 | `<think>` + markdown fences | Alles gestript | Ja |
| GPT-OSS 120B | 164x explanatory text + markdown fences | Alles gestript | Ja |
| Qwen3 UD-Q5 | Al schoon | 0 modified | Ja |
| Qwen3 UD-Q6 | Al schoon | 0 modified | Ja |
| Qwen3 Q6K | Al schoon | 0 modified | Ja |

**Bevinding:** GPT-OSS was NIET schoon (was eerder aangenomen). Alle 164 solutions bevatten explanatory text + code in markdown fences. Postprocessor is dus nodig voor 3 van de 4 model families.

### Nog te doen

- [ ] Pipeline herstructureren (zie hieronder)
- [ ] Testen na herstructurering
- [ ] Volledige clean run met alle modellen

---

## Context

Benchmark scores worden oneerlijk bestraft omdat evalplus de raw model output as-is evalueert. Als modellen explanatory text, markdown fences, of reasoning tags meesturen naast correcte code, faalt de evaluatie.

**Alle modellen die postprocessing nodig hebben:**
- **GLM-4.7 Flash (Q4 + Q8)**: Alle 164 solutions bevatten `<think>` reasoning tags + code in markdown fences
- **GPT-OSS 120B**: Alle 164 solutions bevatten explanatory text + code in markdown fences
- **Claude Opus 4.6**: 13/164 solutions hadden explanatory text voor de code

**Schone modellen (geen postprocessing nodig, maar wordt wel uniform toegepast):**
- **Qwen3-Coder-Next (alle 3 quants)**: Output is pure code

## Herstructurering pipeline

### Huidige situatie (te complex)

Meerdere scripts met overlappende verantwoordelijkheden, postprocessing zit verweven in de flow, handmatig `rm -rf` nodig voor re-runs.

### Nieuwe aanpak: 4 losse stappen, 1 runner

**Principe:** Elke stap is een los script dat 1 ding doet. De runner roept ze in volgorde aan.

#### De 4 scripts

| # | Script | Wat het doet |
|---|--------|-------------|
| 1 | `codegen.sh` | Code genereren via model API. Schrijft raw JSONL. Stopt. |
| 2 | `postprocess.sh` | Postprocess ALLE solutions, ALTIJD, ONGEACHT welk model. Backup + clean. |
| 3 | `evaluate.sh` | Evalplus evaluatie in Docker sandbox. Schrijft eval_results.json. |
| 4 | `report.sh` | Genereer REPORT.md uit alle eval_results.json. |

**Claude uitzondering:** `run-claude-benchmark.py` blijft apart (gebruikt `claude -p` i.p.v. llama.cpp API). Maar postprocess + evaluate + report zijn identiek.

#### De runner: `benchmark.sh`

Roept de 4 stappen sequentieel aan per model. Eén script, duidelijke flags:

```bash
./benchmark.sh --all                    # Alle modellen (6 local + Claude)
./benchmark.sh --local                  # Alleen local modellen (geen Claude subscription nodig)
./benchmark.sh bench-glm-flash-q4       # Specifiek model
./benchmark.sh bench-glm-flash-q4 bench-gpt-oss-120b   # Meerdere modellen
./benchmark.sh --report                 # Alleen rapport genereren
```

#### Bestaande data afhandeling

Als er al resultaten staan voor een model, vraagt het script:

```
Results already exist for bench-glm-flash-q4.
  [o] Overwrite (delete existing, run fresh)
  [s] Skip this model
  [q] Quit
Choice [o/s/q]:
```

Geen handmatig `rm -rf` meer nodig. Veilig en duidelijk.

### Postprocessing

Eén `postprocess.sh` script dat:
- **Altijd** draait, voor **elk** model, **ongeacht** of het nodig is
- `extract_code()` logica in `postprocess-solutions.py` (al gemaakt en getest)
- Schone output passeert ongewijzigd door (Qwen3)
- Vuile output wordt opgeschoond (GLM, GPT-OSS, Claude)
- Backup van origineel als `.raw.jsonl`
- Uniform en eerlijk — geen per-model configuratie nodig

### Wat postprocessing doet

1. Strip `<think>...</think>` blocks (GLM reasoning tags)
2. Extract uit markdown code fences (` ```python ... ``` `) — pakt het grootste blok
3. Strip explanatory text voor eerste `import`/`from`/`def`/`class`/`@` regel
4. Als er niets te strippen valt, passeer ongewijzigd

## Implementatie

### Stap 1: Hernoem en herstructureer scripts

| Huidig | Nieuw | Verandering |
|--------|-------|-------------|
| `run-benchmark.sh` | `benchmark.sh` | Runner met --all/--local/model flags + bestaande data check |
| (nieuw) | `codegen.sh` | Code generatie (extracted uit run-benchmark.sh) |
| `postprocess-solutions.py` | `postprocess-solutions.py` | Blijft (al gemaakt en getest) |
| (deel van run-benchmark.sh) | `evaluate.sh` | Evaluatie (extracted uit run-benchmark.sh), vervangt ook evaluate-claude.sh |
| `generate-report.py` | `generate-report.py` | Blijft |
| (nieuw, wrapper) | `report.sh` | Dunne wrapper om generate-report.py |
| `run-claude-benchmark.py` | `run-claude-benchmark.py` | Blijft (claude -p codegen) |
| `evaluate-claude.sh` | **verwijderd** — evaluate.sh doet dit nu | |

### Stap 2: `benchmark.sh` runner logica

```
benchmark.sh --all:
  for each bench-* model in models.conf:
    1. Check bestaande data → vraag overwrite/skip/quit
    2. codegen.sh $model        (start server, genereer, stop server)
    3. postprocess.sh $model    (altijd, uniform)
    4. evaluate.sh $model       (Docker sandbox)
  for each Claude model (bench-opus4.6, bench-opus4.6-thinking):
    1. Check bestaande data → vraag overwrite/skip/quit
    2. run-claude-benchmark.py  (claude -p codegen)
    3. postprocess.sh $model    (altijd, uniform)
    4. evaluate.sh $model       (evalplus evaluate)
  report.sh                     (genereer REPORT.md)

benchmark.sh --local:
  Zelfde als --all maar skip Claude modellen

benchmark.sh bench-glm-flash-q4:
  Alleen dat model, zelfde stappen
```

### Stap 3: Update README

- Nieuwe script namen en flags documenteren
- `--all`, `--local`, model-specifieke voorbeelden
- Uitleggen dat postprocessing automatisch en uniform is
- Bestaande data check beschrijven

## Bestanden

| Bestand | Actie |
|---------|-------|
| `benchmarks/evalplus/benchmark.sh` | **NIEUW** — hoofdrunner |
| `benchmarks/evalplus/codegen.sh` | **NIEUW** — code generatie (uit run-benchmark.sh) |
| `benchmarks/evalplus/evaluate.sh` | **NIEUW** — evaluatie (uit run-benchmark.sh + evaluate-claude.sh) |
| `benchmarks/evalplus/report.sh` | **NIEUW** — rapport wrapper |
| `benchmarks/evalplus/postprocess-solutions.py` | Bestaat al, getest |
| `benchmarks/evalplus/run-claude-benchmark.py` | Minimale aanpassing (system prompt al gedaan) |
| `benchmarks/evalplus/generate-report.py` | Geen wijziging |
| `benchmarks/evalplus/run-benchmark.sh` | **VERWIJDERD** — vervangen door benchmark.sh |
| `benchmarks/evalplus/evaluate-claude.sh` | **VERWIJDERD** — vervangen door evaluate.sh |
| `benchmarks/evalplus/README.md` | Bijwerken met nieuwe structuur |

## Verificatie

1. `./benchmark.sh --local` draait alle 6 local modellen zonder fouten
2. Postprocessor rapporteert correct aantal modifications per model
3. Bestaande data check werkt (overwrite/skip/quit)
4. `./benchmark.sh bench-glm-flash-q4` draait alleen dat model
5. `./benchmark.sh --all` inclusief Claude werkt
6. REPORT.md toont alle modellen correct gesorteerd
7. Qwen3 modellen: 0 modifications (schoon)
8. GLM/GPT-OSS/Claude: modifications correct gestript
