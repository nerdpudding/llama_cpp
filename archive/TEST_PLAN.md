# Vergelijkingstest: Ollama vs llama.cpp

## Modellen

| Model | Quant | Grootte | Context (Ollama Modelfile) |
|-------|-------|---------|---------------------------|
| GLM-4.7-Flash | Q8_0 | ~31 GB | 114688 (112k) |
| GLM-4.7-Flash | Q4_K_M | ~19 GB | 202752 (198k) |

## Instellingen mapping

### Test 1: GLM-4.7-Flash Q8_0

| Instelling | Ollama | llama.cpp |
|-----------|--------|-----------|
| Model | `glm-4.7-flash:q8_0` | `MODEL=GLM-4.7-Flash-Q8_0.gguf` |
| Context | `num_ctx 114688` (in Modelfile) | `CTX_SIZE=114688` |
| Temperature | `1` (in Modelfile) | `1` (in API request) |
| KV cache | `OLLAMA_KV_CACHE_TYPE=q8_0` | `KV_CACHE_TYPE_K=q8_0` + `KV_CACHE_TYPE_V=q8_0` |
| Flash attention | automatisch | `FLASH_ATTN=1` |
| GPU split | automatisch | `FIT=on` (auto-fit) |

**Ollama starten:**

```bash
docker run -d --network ollama-network --gpus device=all \
  -v ollama:/root/.ollama -p 11434:11434 --name ollama \
  -e OLLAMA_KV_CACHE_TYPE=q8_0 -e OLLAMA_NUM_PARALLEL=1 \
  ollama/ollama
```

**llama.cpp starten:**

```bash
cd ~/vibe_claude_kilo_cli_exp/llama_cpp
MODEL=GLM-4.7-Flash-Q8_0.gguf CTX_SIZE=114688 docker compose up -d
```

### Test 2: GLM-4.7-Flash Q4_K_M

| Instelling | Ollama | llama.cpp |
|-----------|--------|-----------|
| Model | `glm-4.7-flash:q4_K_M` | `MODEL=GLM-4.7-Flash-Q4_K_M.gguf` |
| Context | `num_ctx 202752` (in Modelfile) | `CTX_SIZE=202752` |
| Temperature | `1` (in Modelfile) | `1` (in API request) |
| KV cache | `OLLAMA_KV_CACHE_TYPE=q8_0` | `KV_CACHE_TYPE_K=q8_0` + `KV_CACHE_TYPE_V=q8_0` |
| Flash attention | automatisch | `FLASH_ATTN=1` |
| GPU split | automatisch | `FIT=on` (auto-fit) |

**llama.cpp starten:**

```bash
cd ~/vibe_claude_kilo_cli_exp/llama_cpp
MODEL=GLM-4.7-Flash-Q4_K_M.gguf CTX_SIZE=202752 docker compose up -d
```

---

## Eerlijkheid van de vergelijking

### Zijn het dezelfde modellen?

Beide zijn GLM-4.7-Flash Q8_0, 29.94B parameters, 47 layers, 64 experts. Zelfde
base model van Zhipu. De quantisatie komt uit verschillende bronnen: de Ollama
versie komt uit de Ollama library (quantisatie-bron onbekend), de llama.cpp
versie is de Unsloth GGUF van Hugging Face. De Ollama tag `openclaw-q8-112k` is
een eigen Modelfile met aangepaste num_ctx — niet een apart model.

Voor een performance benchmark maakt de quantisatie-bron geen verschil: de
modelgrootte en berekeningen zijn gelijk.

### Architectuur: deepseek2 vs glm4moelite

GLM-4.7-Flash gebruikt dezelfde architectuur als DeepSeek-V2 (MoE + MLA).
llama.cpp groepeert op architectuur en noemt het `deepseek2`. Ollama heeft een
eigen handler `glm4moelite`. Beide zijn correct — het is hetzelfde model.

Het verschil zit in de implementatie. llama.cpp's deepseek2 handler comprimeert
het KV cache via MLA (n_head_kv=1), Ollama's glm4moelite handler doet dat
minder efficiënt (head_count_kv=20). Resultaat: llama.cpp KV cache ~3.1 GiB vs
Ollama ~5.9 GiB voor dezelfde context.

### Wat de backends ZELF anders doen

