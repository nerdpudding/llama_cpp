# EvalPlus HumanEval+ Benchmark Results

*Generated: 2026-02-15 13:14*

## Local Results (pass@1, greedy decoding, temperature=0)

| # | Model | HumanEval | HumanEval+ | vs FP16 ref |
|---|-------|-----------|------------|-------------|
| 1 | Qwen3-Coder-Next UD-Q6_K_XL | 93.3% | 90.9% | -0.8pp |
| 2 | Qwen3-Coder-Next Q6_K | 93.3% | 90.2% | -0.8pp |
| 3 | Qwen3-Coder-Next UD-Q5_K_XL | 93.3% | 90.2% | -0.8pp |
| 4 | GPT-OSS 120B F16 | 92.1% | 87.8% | +3.8pp |
| 5 | GLM-4.7 Flash Q4_K_M * | 87.8% | 84.8% | +0.8pp |
| 6 | GLM-4.7 Flash Q8_0 * | 87.2% | 82.9% | +0.2pp |

## HumanEval Ranking (pass@1)

| # | Model | HumanEval | Source |
|---|-------|-----------|--------|
| 1 | OpenAI O1 Preview | 96.3% | EvalPlus leaderboard |
| 2 | Claude Opus 4.5 | 94.2% | zoer.ai Jan 2026 benchmark |
| 3 | Qwen3-Coder-Next (FP16, official) | 94.1% | Model card |
| 4 | **Qwen3-Coder-Next Q6_K** | **93.3%** | **Local benchmark** |
| 5 | **Qwen3-Coder-Next UD-Q5_K_XL** | **93.3%** | **Local benchmark** |
| 6 | **Qwen3-Coder-Next UD-Q6_K_XL** | **93.3%** | **Local benchmark** |
| 7 | **GPT-OSS 120B F16** | **92.1%** | **Local benchmark** |
| 8 | Claude 3.5 Sonnet | 92.0% | EvalPlus leaderboard + index.dev |
| 9 | GPT-5.2 Codex | 91.7% | zoer.ai Jan 2026 benchmark |
| 10 | GPT-4o | 90.2% | EvalPlus leaderboard + index.dev |
| 11 | GPT-OSS 120B (official) | 88.3% | Model card |
| 12 | **GLM-4.7 Flash Q4_K_M** | **87.8%** | **Local benchmark** |
| 13 | **GLM-4.7 Flash Q8_0** | **87.2%** | **Local benchmark** |
| 14 | GLM-4.7 (full, not Flash) | 87.0% | zoer.ai |
| 15 | Codestral 25.01 | 86.6% | Mistral AI / index.dev |
| 16 | Gemini 1.5 Pro | 84.1% | index.dev |
| 17 | Llama 3.1 405B | 82.0% | index.dev |

## HumanEval+ Ranking (pass@1, stricter)

| # | Model | HumanEval+ | Source |
|---|-------|------------|--------|
| 1 | **Qwen3-Coder-Next UD-Q6_K_XL** | **90.9%** | **Local benchmark** |
| 2 | **Qwen3-Coder-Next Q6_K** | **90.2%** | **Local benchmark** |
| 3 | **Qwen3-Coder-Next UD-Q5_K_XL** | **90.2%** | **Local benchmark** |
| 4 | OpenAI O1 Preview | 89.0% | EvalPlus leaderboard |
| 5 | **GPT-OSS 120B F16** | **87.8%** | **Local benchmark** |
| 6 | GPT-4o | 87.2% | EvalPlus leaderboard + index.dev |
| 7 | Qwen2.5-Coder-32B-Instruct | 87.2% | EvalPlus leaderboard |
| 8 | DeepSeek-V3 / GPT-4-Turbo | 86.6% | EvalPlus leaderboard |
| 9 | **GLM-4.7 Flash Q4_K_M** | **84.8%** | **Local benchmark** |
| 10 | **GLM-4.7 Flash Q8_0** | **82.9%** | **Local benchmark** |
| 11 | Claude 3.5 Sonnet | 81.7% | EvalPlus leaderboard + index.dev |

## Notes

- All local results use greedy decoding (temperature=0, max_tokens=4096)
- **HumanEval+** uses 80x more tests than standard HumanEval (stricter, scores are typically 3-8% lower)
- Local benchmarks produce both HumanEval and HumanEval+ scores
- "vs FP16 ref" shows difference in HumanEval base score vs the closest official published score
- Many reference models only have HumanEval (not HumanEval+) published — direct comparison on HumanEval+ is limited
- Local scores may differ from published due to quantization, prompt template, and max_tokens differences
- GLM-4.7 Flash is a reasoning model — benchmarked with `--reasoning-format none` to include thinking in output. Scores may be less reliable: the model spends tokens on chain-of-thought reasoning before producing code, and the code extractor must parse it from mixed reasoning+code output. The Q4 > Q8 score inversion is likely caused by this
