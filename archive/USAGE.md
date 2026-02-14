# llama.cpp Docker Setup

RTX 4090 (24 GB) + RTX 5070 Ti (16 GB), Ubuntu 24.04, CUDA 13.0

## Wat is llama.cpp?

llama.cpp is een C/C++ programma dat AI-modellen draait op je GPU's. Het is
de engine die Ollama onder de motorkap gebruikt. Deze setup laat je die engine
rechtstreeks aanspreken, zonder Ollama ertussen.

**Wat het doet**: je geeft het een modelbestand (GGUF), het laadt dat op je
GPU's, en het biedt een API + web UI waar je mee kan chatten.

**Waarom**: meer controle over hoe je GPU's gebruikt worden. Nieuwste features
(die nog niet in Ollama zitten). Direct vergelijken met Ollama.

## Hoe werkt het (de basis)

### Alles zit in het GGUF bestand

Een `.gguf` bestand bevat alles wat het model nodig heeft:
- De gewichten (het "brein" van het model)
- De tokenizer (hoe tekst wordt omgezet naar tokens)
- De chat template (het formaat voor berichten, bijv. waar system/user/assistant komt)
- Tool call ondersteuning (als het model dat kan)

Je hoeft hier **niks** voor te configureren. llama.cpp leest het uit de GGUF.

### Twee soorten instellingen

**1. Server-instellingen** — zet je bij het starten, gelden voor de hele sessie:

```bash
MODEL=mijn-model.gguf CTX_SIZE=114688 docker compose up -d
```

Dit bepaalt: welk model, hoeveel context, hoe de GPU's verdeeld worden.

**2. Chat-instellingen** — stuur je mee per request (of stel je in via de UI):
- System prompt ("Je bent een behulpzame assistent")
- Temperature (hoe creatief/random het antwoord is)
- Max tokens (hoe lang het antwoord mag zijn)
- Tool calls

Je stuurt deze mee in elk API request, of je stelt ze in via de web UI of
OpenWebUI. Voorbeeld:

```bash
curl http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "local",
        "messages": [
            {"role": "system", "content": "Je bent een behulpzame assistent."},
            {"role": "user", "content": "Wat is gravitatielenzing?"}
        ],
        "temperature": 0.7,
        "max_tokens": 512
    }'
```

### Model switchen = server herstarten

Dit is het grootste nadeel ten opzichte van Ollama. llama.cpp laadt **één model
per keer**. Er is geen hot-swap. Wil je een ander model, dan moet je stoppen en
opnieuw starten:

```bash
docker compose down
MODEL=ander-model.gguf docker compose up -d
```

Bij Ollama stuur je gewoon een request met een ander model en Ollama regelt
het laden/ontladen automatisch. Dat kan hier **niet**.

> **Toekomstig**: er is een experimentele `--model-store` optie in ontwikkeling
> waarmee je meerdere modellen kan registreren en via de API wisselen. Dit is
> nog niet getest in onze setup.

### Hoe je het gebruikt in de praktijk

Je hebt drie opties:

1. **Ingebouwde web UI** — open `http://localhost:8080` in je browser. Simpele
   chat interface waar je system prompt, temperature etc. kan instellen.

2. **OpenWebUI** — voeg een connectie toe (type: OpenAI-compatible,
   URL: `http://localhost:8080/v1`, API key: leeg). Dan werkt het precies
   zoals je gewend bent met Ollama via OpenWebUI.

3. **API** — stuur requests via curl, Python, of elke OpenAI-compatible client.

### Quantisatie: GGUF quants (Q4, Q5, Q6, Q8)

GGUF bestanden komen in verschillende quantisaties. Lagere quantisatie =
kleiner bestand + minder VRAM, maar iets minder kwaliteit.

| Quant | Kwaliteit | Grootte (32B model) | Wanneer |
|-------|-----------|-------------------|---------|
| Q8_0 | Beste | ~32 GB | Past nog net op jouw 40 GB, weinig ruimte voor context |
| Q6_K | Zeer goed | ~25 GB | Goede balans, ruimte voor context |
| Q5_K_M | Goed | ~21 GB | Als Q6 net niet past |
| Q4_K_M | OK | ~18 GB | Grotere modellen of veel context nodig |

