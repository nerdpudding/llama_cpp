Comparison to get an idea if a DGX Sprak would be a good buy in my case/ (Tests are with single tasks, NOT Concurrent!!)
==========================
TEST 1:
ministral-3 --> ministral-3:8b-instruct-2512-q4_K_M (6GB in size and this is a MoE model so a Sparse model, NOT a Dense model!)

ollama run ministral-3:8b-instruct-2512-q4_K_M --verbose (to get stats)
--> try a prompt:

https://youtu.be/PhJnZnQuuT0 --> tested with DGX Spark, Jetson Thor and M4 Pro Mac mini:

Notes: 
- token generation (eval rate) --> limited by memory bandwidth 
- prompt eval rate --> does prompt processing, computation (not limited my memory bandwidth)

dgx spark --> 7086 MiB vram | 70 watt --> (eval rate) 34.97 tokens/sec  --> (prompt eval rate) 2406.82 tokens/sec
jetson    --> ?	   MiB vram | 90 watt --> (eval rate) 30.82 tokens/sec  --> (prompt eval rate) 1037.67 tokens/sec
mac mini  --> ?    MiB ram | 140 watt --> (eval rate) 39.76 tokens/sec  --> (prompt eval rate) 353.25 tokens/sec
===
MY CURRENT DESKTOP:
RTX4090   only --> MiB vram | watt--> (eval rate) tokens/sec --> (prompt eval rate) tokens/sec
RTX5070ti only --> MiB vram | watt--> (eval rate) tokens/sec --> (prompt eval rate) tokens/sec

+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
TEST 2:
Tested with ollama and this model:
- LLAMA 3.3 70B (Q4_K_M is 43GB in Size and this is a MoE model so a Dense model, NOT a Sparse model!)

ollama run ollama run llama3.3:70b-instruct-q4_K_M --verbose (to get stats) (Q4_K_M)
--> try a prompt:

Notes: 
- token generation (eval rate) --> limited by memory bandwidth (this is during decode when new tokens (answer) is generated
- prompt eval rate --> does prompt processing, computation (not limited my memory bandwidth, this includes entire prompt, like system prompt, context of chat etc, need to be processed in first stage)

dgx spark --> 42318 MiB vram | 150 watt --> (eval rate) 4.46 tokens/sec  --> (prompt eval rate) 283 tokens/sec
jetson    --> ?	    MiB vram | 100 watt --> (eval rate) 4.61 tokens/sec  --> (prompt eval rate) 104 tokens/sec
mac mini  --> 56.87 GB ram | 75 watt --> (eval rate)  5.43 tokens/sec  --> (prompt eval rate)  34 tokens/sec
===
MY CURRENT DESKTOP:
NEEDS OFFLOADING OVER DEVICES:
RTX4090 + RTX5070ti + a little CPU  --> MiB vram | watt--> (eval rate) tokens/sec --> (prompt eval rate) tokens/sec

++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
TEST 3:
Tested with this model:

GPT-OSS-120B-->  ( in size and this is a MoE model so a Sparse model, NOT a Dense model! BUT a FP4 Model!!!)

https://youtu.be/PhJnZnQuuT0 --> tested with DGX Spark, Jetson Thor and M4 Pro Mac mini:

Notes: 
- token generation (eval rate) --> limited by memory bandwidth 
- prompt eval rate --> does prompt processing, computation (not limited my memory bandwidth)

dgx spark --> (eval rate) 52.77 tokens/sec  --> (prompt eval rate) 977 tokens/sec
jetson    --> (eval rate) 34.97 tokens/sec  --> (prompt eval rate) 464 tokens/sec
mac mini  --> Not possible !! (64 GB max ram)
===
MY CURRENT DESKTOP:
NEEDS OFFLOADING OVER DEVICES:
RTX4090 + RTX5070ti + a little CPU  --> MiB vram | watt--> (eval rate) tokens/sec --> (prompt eval rate) tokens/sec


 

