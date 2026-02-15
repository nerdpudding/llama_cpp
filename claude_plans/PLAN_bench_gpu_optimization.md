# Plan: Benchmark GPU Layer Optimization

**Status: NOT STARTED — waiting for current benchmark test run to complete**

## Goal

Optimize bench profiles in `models.conf` for 16K→8K context reduction.
Less KV cache = more VRAM = potentially more layers on GPU = faster benchmark runs.

## Context from data

**Actual token usage in benchmarks (prompt + response):**

| Model | Max response | ~Max tokens | + prompt | Total |
|-------|-------------|-------------|----------|-------|
| GLM Q8 (incl. `<think>`) | 28,787 chars | ~7,200 | ~500 | ~7,700 |
| GPT-OSS (no reasoning level) | 7,837 chars | ~2,000 | ~500 | ~2,500 |
| Qwen3 UD-Q6 | 6,051 chars | ~1,500 | ~500 | ~2,000 |

**Unknown:** GPT-OSS with `Reasoning: high` — could be significantly longer.

**Target CTX_SIZE:** 10240 (was 16384)

**Why not 8K:** GLM Q8's worst case (HumanEval/10) uses ~8,391 tokens total
(prompt + thinking + response), which exceeds 8192. 10K gives safe margin
for all models including future additions.

## Pre-implementation: manual GPT-OSS test

Before changing anything, test GPT-OSS with `Reasoning: high` to confirm 8K is safe.

1. Start GPT-OSS via `./start.sh gpt-oss-120b`
2. In web UI, configure to match benchmark settings:
   - System prompt: `Reasoning: high`
   - Temperature: `0` (greedy, same as evalplus `--greedy`)
   - Top-P: `1` (effectively disabled)
   - Min-P: `0`
   - Max tokens (response): not available in GUI, leave default (will be unlimited — better for testing worst case)
3. Test these two prompts (worst-case from existing data). Copy-paste each
   into the web UI chat box:

   **Test 1 — HumanEval/10** (GLM's longest response):
   ```
   Complete this Python function:

   def is_palindrome(string: str) -> bool:
       """ Test if given string is a palindrome """
       return string == string[::-1]


   def make_palindrome(string: str) -> str:
       """ Find the shortest palindrome that begins with a supplied string.
       Algorithm idea is simple:
       - Find the longest postfix of supplied string that is a palindrome.
       - Append to the end of the string reverse of a string prefix that comes before the palindromic suffix.
       >>> make_palindrome('')
       ''
       >>> make_palindrome('cat')
       'catac'
       >>> make_palindrome('cata')
       'catac'
       """
   ```

   **Test 2 — HumanEval/129** (GPT-OSS's own longest response):
   ```
   Complete this Python function:

   def minPath(grid, k):
       """
       Given a grid with N rows and N columns (N >= 2) and a positive integer k,
       each cell of the grid contains a value. Every integer in the range [1, N * N]
       inclusive appears exactly once on the cells of the grid.

       You have to find the minimum path of length k in the grid. You can start
       from any cell, and in each step you can move to any of the neighbor cells,
       in other words, you can go to cells which share an edge with you current
       cell.
       Please note that a path of length k means visiting exactly k cells (not
       necessarily distinct).
       You CANNOT go off the grid.
       A path A (of length k) is considered less than a path B (of length k) if
       after making the ordered lists of the values on the cells that A and B go
       through (let's call them lst_A and lst_B), lst_A is lexicographically less
       than lst_B, in other words, there exist an integer index i (1 <= i <= k)
       such that lst_A[i] < lst_B[i] and for any j (1 <= j < i) we have
       lst_A[j] = lst_B[j].
       It is guaranteed that the answer is unique.
       Return an ordered list of the values on the cells that the minimum path go through.

       Examples:

           Input: grid = [ [1,2,3], [4,5,6], [7,8,9]], k = 3
           Output: [1, 2, 1]

           Input: grid = [ [5,9,3], [4,1,6], [7,8,2]], k = 1
           Output: [1]
       """
   ```

4. Note the response lengths (tokens shown in web UI). If both stay under
   ~7,500 tokens, 8K is safe.

## Implementation steps

### 1. Add bench profiles to start.sh model picker

Add a separate "Benchmark profiles" section in the start.sh menu so bench configs
can be selected for manual testing (OOM checks, response length checks).

### 2. Reduce CTX_SIZE for all bench profiles

Change all bench profiles from `CTX_SIZE=16384` to `CTX_SIZE=10240`.

### 3. Calculate VRAM freed per model

**KV cache savings (16K → 10K):**

- **GLM Flash:** Standard attention on all layers. KV cache scales linearly.
  At q8_0: 16K uses ~X MiB, 8K uses ~X/2 MiB. Need to measure.
- **GPT-OSS 120B:** Half SWA layers (18/36) have fixed tiny KV regardless of
  context. Only non-SWA layers benefit. Savings are smaller than GLM.
  At 64K production: KV = 1,224 MiB non-SWA + 81 MiB SWA.
  At 8K: non-SWA scales down ~8x → significant saving.
- **Qwen3-Coder-Next:** Only 12/48 layers have KV cache (DeltaNet).
  At 256K production (q8_0): 3,264 MiB total KV.
  At 8K: ~102 MiB. Saves ~3,162 MiB. Plus smaller compute buffers.

### 4. Try fitting models entirely on RTX 4090

With 10K context, some models might fit entirely on the 4090 (24 GB):

- **GLM Flash Q4 (~8 GB weights):** Almost certainly fits on 4090 alone.
  Already uses FIT=on. Might not even need 5070 Ti at all.
- **GLM Flash Q8 (~16 GB weights):** Possible with 10K context.
  24 GB - 16 GB weights = 8 GB for KV cache + compute buffers.
- **GPT-OSS 120B (~61 GB weights):** No chance on single GPU. But freed VRAM
  could allow more layers on GPU → faster.
- **Qwen3 UD-Q5 (~57 GB) / UD-Q6 (~64 GB) / Q6K (~66 GB):** No chance on
  single GPU. But with tiny KV at 10K, significantly more layers on GPU.

### 5. Optimize layer splits for MoE models

For GPT-OSS and Qwen3 (can't fit on single GPU):
- Calculate new VRAM budget with 8K context
- Try adding more layers to CUDA0 and/or CUDA1
- Update `-ot` regex patterns in models.conf

### 6. Test each model for OOM

Use start.sh (with bench profiles in menu) to start each model and verify:
- No OOM on startup
- Generate a response successfully
- Check VRAM usage with `nvidia-smi`

### 7. Update models.conf bench profiles

After successful tests, update the profiles with optimized settings.

## Order of execution

1. Manual GPT-OSS test (user) → confirm 8K is safe
2. Add bench profiles to start.sh menu
3. Change CTX_SIZE to 8192 for all bench profiles
4. Test GLM Q4 and Q8 on 4090-only (remove -ot, just FIT=on)
5. Calculate and test new layer splits for GPT-OSS and Qwen3
6. Update models.conf with final optimized profiles
7. Run full benchmark with new profiles
