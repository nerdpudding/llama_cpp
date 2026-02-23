Hier is een overzicht van alle 13 benchmarks uit de afbeelding, met wat ze precies meten:
Agentic/Coding Benchmarks

    Terminal-Bench 2.0 meet hoe goed een AI-agent zelfstandig werkt in een echte terminal. De 89 taken omvatten dingen als databases opzetten, gefaalde deployments debuggen en log-bestanden verwerken — de score is het percentage succesvol afgeronde taken.
    
    SWE-bench Verified test of een model echte GitHub-issues kan oplossen in 12 bekende Python-repository's. Het is een menselijk geverifieerde subset van 500 taken, en de score is het % bugs dat correct gefixed wordt.
    
    OSWorld-Verified evalueert "computer use": een AI die autonoom een OS bedient (Linux, Windows, macOS) via screenshots en muisklikken. De "Verified" variant heeft striktere, menselijk gecheckte succescriteria.​

Tool Use & Agentic Search

    τ2-bench (tau²) simuleert klantenservice-scenario's in retail en telecom, waarbij zowel de agent als de gebruiker acties uitvoert in een gedeelde omgeving. Dit is uniek: de gebruiker is géén passieve toeschouwer maar voert zelf stappen uit.
    
    MCP-Atlas test hoe goed een model tientallen tools tegelijk kan coördineren via het MCP-protocol — bij "scaled" gebruik dus, niet alleen één tool per keer.​
    
    BrowseComp (OpenAI) meet of een AI moeilijk vindbare informatie op het web kan opzoeken via meerstaps browsen. De vragen hebben verifieerbare, korte antwoorden en vereisen creatief zoekgedrag over veel webpagina's.

Redeneren & Kennis

    Humanity's Last Exam (HLE) is een extreem moeilijke multidisciplinaire test op PhD/expert-niveau, met vragen die zelfs menselijke experts missen. Gescoord zowel met als zonder tools.​
    
    GPQA Diamond bevat graduate-level wetenschapsvragen (biologie, chemie, fysica) die zo moeilijk zijn dat zelfs domeinexperts ze niet altijd goed beantwoorden. Score = % correct.​
    
    ARC-AGI-2 test "fluid intelligence": visuele abstracte patronen herkennen en generaliseren vanuit minimale voorbeelden. Expliciet ontworpen om memorisatie te weerstaan — het model moet echt redeneren, niet onthouden.

Professioneel & Financieel

    Finance Agent v1.1 evalueert realistische financiële taken: data-interpretatie, berekeningen en financieel redeneren. Score = % correct afgeronde taken.​
    
    GDPval-AA Elo meet prestaties op echte werkproducten uit 44 beroepen (juridische brieven, engineeringplannen, zorgplannen, etc.). Gescoord via Elo (geen percentage), dus relatief aan andere modellen — hogere Elo = beter.​

Multimodaal & Meertalig

    MMMU-Pro test visueel redeneren met afbeeldingen + tekst gecombineerd, zwaarder dan standaard MMMU. Gescoord zonder tools (puur model) en met tools.​
    
    MMMLU is de meertalige variant van het MMLU-kennisexamen, getest over meerdere talen tegelijk. Score = gemiddeld % correct over alle talen.​

Scores: % vs Elo

De meeste benchmarks rapporteren een succespercentage (%), maar GDPval gebruikt Elo — een relatief rangsysteem zoals in schaken. Dat verklaart waarom Sonnet 4.6 daar een score van 1633 heeft in plaats van een percentage.​
Prepared using Claude Sonnet 4.6 Thinking
Ik wil graag van al die dingen dat in een matric overzicht. het punt is namelijk, ik doe wel eens wat met local modellen en dan bench ik wel eens met eval_plus dat human eval ding zeg maar. maar is zou toch grag eens beter willen kunnen vergelijken met wat in de dingen die in de screenshoit staan gedaan zijn. maar ik draai local met LLAMA.CPP en een RTX4090+5070TI en kan niet dagen lang een bench laten lopen. maar toech zijn er vast wel een paar die via een local api of script ofzo als ik gewoon met llama.cpp kan server kan deon den k ik"? maar welke komen dan het beste in aanmerking daarvoor uit de rij die in de screenshot zaten en waarom of waarom niet?

