# Overleg: Claude Code Local Setup — 24 februari 2026

## Waar staan de dingen nu?

### Wat er al gebouwd is

Er is een lokale llama-server (llama.cpp in Docker) met 6 MoE-modellen, automatische
GPU-plaatsing via `--fit`, een monitoring dashboard met model-switching, en een
management API op port 8081 waarmee programmatisch van model gewisseld kan worden.

Sinds build `ed4837891` ondersteunt llama.cpp de **Anthropic Messages API** native
(`POST /v1/messages`). Dat betekent dat Claude Code er direct mee kan praten zonder
proxy of vertaallaag.

### Wat er al getest is (Phase 1-3)

- Anthropic Messages API werkt (curl-test met GLM Flash Q4)
- Token counting endpoint werkt (`/v1/messages/count_tokens`)
- Claude Code verbonden met lokale server: **chat en tool use werken** (Glob, Read)
- Auth bypass: `ANTHROPIC_AUTH_TOKEN=llamacpp` + `ANTHROPIC_API_KEY=""`
- Launch script: `test/run.sh` met environment variables

### Wat het probleem is

Het huidige launch script (`test/run.sh`) gebruikt `HOME=/path/to/test` om de lokale
Claude Code sessie te isoleren van de normale installatie. Dat voorkomt credential-
conflicten, maar er is geen beperking op het bestandssysteem. Bestanden lezen en
schrijven *binnen* de project-workspace (code, `.claude/agents/`, `AI_INSTRUCTIONS.md`)
is gewenst — dat is waar het model mee moet werken. Bash-commando's uitvoeren moet
ook kunnen, maar gecontroleerd: Claude Code vraagt standaard toestemming voor elk
commando, en met een minder capabel lokaal model is het verstandig om daar extra
kritisch op te zijn en niet zomaar alles te accepteren.

Het eigenlijke risico zit in het bereik *buiten* de workspace. Een lokaal model maakt
vaker fouten dan Opus en kan onbedoeld buiten het project navigeren — andere projecten
openen, bestanden in de home-folder wijzigen, of systeemcommando's uitvoeren die niet
bedoeld waren. Daar moet een harde grens op zitten, niet alleen afhankelijk van de
discipline van de gebruiker bij het goedkeuren van prompts.

### Huidige installatie (normale Claude Code)

- Claude Code v2.1.52 via apt (Debian package), geinstalleerd op Ubuntu Desktop
- Ingelogd via **OAuth** (Max subscription)
- Globale config in `~/.claude/` (settings, credentials, CLAUDE.md)
- Per-project config in `.claude/` folders (agents, skills)
- Geen sandboxing actief (standaard permissie-prompts)

---

## Wat is het doel?

### Twee manieren om Claude Code te gebruiken, naast elkaar

1. **Normaal (OAuth/Max subscription)** — voor serieus werk, toegang tot Opus 4.6
   en andere Anthropic-modellen. Dit is en blijft de primaire manier.
2. **Lokaal (llama-server)** — experimenteel, voor het testen van lokale modellen
   als Claude Code backend. Sporadisch gebruik.

### Waarom?

- De Max subscription is en blijft het sterkste: betere modellen, prompt caching,
  adaptive reasoning — dingen die lokaal niet werken.
- Lokaal draaien is interessant om te experimenteren: hoe ver komen lokale modellen
  als coding agent? Wat kunnen ze wel/niet? Zijn er taken waarvoor ze goed genoeg
  zijn?
- En het is gewoon leuk om te zien hoe ver je kunt komen met eigen hardware.

### Vereisten

- De normale OAuth-installatie mag **nooit** beinvloed worden door de lokale setup.
- De lokale versie moet:
  - In een project-workspace kunnen werken (files lezen/schrijven binnen het project)
  - VS Code IDE-integratie behouden (diagnostics, etc.)
  - Bash-commando's kunnen uitvoeren (maar altijd eerst vragen, nooit automatisch)
  - Geen `sudo` of andere privilege-escalatie kunnen doen
  - Niet zomaar buiten de workspace kunnen schrijven
  - Localhost bereiken (voor de llama-server API op port 8080)
  - Liefst ook internet (web search, curl) maar dat is niet strikt noodzakelijk

