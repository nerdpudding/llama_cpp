# Plan: Separation of concerns — server config vs client config

## Context

models.conf bevat server-configuratie: welk model laden, hoeveel GPU layers, context size, extra server flags. Dit wordt via `.env` → `docker-compose.yml` naar `llama-server` gestuurd.

Sommige modellen hebben ook **client-side** configuratie nodig. GPT-OSS 120B heeft bijvoorbeeld een reasoning level dat via de system prompt gestuurd moet worden (`"Reasoning: high"`). Dit is géén server flag — `--system-prompt` is expliciet uitgesloten van de llama-server binary. Het moet door de client meegestuurd worden.

### Huidige clients

| Client | Hoe system prompt werkt |
|--------|------------------------|
| llama.cpp web UI | Gebruiker typt het in het UI veld |
| API consumers (curl, apps) | Stuurt het mee in messages array |
| Agentic frameworks | Eigen config per framework |
| Benchmark (evalplus.codegen) | Ondersteunt GEEN system prompt |
| Benchmark (run-claude-benchmark.py) | Hardcoded system prompt in script |

### Probleem

- evalplus.codegen kan geen system prompt meesturen
- GPT-OSS wordt dus gebenchmarkt zonder reasoning level instructie
- Er is geen plek voor client-side config per model

### Wie genereert .env (server config)?

| Script | Leest models.conf | Genereert .env | Doel |
|--------|-------------------|----------------|------|
| `start.sh` | Ja | Ja | Productie-gebruik, start server + dashboard |
| `benchmark.sh` | Ja | Ja | Benchmark, start server per model |
| `dashboard.py` | Nee | Nee | Ontvangt compose-file + model-name als args |

Beide `.env` generators (`start.sh` en `benchmark.sh`) beperken zich al tot server-velden (MODEL, CTX_SIZE, N_GPU_LAYERS, FIT, EXTRA_ARGS). Client-config in models.conf zou automatisch genegeerd worden door deze generators.

## Aanpak

### 1. models.conf blijft puur server config

Geen wijzigingen nodig — het is al zuiver server-side. Documenteer dit expliciet in de comments bovenaan het bestand.

### 2. Benchmark client config: `benchmarks/evalplus/bench-client.conf`

Nieuw bestand voor client-side benchmark configuratie per model.

```ini
# bench-client.conf — Client-side config for benchmark codegen
#
# These settings are sent BY the client TO the model API during code
# generation. They do NOT affect server startup (that's models.conf).
#
# Only models that need special client config are listed here.
# Models without an entry use default behavior (no system prompt).

[bench-gpt-oss-120b]
SYSTEM_PROMPT=Reasoning: low
```

Alleen modellen die afwijkend client-gedrag nodig hebben staan erin. Qwen3, GLM Flash → niet vermeld → geen system prompt → standaard gedrag.

### 3. Custom codegen wanneer SYSTEM_PROMPT gezet is

Wanneer `bench-client.conf` een `SYSTEM_PROMPT` bevat voor een model, kan evalplus.codegen niet gebruikt worden (geen system prompt support). In dat geval gebruikt `codegen.sh` een custom codegen script dat:
- De OpenAI-compatible API aanroept op localhost:8080
- De system prompt meestuurt
- Hetzelfde JSONL format produceert als evalplus.codegen
- Dezelfde 164 HumanEval prompts gebruikt (uit `humaneval_prompts.json`)

Dit script bestaat al in essentie: `run-claude-benchmark.py` doet hetzelfde maar dan via `claude -p`. We maken een generieke variant die de lokale API aanspreekt.

**Nieuw script:** `benchmarks/evalplus/codegen-custom.py`

```python
# Aanroep vanuit codegen.sh:
# python codegen-custom.py --model-name "GPT-OSS 120B" \
#     --system-prompt "Reasoning: low" \
#     --output-dir results/bench-gpt-oss-120b/
```

### 4. codegen.sh aanpassen

Huidige flow:
```
codegen.sh → evalplus.codegen (altijd)
```

Nieuwe flow:
```
codegen.sh → check bench-client.conf voor SYSTEM_PROMPT
  → als gezet: codegen-custom.py (met system prompt)
  → als niet gezet: evalplus.codegen (standaard)
```

### 5. Documentatie updaten

**models.conf header comments:**
- Expliciet vermelden: dit is server config
- Verwijzen naar bench-client.conf voor client config

**README.md:**
- Sectie over server vs client configuratie
- Uitleggen dat reasoning levels (GPT-OSS) client-side zijn
- Benchmarks gebruiken bench-client.conf voor client config

**benchmarks/evalplus/README.md:**
- bench-client.conf documenteren
- Uitleggen wanneer custom codegen wordt gebruikt

## Bestanden

| Bestand | Actie |
|---------|-------|
| `benchmarks/evalplus/bench-client.conf` | **NIEUW** — client config per bench model |
| `benchmarks/evalplus/codegen-custom.py` | **NIEUW** — codegen met system prompt via lokale API |
| `benchmarks/evalplus/codegen.sh` | Aanpassen: check bench-client.conf, kies codegen methode |
| `benchmarks/evalplus/benchmark.sh` | Aanpassen: parse bench-client.conf, geef SYSTEM_PROMPT door aan codegen.sh |
| `models.conf` | Comments toevoegen: "dit is server config" |
| `README.md` | Sectie over server vs client config |
| `benchmarks/evalplus/README.md` | bench-client.conf documenteren |

---

## Apart: GPU layer optimalisatie voor bench profielen

**Los van bovenstaande refactor.** Aparte stap, vereist testen.

Bench profielen gebruiken 16K context i.p.v. 64K-256K productie context. Daardoor is er meer VRAM beschikbaar. De huidige `-ot` layer splits zijn gekopieerd van productie en laten VRAM onbenut.

**Potentiële winst:** meer layers op GPU → snellere codegen → kortere benchmark runs.

**Aanpak:**
1. Bereken hoeveel VRAM er vrijkomt door de kleinere KV cache (16K vs 64K/256K)
2. Pas de layer splits aan voor bench profielen
3. Test per model: start met bench profiel, check VRAM usage, check geen OOM
4. Als stabiel: update models.conf bench profielen

**Dit doen we NA de separation of concerns refactor en NA een succesvolle benchmark run.**