Hier is het volledige matrix-overzicht, gevolgd door welke je realistisch lokaal kunt draaien.
Benchmark Matrix
Benchmark	Categorie	Meet	Score-type	Vereist tools/env
Terminal-Bench 2.0	Agentic coding	Agent lost echte terminal-taken op (debug, deploy, scripts)	% succes	Ja – container sandbox per taak
SWE-bench Verified	Code bugs fixen	GitHub-issues oplossen in Python repo's	% resolved	Ja – Docker per issue
OSWorld-Verified	Computer use	OS bedienen via screenshots + muisklikken	% succes	Ja – volledige VM images
τ2-bench	Tool use	Klantenservice-agent (retail/telecom) met actieve gebruiker	% succes	Ja – dual-control simulatie
MCP-Atlas	Scaled tool use	Tientallen MCP-tools tegelijk coördineren	% succes	Ja – MCP-infrastructure
BrowseComp	Agentic search	Moeilijk vindbare info opzoeken via multi-step browsen	% correct	Ja – live internet + browser agent
HLE	Kennisredeneren	PhD/expert-niveau vragen over alle disciplines	% correct	Nee – statische dataset
Finance Agent v1.1	Financieel	Financiële berekeningen en data-interpretatie	% succes	Deels – financiële tools
GDPval-AA Elo	Kantoorwerk	Echte werkproducten over 44 beroepen, Elo-gerankt	Elo	Ja – LLM-judge vereist
ARC-AGI-2	Probleemoplossen	Visuele abstracte patronen generaliseren	% correct	Nee – statische dataset
GPQA Diamond	Academisch redeneren	Graduate-level wetenschap (bio/chem/fysica)	% correct	Nee – statische dataset
MMMU-Pro	Visueel redeneren	Multimodale vragen (afbeelding + tekst)	% correct	Nee – maar vereist vision model
MMMLU	Meertalig	MMLU-kennistest over meerdere talen	% correct	Nee – statische dataset
Lokaal draaien via llama.cpp server

De llama.cpp server draait een OpenAI-compatibele API op http://localhost:8080/v1, en diverse benchmarktools kunnen daar simpelweg naar poinen.​
✅ Prima te doen

    GPQA Diamond — Gebruik de fork
    chigkim/openai-api-gpqa
    , puur tekst, draait op elke OpenAI-compatibele API inclusief llama.cpp.
    
    MMMLU — Via lm-evaluation-harness met --model openai-completions en je lokale base_url. Tekst-only, redelijk snel.
    
    HLE — Statische dataset, tekst Q&A, werkt via lm-eval of een eigen script tegen je lokale endpoint.​
    
    ARC-AGI-2 — Het officiële
    arcprize/arc-agi-benchmarking
    script ondersteunt OpenAI API-keys + custom base_url, dus simpel door te verwijzen naar localhost.​