FP4 en FP8 zijn hardware-specifieke formaten voor andere frameworks — niet
relevant hier. Bij GGUF kies je altijd een Q-variant.

### API

llama.cpp biedt een **OpenAI-compatible API**:

| Endpoint | Wat |
|----------|-----|
| `POST /v1/chat/completions` | Chat |
| `POST /v1/completions` | Text completion |
| `GET /v1/models` | Welk model geladen is |
| `GET /health` | Server status |

Apps die de OpenAI API spreken (OpenWebUI, Continue, etc.) werken hier mee.
Apps die specifiek de Ollama API verwachten (`/api/chat`, `/api/tags`) werken
**niet** met llama.cpp.

## Als je Ollama kent: de verschillen

Dit is hoe Ollama nu draait:

```bash
docker run -d --network ollama-network --gpus device=all \
  -v ollama:/root/.ollama -p 11434:11434 --name ollama \
  -e OLLAMA_KV_CACHE_TYPE=q8_0 -e OLLAMA_NUM_PARALLEL=1 \
  ollama/ollama
```

En dit is het equivalent in llama.cpp:

```bash
MODEL=mijn-model.gguf docker compose up -d
```

Per instelling:

| Ollama | llama.cpp | Toelichting |
|--------|-----------|-------------|
| `--gpus device=all` | Staat in docker-compose.yml | Beide gebruiken alle GPU's |
| `-v ollama:/root/.ollama` | `./models:/models:ro` | Ollama: volume. llama.cpp: je eigen `models/` map |
| `-p 11434:11434` | `-p 8080:8080` | Ander poortnummer |
| `OLLAMA_KV_CACHE_TYPE=q8_0` | `KV_CACHE_TYPE_K=q8_0` + `KV_CACHE_TYPE_V=q8_0` | Bij llama.cpp apart voor keys en values |
| `OLLAMA_NUM_PARALLEL=1` | _(default)_ | llama.cpp is standaard single-user |
| `ollama pull model:tag` | Download zelf een GGUF naar `models/` | |
| Model switchen per request | Server herstarten | Grootste verschil |

### Ollama Modelfile → llama.cpp

Bij Ollama bundel je instellingen in een Modelfile:

```
FROM qwen3:32b
PARAMETER temperature 0.7
PARAMETER num_ctx 131072
SYSTEM "Je bent een behulpzame assistent."
```

Bij llama.cpp is dit verdeeld:

| Ollama Modelfile | llama.cpp | Waar/wanneer |
|-----------------|-----------|-------------|
| `FROM qwen3:32b` | `MODEL=model.gguf` | Bij server starten |
| `PARAMETER num_ctx 131072` | `CTX_SIZE=131072` | Bij server starten |
| `PARAMETER temperature 0.7` | `"temperature": 0.7` | Per request (API/UI) |
| `SYSTEM "..."` | `{"role": "system", ...}` | Per request (API/UI) |
| `TEMPLATE` / `PARSER` / `RENDERER` | _(niet nodig)_ | Zit al in de GGUF — Ollama's Modelfile kan dit overschrijven, maar de GGUF heeft het al |

**Waarom heeft Ollama een Modelfile als het al in de GGUF zit?**
De Modelfile is een override-laag. De GGUF bevat al een template, maar via de
Modelfile kan je die overschrijven (ander system prompt, andere defaults). Bij
de meeste modellen is dat niet nodig.

---

## 1. Build

```bash
cd ~/vibe_claude_kilo_cli_exp/llama_cpp
docker compose build
```