De user-facing settings (context, temperature, KV cache type, flash attention)
zijn gelijk gezet. Onderstaande verschillen bepalen de backends zelf — dit kun
je als gebruiker niet aanpassen:

| Aspect | Ollama | llama.cpp |
|--------|--------|-----------|
| GPU layers | 44/48 (4 op CPU) | 48/48 (alles op GPU) |
| Model op CPU | 2.0 GiB | 321 MiB |
| KV cache op CPU | 379 MiB | 0 |
| KV cache totaal | ~5.9 GiB | ~3.1 GiB |

Dit verklaart het snelheidsverschil. Ollama's fit-algoritme is conservatiever
en de KV cache implementatie gebruikt meer geheugen, waardoor er minder ruimte
is voor model layers op de GPU.

### Conclusie

Dit is een eerlijke vergelijking. De settings zijn gelijk, de verschillen komen
uit hoe elke backend de hardware benut. Dat is precies wat we willen meten.

---

## Model wisselen

**Ollama**: stuur gewoon een request met een ander model, Ollama regelt het.

**llama.cpp**: moet je de server stoppen en opnieuw starten met het andere model:

```bash
docker compose down
MODEL=ander-model.gguf docker compose up -d
```

Er is geen andere manier. Dit is het grootste verschil met Ollama.

---

## Sampling defaults: let op de verschillen

| Parameter | llama.cpp default | Ollama default | Verschil? |
|-----------|------------------|----------------|-----------|
| temperature | 0.8 | 0.8 | Nee |
| top_k | 40 | 40 | Nee |
| top_p | 0.95 | 0.9 | **Ja, klein** |
| min_p | 0.05 | 0.0 | **Ja** |
| repeat_penalty | 1.0 (uit) | 1.1 | **Ja** |
| DRY sampler | Aanwezig (nieuw) | Niet beschikbaar | llama.cpp only |

Bij de benchmark via curl sturen we exact dezelfde parameters mee naar beide
backends zodat het eerlijk is. Via de UI kunnen de defaults net anders zijn.

Voor snelle tests via de UI: pas alleen temperature aan en laat de rest staan.
Het verschil is minimaal.

System message staat standaard **leeg** bij llama.cpp (bij Ollama kun je het
in de Modelfile zetten). Vul het in via de UI of stuur het mee per API request.

---

## Test prompt

Gebruik dezelfde prompt voor alle tests. Temperature=1 in alle requests.
Geen max_tokens limiet — het model stopt zelf (EOS token). Dit is de default
van zowel llama.cpp als Ollama.

```bash
curl -s http://localhost:PORT/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "MODEL_NAAM",
        "messages": [
            {"role": "user", "content": "Schrijf een gedetailleerde uitleg over hoe neurale netwerken werken, inclusief backpropagation, gradient descent, en de rol van activatiefuncties. Geef concrete voorbeelden."}
        ],
        "temperature": 1
    }'
```

Vervang:
- `PORT`: `8080` voor llama.cpp, `11434` voor Ollama
- `MODEL_NAAM`: `local` voor llama.cpp, `glm-4.7-flash:openclaw-q8-112k` of `glm-4.7-flash:openclaw-q4-198k` voor Ollama

## Wat je noteert

Uit de **JSON response**:
- `usage.prompt_tokens` — hoeveel tokens de prompt was
- `usage.completion_tokens` — hoeveel tokens het antwoord was
- Ollama: `eval_count` en `eval_duration` → bereken tokens/sec: `eval_count / (eval_duration / 1e9)`
- llama.cpp: `timings.prompt_per_second` en `timings.predicted_per_second` staan er direct in

Uit **nvidia-smi** (run terwijl model geladen is):
- VRAM per GPU (memory.used)

```bash
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv
```

Uit **server logs** (optioneel, voor meer detail):
- llama.cpp: `docker compose logs` — toont bij startup hoe layers verdeeld zijn
- Ollama: `docker logs ollama` — toont GPU allocatie

---

## Testvolgorde

**Belangrijk**: draai nooit beide tegelijk. Stop de ene voordat je de andere start.

### Ronde 1: GLM-4.7-Flash Q8_0 (~31 GB, 112k context)

#### 1A. Ollama

