# EvalPlus HumanEval+ Benchmark Results

*Generated: 2026-02-27 00:27*

## Local Results (pass@1, greedy decoding, temperature=0)

| # | Model | HumanEval | HumanEval+ | vs published |
|---|-------|-----------|------------|-------------|
| 1 | Claude Opus 4.6 | 98.2% | 95.1% | +4.0pp |
| 2 | Qwen3.5-122B-A10B UD-Q4_K_XL | 97.6% | 94.5% | — |
| 3 | Qwen3.5-27B UD-Q6_K_XL (dense) | 98.2% | 94.5% | — |
| 4 | Claude Opus 4.6 (thinking) | 99.4% | 93.9% | +5.2pp |
| 5 | Qwen3-Next-80B-A3B UD-Q5_K_XL | 98.2% | 93.9% | — |
| 6 | Qwen3-Coder-Next UD-Q5_K_XL | 93.9% | 90.9% | -0.2pp |
| 7 | Qwen3.5-35B-A3B UD-Q6_K_XL | 95.1% | 90.9% | — |
| 8 | bench-qwen3-coder-ud-q6 | 92.1% | 89.0% | — |
| 9 | GLM-4.7 Flash Q8_0 * | 89.0% | 87.2% | +2.0pp |
| 10 | GPT-OSS 120B F16 | 93.3% | 87.2% | +5.0pp |
| 11 | GLM-4.7 Flash Q4_K_M * | 87.8% | 83.5% | +0.8pp |

## HumanEval Ranking (pass@1)

| # | Model | HumanEval | Source |
|---|-------|-----------|--------|
| 1 | **Claude Opus 4.6 (thinking)** | **99.4%** | **Local benchmark** |
| 2 | **Claude Opus 4.6** | **98.2%** | **Local benchmark** |
| 3 | **Qwen3-Next-80B-A3B UD-Q5_K_XL** | **98.2%** | **Local benchmark** |
| 4 | **Qwen3.5-27B UD-Q6_K_XL (dense)** | **98.2%** | **Local benchmark** |
| 5 | **Qwen3.5-122B-A10B UD-Q4_K_XL** | **97.6%** | **Local benchmark** |
| 6 | OpenAI O1 Preview | 96.3% | EvalPlus leaderboard |
| 7 | **Qwen3.5-35B-A3B UD-Q6_K_XL** | **95.1%** | **Local benchmark** |
| 8 | Claude Opus 4.5 | 94.2% | zoer.ai Jan 2026 benchmark |
| 9 | Qwen3-Coder-Next (FP16, official) | 94.1% | Model card |
| 10 | **Qwen3-Coder-Next UD-Q5_K_XL** | **93.9%** | **Local benchmark** |
| 11 | **GPT-OSS 120B F16** | **93.3%** | **Local benchmark** |
| 12 | **bench-qwen3-coder-ud-q6** | **92.1%** | **Local benchmark** |
| 13 | Claude 3.5 Sonnet | 92.0% | EvalPlus leaderboard |
| 14 | GPT-5.2 Codex | 91.7% | zoer.ai Jan 2026 benchmark |
| 15 | GPT-4o | 90.2% | EvalPlus leaderboard |
| 16 | Llama 3.1 405B | 89.0% | Meta official eval (0-shot, pass@1) |
| 17 | **GLM-4.7 Flash Q8_0** | **89.0%** | **Local benchmark** |
| 18 | GPT-OSS 120B (official) | 88.3% | Model card |
| 19 | **GLM-4.7 Flash Q4_K_M** | **87.8%** | **Local benchmark** |
| 20 | GLM-4.7 (full, not Flash) | 87.0% | zoer.ai |
| 21 | Codestral 25.01 | 86.6% | Mistral AI |
| 22 | Gemini 1.5 Pro | 84.1% | Gemini 1.5 technical report (arxiv:2403.05530) |

## HumanEval+ Ranking (pass@1, stricter)

| # | Model | HumanEval+ | Source |
|---|-------|------------|--------|
| 1 | **Claude Opus 4.6** | **95.1%** | **Local benchmark** |
| 2 | **Qwen3.5-122B-A10B UD-Q4_K_XL** | **94.5%** | **Local benchmark** |
| 3 | **Qwen3.5-27B UD-Q6_K_XL (dense)** | **94.5%** | **Local benchmark** |
| 4 | **Claude Opus 4.6 (thinking)** | **93.9%** | **Local benchmark** |
| 5 | **Qwen3-Next-80B-A3B UD-Q5_K_XL** | **93.9%** | **Local benchmark** |
| 6 | **Qwen3-Coder-Next UD-Q5_K_XL** | **90.9%** | **Local benchmark** |
| 7 | **Qwen3.5-35B-A3B UD-Q6_K_XL** | **90.9%** | **Local benchmark** |
| 8 | OpenAI O1 Preview | 89.0% | EvalPlus leaderboard |
| 9 | **bench-qwen3-coder-ud-q6** | **89.0%** | **Local benchmark** |
| 10 | GPT-4o | 87.2% | EvalPlus leaderboard |
| 11 | Qwen2.5-Coder-32B-Instruct | 87.2% | EvalPlus leaderboard |
| 12 | **GLM-4.7 Flash Q8_0** | **87.2%** | **Local benchmark** |
| 13 | **GPT-OSS 120B F16** | **87.2%** | **Local benchmark** |
| 14 | DeepSeek-V3 / GPT-4-Turbo | 86.6% | EvalPlus leaderboard |
| 15 | **GLM-4.7 Flash Q4_K_M** | **83.5%** | **Local benchmark** |
| 16 | Claude 3.5 Sonnet | 81.7% | EvalPlus leaderboard |

## Notes

- All local results use greedy decoding (temperature=0, max_tokens=4096)
- **HumanEval+** uses 80x more tests than standard HumanEval (stricter, scores are typically 3-8% lower)
- Local benchmarks produce both HumanEval and HumanEval+ scores
- "vs published" shows difference in HumanEval base score vs the closest official published score
- Many reference models only have HumanEval (not HumanEval+) published — direct comparison on HumanEval+ is limited
- Local scores may differ from published due to quantization, prompt template, and max_tokens differences
- GLM-4.7 Flash is a reasoning model — benchmarked with `--reasoning-format none` to include thinking in output. Scores may be less reliable: the model spends tokens on chain-of-thought reasoning before producing code, and the code extractor must parse it from mixed reasoning+code output. The Q4 > Q8 score inversion is likely caused by this
- Claude Opus 4.6 was tested via Claude Code (Max subscription) using a custom agent that solves each problem from the prompt alone — no code execution, no internet, no tools. "vs published" compares against the published Opus 4.5 score (no Opus 4.6 reference available yet)