Eerste keer duurt lang (compileert voor beide GPU's). Daarna cached Docker.

## 2. Model downloaden

Download een `.gguf` bestand naar `models/`. Maakt niet uit hoe — browser,
wget, huggingface-cli, slepen vanuit je file manager.

```bash
# Via Hugging Face CLI
pip install -U huggingface-hub
huggingface-cli download Qwen/Qwen3-32B-GGUF qwen3-32b-q4_k_m.gguf --local-dir models

# Of gewoon wget
wget -P models/ "https://huggingface.co/Qwen/Qwen3-32B-GGUF/resolve/main/qwen3-32b-q4_k_m.gguf"
```

Tip: zoek op Hugging Face naar je model + "GGUF". Kies een quantisatie — zie de
tabel hierboven voor advies.

## 3. Starten

```bash
MODEL=qwen3-32b-q4_k_m.gguf docker compose up
```

Of op de achtergrond:

```bash
MODEL=qwen3-32b-q4_k_m.gguf docker compose up -d
docker compose logs -f    # logs volgen
```

Server draait op `http://localhost:8080` (web UI + API).

## 4. Testen

Open `http://localhost:8080` in je browser voor de ingebouwde chat UI.

Of via de API:

```bash
curl http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "local",
        "messages": [{"role": "user", "content": "Hallo!"}],
        "max_tokens": 256
    }'
```

In de JSON response zie je:
- `usage.prompt_tokens` — tokens in je prompt
- `usage.completion_tokens` — tokens in het antwoord
- `timings.prompt_per_second` — prompt processing snelheid
- `timings.predicted_per_second` — generatie snelheid (tokens/sec)

## 5. Stoppen

```bash
docker compose down
```

## 6. Ander model laden

```bash
docker compose down
MODEL=ander-model.gguf docker compose up -d
```

## 7. VRAM checken

```bash
nvidia-smi
# Of alleen geheugen per GPU:
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv
```

## 8. Configuratie

Alle settings via environment variabelen. Zet ze op de command line of in
een `.env` file.

| Variable | Default | Wat doet het |
|----------|---------|-------------|
| `MODEL` | `model.gguf` | GGUF bestandsnaam in `models/`. Enige die je altijd moet meegeven. |
| `CTX_SIZE` | `131072` | Context window (tokens). Vergelijkbaar met `num_ctx` in Ollama Modelfile. |
| `N_GPU_LAYERS` | `99` | Hoeveel layers naar GPU. 99 = alles. Lager = deels op CPU (langzamer). |
| `SPLIT_MODE` | `layer` | Hoe werk verdeeld wordt over GPU's. Zie uitleg hieronder. |
| `TENSOR_SPLIT` | _(leeg)_ | Handmatige verhouding per GPU, bijv. `60,40`. Leeg = `--fit` bepaalt het automatisch. |
| `MAIN_GPU` | `0` | Welke GPU primair is. Alleen relevant bij `SPLIT_MODE=row` (KV cache gaat naar main GPU). Bij `layer` mode worden altijd **alle GPU's** gebruikt, ongeacht deze instelling. |
| `FLASH_ATTN` | `1` | Flash attention staat standaard **aan**. Sneller en minder VRAM. Zet op `0` om uit te schakelen. |
| `KV_CACHE_TYPE_K` | `q8_0` | Quantisatie van KV cache keys. `q8_0` = zelfde als `OLLAMA_KV_CACHE_TYPE=q8_0`. Alternatief: `f16` (meer VRAM, iets preciezer). |
| `KV_CACHE_TYPE_V` | `q8_0` | Quantisatie van KV cache values. Bij Ollama is dit één instelling, hier apart voor K en V. |
| `FIT` | `on` | Auto-fit: llama.cpp past automatisch aan hoeveel layers en context op je GPU's passen. Als het niet past, verlaagt het de context en meldt dat in de logs. |
| `FIT_TARGET` | _(leeg)_ | Hoeveel VRAM per GPU vrij laten (in MiB). Bijv. `512,4096` = 512 MiB vrij op 4090, 4 GB vrij op 5070 Ti (voor desktop). |
| `EXTRA_ARGS` | _(leeg)_ | Overige llama-server flags die niet hierboven staan. |

Je hoeft **geen van deze aan te passen** om te beginnen — de defaults werken.
Het enige wat je altijd meegeeft is `MODEL=`. De rest pas je aan als je wilt
experimenteren.

### Split modes

Bepaalt hoe werk over je GPU's verdeeld wordt:

- **layer** (default) — Layers worden sequentieel verdeeld over alle GPU's.
  Stabiel en voorspelbaar. Zelfde methode als Ollama. Beide GPU's worden
  gebruikt, maar ze werken om de beurt (niet tegelijk).
- **row** — Weight matrices worden gesplitst, beide GPU's rekenen tegelijk
  aan dezelfde layer. Kan sneller zijn maar voegt communicatie-overhead toe.
  `MAIN_GPU` bepaalt hier welke GPU de KV cache krijgt.
- **none** — Slechts één GPU. Alle layers gaan naar `MAIN_GPU`.
- **tensor** — Nog niet beschikbaar in mainline llama.cpp (PR #19378 open).

### Referentie

Alle llama-server flags en opties:
https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md

### Voorbeelden

```bash
# Desktop headroom op 5070 Ti (4GB vrij laten voor desktop)
MODEL=qwen3-32b-q4_k_m.gguf FIT_TARGET=512,4096 docker compose up

# Handmatige split (auto-fit uit)
MODEL=qwen3-32b-q4_k_m.gguf FIT=off TENSOR_SPLIT=60,40 docker compose up

# Row split mode
MODEL=qwen3-32b-q4_k_m.gguf SPLIT_MODE=row docker compose up

# Kleiner context window
MODEL=qwen3-32b-q4_k_m.gguf CTX_SIZE=32768 docker compose up
```

## 9. Vergelijken met Ollama

Test elke backend apart — niet tegelijk, ze delen dezelfde GPU's.

### Stap 1: Test met llama.cpp

```bash
MODEL=qwen3-32b-q4_k_m.gguf CTX_SIZE=32768 docker compose up -d

# Wacht tot model geladen is
docker compose logs -f
# (wacht tot je "model loaded" ziet, dan Ctrl+C)

# Check VRAM
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv

# Stuur test prompt
curl http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "local",
        "messages": [{"role": "user", "content": "Explain gravitational lensing in 2 paragraphs."}],
        "max_tokens": 256,
        "temperature": 0
    }'

# Noteer: timings.prompt_per_second, timings.predicted_per_second, VRAM

# Stop
docker compose down
```

### Stap 2: Test met Ollama (zelfde model, zelfde settings)

```bash
# Start Ollama
docker run -d --network ollama-network --gpus device=all \
  -v ollama:/root/.ollama -p 11434:11434 --name ollama \
  -e OLLAMA_KV_CACHE_TYPE=q8_0 -e OLLAMA_NUM_PARALLEL=1 \
  ollama/ollama

# Pull hetzelfde model als je dat nog niet hebt
docker exec ollama ollama pull qwen3:32b

# Stuur dezelfde prompt
curl http://localhost:11434/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "qwen3:32b",
        "messages": [{"role": "user", "content": "Explain gravitational lensing in 2 paragraphs."}],
        "max_tokens": 256,
        "temperature": 0
    }'

# Check VRAM
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv
```

### Zorg dat deze settings gelijk zijn

| Setting | llama.cpp | Ollama |
|---------|-----------|--------|
| Model | Zelfde (bijv. Qwen3-32B Q4_K_M) | Zelfde |
| Context | `CTX_SIZE=32768` | `OLLAMA_NUM_CTX=32768` of via Modelfile |
| KV cache | `q8_0` (default) | `OLLAMA_KV_CACHE_TYPE=q8_0` |
| Prompt | Exact dezelfde tekst | Exact dezelfde tekst |
| max_tokens | 256 | 256 |
| temperature | 0 | 0 |

## 10. Updaten

llama.cpp wordt niet automatisch geupdate. De Docker build pakt wat er lokaal
staat in de `llama.cpp/` folder. Wil je een nieuwere versie:

```bash
cd ~/vibe_claude_kilo_cli_exp/llama_cpp/llama.cpp
git pull origin master
cd ..
docker compose build --no-cache
```