```bash
# Zorg dat llama.cpp gestopt is
docker compose down 2>/dev/null

# Start Ollama
docker run -d --network ollama-network --gpus device=all \
  -v ollama:/root/.ollama -p 11434:11434 --name ollama \
  -e OLLAMA_KV_CACHE_TYPE=q8_0 -e OLLAMA_NUM_PARALLEL=1 \
  ollama/ollama

# Wacht even tot Ollama klaar is
sleep 5

# Test request
curl -s http://localhost:11434/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "glm-4.7-flash:openclaw-q8-112k",
        "messages": [
            {"role": "user", "content": "Schrijf een gedetailleerde uitleg over hoe neurale netwerken werken, inclusief backpropagation, gradient descent, en de rol van activatiefuncties. Geef concrete voorbeelden."}
        ],
        "temperature": 1
    }'

# VRAM
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv

# Stop Ollama
docker stop ollama && docker rm ollama
```

#### 1B. llama.cpp

```bash
# Start llama.cpp
cd ~/vibe_claude_kilo_cli_exp/llama_cpp
MODEL=GLM-4.7-Flash-Q8_0.gguf CTX_SIZE=114688 docker compose up -d

# Wacht tot model geladen: kijk naar logs
docker compose logs -f
# (wacht tot je "model loaded" ziet, dan Ctrl+C)

# Test request
curl -s http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "local",
        "messages": [
            {"role": "user", "content": "Schrijf een gedetailleerde uitleg over hoe neurale netwerken werken, inclusief backpropagation, gradient descent, en de rol van activatiefuncties. Geef concrete voorbeelden."}
        ],
        "temperature": 1
    }'

# VRAM
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv

# Stop
docker compose down
```

### Ronde 2: GLM-4.7-Flash Q4_K_M (~19 GB, 198k context)

Herhaal bovenstaande stappen met:
- Ollama model: `glm-4.7-flash:openclaw-q4-198k`
- llama.cpp: `MODEL=GLM-4.7-Flash-Q4_K_M.gguf CTX_SIZE=202752`

---

## Resultaten

### Test 1: GLM-4.7-Flash Q8_0 (112k context)

| Meting | Ollama | llama.cpp |
|--------|--------|-----------|
| Prompt tokens | 49 | 49 |
| Completion tokens | 3218 | 3485 (thinking: 5380 chars + content: 6536 chars) |
| Prompt verwerking (t/s) | 249.81 | 245.27 |
| Generatie snelheid (t/s) | **31.67** | **108.83** |
| VRAM GPU 0 (4090) | 23765 / 24564 MiB | 23769 / 24564 MiB |
| VRAM GPU 1 (5070 Ti) | 15403 / 16303 MiB | 14725 / 16303 MiB |
| Layer verdeling | **44/48 GPU** (4 op CPU) | **48/48 GPU** |
| Model verdeling | 4090=18.2 GiB, 5070Ti=9.4 GiB, **CPU=2.0 GiB** | 4090=20054 MiB, 5070Ti=9983 MiB, CPU=321 MiB |
| KV cache verdeling | 4090=3.6 GiB, 5070Ti=1.9 GiB, **CPU=379 MiB** | 4090=2142 MiB, 5070Ti=1004 MiB |
| Compute buffers | 4090=898 MiB, 5070Ti=493 MiB | 4090=1107 MiB, 5070Ti=795 MiB, CPU_Host=904 MiB |
| GPU layers verdeling | 4090: layers 3..31 (29), 5070Ti: layers 32..46 (15) | auto-fit |
| Totale response tijd | ~109 sec (load 8s + prompt 0.05s + gen 101.6s) | ~32.2 sec (prompt 0.2s + generatie 32.0s) |
| Processor | 6%/94% CPU/GPU | 100% GPU |
| finish_reason | stop | stop |

Opmerkingen:
> - **Ollama is 3.4x langzamer** bij 112k context doordat 4 layers op CPU staan
> - Ollama KV cache is ~5.9 GiB vs llama.cpp ~3.1 GiB (verschil in MLA-implementatie)
> - Ollama past niet volledig op GPU bij 112k → CPU offload → bottleneck
> - llama.cpp fit warning "cannot meet free memory targets" maar laadde wel alles op GPU
> - Dit is GEEN eerlijke snelheidsvergelijking — zie Test 1b hieronder

### Test 1b: GLM-4.7-Flash Q8_0 (64k context — eerlijke vergelijking)

