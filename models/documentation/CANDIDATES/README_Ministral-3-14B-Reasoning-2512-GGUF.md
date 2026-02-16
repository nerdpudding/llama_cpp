---
library_name: vllm
language:
- en
- fr
- es
- de
- it
- pt
- nl
- zh
- ja
- ko
- ar
license: apache-2.0
inference: false
base_model:
- mistralai/Ministral-3-14B-Reasoning-2512
extra_gated_description: >-
  If you want to learn more about how we process your personal data, please read
  our <a href="https://mistral.ai/terms/">Privacy Policy</a>.
tags:
- mistral-common
- mistral
- unsloth
---
<div>
  <p style="margin-bottom: 0; margin-top: 0;">
    <strong>See our <a href="https://huggingface.co/collections/unsloth/ministral-3">Ministral 3 collection</a> for all versions including GGUF, 4-bit & FP8 formats.</strong>
  </p>
  <p style="margin-bottom: 0;">
    <em>Learn to run Ministral correctly - <a href="https://docs.unsloth.ai/new/ministral-3">Read our Guide</a>.</em>
  </p>
<p style="margin-top: 0;margin-bottom: 0;">
   <em>See <a href="https://docs.unsloth.ai/basics/unsloth-dynamic-v2.0-gguf">Unsloth Dynamic 2.0 GGUFs</a> for our quantization benchmarks.</em>
  </p>
  <div style="display: flex; gap: 5px; align-items: center; ">
    <a href="https://github.com/unslothai/unsloth/">
      <img src="https://github.com/unslothai/unsloth/raw/main/images/unsloth%20new%20logo.png" width="133">
    </a>
    <a href="https://discord.gg/unsloth">
      <img src="https://github.com/unslothai/unsloth/raw/main/images/Discord%20button.png" width="173">
    </a>
    <a href="https://docs.unsloth.ai/new/ministral-3">
      <img src="https://raw.githubusercontent.com/unslothai/unsloth/refs/heads/main/images/documentation%20green%20button.png" width="143">
    </a>
  </div>
<h1 style="margin-top: 0rem;">✨ Read our Ministral 3 Guide <a href="https://docs.unsloth.ai/new/ministral-3">here</a>!</h1>
</div>

