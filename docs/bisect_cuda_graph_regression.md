# Bisecting the CUDA Graph Regression

**Issue:** https://github.com/ggml-org/llama.cpp/issues/19816
**Goal:** Find the exact commit that introduced the CUDA illegal memory access crash with `-ot` multi-GPU splits on MoE models.

---

## How bisect works

You have a known **good** commit and a known **bad** commit with 93 commits in between. `git bisect` does a binary search: it picks the middle commit, you test it, tell Git if it's good or bad, and it picks the next midpoint. This narrows 93 commits down in about **7 steps**.

```
good (b48e80f67) -------- 93 commits -------- bad (ed4837891)
                    ^
              bisect picks middle,
              you test, say good/bad,
              repeat ~7 times
```

---

## Before you start

Make sure the container is stopped:
```bash
docker compose down
```

---

## Step 1: Start the bisect

```bash
cd ~/vibe_claude_kilo_cli_exp/llama_cpp/llama.cpp

git bisect start
git bisect bad ed4837891
git bisect good b48e80f67
```

Git will check out a commit in the middle and tell you something like:
```
Bisecting: 46 revisions left to test after this (roughly 6 steps)
[abc123...] Some commit message
```

**Write down the commit hash it shows.** You'll need it if something goes wrong.

---

## Step 2: Build and test (repeat this for each bisect step)

### 2a. Build

From the project root (not inside llama.cpp/):
```bash
cd ~/vibe_claude_kilo_cli_exp/llama_cpp
docker compose build --no-cache
```

This takes a while. The `--no-cache` is important because Docker needs to pick up the changed source.

### 2b. Start the server with the Qwen3-Next bench profile

```bash
./start.sh bench-qwen3-next-ud-q5
```

Wait for the server to finish loading the model. You'll see it in the dashboard or logs.

### 2c. Test with a long prompt

The bug only shows on prompts longer than ~100 tokens. Send a test request:

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "test",
    "messages": [{"role": "user", "content": "Write a detailed explanation of how neural networks work, covering the following topics: perceptrons, activation functions, backpropagation, gradient descent, learning rates, overfitting, regularization techniques including dropout and L2 regularization, batch normalization, convolutional layers, pooling layers, recurrent networks, LSTM cells, attention mechanisms, and transformer architectures. For each topic provide a clear definition and one practical example."}],
    "max_tokens": 50
  }' | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('choices',[{}])[0].get('message',{}).get('content','NO RESPONSE'))" 2>/dev/null
```

### 2d. Check the result

- **If you got a text response** (even a partial one) = this commit is **good**
- **If the server crashed** with `CUDA error: an illegal memory access` = this commit is **bad**
- **If the build failed** (cmake/compile error) = this commit can't be tested (see step 3)

### 2e. Stop the server

```bash
docker compose down
```

---

## Step 3: Tell Git the result

Go back to the llama.cpp directory:

```bash
cd ~/vibe_claude_kilo_cli_exp/llama_cpp/llama.cpp
```

Then depending on the result:

```bash
# If the test PASSED (got a response):
git bisect good

# If the test FAILED (CUDA crash):
git bisect bad

# If the build failed or you can't test this commit:
git bisect skip
```

Git will check out the next commit and tell you how many steps remain. **Go back to Step 2** and repeat.

---

## Step 4: Bisect finds the culprit

After ~7 rounds, Git will print something like:
```
abc123def is the first bad commit
commit abc123def
Author: Someone <email>
Date:   ...

    Some commit message about CUDA graphs
```

**Copy this entire output!** This is what we need to post on the GitHub issue.

---

## Step 5: Clean up

When done (whether successful or if you want to abort):

```bash
cd ~/vibe_claude_kilo_cli_exp/llama_cpp/llama.cpp

# End the bisect session and go back to where you were
git bisect reset
```

This puts you back on the commit you were on before bisecting (`b48e80f67`).

---

## Quick reference card

| Situation | Command |
|-----------|---------|
| Test passed (got response) | `git bisect good` |
| Test failed (CUDA crash) | `git bisect bad` |
| Build failed / can't test | `git bisect skip` |
| Want to see current status | `git bisect log` |
| Want to abort everything | `git bisect reset` |
| Forgot which commit you're on | `git log --oneline -1` |

---

## What we expect to find

Based on the analysis in `docs/known_issue_llama_cpp_cuda_graphs_2026-02-22.md`, the likely culprits are:

- **PR #19645** — `cuda: enable CUDA graphs for MMID 1 <= BS <= 4`
- **PR #19754** — `Improve CUDA graph capture`

The bisect will confirm which one (or if it's something else entirely).

---

## After finding the commit

Don't post yet. Come back to Claude and we'll:
1. Review what the commit actually changed
2. Write a clear, helpful response for the issue
3. Update our docs with the finding