⚠️ Kan maar heeft haken en ogen

    MMMU-Pro — Technisch haalbaar als je een vision-model draait (llama.cpp ondersteunt multimodale GGUF's), maar je hebt een model nodig dat ook afbeeldingen aankan, dus niet met elk model.​
    
    SWE-bench Verified — Kan via swebench/inference/run_api.py met aangepaste base_url, maar elke taak draait een Docker-sandbox. Met 500 taken en 4090+5070Ti ben je alsnog uren/dagen bezig.

❌ Niet realistisch lokaal

    OSWorld-Verified, Terminal-Bench 2.0, τ2-bench, MCP-Atlas — Vereisen complexe omgevingen (VM's, containers, dual-control simulaties). Veel setup, minimale community-ondersteuning voor lokale draaibaarheid.
    
    BrowseComp — Vereist een live browser-agent die echt het web op gaat.
    
    GDPval-AA Elo — Vereist een tweede "judge" LLM om antwoorden te scoren; Elo-berekening is alleen zinvol over meerdere modellen tegelijk.​

Vergelijking met jouw huidige EvalPlus/HumanEval
	EvalPlus/HumanEval	GPQA Diamond	ARC-AGI-2	MMMLU
Meet	Functionele correctheid van code	Wetenschappelijk redeneren	Abstracte generalisatie	Brede kennisbreedte
Overlap met screenshot	Deels (SWE-bench gaat verder)	Direct vergelijkbaar	Direct vergelijkbaar	Direct vergelijkbaar
Lokaal draaibaar	✅ Ja	✅ Ja	✅ Ja	✅ Ja
Snelheid	Snel	Snel (~1u)	Snel (~30min)	Middel (~2u volledig)

De beste combo om je lokale modellen serieus te vergelijken met de screenshot: GPQA Diamond + ARC-AGI-2 + MMMLU (subset). Dat dekt redeneren, generalisatie én kennisbreedte af, en alles werkt gewoon via je llama.cpp server zonder extra infrastructuur.
Prepared using Claude Sonnet 4.6 Thinking

----


Hier werkeleijke scores (vanaf officiele claude webpage, is zelfde als de bechmarks_example.jpeg)

Model Benchmark Scores
Benchmark	Sonnet 4.6	Sonnet 4.5	Opus 4.6	Opus 4.5	Gemini 3 Pro	GPT-5.2
Agentic terminal coding Terminal-Bench 2.0	59.1%	51.0%	65.4%	59.8%	56.2% (54.2% self-reported)	64.7% (64.0% self-reported, Codex CLI)
Agentic coding SWE-bench Verified	79.6%	77.2%	80.8%	80.9%	78.0% (Flash)	80.0%
Agentic computer use OSWorld-Verified	72.5%	61.4%	72.7%	66.3%	—	38.2%
Agentic tool use τ2-bench	Retail 91.7% / Telecom 97.9%	Retail 86.2% / Telecom 98.0%	Retail 91.9% / Telecom 99.3%	Retail 88.9% / Telecom 98.2%	Retail 85.3% / Telecom 98.0%	Retail 82.0% / Telecom 98.7%
Scaled tool use MCP-Atlas	61.3%	43.8%	59.5%	62.3%	54.1%	60.6%
Agentic search BrowseComp	74.7%	43.9%	84.0%	67.8%	59.2% (Deep Research)	77.9% (Pro)
Multidisciplinary reasoning HLE	33.2% / 49.0% (tools)	17.7% / 33.6% (tools)	40.0% / 53.0% (tools)	30.8% / 43.4% (tools)	37.5% / 45.8% (tools)	36.6% / 50.0% (tools, Pro)
Agentic financial analysis Finance Agent v1.1	63.3%	54.5%	60.1%	58.8%	55.2%	59.0%
Office tasks GDPval-AA Elo	1633	1276	1606	1416	1201	1462
Novel problem-solving ARC-AGI-2	58.3%	13.6%	68.8%	37.6%	31.1%	54.2% (Pro)
Graduate-level reasoning GPQA Diamond	89.9%	83.4%	91.3%	87.0%	91.9%	93.2% (Pro)
Visual reasoning MMMU-Pro	74.5% / 75.6% (tools)	63.4% / 68.9% (tools)	73.9% / 77.3% (tools)	70.6% / 73.9% (tools)	81.0% / —	79.5% / 80.4% (tools)
Multilingual Q&A MMMLU	89.3%	89.5%	91.1%	90.8%	91.8%	89.6%

De vetgedrukte scores per rij zijn de hoogste scores, exact zoals ze in de originele afbeelding gehighlight waren. HLE en MMMU-Pro zijn gesplitst als zonder tools / met tools.