---

## Vraag 1: Kan OAuth en lokaal in dezelfde Claude Code instance?

### Kort antwoord: Nee, niet echt.

Claude Code gebruikt **een authenticatiemethode per sessie**:
- **OAuth** (subscription login) — de huidige werkwijze
- **API key** (`ANTHROPIC_API_KEY`) — voor pay-per-use of third-party backends
- **Auth token** (`ANTHROPIC_AUTH_TOKEN`) — voor lokale backends (Ollama-stijl)

Deze zijn wederzijds exclusief. Het is niet mogelijk om in dezelfde sessie zowel
OAuth als een lokale backend actief te hebben. Het `/model` commando binnen Claude
Code kan switchen tussen Anthropic-modellen (Opus, Sonnet, Haiku), maar niet naar
een compleet andere backend.

### Wat wel kan

Er kunnen **twee aparte sessies** draaien, elk met eigen authenticatie en backend.
Dat is de benadering die al in Phase 3 getest is. De vraag is dan: hoe doe je dat
netjes?

---

## Vraag 2: Hoe twee Claude Code instances naast elkaar draaien?

Er zijn drie opties, elk met een ander isolatieniveau.

### Optie A: Environment variables via shell alias

**Hoe werkt het:** Een alias of wrapper script dat Claude Code start met environment
variables die de backend overschrijven, plus een apart HOME-pad zodat de
OAuth-credentials niet conflicteren.

```bash
# In ~/.bashrc of ~/.zshrc
alias claude-local='HOME=/home/rvanpolen/.claude-local \
  ANTHROPIC_BASE_URL=http://127.0.0.1:8080 \
  ANTHROPIC_AUTH_TOKEN=llamacpp \
  ANTHROPIC_API_KEY="" \
  ANTHROPIC_MODEL=glm-flash-q4 \
  ANTHROPIC_SMALL_FAST_MODEL=glm-flash-q4 \
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
  claude'
```

Of als wrapper script (wat er in `test/run.sh` al stond):

```bash
#!/bin/bash
export HOME=/home/rvanpolen/.claude-local
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080
export ANTHROPIC_AUTH_TOKEN=llamacpp
# ... etc
exec claude --model glm-flash-q4
```

**Voordelen:**
- Simpelste oplossing, nul extra software nodig
- `claude` voor normaal, `claude-local` voor lokaal
- De lokale sessie heeft een eigen HOME, dus geen conflict met OAuth-credentials

**Nadelen:**
- **Geen beperking buiten de workspace.** Er is geen harde grens op het
  bestandssysteem — het lokale model kan buiten het project navigeren, andere
  projecten openen, of bestanden in de home-folder wijzigen.
- Geen harde blokkade op `sudo` (al faalt het in de praktijk omdat het
  wachtwoord vereist is en Claude Code dat niet kent). Destructieve commando's
  die geen root vereisen zijn wel mogelijk.
- Volledig afhankelijk van de permissie-prompts ("mag ik dit uitvoeren?"). Die
  bieden bescherming, maar vereisen dat elke prompt kritisch beoordeeld wordt —
  met een minder capabel model is dat extra belangrijk.

**Geschikt voor:** Snel testen, met actief toezicht op elke actie. Niet geschikt
voor langere of meer autonome taken.

---

### Optie B: Bubblewrap sandbox (Claude Code's ingebouwde `/sandbox`)

**Wat is bubblewrap?** Een lichtgewicht Linux sandboxing tool (origineel ontwikkeld
voor Flatpak). Het maakt geisoleerde omgevingen via Linux kernel namespaces, zonder
root nodig te hebben. Het is een enkel binary bestand, geen daemon, en start in
milliseconden.

**Hoe werkt het in Claude Code?** Je typt `/sandbox` in een Claude Code sessie.
Als `bubblewrap` en `socat` geinstalleerd zijn, schakelt Claude Code over naar
sandbox-modus:

- **Bestandssysteem:** Lezen en schrijven alleen in de huidige werkdirectory.
  De rest van het systeem is read-only beschikbaar (systeem-binaries, libraries)
  of geblokkeerd (gevoelige directories).
