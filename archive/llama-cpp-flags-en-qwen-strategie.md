# llama.cpp Deep-Dive: Flags, Trade-offs & Qwen3-Coder-Next Strategie

## Inhoudsopgave

- [Executive Summary](#executive-summary)
- [Quick Start: Qwen3-Coder-Next op jouw hardware](#quick-start)
  - [Aanbevolen quants](#welk-model-downloaden)
  - [Gouden regel: GPU's eerst vullen](#gouden-regel)
  - [Tuning methode](#tuning-methode)
  - [-ot regex opzoektabel](#ot-regex-opzoektabel)
  - [Strategieën & testresultaten](#strategieen)
  - [KV cache precisie: q8_0 is de sweet spot](#kv-cache-precisie)
  - [Flags referentie](#flags-referentie)
- [Deel 1: GPT-OSS Docker setup — flags uitgelegd](#deel-1)
- [Deel 2: Flags die je nog niet gebruikt maar relevant zijn](#deel-2)
- [Deel 3: Qwen3-Coder-Next vs GPT-OSS — architectuurverschillen](#deel-3)
- [Deel 4: Docker setup aanpassingen](#deel-4)
- [Deel 5: Aandachtspunten & bekende issues](#deel-5)
- [Volgende stappen](#volgende-stappen)

---

## Executive Summary {#executive-summary}

### Hardware

RTX 4090 (24 GB) + RTX 5070 Ti (16 GB) + 64 GB DDR4 RAM + AMD 5800X3D.

### Model

Qwen3-Coder-Next 80B MoE (512 experts, 10 actief, ~3B active params/token). 75% DeltaNet (lineaire attention, geen KV cache) + 25% standard attention. Dit maakt 256K context haalbaar — slechts 12/48 layers hebben KV cache.

### Aanbevolen configuratie

**⭐ Primair: UD-Q6_K_XL + 256K context + q8_0 KV cache**

```bash
MODEL=Qwen3-Coder-Next-UD-Q6_K_XL-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU" \
docker compose up
```

**21.4 t/s** | 19/48 layers op GPU | 256K context | Beste kwaliteit van alle geteste configuraties.

**✅ Alternatief: UD-Q5_K_XL** — zelfde command maar ander model, 15+7 layers, **25.8 t/s** (+21% sneller). Gebruik wanneer speed belangrijker is dan maximale accuracy.

### Kernbevindingen

1. **Unsloth Dynamic (UD) quants zijn strikt beter dan standaard quants** voor MoE modellen. UD geeft hogere precisie aan expert router tensors → betere expert selectie → minder self-correction → efficiëntere context benutting.
2. **Q4 quants zijn onbruikbaar voor agentic coding** — 5x meer tokens door eindeloos herschrijven.
3. **KV cache: q8_0 is functioneel lossless, q4_0 veroorzaakt self-correction, f16 is verspild VRAM.**
4. **256K context kost ~4 GPU layers vs 64K** door grotere compute buffers en KV cache, maar speed impact is acceptabel (~9-17% afhankelijk van quant).
5. **Compute buffer schaalt met context** — dit was de grootste verrassing bij het opschalen van 64K naar 256K. Budget ~5.4 GB CUDA0 en ~3.8 GB CUDA1 aan vaste overhead.

---

## Quick Start: Qwen3-Coder-Next op jouw hardware {#quick-start}

### Welk model downloaden? {#welk-model-downloaden}

| Quant | Type | Grootte | BPW | Status | Aanbeveling |
|-------|------|---------|-----|--------|-------------|
| Q4_K_M | Standaard 4-bit | ~44 GB | 4.83 | ❌ Getest, ONBRUIKBAAR | Niet downloaden |
| Q5_K_M | Standaard 5-bit | 52.9 GB | 5.70 | ✅ Getest, werkt | Verwijderen (UD is beter) |
| **UD-Q5_K_XL** | Unsloth Dynamic 5-bit | 56.8 GB | ~5.9 | **✅ Getest, speed-optie** | Behouden |
| Q6_K | Standaard 6-bit | 65.5 GB | 6.57 | ✅ Getest, werkt | Verwijderen (UD is beter) |
| **UD-Q6_K_XL** | Unsloth Dynamic 6-bit | 63.9 GiB | 6.89 | **⭐ Getest, BASELINE** | Behouden |

**Conclusie:** Alleen **UD-Q6_K_XL** (primair) en **UD-Q5_K_XL** (snellere optie) zijn nodig. Alle andere quants kunnen verwijderd worden.

**Unsloth Dynamic (UD):** niet elke tensor is even belangrijk. UD geeft gevoelige tensors (expert router, attention) hogere precisie en minder belangrijke tensors lagere. **XL** = nog meer tensors op hogere precisie. Slimmer dan uniform → betere kwaliteit bij vergelijkbare grootte. Bij MoE modellen met 512 experts is router-precisie cruciaal — UD maakt hier het verschil.

### Gouden regel: ALTIJD beide GPU's eerst volledig vullen {#gouden-regel}

```
Stap 1: Vul GPU0 (4090) → doel: minstens 23 GB van 24.5 GB benut
Stap 2: Vul GPU1 (5070 Ti) → doel: minstens 13 GB van 13.3 GB benut
Stap 3: Pas daarna overflow naar CPU
```

**Waarom:** GPU geheugen = ~1 TB/s. DDR4 RAM = ~50 GB/s. Dat is 20x verschil. Elke GB experts op CPU i.p.v. GPU kost direct snelheid.

### Tuning methode: begin AGRESSIEF, schaal terug bij OOM {#tuning-methode}

Start met zoveel mogelijk layers op GPU. OOM? Schuif één layer terug naar CPU. Herhaal. Zo vind je het snelst de optimale config.

### `-ot` regex opzoektabel {#ot-regex-opzoektabel}

De `-ot` flag gebruikt regex om layers aan GPUs toe te wijzen. Hieronder kun je direct opzoeken welke regex je nodig hebt — geen regex-kennis nodig.

**CUDA0 (4090) — kies het aantal layers:**

| Layers | Welke | Regex voor CUDA0 |
|--------|-------|-----------------|
| 11 | 0-10 | `blk\.([0-9]\|10)\.=CUDA0` |
| 12 | 0-11 | `blk\.([0-9]\|1[0-1])\.=CUDA0` |
| **13** | **0-12** | **`blk\.([0-9]\|1[0-2])\.=CUDA0`** ← UD-Q6_K_XL baseline |
| 14 | 0-13 | `blk\.([0-9]\|1[0-3])\.=CUDA0` |
| **15** | **0-14** | **`blk\.([0-9]\|1[0-4])\.=CUDA0`** ← UD-Q5_K_XL baseline |
| 16 | 0-15 | `blk\.([0-9]\|1[0-5])\.=CUDA0` |
| 17 | 0-16 | `blk\.([0-9]\|1[0-6])\.=CUDA0` |
| 18 | 0-17 | `blk\.([0-9]\|1[0-7])\.=CUDA0` |
| 19 | 0-18 | `blk\.([0-9]\|1[0-8])\.=CUDA0` |
| 20 | 0-19 | `blk\.([0-9]\|1[0-9])\.=CUDA0` |

**CUDA1 (5070 Ti) — kies het aantal layers (start waar CUDA0 stopt):**

| Layers | Als CUDA0=13 (start 13) | Regex voor CUDA1 |
|--------|------------------------|-----------------|
| 5 | 13-17 | `blk\.(1[3-7])\.=CUDA1` |
| **6** | **13-18** | **`blk\.(1[3-8])\.=CUDA1`** ← UD-Q6_K_XL baseline |
| 7 | 13-19 | `blk\.(1[3-9])\.=CUDA1` |

| Layers | Als CUDA0=15 (start 15) | Regex voor CUDA1 |
|--------|------------------------|-----------------|
| 6 | 15-20 | `blk\.(1[5-9]\|20)\.=CUDA1` |
| **7** | **15-21** | **`blk\.(1[5-9]\|2[0-1])\.=CUDA1`** ← UD-Q5_K_XL baseline |
| 8 | 15-22 | `blk\.(1[5-9]\|2[0-2])\.=CUDA1` |

| Layers | Als CUDA0=18 (start 18) | Regex voor CUDA1 |
|--------|------------------------|-----------------|
| 6 | 18-23 | `blk\.(1[8-9]\|2[0-3])\.=CUDA1` |
| 7 | 18-24 | `blk\.(1[8-9]\|2[0-4])\.=CUDA1` |
| 8 | 18-25 | `blk\.(1[8-9]\|2[0-5])\.=CUDA1` |

**Samenvoegen:** plak de twee delen aan elkaar met een komma + `exps=CPU` erachter:
```
-ot <CUDA0 regex>,<CUDA1 regex>,exps=CPU
```

**Voorbeeld (13 op CUDA0, 6 op CUDA1 — UD-Q6_K_XL baseline):**
```
-ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU
```
Layers 0-12 → 4090, layers 13-18 → 5070 Ti, layers 19-47 experts → CPU.

### Strategieën & testresultaten {#strategieen}

**VRAM budget (gemeten bij 256K context):**

| | CUDA0 (4090) | CUDA1 (5070 Ti) |
|---|---|---|
| Totaal beschikbaar | 23,671 MiB | 12,761 MiB |
| Compute buffer (256K) | ~3,216 MiB | ~2,673 MiB |
| KV cache (q8_0, 256K) | 2,176 MiB | 1,088 MiB |
| RS buffer | 50 MiB | 25 MiB |
| **Vaste overhead totaal** | **~5,442 MiB** | **~3,786 MiB** |
| **Beschikbaar voor model weights** | **~18,229 MiB** | **~8,975 MiB** |

**Let op:** Compute buffer schaalt met context size — bij 64K is dit ~2 GB, bij 256K ~3.2 GB per GPU. Dit was de voornaamste reden dat 256K minder GPU layers toestaat dan 64K.

**KV cache schaling (alleen 12/48 layers hebben KV — DeltaNet heeft geen KV):**

| Context | q8_0 KV totaal | q4_0 KV totaal |
|---------|---------------|---------------|
| 64K | 816 MiB | 408 MiB |
| 128K | 1,632 MiB | 816 MiB |
| 256K | 3,264 MiB | 1,632 MiB |

---

### Doel: hoogste accuracy → hoogste context → acceptabele speed

---

**Strategie 1: Q5_K_M + 64K q8_0 — "eerste werkende config" (achterhaald)**

```bash
MODEL=Qwen3-Coder-Next-Q5_K_M-00001-of-00003.gguf \
CTX_SIZE=65536 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-7])\.=CUDA0,blk\.(1[8-9]|2[0-5])\.=CUDA1,exps=CPU" \
docker compose up
```

**Verdeling:** 18 layers CUDA0, 8 layers CUDA1 = 26/48 op GPU.

**✅ GETEST — resultaten:**

| Metric | Waarde |
|--------|--------|
| CUDA0 (4090) VRAM | 23,489 / 24,564 MiB (**95.6%**) |
| CUDA1 (5070 Ti) VRAM | 14,869 / 16,303 MiB (**91.2%**) |
| Token generation speed | **27.4 t/s** (626 tokens in 22.8s) |
| RAM gebruik (idle) | 7.4 GB / 62.7 GB |
| Code kwaliteit | Correct, clean, geen self-correction |

**Status:** Achterhaald. UD-Q5_K_XL en UD-Q6_K_XL zijn beter in alles behalve speed.

---

**Strategie 2: Q5_K_M + 256K q8_0 — "context opschaling test" (achterhaald)**

Zelfde model als strat 1, maar 256K context. Bewees dat 256K haalbaar is.
Compute buffer schaalt mee met context (64K: ~2 GB → 256K: ~3.2 GB per GPU).

```bash
MODEL=Qwen3-Coder-Next-Q5_K_M-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-4])\.=CUDA0,blk\.(1[5-9]|2[0-1])\.=CUDA1,exps=CPU" \
docker compose up
```

**Verdeling:** 15 CUDA0 + 7 CUDA1 = 22/48 op GPU.

**✅ GETEST — resultaten:**

| Metric | Waarde | vs Strat 1 (64K) |
|--------|--------|-------------------|
| CUDA0 VRAM | 23,108 / 24,564 MiB (**94.1%**) | was 95.6% |
| CUDA1 VRAM | 15,520 / 16,303 MiB (**95.2%**) | was 91.2% |
| Token generation speed | **24.9 t/s** | was 27.4 t/s (-9%) |
| Output tokens | **2,628** (self-correction!) | was 626 |
| Context | **262,144 (256K)** | was 64K |
| GPU layers | 22/48 | was 26/48 (-4 layers) |

**Observatie:** Output toonde self-correction gedrag (3x herschreven). Dit is sampling variance bij temp 1.0, verergerd door uniforme quantization op router tensors.

**Mislukte pogingen:** 17+8 OOM (CUDA0), 16+8 OOM (CUDA1).

**Status:** Achterhaald door strat 3 (UD-Q5_K_XL elimineert self-correction).

---

**Strategie 3: UD-Q5_K_XL + 256K q8_0 — "speed-alternatief" ✅ SNELLERE OPTIE**

Unsloth Dynamic verdeling: router en attention op hogere precisie, experts op lagere precisie.
Resultaat: significant betere output kwaliteit dan standaard Q5_K_M bij identieke VRAM footprint.

```bash
MODEL=Qwen3-Coder-Next-UD-Q5_K_XL-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-4])\.=CUDA0,blk\.(1[5-9]|2[0-1])\.=CUDA1,exps=CPU" \
docker compose up
```

**Verdeling:** 15 CUDA0 + 7 CUDA1 = 22/48 op GPU.

**✅ GETEST — resultaten:**

| Metric | Waarde | vs Strat 2 (Q5_K_M 256K) |
|--------|--------|---------------------------|
| CUDA0 model weights | 17,176 MiB | -8 MiB |
| CUDA1 model weights | 8,192 MiB | -250 MiB (UD bespaart op GPU!) |
| Token generation speed | **25.8 t/s** (821 tokens in 31.9s) | +4% |
| Self-correction | **Geen** | vs 3x herschreven |
| Output kwaliteit | Clean, 1x correct | vs twijfelgedrag |

**Waarom UD beter presteert:** UD alloceert hogere precisie aan router tensors (die bepalen welke 10/512 experts per token actief zijn). Betere router precisie → betere expert selectie → minder twijfel → minder self-correction loops.

---

**Strategie 4: Q6_K + 256K q8_0 — "hogere accuracy, uniforme quant" (achterhaald)**

Hogere model precisie (6-bit uniform). Iets langzamer door minder GPU layers, maar output kwaliteit
vergelijkbaar met UD-Q5_K_XL.

```bash
MODEL=Qwen3-Coder-Next-Q6_K-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-1])\.=CUDA0,blk\.(1[2-7])\.=CUDA1,exps=CPU" \
docker compose up
```

**Verdeling:** 12 CUDA0 + 6 CUDA1 = 18/48 op GPU.

**✅ GETEST — resultaten:**

| Metric | Waarde | vs Strat 3 (UD-Q5_K_XL) |
|--------|--------|---------------------------|
| Token generation speed | **21.7 t/s** | was 25.8 t/s (-16%) |
| Output tokens | 691 | vs 821 |
| Self-correction | Geen | Geen |
| Output kwaliteit | Clean, iets elegantere code | Clean |
| GPU layers | 18/48 | was 22/48 (-4 layers) |

**Mislukte poging:** 13+6 OOM op CUDA0 (compute buffer paste niet).

**Status:** Achterhaald door strat 5 (UD-Q6_K_XL = zelfde precision, betere router, meer layers).

---

**Strategie 5: UD-Q6_K_XL + 256K q8_0 — "best beschikbare kwaliteit" ⭐ BASELINE**

63.87 GiB effectief (6.89 BPW). Unsloth Dynamic Q6 met XL bit-allocatie.
Metadata bug (gemeld ~11 feb 2026) is **gefixt** in reupload 13 feb.

```bash
MODEL=Qwen3-Coder-Next-UD-Q6_K_XL-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU" \
docker compose up
```

**Verdeling:** 13 CUDA0 + 6 CUDA1 = 19/48 op GPU.

**✅ GETEST — resultaten:**

| Metric | Waarde | vs Strat 4 (Q6_K) | vs Strat 3 (UD-Q5_K_XL) |
|--------|--------|---------------------|---------------------------|
| CUDA0 model weights | 17,361 MiB | +1,414 MiB | +185 MiB |
| CUDA1 model weights | 8,835 MiB | +327 MiB | +643 MiB |
| CUDA0 VRAM totaal | 23,525 / 24,564 MiB (**95.8%**) | was 89.0% | — |
| CUDA1 VRAM totaal | 15,287 / 16,303 MiB (**93.8%**) | was 95.0% | — |
| Token generation speed | **21.4 t/s** (871 tokens in 40.8s) | -1% | -17% |
| Self-correction | Geen | Geen | Geen |
| Output kwaliteit | Clean, goed gedocumenteerd | Clean | Clean |
| GPU layers | 19/48 | +1 | -3 |
| RAM gebruik | ~5.7 GB | ~6.5 GB | ~7.1 GB |

**Eerste poging (11+5 = 16/48):** Werkte, maar had ~3,300 MiB vrij op CUDA0. 13+6 benut VRAM beter.

---

### Overzicht alle strategieën

| Strat | Quant | Context | KV | GPU layers | Speed | Kwaliteit | Status |
|-------|-------|---------|-----|------------|-------|-----------|--------|
| 1 | Q5_K_M | 64K | q8_0 | 26/48 | 27.4 t/s | Goed | Achterhaald |
| 2 | Q5_K_M | 256K | q8_0 | 22/48 | 24.9 t/s | Self-correction | Achterhaald |
| **3** | **UD-Q5_K_XL** | **256K** | **q8_0** | **22/48** | **25.8 t/s** | **Clean** | **✅ Speed-optie** |
| 4 | Q6_K | 256K | q8_0 | 18/48 | 21.7 t/s | Clean | Achterhaald |
| **5** | **UD-Q6_K_XL** | **256K** | **q8_0** | **19/48** | **21.4 t/s** | **Clean** | **⭐ Baseline** |
| 5b | UD-Q6_K_XL | 256K | q4_0 | 20/48 | ~21 t/s | Self-correction | ❌ Niet bruikbaar |
| — | Q4_K_M | 64K | q8_0 | 30/48 | 31.0 t/s | 5x herschreven | ❌ Niet bruikbaar |

---

### KV cache precisie: q8_0 is de sweet spot {#kv-cache-precisie}

KV cache is **werkgeheugen** (runtime attention scores), niet geleerde kennis. Quantizen ervan is anders dan model weight quantization.

| KV type | Ondersteund | VRAM (256K) | Kwaliteit | Aanbeveling |
|---------|------------|-------------|-----------|-------------|
| **f16** | Ja | 6,528 MiB | Referentie | **Niet doen** — kost ~5 extra layers, winst onmeetbaar |
| **q8_0** | Ja | 3,264 MiB | Functioneel lossless | **⭐ Altijd gebruiken** |
| q5_0 | Ja | ~2,448 MiB | Minimaal verlies | Tussenweg (niet getest) |
| **q4_0** | Ja | 1,632 MiB | Self-correction | **❌ Niet bruikbaar voor agentic coding** |

**Waarom f16 KV verspild VRAM is:** q8_0 houdt 256 discrete niveaus per waarde. KV cache bevat attention scores die van nature al ruis bevatten door softmax-afronding. Het verschil tussen 256 niveaus (q8_0) en 65,536 niveaus (f16) verdwijnt in die ruis. De consensus in de llama.cpp community is dat q8_0 KV functioneel lossless is t.o.v. f16.

**Waarom q4_0 KV niet werkt:** Getest met UD-Q6_K_XL (strat 5b). 14+6 layers (20/48, 1 meer dan strat 5). Output toonde **ernstig self-correction gedrag** — halverwege afgekapt vanwege zinloze herschrijvingen. q4_0 heeft slechts 16 discrete niveaus — te weinig voor betrouwbare attention recall over lange context. Het wint 1 extra GPU layer maar verliest bruikbaarheid.

**q6 KV bestaat niet** — llama.cpp ondersteunt alleen q8_0, q5_0, en q4_0 voor KV cache. q6_K is een weight-only quantization formaat.

---

### Q4_K_M test archief — NIET AANBEVOLEN

Q4_K_M is getest en **niet geschikt voor agentic coding**. De resultaten staan hier als referentie.

**Configuratie:** 20 layers CUDA0, 10 layers CUDA1 = 30/48 op GPU, 64K q8_0 context.

| Metric | Q5_K_M (strat 1) | Q4_K_M |
|--------|-------------------|--------|
| Snelheid | 27.4 t/s | 31.0 t/s (+13%) |
| CUDA0 VRAM | 95.6% | 90.7% |
| CUDA1 VRAM | 91.2% | 96.0% |
| Tokens voor zelfde prompt | 626 | 3096 (**5x meer**) |
| Output kwaliteit | Één correcte functie | 5 herschrijvingen, "Wait, there's an issue..." |
| Agentic coding bruikbaar? | ✅ Ja | ❌ Nee |

**Analyse:** Q4 quantization degradeert de expert router precisie. Met 512 experts en slechts 10 actief per token is de router het meest gevoelige onderdeel — het model selecteert verkeerde experts, twijfelt, en herschrijft eindeloos. Voor agentic coding vult dit het context window 5x sneller met ruis.

---

**⚠️ Bij alle strategieën:**
- **OOM → eerst layers verlagen (1 tegelijk), daarna context (256K → 192K → 128K)**
- **VRAM over → zoek in de opzoektabel, voeg 1-2 layers toe**
- Doel: beide GPUs op 90%+ VRAM (`nvidia-smi`)

### Flags die ALTIJD aan moeten {#flags-referentie}

| Flag | In één zin |
|------|-----------|
| `--jinja` | Zonder dit werkt de chat template en tool calling niet |
| `--flash-attn on` | Gratis geheugenwinst, geen nadeel |
| `-np 1` | Meer slots = meer KV cache geheugen kwijt, voor single-user onnodig |
| `--no-context-shift` | Voorkomt dat code stiekem uit je context verdwijnt |
| `-ngl 99` | Alle layers naar GPU, experts worden door `-ot` selectief teruggestuurd |
| `FIT=off` | Auto-fit snapt expert/attention split niet bij `-ot` |

### Flags om mee te experimenteren

| Flag | Wat het regelt | Begin met | Richting |
|------|---------------|-----------|----------|
| `-b` / `-ub` | Batch size prompt verwerking | 2048 | Omhoog als VRAM over is = snellere prompts |
| `-ot` | Precieze tensor plaatsing per layer | Zie strategieën | Tune via trial & error op VRAM |
| `--cache-type-k/v` | KV cache precisie | q8_0 | Niet verlagen — q4_0 veroorzaakt self-correction |
| `-sm` | Multi-GPU split | layer | Test ook `row` (Qwen advies, maar kan conflicteren met `-ot`) |
| `--temp` | Sampling temperature | 1.0 (Qwen advies) | 0.6-0.8 voor meer deterministische coding |

### Let op: multi-part GGUF

Alle grote quants zijn gesplitst in **3 bestanden**. Wijs MODEL altijd naar het eerste bestand (`-00001-of-0000X.gguf`), llama.cpp laadt de rest automatisch uit dezelfde directory.

---

## Deel 1: GPT-OSS Docker setup — flags uitgelegd {#deel-1}

Je working config:
```bash
MODEL=gpt-oss-120b-F16.gguf \
CTX_SIZE=65536 \
FIT=off \
N_GPU_LAYERS=99 \
EXTRA_ARGS="--jinja -np 1 -b 4096 -ub 4096 \
  -ot blk\.([0-9]|1[01])\.=CUDA0,blk\.(1[2-5])\.=CUDA1,exps=CPU"
```

Plus docker-compose defaults: `--flash-attn on`, `--cache-type-k q8_0`, `--cache-type-v q8_0`, `--split-mode layer`, `--main-gpu 0`

| Flag | Wat het doet | Trade-off |
|------|-------------|-----------|
| `--flash-attn on` | Berekent attention zonder volledige NxN matrix. Halveert attention geheugen. | Geen nadeel. Altijd aan. |
| `--cache-type-k/v q8_0` | KV cache van FP16 naar Q8. Halveert KV cache geheugen. | Functioneel lossless. Niet verder verlagen. |
| `-ngl 99` | Alle 36 layers naar GPU. `-ot` stuurt sommige tensors terug naar CPU. | Zonder `-ot` = OOM. Met `-ot` = alle attention op GPU, experts selectief op CPU. |
| `--split-mode layer` | Layers sequentieel over GPUs: 0-N op GPU0, N+1-M op GPU1. | Simpel, effectief voor asymmetrische GPUs. |
| `--main-gpu 0` | 4090 als primaire GPU. | Meer VRAM, meer compute. |
| `-ot` | Regex-based tensor plaatsing per device. | Meeste controle, maar lastig door Docker shell escaping. |
| `--jinja` | Jinja chat template uit model metadata. | Essentieel voor GPT-OSS en Qwen3-Coder-Next. |
| `-np 1` | Eén parallel slot = één KV cache. | Single-user: 1 is juist. |
| `-b 4096 -ub 4096` | Batch size voor prompt processing. Triggert disaggregated prompt processing. | Snellere prompts, maar meer tijdelijk VRAM (~3.2 GB compute buffer op CUDA1). |
| `--fit off` | Schakelt auto-fit uit. | Noodzakelijk bij `-ot`. |

---

## Deel 2: Flags die je nog niet gebruikt maar relevant zijn {#deel-2}

### MoE-specifieke flags

| Flag | Wat het doet | Wanneer |
|------|-------------|---------|
| `--cpu-moe` | Alle expert weights naar CPU. | Simpelste optie, maar laat VRAM onbenut. Gebruik `-ot` in plaats hiervan. |
| `--n-cpu-moe N` | Experts van N layers naar CPU (telt vanaf hoogste layer). | Makkelijker dan `-ot`, minder controle over GPU-verdeling. |
| `--no-op-offload` | Schakelt disaggregated prompt processing uit. | Soms sneller voor token gen als je al genoeg experts op GPU hebt. |

### Context & Memory

| Flag | Wat het doet | Trade-off |
|------|-------------|-----------|
| `--ctx-size 0` | Max context uit model metadata. | Kan OOM als model meer claimt dan past. |
| `--no-context-shift` | Stop bij vol i.p.v. oudste tokens wegschuiven. | Veiliger voor coding. |
| `--cache-type-k/v q4_0` | Agressieve KV quantization. | ❌ Veroorzaakt self-correction — niet gebruiken voor agentic coding. |
| `--cache-type-k/v q5_0` | Tussenweg. | Niet getest, mogelijk bruikbaar als tussenoplossing. |

### Sampling (Qwen3-Coder-Next)

Officieel: `temperature=1.0, top_p=0.95, top_k=40, min_p=0`. Optioneel: `--presence-penalty 0.0-2.0` tegen herhaling. Voor agentic coding: overweeg `--temp 0.6-0.8` voor meer deterministische output.

### Performance tuning

| Flag | Wat het doet | Trade-off |
|------|-------------|-----------|
| `-t N` | CPU threads (5800X3D = 8C/16T). | Meer = snellere expert processing, steelt van HTTP server. |
| `--prio 2` | Hoge process priority. | Helpt bij CPU-bound expert processing. |
| `-sm row` | Elke layer over beide GPUs. | Qwen adviseert dit, maar kan conflicteren met per-GPU `-ot`. |
| `--no-mmap` | Laad alles in RAM upfront. | Consistenter, riskant met 64 GB RAM + 50+ GB model. |

---

## Deel 3: Qwen3-Coder-Next vs GPT-OSS — architectuurverschillen {#deel-3}

| Aspect | GPT-OSS-120B | Qwen3-Coder-Next |
|--------|--------------|------------------|
| Total params | 116.8B | 80B |
| Active params/token | ~5.1B (4/128 experts) | ~3B (10/512 experts) |
| Layers | 36 | 48 |
| Attention | Standard + SWA (50/50) | 75% DeltaNet (lineair) + 25% standard |
| Experts per layer | 128, 4 actief | 512, 10 actief + 1 shared |
| KV cache | SWA layers = tiny KV | DeltaNet layers = géén KV |
| Base precision | MXFP4 (native FP4) | BF16 (dan GGUF quantized) |

**Wat dit betekent:**
- Minder active params → snellere inference per token
- 75% DeltaNet → drastisch minder KV cache → meer context per GB
- 512 experts/layer → expert weights ~85-90% van model → cruciaal om zoveel mogelijk op GPU te houden
- 48 layers → meer granulariteit in `-ot` layer verdeling

---

## Deel 4: Docker setup aanpassingen {#deel-4}

### Toe te voegen aan docker-compose.yml:

```yaml
- CPU_MOE=${CPU_MOE:-}
- N_CPU_MOE=${N_CPU_MOE:-}
- NO_CONTEXT_SHIFT=${NO_CONTEXT_SHIFT:-1}
```

### Toe te voegen aan Dockerfile CMD:

```bash
if [ "${CPU_MOE}" = "1" ]; then ARGS="${ARGS} --cpu-moe"; fi;
if [ -n "${N_CPU_MOE}" ]; then ARGS="${ARGS} --n-cpu-moe ${N_CPU_MOE}"; fi;
if [ "${NO_CONTEXT_SHIFT}" = "1" ]; then ARGS="${ARGS} --no-context-shift"; fi;
```

---

## Deel 5: Aandachtspunten & bekende issues {#deel-5}

### llama.cpp support status
- `qwen3next` architectuur recent toegevoegd (PR #16095) — performance nog niet volledig geoptimaliseerd
- DeltaNet kernels zijn nieuw — verwacht verbeteringen
- **Herbouw Docker image met nieuwste llama.cpp master** voor je begint
- Unsloth Feb 4 bugfix voor looping/slechte output — download recente GGUFs
- **UD-Q6_K_XL metadata bug (gemeld 11 feb)** — gefixt in reupload 13 feb 2026. Bevestigd werkend.

### Officieel Qwen referentiecommando
```bash
./llama-cli \
  -m Qwen3-Coder-Next-Q5_K_M-00001-of-00003.gguf \
  --jinja -ngl 99 -fa on -sm row \
  --temp 1.0 --top-k 40 --top-p 0.95 --min-p 0 \
  -c 40960 -n 32768 --no-context-shift
```

### YaRN voor context voorbij 256K
```
--rope-scaling yarn --yarn-orig-ctx 262144
```
Gevalideerd tot 131K. Niet nodig voor nu (256K is native context length).

---

## Volgende stappen {#volgende-stappen}

### 1. API-integratie met Claude Code / CLI tooling

De lokale Qwen3-Coder-Next draait als OpenAI-compatible API (llama-server op port 8080). Volgende stap is integratie met development tooling:

- **Claude Code** of andere CLI-assistenten configureren om de lokale API als backend te gebruiken
- **VS Code integratie** testen voor code completion en agentic workflows
- **Use case afbakening:** bepalen wanneer de lokale setup zinvol is vs. de Anthropic Max subscription (Opus 4.6 / Sonnet). De proprietary modellen zijn significant sterker — de lokale setup is interessant voor privacy-gevoelige taken, offline gebruik, onbeperkt tokenvolume, en als experimenteerplatform.

### 2. Formele benchmarks

De huidige tests zijn kwalitatief (één prompt, visuele beoordeling). Voor een objectieve vergelijking:

- **LiveCodeBench** (of vergelijkbare coding-specifieke benchmark) draaien op de drie bruikbare configs: UD-Q5_K_XL, Q6_K, UD-Q6_K_XL
- **Vergelijking met proprietary modellen** (Opus 4.6, GPT-5.3 Codex, etc.) om te weten waar het lokale model staat — niet om te concurreren, maar om te begrijpen welke taken wel en niet geschikt zijn
- **Temperature sweep** (0.6 / 0.8 / 1.0) om het optimale sampling punt te vinden voor agentic coding vs. creatieve taken
- Resultaten documenteren als score-referentie voor toekomstige model upgrades
