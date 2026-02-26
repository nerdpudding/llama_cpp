# Extended Benchmarks Research

Research into benchmarks beyond EvalPlus HumanEval+ for comparing local models
against frontier model scores. Focus: what can realistically run locally via the
llama.cpp OpenAI-compatible API without days of compute or complex infrastructure.

---

## Benchmark overview

| Benchmark | Category | What it measures | Score type | Needs infra? |
|-----------|----------|------------------|------------|:------------:|
| Terminal-Bench 2.0 | Agentic coding | Agent solves real terminal tasks (debug, deploy, scripts) | % success | Yes — container sandbox per task |
| SWE-bench Verified | Code bug fixing | Solve real GitHub issues in Python repos | % resolved | Yes — Docker per issue |
| OSWorld-Verified | Computer use | Control an OS via screenshots + mouse clicks | % success | Yes — full VM images |
| tau2-bench | Tool use | Customer service agent (retail/telecom) with active user | % success | Yes — dual-control simulation |
| MCP-Atlas | Scaled tool use | Coordinate dozens of MCP tools simultaneously | % success | Yes — MCP infrastructure |
| BrowseComp | Agentic search | Find hard-to-locate info via multi-step web browsing | % correct | Yes — live browser agent |
| HLE | Knowledge reasoning | PhD/expert-level questions across all disciplines | % correct | No — static dataset |
| Finance Agent v1.1 | Financial | Financial calculations and data interpretation | % success | Partial — financial tools |
| GDPval-AA Elo | Office work | Real work products across 44 professions, Elo-ranked | Elo | Yes — LLM judge required |
| ARC-AGI-2 | Problem solving | Generalize visual abstract patterns from minimal examples | % correct | No — static dataset |
| GPQA Diamond | Academic reasoning | Graduate-level science (bio/chem/physics) | % correct | No — static dataset |
| MMMU-Pro | Visual reasoning | Multimodal questions (image + text) | % correct | No — but requires vision model |
| MMMLU | Multilingual | MMLU knowledge test across multiple languages | % correct | No — static dataset |

---

## Feasibility for local llama.cpp

### Feasible — works via OpenAI-compatible API

| Benchmark | How to run | Est. duration | Notes |
|-----------|-----------|:-------------:|-------|
| **GPQA Diamond** | [chigkim/openai-api-gpqa](https://github.com/chigkim/openai-api-gpqa) — points at local API | ~1 hour | Pure text, 198 questions. Direct comparison with frontier scores. |
| **ARC-AGI-2** | [arcprize/arc-agi-benchmarking](https://github.com/arcprize/arc-agi-benchmarking) — supports custom base_url | ~30 min | Text-based pattern tasks. Tests reasoning, not memorization. |
| **MMMLU** | lm-evaluation-harness with `--model openai-completions` and local base_url | ~2 hours (full) | Can run a subset for faster results. Tests breadth of knowledge. |
| **HLE** | lm-eval or custom script against local endpoint | ~1-2 hours | Static Q&A dataset. Very hard — even frontier models score 30-50%. |

### Possible but with caveats

| Benchmark | Issue |
|-----------|-------|
| **MMMU-Pro** | Requires a vision model. llama.cpp supports multimodal GGUFs but none of our current models have vision. |
| **SWE-bench Verified** | Can run via `swebench/inference/run_api.py` with custom base_url. But 500 tasks each spinning up a Docker sandbox — likely days of compute. |

### Not realistic locally

| Benchmark | Why not |
|-----------|---------|
| OSWorld-Verified | Requires full VM images per task |
| Terminal-Bench 2.0 | Container sandbox per task, complex setup |
| tau2-bench | Dual-control simulation environment |
| MCP-Atlas | Full MCP infrastructure needed |
| BrowseComp | Needs a live browser agent on the web |
| GDPval-AA Elo | Needs a second LLM as judge; Elo only meaningful across many models |
| Finance Agent v1.1 | Requires financial tool infrastructure |

---

## Selection criteria

Benchmarks in this project are selected primarily for practical ease of setup and evaluation:

1. **Automated evaluation** — objectively correct answers (multiple-choice, exact match). No LLM-as-judge, no human evaluation. Keeps results reproducible and the pipeline simple.
2. **Runs via OpenAI-compatible API** — works by sending prompts to a local endpoint. No custom model loading or framework-specific code.
3. **Reasonable runtime** — hours, not days.
4. **Published frontier scores available** — enables direct comparison with proprietary models.

This means the current and near-term benchmarks test knowledge recall, pattern recognition, and structured problem-solving. More complex benchmarks that test real-world agentic capability (SWE-bench, Terminal-Bench, tau2-bench) require more infrastructure but are not ruled out for the future.

## Recommended additions

The best combination for comparing local models against frontier scores:

| Priority | Benchmark | Why | Complements |
|:--------:|-----------|-----|-------------|
| 1 | **GPQA Diamond** | Graduate-level reasoning. Directly comparable with published scores. Easy setup. | Tests reasoning depth (HumanEval tests code correctness) |
| 2 | **ARC-AGI-2** | Abstract problem solving. Resists memorization. Shows true reasoning ability. | Tests generalization (HumanEval tests pattern application) |
| 3 | **MMMLU** | Broad knowledge across languages. Well-established benchmark. | Tests knowledge breadth (HumanEval tests coding only) |

Together with EvalPlus HumanEval+, this covers: **coding, reasoning, generalization, knowledge breadth**.

---

## Frontier reference scores

From Anthropic's published benchmarks (2026):

| Benchmark | Sonnet 4.6 | Opus 4.6 | Gemini 3 Pro | GPT-5.2 |
|-----------|:----------:|:--------:|:------------:|:-------:|
| GPQA Diamond | 89.9% | 91.3% | 91.9% | 93.2% |
| ARC-AGI-2 | 58.3% | 68.8% | 31.1% | 54.2% |
| MMMLU | 89.3% | 91.1% | 91.8% | 89.6% |
| HLE | 33.2% | 40.0% | 37.5% | 36.6% |
| HLE (with tools) | 49.0% | 53.0% | 45.8% | 50.0% |
| SWE-bench Verified | 79.6% | 80.8% | 78.0% | 80.0% |
| Terminal-Bench 2.0 | 59.1% | 65.4% | 56.2% | 64.7% |

*Scores from claude.ai model comparison page. HLE and MMMU-Pro split as without/with tools.*