- **Netwerk:** Alle extern verkeer gaat via een filtering proxy op de host. Er kan
  een allowlist geconfigureerd worden. Localhost is altijd bereikbaar (dus de
  llama-server API op port 8080 werkt).
- **Sudo blokkade:** `PR_SET_NO_NEW_PRIVS` wordt gezet — setuid-binaries (sudo, su)
  kunnen geen rechten escaleren, zelfs als ze beschikbaar zijn in de sandbox.
- **Performance:** Voegt minder dan 15ms latency toe per commando.

**Installatie (eenmalig):**
```bash
sudo apt install bubblewrap socat
```

**Gecombineerd met Optie A:**
```bash
#!/bin/bash
export HOME=/home/rvanpolen/.claude-local
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080
export ANTHROPIC_AUTH_TOKEN=llamacpp
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL=glm-flash-q4
export ANTHROPIC_SMALL_FAST_MODEL=glm-flash-q4
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
cd /pad/naar/je/project
exec claude --model glm-flash-q4
# Vervolgens /sandbox typen in de Claude Code sessie
```

**Voordelen:**
- Echte OS-level isolatie: geen schrijven buiten de workspace, geen sudo
- Localhost bereikbaar (llama-server werkt)
- VS Code integratie werkt (communiceert via localhost, niet via bestandssysteem)
- Lichtgewicht: geen Docker daemon, geen images, milliseconden startup
- Claude Code's eigen tooling — goed geintegreerd, reduceert permissie-prompts
  met 84% (want gesandboxte commando's worden automatisch toegestaan)
- Optioneel: internet-toegang via de proxy allowlist (voor web search, curl)

**Nadelen:**
- `/sandbox` is een commando dat je **in de sessie** moet typen — het is niet
  automatisch bij het starten. Vergeten is mogelijk. (Er is mogelijk een setting
  om het standaard aan te zetten, maar dat moet uitgezocht worden.)
- De sandbox geldt voor bash-commando's, niet voor Claude Code's eigen file
  operaties (Read/Write/Edit tools). Die worden apart afgehandeld via permissies.
  In de praktijk is dit prima omdat die prompts toch zichtbaar zijn.
- Linux-only (geen probleem hier, maar goed om te weten).

**Geschikt voor:** De meeste scenario's. Goede balans tussen veiligheid en
bruikbaarheid.

---

### Optie C: Docker container

**Hoe werkt het:** Claude Code draait zelf in een Docker container met
gecontroleerde volume mounts. Het project wordt als volume gemount (read-write),
de rest van het hostsysteem is onbereikbaar.

```yaml
# docker-compose.claude-local.yml
services:
  claude-local:
    build: ./claude-local-docker
    volumes:
      - /pad/naar/project:/workspace
    environment:
      - ANTHROPIC_BASE_URL=http://host.docker.internal:8080
      - ANTHROPIC_AUTH_TOKEN=llamacpp
    network_mode: host  # of een beperkt netwerk
    stdin_open: true
    tty: true
```

**Voordelen:**
- Sterkste isolatie: de container ziet alleen wat gemount wordt
- Volledige controle over wat beschikbaar is (geen sudo, geen host-bestanden)
- Reproduceerbaar: Dockerfile beschrijft exact de omgeving
- Geen parent-directory traversal mogelijk — het project in `/workspace` heeft
  geen parent met `.claude/` of `AI_INSTRUCTIONS.md` (tenzij dat gemount wordt)

**Nadelen:**
- **VS Code integratie wordt lastig.** De IDE-integratie van Claude Code werkt
  via localhost MCP — als Claude Code in een container draait, moet die
  communicatie gebridged worden. Dat is niet onmogelijk, maar voegt complexiteit
  toe.
- **Meer overhead:** Docker daemon, image builds, ~300ms startup per container.
- **Interactieve terminal in Docker** is minder smooth dan native.
- **Claude Code is niet ontworpen om in Docker te draaien.** Er is geen officiele
  Docker image. Het kan, maar de setup is volledig eigen verantwoordelijkheid.
- **Dubbele Docker:** Er draait al een llama-server in Docker. Nu Claude Code ook
  in Docker. Die moeten dan met elkaar communiceren (netwerk-bridging).

**Geschikt voor:** Scenario's waar maximale isolatie vereist is en de extra
complexiteit acceptabel is. Minder praktisch voor dagelijks experimenteel gebruik.

---

## Vergelijkingstabel

| | Optie A: Alias | Optie B: Bubblewrap | Optie C: Docker |
|---|---|---|---|
| **Installatie** | Niks extra | `apt install bubblewrap socat` | Docker image bouwen |
| **Isolatie bestandssysteem** | Geen | Workspace r/w, rest r/o of geblokkeerd | Alleen gemounte volumes |
| **Sudo blokkade** | Nee (wachtwoord-gated) | Ja (kernel-level) | Ja (geen sudo in container) |
| **Bereik buiten workspace** | Onbeperkt | Geblokkeerd (r/o of denied) | Geblokkeerd (niet gemount) |
| **Netwerk** | Volledig open | Localhost + proxy allowlist | Configureerbaar |
| **VS Code integratie** | Werkt | Werkt | Lastig (bridging nodig) |
| **llama-server bereikbaar** | Ja | Ja (localhost) | Ja (host.docker.internal) |
| **Startup overhead** | Geen | <15ms | ~300ms + image |
| **Complexiteit** | Laag | Laag-middel | Hoog |
| **Geschikt voor** | Snel testen | Dagelijks experimenteel gebruik | Maximale isolatie |

---

## Aanbeveling

**Optie A + B gecombineerd**, in twee stappen:

### Stap 1: Aparte config (Optie A)

Een apart HOME-pad voor de lokale Claude Code (`~/.claude-local/`) met een eigen
settings.json. Een wrapper script of alias zodat er gekozen kan worden:

- `claude` — normaal (OAuth, Anthropic, zoals nu)
- `claude-local` — lokaal (llama-server, experimenteel)

Dit houdt de credentials en configuratie gescheiden. De normale setup wordt nooit
aangeraakt.

### Stap 2: Sandbox erbij (Optie B)

Bubblewrap + socat installeren, en de sandbox activeren in de lokale sessie. Dit
geeft:

- Geen schrijven buiten de workspace
- Geen sudo
- Localhost bereikbaar (llama-server)
- VS Code integratie intact
- Optioneel internet via proxy

### Wat dat oplevert

```
claude          -> OAuth -> Anthropic -> Opus 4.6 (geen sandbox, volle vrijheid)
claude-local    -> API -> localhost:8080 -> llama-server -> GLM/Qwen/GPT-OSS
                   (sandbox: workspace-only schrijven, geen sudo, localhost ok)
```

Twee commando's, twee werelden, geen interferentie.

---

## Open vragen

1. **Is een sandbox op de normale Claude Code (OAuth) ook wenselijk?** Het kan, maar
   er is nu geen last van — Opus is betrouwbaar en de prompts worden gereviewed. Een
   sandbox zou het veiliger maken maar ook restrictiever.

2. **Welk model standaard voor de lokale versie?** GLM Flash Q4 is het snelst
   (~147 t/s). Maar er kan ook geswitcht worden via de management API.

3. **Is internet nodig in de lokale sandbox?** Web search en curl zijn handig, maar
   niet strikt nodig voor lokaal experimenteren. De proxy allowlist kan dit
   configureerbaar maken.

4. **Moet de lokale versie in willekeurige projecten bruikbaar zijn, of alleen in
   specifieke test-workspaces?** Dit bepaalt of er een vaste werkdirectory
   geconfigureerd wordt of dat het flexibel blijft.

---

## Volgende stappen (na overeenstemming over de richting)

1. Bubblewrap en socat installeren
2. `~/.claude-local/` opzetten met eigen settings.json
3. Wrapper script maken (`claude-local`)
4. Testen: lokale sessie starten, sandbox activeren, basis-functionaliteit checken
5. VS Code integratie verifiieren vanuit de gesandboxte sessie
6. Documenteren in het project