Omdat Ollama bij 112k context 4 layers op CPU moest zetten, herhalen we de test
met 64k context zodat beide backends 48/48 layers op GPU hebben. Dit is de
eerlijke snelheidsvergelijking.

**Methode:** llama.cpp gestart met CTX_SIZE=65536. Ollama gestart met
num_ctx=65536 via `options` in het API request (overschrijft de Modelfile).
Beide keren schone start (docker restart, geen modellen geladen, cache_n=0).
Benchmark via curl naar native API (Ollama: /api/chat, llama.cpp: /v1/chat/completions).

| Meting | Ollama | llama.cpp |
|--------|--------|-----------|
| Prompt tokens | 49 | 49 |
| Completion tokens | 3579 | 3460 |
| Prompt verwerking (t/s) | 935.43 | 224.02 |
| Generatie snelheid (t/s) | **100.33** | **109.03** |
| VRAM GPU 0 (4090) | 22701 / 24564 MiB | 21733 / 24564 MiB |
| VRAM GPU 1 (5070 Ti) | 14829 / 16303 MiB | 14626 / 16303 MiB |
| Layer verdeling | **48/48 GPU** (100% GPU) | **48/48 GPU** |
| Model verdeling | 4090=19.0 GiB, 5070Ti=10.4 GiB, CPU=321 MiB | 4090=19410 MiB, 5070Ti=10628 MiB, CPU=321 MiB |
| KV cache verdeling | 4090=2.2 GiB, 5070Ti=1.1 GiB | 4090=1186 MiB, 5070Ti=612 MiB |
| Compute buffers | 4090=523 MiB, 5070Ti=343 MiB | 4090=675 MiB, 5070Ti=583 MiB, CPU_Host=520 MiB |
| GPU layers verdeling | 4090: layers 0..30 (31), 5070Ti: layers 31..47 (17) | auto-fit |
| Totale response tijd | ~44.8 sec (load 8.0s + prompt 0.05s + gen 35.7s) | ~31.9 sec (prompt 0.2s + gen 31.7s) |
| Processor | 100% GPU | 100% GPU |
| finish_reason | stop | stop |

Opmerkingen:
> - **Beide 48/48 layers op GPU** — eerlijke vergelijking
> - llama.cpp ~9% sneller in generatie (109 vs 100 t/s)
> - Ollama prompt verwerking veel sneller (935 vs 224 t/s) — mogelijk door BatchSize verschil
> - Ollama KV cache nog steeds groter (3.3 GiB vs 1.8 GiB) door andere MLA-implementatie
> - llama.cpp VRAM iets lager ondanks n_parallel=4 (vs Ollama parallel=1)
> - Model verdeling bijna gelijk nu beide volledig op GPU passen

### Test 2: GLM-4.7-Flash Q4_K_M (198k context)

Beide backends 48/48 layers op GPU, 100% GPU. Eerlijke vergelijking.

**Methode:** llama.cpp gestart met `MODEL=GLM-4.7-Flash-Q4_K_M.gguf CTX_SIZE=202752`.
Ollama gestart met num_ctx=202752 via `options` in het API request. Beide keren
schone start, cache_n=0. Benchmark via curl.

| Meting | Ollama | llama.cpp |
|--------|--------|-----------|
| Prompt tokens | 49 | 49 |
| Completion tokens | 3311 | 3918 |
| Prompt verwerking (t/s) | 1053.34 | 194.10 |
| Generatie snelheid (t/s) | **121.91** | **132.72** |
| VRAM GPU 0 (4090) | 20677 / 24564 MiB | 17029 / 24564 MiB |
| VRAM GPU 1 (5070 Ti) | 12974 / 16303 MiB | 11946 / 16303 MiB |
| Layer verdeling | **48/48 GPU** (100% GPU) | **48/48 GPU** |
| Model verdeling | 4090=11.5 GiB, 5070Ti=6.1 GiB, CPU=170 MiB | 4090=11013 MiB, 5070Ti=6272 MiB, CPU=170 MiB |
| KV cache verdeling | 4090=7.0 GiB, 5070Ti=3.3 GiB | 4090=3668 MiB, 5070Ti=1893 MiB |
| Compute buffers | 4090=1.2 GiB, 5070Ti=761 MiB | 4090=1881 MiB, 5070Ti=1119 MiB, CPU_Host=1592 MiB |
| Totale response tijd | ~73.8 sec (load 45.6s + prompt 0.05s + gen 27.2s) | ~29.8 sec (prompt 0.3s + gen 29.5s) |
| Processor | 100% GPU | 100% GPU |
| finish_reason | stop | stop |