- Fine-tune Ministral 3 for free using our [Google Colab notebook](https://docs.unsloth.ai/new/ministral-3#fine-tuning)
- Or train Ministral 3 with reinforcement learning (GSPO) with our [free notebook](https://docs.unsloth.ai/new/ministral-3#reinforcement-learning-grpo).
- View the rest of our notebooks in our [docs here](https://docs.unsloth.ai/get-started/unsloth-notebooks).
---

# Ministral 3 14B Reasoning 2512

The largest model in the Ministral 3 family, **Ministral 3 14B** offers frontier capabilities and performance comparable to its larger [Mistral Small 3.2 24B](https://huggingface.co/mistralai/Mistral-Small-3.2-Instruct-2506) counterpart. A powerful and efficient language model with vision capabilities.

This model is the reasoning post-trained version, trained for reasoning tasks, making it ideal for math, coding and stem related use cases.

The Ministral 3 family is designed for edge deployment, capable of running on a wide range of hardware. Ministral 3 14B can even be deployed locally, capable of fitting in 32GB of VRAM in BF16, and less than 24GB of RAM/VRAM when quantized.

## Key Features
Ministral 3 14B consists of two main architectural components:
- **13.5B Language Model**
- **0.4B Vision Encoder**

The Ministral 3 14B Reasoning model offers the following capabilities:
- **Vision**: Enables the model to analyze images and provide insights based on visual content, in addition to text.
- **Multilingual**: Supports dozens of languages, including English, French, Spanish, German, Italian, Portuguese, Dutch, Chinese, Japanese, Korean, Arabic.
- **System Prompt**: Maintains strong adherence and support for system prompts.
- **Agentic**: Offers best-in-class agentic capabilities with native function calling and JSON outputting.
- **Reasoning**: Excels at complex, multi-step reasoning and dynamic problem-solving.
- **Edge-Optimized**: Delivers best-in-class performance at a small scale, deployable anywhere.
- **Apache 2.0 License**: Open-source license allowing usage and modification for both commercial and non-commercial purposes.
- **Large Context Window**: Supports a 256k context window.

### Use Cases
Private AI deployments where advanced capabilities meet practical hardware constraints:
- Private/custom chat and AI assistant deployments in constrained environments
- Advanced local agentic use cases
- Fine-tuning and specialization
- And more...
  
Bringing advanced AI capabilities to most environments.

## Ministral 3 Family

| Model Name                     | Type               | Precision | Link                                                                                     |
|--------------------------------|--------------------|-----------|------------------------------------------------------------------------------------------|
| Ministral 3 3B Base 2512       | Base pre-trained   | BF16      | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-3B-Base-2512)                |
| Ministral 3 3B Instruct 2512   | Instruct post-trained | FP8   | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512)            |
| Ministral 3 3B Reasoning 2512  | Reasoning capable  | BF16      | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-3B-Reasoning-2512)           |
| Ministral 3 8B Base 2512       | Base pre-trained   | BF16      | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-8B-Base-2512)                |
| Ministral 3 8B Instruct 2512   | Instruct post-trained | FP8    | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512)            |
| Ministral 3 8B Reasoning 2512  | Reasoning capable  | BF16      | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-8B-Reasoning-2512)           |
| Ministral 3 14B Base 2512      | Base pre-trained**   | BF16      | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-14B-Base-2512)               |
| Ministral 3 14B Instruct 2512  | Instruct post-trained | FP8    | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512)           |
| **Ministral 3 14B Reasoning 2512** | **Reasoning capable**  | **BF16**      | [Hugging Face](https://huggingface.co/mistralai/Ministral-3-14B-Reasoning-2512)          |

Other formats available [here](https://huggingface.co/collections/mistralai/ministral-3-more).

## Benchmark Results

We compare Ministral 3 to similar sized models.

### Reasoning

| Model                     | AIME25      | AIME24      | GPQA Diamond | LiveCodeBench |
|---------------------------|-------------|-------------|--------------|---------------|
| **Ministral 3 14B**       | <u>0.850</u>| <u>0.898</u>| <u>0.712</u> | <u>0.646</u>  |
| Qwen3-14B (Thinking)      | 0.737       | 0.837       | 0.663        | 0.593         |
|                           |             |             |              |               |
| **Ministral 3 8B**        | 0.787       | <u>0.860</u>| 0.668        | <u>0.616</u>  |
| Qwen3-VL-8B-Thinking      | <u>0.798</u>| <u>0.860</u>| <u>0.671</u> | 0.580         |
|                           |             |             |              |               |
| **Ministral 3 3B**        | <u>0.721</u>| <u>0.775</u>| 0.534        | <u>0.548</u>  |
| Qwen3-VL-4B-Thinking      | 0.697       | 0.729       | <u>0.601</u> | 0.513         |

### Instruct

| Model                     | Arena Hard  | WildBench  | MATH Maj@1  | MM MTBench       |
|---------------------------|-------------|------------|-------------|------------------|
| **Ministral 3 14B**       | <u>0.551</u>| <u>68.5</u>| <u>0.904</u>| <u>8.49</u>      |
| Qwen3 14B (Non-Thinking)  | 0.427       | 65.1       | 0.870       | NOT MULTIMODAL   |
| Gemma3-12B-Instruct       | 0.436       | 63.2       | 0.854       | 6.70             |
|                           |             |            |             |                  |
| **Ministral 3 8B**        | 0.509       | <u>66.8</u>| 0.876       | <u>8.08</u>      |
| Qwen3-VL-8B-Instruct      | <u>0.528</u>| 66.3       | <u>0.946</u>| 8.00             |
|                           |             |            |             |                  |
| **Ministral 3 3B**        | 0.305       | <u>56.8</u>| 0.830       | 7.83             |
| Qwen3-VL-4B-Instruct      | <u>0.438</u>| <u>56.8</u>| <u>0.900</u>| <u>8.01</u>      |
| Qwen3-VL-2B-Instruct      | 0.163       | 42.2       | 0.786       | 6.36             |
| Gemma3-4B-Instruct        | 0.318       | 49.1       | 0.759       | 5.23             |

### Base

| Model               | Multilingual MMLU | MATH CoT 2-Shot | AGIEval 5-shot | MMLU Redux 5-shot | MMLU 5-shot | TriviaQA 5-shot |
|---------------------|-------------------|-----------------|----------------|-------------------|-------------|-----------------|
| **Ministral 3 14B** | 0.742             | <u>0.676</u>    | 0.648          | 0.820             | 0.794       | 0.749           |
| Qwen3 14B Base      | <u>0.754</u>      | 0.620           | <u>0.661</u>   | <u>0.837</u>      | <u>0.804</u>| 0.703           |
| Gemma 3 12B Base    | 0.690             | 0.487           | 0.587          | 0.766             | 0.745       | <u>0.788</u>    |
|                     |                   |                 |                |                   |             |                 |
| **Ministral 3 8B**  | <u>0.706</u>      | <u>0.626</u>    | 0.591          | 0.793             | <u>0.761</u>| <u>0.681</u>    |
| Qwen 3 8B Base      | 0.700             | 0.576           | <u>0.596</u>   | <u>0.794</u>      | 0.760       | 0.639           |
|                     |                   |                 |                |                   |             |                 |
| **Ministral 3 3B**  | 0.652             | <u>0.601</u>    | 0.511          | 0.735             | 0.707       | 0.592           |
| Qwen 3 4B Base      | <u>0.677</u>      | 0.405           | <u>0.570</u>   | <u>0.759</u>      | <u>0.713</u>| 0.530           |
| Gemma 3 4B Base     | 0.516             | 0.294           | 0.430          | 0.626             | 0.589       | <u>0.640</u>    |

## Usage

The model can be used with the following frameworks;
- [`vllm`](https://github.com/vllm-project/vllm): See [here](#vllm)
- [`transformers`](https://github.com/huggingface/transformers): See [here](#transformers)
  
### vLLM

We recommend using this model with [vLLM](https://github.com/vllm-project/vllm).

#### Installation

Make sure to install [`vLLM >= 0.12.0`](https://github.com/vllm-project/vllm/releases/tag/v0.12.0):

```
pip install vllm --upgrade
```

Doing so should automatically install [`mistral_common >= 1.8.6`](https://github.com/mistralai/mistral-common/releases/tag/v1.8.6).

To check:
```
python -c "import mistral_common; print(mistral_common.__version__)"
```

You can also make use of a ready-to-go [docker image](https://github.com/vllm-project/vllm/blob/main/Dockerfile) or on the [docker hub](https://hub.docker.com/layers/vllm/vllm-openai/latest/images/sha256-de9032a92ffea7b5c007dad80b38fd44aac11eddc31c435f8e52f3b7404bbf39).

#### Serve

To fully exploit the `Ministral-3-14B-Reasoning-2512` we recommed using 2xH200 GPUs for deployment due to its large context. However if you don't need a large context, you can fall back to a single GPU.

A simple launch command is:

```bash

vllm serve mistralai/Ministral-3-14B-Reasoning-2512-FP8 \
  --tensor-parallel-size 2 \
  --enable-auto-tool-choice --tool-call-parser mistral \
  --reasoning-parser mistral
```

Key parameter notes:

* enable-auto-tool-choice: Required when enabling tool usage.
* tool-call-parser mistral: Required when enabling tool usage.
* reasoning-parser mistral: Required when enabling reasoning.

Additional flags:

* You can set `--max-model-len` to preserve memory. By default it is set to `262144` which is quite large but not necessary for most scenarios.
* You can set `--max-num-batched-tokens` to balance throughput and latency, higher means higher throughput but higher latency.

#### Usage of the model

Here we asumme that the model `mistralai/Ministral-3-8B-Reasoning-2512` is served and you can ping it to the domain `localhost` with the port `8000` which is the default for vLLM.

<details>
  <summary>Vision Reasoning</summary>

Let's see if the Ministral 3 model knows when to pick a fight !

```python
from typing import Any

from openai import OpenAI
from huggingface_hub import hf_hub_download

# Modify OpenAI's API key and API base to use vLLM's API server.
openai_api_key = "EMPTY"
openai_api_base = "http://localhost:8000/v1"

TEMP = 0.7
TOP_P = 0.95
MAX_TOK = 262144
client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

models = client.models.list()
model = models.data[0].id


def load_system_prompt(repo_id: str, filename: str) -> dict[str, Any]:
    file_path = hf_hub_download(repo_id=repo_id, filename=filename)
    with open(file_path, "r") as file:
        system_prompt = file.read()

    index_begin_think = system_prompt.find("[THINK]")
    index_end_think = system_prompt.find("[/THINK]")

    return {
        "role": "system",
        "content": [
            {"type": "text", "text": system_prompt[:index_begin_think]},
            {
                "type": "thinking",
                "thinking": system_prompt[
                    index_begin_think + len("[THINK]") : index_end_think
                ],
                "closed": True,
            },
            {
                "type": "text",
                "text": system_prompt[index_end_think + len("[/THINK]") :],
            },
        ],
    }


SYSTEM_PROMPT = load_system_prompt(model, "SYSTEM_PROMPT.txt")

image_url = "https://static.wikia.nocookie.net/essentialsdocs/images/7/70/Battle.png/revision/latest?cb=20220523172438"

messages = [
    SYSTEM_PROMPT,
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "What action do you think I should take in this situation? List all the possible actions and explain why you think they are good or bad.",
            },
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
    },
]


stream = client.chat.completions.create(
    model=model,
    messages=messages,
    stream=True,
    temperature=TEMP,
    top_p=TOP_P,
    max_tokens=MAX_TOK,
)

print("client: Start streaming chat completions...:\n")
printed_reasoning_content = False
answer = []

for chunk in stream:
    reasoning_content = None
    content = None
    # Check the content is reasoning_content or content
    if hasattr(chunk.choices[0].delta, "reasoning_content"):
        reasoning_content = chunk.choices[0].delta.reasoning_content
    if hasattr(chunk.choices[0].delta, "content"):
        content = chunk.choices[0].delta.content

    if reasoning_content is not None:
        if not printed_reasoning_content:
            printed_reasoning_content = True
            print("Start reasoning:\n", end="", flush=True)
        print(reasoning_content, end="", flush=True)
    elif content is not None:
        # Extract and print the content
        if not reasoning_content and printed_reasoning_content:
            answer.extend(content)
        print(content, end="", flush=True)

if answer:
    print("\n\n=============\nAnswer\n=============\n")
    print("".join(answer))
else:
    print("\n\n=============\nNo Answer\n=============\n")
    print(
        "No answer was generated by the model, probably because the maximum number of tokens was reached."
    )
```

Now we'll make it compute some maths !

```python
from typing import Any

from openai import OpenAI
from huggingface_hub import hf_hub_download

# Modify OpenAI's API key and API base to use vLLM's API server.
openai_api_key = "EMPTY"
openai_api_base = "http://localhost:8000/v1"

TEMP = 0.7
TOP_P = 0.95
MAX_TOK = 262144
client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

models = client.models.list()
model = models.data[0].id


def load_system_prompt(repo_id: str, filename: str) -> dict[str, Any]:
    file_path = hf_hub_download(repo_id=repo_id, filename=filename)
    with open(file_path, "r") as file:
        system_prompt = file.read()

    index_begin_think = system_prompt.find("[THINK]")
    index_end_think = system_prompt.find("[/THINK]")

    return {
        "role": "system",
        "content": [
            {"type": "text", "text": system_prompt[:index_begin_think]},
            {
                "type": "thinking",
                "thinking": system_prompt[
                    index_begin_think + len("[THINK]") : index_end_think
                ],
                "closed": True,
            },
            {
                "type": "text",
                "text": system_prompt[index_end_think + len("[/THINK]") :],
            },
        ],
    }


SYSTEM_PROMPT = load_system_prompt(model, "SYSTEM_PROMPT.txt")

image_url = "https://i.ytimg.com/vi/5Y3xLHeyKZU/hqdefault.jpg"

messages = [
    SYSTEM_PROMPT,
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Solve the equations. If they contain only numbers, use your calculator, else only think. Answer in the language of the image.",
            },
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
    },
]

stream = client.chat.completions.create(
    model=model,
    messages=messages,
    stream=True,
    temperature=TEMP,
    top_p=TOP_P,
    max_tokens=MAX_TOK,
)

print("client: Start streaming chat completions...:\n")
printed_reasoning_content = False
answer = []

for chunk in stream:
    reasoning_content = None
    content = None
    # Check the content is reasoning_content or content
    if hasattr(chunk.choices[0].delta, "reasoning_content"):
        reasoning_content = chunk.choices[0].delta.reasoning_content
    if hasattr(chunk.choices[0].delta, "content"):
        content = chunk.choices[0].delta.content

    if reasoning_content is not None:
        if not printed_reasoning_content:
            printed_reasoning_content = True
            print("Start reasoning:\n", end="", flush=True)
        print(reasoning_content, end="", flush=True)
    if content is not None:
        # Extract and print the content
        if not reasoning_content and printed_reasoning_content:
            answer.extend(content)
        print(content, end="", flush=True)

if answer:
    print("\n\n=============\nAnswer\n=============\n")
    print("".join(answer))
else:
    print("\n\n=============\nNo Answer\n=============\n")
    print(
        "No answer was generated by the model, probably because the maximum number of tokens was reached."
    )
```

</details>

<details>
  <summary>Text-Only Request</summary>

Let's do more maths and leave it up to the model to figure out how to achieve a result.

```python
from typing import Any
from openai import OpenAI
from huggingface_hub import hf_hub_download

# Modify OpenAI's API key and API base to use vLLM's API server.
openai_api_key = "EMPTY"
openai_api_base = "http://localhost:8000/v1"

TEMP = 0.7
TOP_P = 0.95
MAX_TOK = 262144
client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

models = client.models.list()
model = models.data[0].id


def load_system_prompt(repo_id: str, filename: str) -> dict[str, Any]:
    file_path = hf_hub_download(repo_id=repo_id, filename=filename)
    with open(file_path, "r") as file:
        system_prompt = file.read()

    index_begin_think = system_prompt.find("[THINK]")
    index_end_think = system_prompt.find("[/THINK]")

    return {
        "role": "system",
        "content": [
            {"type": "text", "text": system_prompt[:index_begin_think]},
            {
                "type": "thinking",
                "thinking": system_prompt[
                    index_begin_think + len("[THINK]") : index_end_think
                ],
                "closed": True,
            },
            {
                "type": "text",
                "text": system_prompt[index_end_think + len("[/THINK]") :],
            },
        ],
    }


SYSTEM_PROMPT = load_system_prompt(model, "SYSTEM_PROMPT.txt")

query = "Use each number in 2,5,6,3 exactly once, along with any combination of +, -, ×, ÷ (and parentheses for grouping), to make the number 24."

messages = [
    SYSTEM_PROMPT,
    {"role": "user", "content": query}
]
stream = client.chat.completions.create(
  model=model,
  messages=messages,
  stream=True,
  temperature=TEMP,
  top_p=TOP_P,
  max_tokens=MAX_TOK,
)

print("client: Start streaming chat completions...:\n")
printed_reasoning_content = False
answer = []

for chunk in stream:
    reasoning_content = None
    content = None
    # Check the content is reasoning_content or content
    if hasattr(chunk.choices[0].delta, "reasoning_content"):
        reasoning_content = chunk.choices[0].delta.reasoning_content
    if hasattr(chunk.choices[0].delta, "content"):
        content = chunk.choices[0].delta.content

    if reasoning_content is not None:
        if not printed_reasoning_content:
            printed_reasoning_content = True
            print("Start reasoning:\n", end="", flush=True)
        print(reasoning_content, end="", flush=True)
    if content is not None:
        # Extract and print the content
        if not reasoning_content and printed_reasoning_content:
            answer.extend(content)
        print(content, end="", flush=True)

if answer:
    print("\n\n=============\nAnswer\n=============\n")
    print("".join(answer))
else:
    print("\n\n=============\nNo Answer\n=============\n")
    print("No answer was generated by the model, probably because the maximum number of tokens was reached.")
```

</details>

### Transformers

You can also use Ministral 3 3B Reasoning 2512 with `Transformers` !
Make sure to install `Transformers` from its first v5 release candidate or from "main":

```
pip install transformers==5.0.0rc0
```

To make the best use of our model with `Transformers` make sure to have [installed](https://github.com/mistralai/mistral-common) `mistral-common >= 1.8.6` to use our tokenizer.

```bash
pip install mistral-common --upgrade
```

Then load our tokenizer along with the model and generate:

<details>
  <summary>Python snippet</summary>

```python
import torch
from transformers import Mistral3ForConditionalGeneration, MistralCommonBackend

model_id = "mistralai/Ministral-3-14B-Reasoning-2512"

tokenizer = MistralCommonBackend.from_pretrained(model_id)
model = Mistral3ForConditionalGeneration.from_pretrained(
    model_id, torch_dtype=torch.bfloat16, device_map="auto"
)

image_url = "https://static.wikia.nocookie.net/essentialsdocs/images/7/70/Battle.png/revision/latest?cb=20220523172438"

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "What action do you think I should take in this situation? List all the possible actions and explain why you think they are good or bad.",
            },
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
    },
]

tokenized = tokenizer.apply_chat_template(messages, return_tensors="pt", return_dict=True)

tokenized["input_ids"] = tokenized["input_ids"].to(device="cuda")
tokenized["pixel_values"] = tokenized["pixel_values"].to(dtype=torch.bfloat16, device="cuda")
image_sizes = [tokenized["pixel_values"].shape[-2:]]

output = model.generate(
    **tokenized,
    image_sizes=image_sizes,
    max_new_tokens=8092,
)[0]

decoded_output = tokenizer.decode(output[len(tokenized["input_ids"][0]):])
print(decoded_output)
```

</details>

## License

This model is licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0.txt).

*You must not use this model in a manner that infringes, misappropriates, or otherwise violates any third party’s rights, including intellectual property rights.*