# Run 1 — max_new_tokens=768 (evalplus default)

Date: 2026-02-14

## Settings
- evalplus default: max_new_tokens=768
- GLM Flash: no --reasoning-format flag (first attempt), then --reasoning-format none (second attempt)
- All other settings: bench-* profiles from models.conf, greedy decoding (temperature=0)

## Results

| Model | HumanEval (base) | HumanEval+ | Notes |
|-------|-----------------|------------|-------|
| bench-glm-flash-q4 | 4.3% | 4.3% | All solutions empty — reasoning_content consumed all 768 tokens, content field empty |
| bench-qwen3-coder-ud-q5 | 91.5% | 88.4% | 0 empty solutions, max 2845 chars |
| bench-qwen3-coder-ud-q6 | 90.9% | 88.4% | 0 empty solutions, max 3055 chars |
| bench-qwen3-coder-q6k | 92.1% | 88.4% | 0 empty solutions, max 2508 chars |
| bench-gpt-oss-120b | 68.3% | 65.9% | 8 empty solutions, 26 solutions >2500 chars (likely truncated) |

## Conclusions

1. **GLM Flash failed completely** — reasoning model puts chain-of-thought in `reasoning_content` field, EvalPlus only reads `content`. Fix: add `--reasoning-format none` to server args so everything goes in `content`.
2. **GPT-OSS score is artificially low** — 768 tokens too few for verbose chat-style answers. 8 empty + 26 likely truncated solutions.
3. **Qwen3 scores may be slightly depressed** — no empty solutions but some answers near the 768 token limit.
4. **All three Qwen3 quants scored identically on HumanEval+** (88.4%) — quantization has no measurable impact on this benchmark.

## Action taken
- Increased max_new_tokens to 4096 in evalplus source (provider/base.py)
- Added --reasoning-format none to GLM bench-* profiles in models.conf
- Re-running all 6 models as run 2