Opmerkingen:
> - Beide 48/48 layers op GPU — eerlijke vergelijking
> - llama.cpp ~9% sneller in generatie (132.72 vs 121.91 t/s)
> - Ollama prompt verwerking veel sneller (1053 vs 194 t/s)
> - Ollama KV cache nog steeds ~2x groter (10.3 GiB vs 5.6 GiB) — MLA-implementatie verschil
> - Ollama VRAM hoger (33.7 GiB vs 29.0 GiB) door groter KV cache
> - Ollama load_duration 45.6 sec vs llama.cpp ~20 sec
> - llama.cpp heeft n_parallel=4 (auto) vs Ollama parallel=1, maar gebruikt toch minder VRAM

### Samenvatting alle eerlijke tests (beide 100% GPU)

| Test | Ollama | llama.cpp | Verschil |
|------|--------|-----------|----------|
| Q8_0 64k generatie | 100.33 t/s | 109.03 t/s | llama.cpp +9% |
| Q4_K_M 202k generatie | 121.91 t/s | 132.72 t/s | llama.cpp +9% |
| Q8_0 64k prompt | 935 t/s | 224 t/s | Ollama +4.2x |
| Q4_K_M 202k prompt | 1053 t/s | 194 t/s | Ollama +5.4x |
| Q8_0 112k generatie | 31.67 t/s | 108.83 t/s | llama.cpp +3.4x (Ollama CPU offload) |

---

## Analyse en verklaringen

### 1. Generatie snelheid: llama.cpp consistent ~9% sneller

Bij eerlijke tests (beide 100% GPU) is llama.cpp ~9% sneller in generatie.
Dit is een klein maar consistent verschil. Mogelijke oorzaken:

- **Kleinere KV cache = minder geheugenbandbreedte.** Tijdens generatie moet
  elke token het hele KV cache lezen. llama.cpp's cache is ~2x kleiner, wat
  minder geheugenverkeer betekent. Dit is waarschijnlijk de hoofdoorzaak.
- **Nieuwere llama.cpp versie.** Onze build is van recente source code. Ollama
  bundelt een oudere versie van llama.cpp die mogelijk minder geoptimaliseerde
  CUDA kernels heeft.
- **MLA-implementatie.** llama.cpp's deepseek2 handler lijkt MLA (Multi-head
  Latent Attention) efficiënter te implementeren dan Ollama's glm4moelite
  handler (zie KV cache analyse hieronder).

### 2. Prompt verwerking: Ollama 4-5x sneller

Dit is opvallend. Ollama verwerkt prompts veel sneller (935-1053 t/s vs
194-224 t/s). De prompts waren slechts 49 tokens, dus absolute tijden zijn
klein (Ollama ~0.05s, llama.cpp ~0.2-0.3s). Mogelijke oorzaken:

- **Onzeker:** het verschil kan komen door hoe de timing gemeten wordt. Ollama
  rapporteert `prompt_eval_duration` apart, llama.cpp meet `prompt_ms` maar
  kan daar overhead in meerekenen (graph compilatie, warmup).
- **Onzeker:** Ollama zou CUDA graphs agressiever kunnen cachen voor kleine
  prompts.
- Bij langere prompts (duizenden tokens) kan dit verschil kleiner of groter
  worden — dat hebben we niet getest.

### 3. KV cache: llama.cpp ~2x kleiner — waarom?

Dit is het meest concrete verschil en verdient uitleg.

**De feiten:**

| | Ollama | llama.cpp |
|--|--|--|
| KV cache Q8_0 112k | ~5.9 GiB | ~3.1 GiB |
| KV cache Q4_K_M 202k | ~10.3 GiB | ~5.6 GiB |
| n_head_kv | 20 (vol) | 1 (MLA-compressed) |
| V cache | apart opgeslagen | **0 MiB** (afgeleid uit K) |

**Instelling:** bij llama.cpp stel je KV cache quantisatie apart in voor K en V:
`KV_CACHE_TYPE_K=q8_0` en `KV_CACHE_TYPE_V=q8_0`. Bij Ollama is dit één
instelling: `OLLAMA_KV_CACHE_TYPE=q8_0`. Functioneel hetzelfde (beide q8_0),
dus dit verklaart het verschil NIET.

**Wat het WEL verklaart:** GLM-4.7-Flash gebruikt MLA (Multi-head Latent
Attention), dezelfde techniek als DeepSeek-V2. Bij MLA wordt het KV cache
gecomprimeerd naar een latente representatie. De V (values) worden niet apart
opgeslagen maar tijdens de berekening afgeleid uit de gecomprimeerde K.

- **llama.cpp** (deepseek2 handler) implementeert dit correct:
  `n_head_kv=1`, V cache = 0 MiB. Alleen de gecomprimeerde latente K wordt
  opgeslagen.
- **Ollama** (glm4moelite handler) lijkt MLA minder efficiënt te
  implementeren: `head_count_kv=20`, wat suggereert dat K en V apart worden
  opgeslagen zonder volledige MLA-compressie.

**Impact:** bij 202k context scheelt dit ~5 GiB VRAM. Dat is het verschil
tussen wel of niet passen op de GPU's bij grotere modellen of langere context.

### 4. VRAM en GPU fit: llama.cpp is zuiniger

Door de kleinere KV cache gebruikt llama.cpp significant minder VRAM, ondanks
dat het 4 parallel slots alloceert (vs Ollama's 1). Concreet:

| Test | Ollama VRAM | llama.cpp VRAM |
|------|-------------|----------------|
| Q8_0 112k | 39.2 GiB (past NIET, CPU offload) | 38.5 GiB (past net) |
| Q8_0 64k | 37.5 GiB | 36.4 GiB |
| Q4_K_M 202k | 33.7 GiB | 29.0 GiB |

Bij Q8_0 met 112k context kon Ollama slechts 44/48 layers op GPU zetten.
De overige 4 layers + output layer + deel van KV cache gingen naar CPU.
Resultaat: **31.67 t/s** (vs 108.83 t/s op llama.cpp). De CPU vormt een
bottleneck — elke token moet wachten op de langzame CPU-layers.

llama.cpp paste het wél volledig op GPU bij dezelfde 112k context, grotendeels
doordat het KV cache ~3 GiB kleiner is.

### 5. Ollama fit-algoritme is conservatiever

Zelfs bij gelijke KV cache grootte zou Ollama mogelijk conservatiever zijn.
De logs tonen dat Ollama eerst probeert met 48 layers op 1 GPU, dan herverdelen
over 2 GPU's. llama.cpp's `--fit` doet dit anders en agressiever — het duwt
meer naar de GPU en laat minder marge vrij.

Dit is geen instelling die je kunt aanpassen. Het is een implementatieverschil.

### 6. Model laden: Ollama trager bij Q4_K_M

Ollama had 45.6 sec load_duration bij Q4_K_M 202k, vs llama.cpp ~20 sec. Bij
Q8_0 was het verschil kleiner (8 sec Ollama, want model was al
gedownload/gecached).

---

## Conclusies

| Vraag | Antwoord |
|-------|----------|
| Welke is sneller bij Q8? | llama.cpp, +9% bij eerlijke vergelijking (64k). Bij 112k context is llama.cpp 3.4x sneller doordat Ollama naar CPU offload. |
| Welke is sneller bij Q4? | llama.cpp, +9% (beide passen op GPU bij 202k). |
| Verschil in VRAM gebruik? | llama.cpp gebruikt ~2x minder KV cache door betere MLA-implementatie. Scheelt 3-5 GiB bij lange context. |
| Verschil in GPU verdeling? | Bij voldoende ruimte: vergelijkbaar (beide 48/48). Bij krappe VRAM: Ollama valt eerder terug naar CPU. |
| Is llama.cpp de moeite waard? | **Ja**, met name voor lange context. De KV cache besparing betekent dat je meer context kunt gebruiken zonder CPU offload. Het snelheidsverschil van 9% is nice-to-have, de VRAM besparing is het echte voordeel. |
| Prompt verwerking? | Ollama is 4-5x sneller, maar bij korte prompts (49 tokens) maakt dit nauwelijks uit (<0.3 sec verschil). Oorzaak onduidelijk. |
| Nadeel llama.cpp? | Geen hot-swap van modellen. Server moet herstarten bij model wissel. Ollama regelt dit automatisch. |
