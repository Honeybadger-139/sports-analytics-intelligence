# LLM Fine-tuning: LoRA / QLoRA Deep Dive
> Module 6.6 — SCR-325 | Sports Analytics Intelligence Platform

---

## What Is It?

**Fine-tuning** adapts a pre-trained language model to a specific domain by continuing training on domain-relevant data. **LoRA (Low-Rank Adaptation)** is a parameter-efficient fine-tuning (PEFT) technique that trains a tiny fraction of parameters while keeping the base model frozen.

**QLoRA** combines LoRA with **4-bit quantisation** (via bitsandbytes), cutting VRAM requirements in half — enabling fine-tuning on a single consumer GPU.

---

## Why Does It Matter?

Pre-trained LLMs (Gemini, GPT-4, Phi-3) are general-purpose. They lack:
- Exact knowledge of our platform's metrics (e.g., "What is our eFG% definition?")
- Precise recall of historical NBA facts not in training data
- Domain-specific language (e.g., team abbreviations, advanced stat abbreviations)

Fine-tuning on a Q&A dataset built from our live database teaches the model **facts that are specific to our application** — something RAG alone cannot fully solve (RAG retrieves, it doesn't teach the model to reason with domain concepts fluently).

---

## How Does It Work?

### Full Fine-tuning vs LoRA

| Aspect | Full Fine-tuning | LoRA |
|--------|-----------------|------|
| Parameters updated | All ~3.8B | ~5M (0.13%) |
| VRAM needed | ~16GB | ~8GB (4-bit: ~4GB) |
| Training time (T4) | Hours | 20-30 min |
| Cost (GCP T4) | ~$500 | ~$2 |
| Catastrophic forgetting | High risk | Minimal (base frozen) |

### The LoRA Math (Intuition)

Each attention weight matrix `W` is `d×d` (e.g., 4096×4096). Full fine-tuning updates all `d²` values.

LoRA instead learns two small matrices: `A (d×r)` and `B (r×d)` where `r << d` (we use `r=16`).

```
Updated weight = W + ΔW
ΔW = A · B   (rank-r decomposition)
```

For r=16, d=4096: `A` has 65,536 params, `B` has 65,536. Together: 131K per layer vs 16.7M for full. **You're updating 1 in 800 parameters.**

### 4-bit Quantisation (QLoRA)

The **base model** is loaded in 4-bit NF4 (normal float 4) format instead of 16-bit. This halves VRAM from ~8GB to ~4GB. The **LoRA adapters themselves stay in bfloat16** for training stability — you can't backprop through 4-bit precision.

```python
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",           # optimal for normally-distributed weights
    bnb_4bit_use_double_quant=True,       # saves another 0.4 bits per param
    bnb_4bit_compute_dtype=torch.bfloat16 # compute in bfloat16, store in 4-bit
)
```

### Target Modules

We apply LoRA to all 4 attention projection matrices: `q_proj`, `k_proj`, `v_proj`, `o_proj`. This covers the full self-attention mechanism. Skipping FFN layers is a common trade-off (they add more params for marginal gains on Q&A tasks).

### Training Format (ChatML)

Phi-3-mini was trained with the ChatML template, so we fine-tune with the same format:

```
<|user|>
What is eFG%?<|end|>
<|assistant|>
Effective Field Goal percentage adjusts for the fact that 3-point shots are worth 1.5× a 2-pointer.
Formula: (FGM + 0.5 × 3PM) / FGA. League average is ~54%.<|end|>
```

This is critical — using the wrong format at fine-tuning time causes the model to hallucinate in the wrong template at inference time.

---

## Dataset Generation Strategy

We generate synthetic Q&A pairs from our live NBA PostgreSQL database:

| Category | % of Dataset | Example |
|----------|-------------|---------|
| Team stats | 50% | "What is the Lakers' win rate this season?" |
| Game predictions | 20% | "Who is favoured in Lakers vs Celtics tonight?" |
| Analytics concepts | 10% | "Explain Net Rating in plain English" |
| Trend analysis | 10% | "Which teams are on a hot streak?" |
| Augmented (paraphrase) | 10% | Prefix variations of the above |

Target: **5,000 to 10,000 pairs**. Below 5K, the model overfits. Above 10K with synthetic data, you get dataset noise compounding.

**Why synthetic data?**

We don't have real user conversations (cold-start problem). Template-based generation from a live database ensures factual accuracy — the answers come from SQL queries, not hallucination. The risk: narrow template coverage. Mitigation: augmentation + concept templates that cover open-ended questions.

---

## LLM Router: When to Use Fine-tuned vs Base

```
Query → LLMRouter → fine-tuned Phi-3-mini   (sports facts, stats, definitions)
                  → base Gemini              (complex reasoning, multi-step math)
```

The fine-tuned model excels at **factual recall** but is 3.8B params — it can't match Gemini for complex multi-step reasoning. The router picks the right tool for the query:

- "What is eFG%?" → fine-tuned (trained on exact definition)
- "Compare the Lakers and Celtics offensive strategies and predict who wins in 7 games" → base LLM (complex reasoning)

In production, you'd train a lightweight BERT classifier to route. We use keyword heuristics for now (fast, interpretable, good enough for demo).

---

## Evaluation

### ROUGE-L (Fluency)

Measures longest common subsequence between model output and reference answer. Score >0.4 is acceptable for instruction tuning. ROUGE-L is necessary but not sufficient — a model can score high ROUGE by repeating words without accuracy.

### Domain Fact Accuracy (Custom)

For each answer with a numerical claim (e.g., "Lakers win rate is 62%"), verify against the database. This is the metric that actually matters for our use case.

```
fact_accuracy = correct_numerical_claims / total_numerical_claims
```

Target: >85% fact accuracy on the held-out test set.

### Perplexity on Domain Corpus

Lower perplexity after fine-tuning vs base model confirms the model has learned domain language patterns.

---

## When To Use Fine-tuning vs Alternatives

| Approach | Cost | Latency | Freshness | Best For |
|----------|------|---------|-----------|---------|
| RAG | Low | Medium | Real-time | Dynamic facts (today's scores) |
| Fine-tuning | Medium | Low | Static | Domain concepts, terminology, reasoning patterns |
| RAG + Fine-tuning | High | Medium | Real-time | Best accuracy (our target architecture) |
| Prompt engineering | Zero | Low | Real-time | Simple tasks, GPT-4 class models |

**Key insight**: RAG and fine-tuning are complementary, not competing:
- **RAG** handles *recent, specific facts* (today's game scores, current standings)
- **Fine-tuning** handles *stable domain knowledge* (what eFG% means, how ORTG is calculated, how to interpret momentum)

---

## Architecture in Our Platform

```
User query
    │
    ▼
LLMRouter ──────────────────────────────────────────────┐
    │ sports keywords matched                            │ complex reasoning
    ▼                                                   ▼
Fine-tuned Phi-3-mini                            Base Gemini (via LangGraph)
(models/phi3_sports_adapter/)                    (RAG + PostgreSQL tools)
    │
    ▼
Response with sports-domain accuracy
```

The adapter weights (50MB PEFT checkpoint) are loaded on top of the shared 4-bit base model. In production, **one base model serves thousands of domain adapters** — this is how multi-tenant LLM serving works (S-LoRA, Punica).

---

## Files Built

| File | Purpose |
|------|---------|
| `backend/src/models/dataset_generator.py` | Template Q&A generation from live DB |
| `backend/src/models/lora_trainer.py` | QLoRA fine-tuning pipeline + LLMRouter |
| `backend/requirements.txt` | Fine-tuning deps (commented for local-only install) |

---

## Interview Questions

### Q: What is LoRA and why did you use it instead of full fine-tuning?

**Junior answer**: "LoRA fine-tunes a small portion of the model weights."

**Senior answer**: "LoRA adds trainable low-rank matrices (A·B where rank=16) to each attention projection layer, updating only 5M of 3.8B parameters — 0.13%. This means I can fine-tune Phi-3-mini on a single T4 GPU in 30 minutes for ~$2 instead of $500 for full fine-tuning on an A100. Combined with 4-bit QLoRA quantisation (bitsandbytes NF4), I fit the full pipeline in 4GB VRAM. The adapter weights are 50MB — you can version, share, and hot-swap them without reloading the base model."

### Q: How do you evaluate whether fine-tuning actually helped?

**Junior answer**: "I check the training loss curve."

**Senior answer**: "Training loss tells you the model is learning, not that it's learning the right things. I use three metrics: ROUGE-L for fluency (>0.4 baseline), custom fact accuracy checking numerical claims against the database (>85% target), and perplexity on a held-out domain corpus. I also compare side-by-side outputs on 50 gold-standard questions rated by domain knowledge. Loss alone is misleading — a model can memorise training samples with near-zero loss and still hallucinate on unseen questions."

### Q: When would you use fine-tuning vs RAG vs prompt engineering?

**Senior answer**: "It's not either/or. RAG handles dynamic, recent facts that change daily (today's game scores, current standings) — you can't fine-tune on data that doesn't exist yet. Fine-tuning handles stable domain knowledge (metric definitions, reasoning patterns, terminology) that RAG retrieval is unreliable for because it's scattered across many documents. Prompt engineering works when you have a GPT-4 class model and the task is simple enough to solve with better prompts — no training needed. For our platform, we combine all three: fine-tuned base model + RAG for retrieval + structured prompts for formatting."

### Q: What is catastrophic forgetting and how does LoRA prevent it?

**Senior answer**: "Catastrophic forgetting is when a neural network forgets previously learned knowledge when trained on new data — the gradient updates for domain fine-tuning overwrite the weights that encode general language understanding. LoRA prevents this by keeping the base weights completely frozen and only training the adapter matrices A and B. Since W is never updated, the model retains all its general capabilities. The adapter adds domain knowledge without destroying the foundation. This is also why LoRA adapters are composable — you can stack multiple adapters or switch between them."

### Q: What is QLoRA?

**Senior answer**: "QLoRA = 4-bit Quantised LoRA. The base model is loaded in 4-bit NF4 precision (cutting VRAM from 8GB to 4GB for Phi-3-mini), while LoRA adapters are maintained in bfloat16 for gradient stability. The key insight from the QLoRA paper (Dettmers et al., 2023) is that you can quantise the frozen base weights aggressively without affecting adapter training quality — because gradients only flow through the adapters, not the quantised base. This enabled fine-tuning 65B parameter models on a single GPU for the first time."

---

## Awe Moment Insights

1. **The sharing insight**: The same 4-bit Phi-3-mini base (4GB) can host 1000 different 50MB adapters on a single server. You load the base once and hot-swap adapters per tenant — this is how companies like Predibase serve multi-tenant fine-tuned models at 1/100th the cost of running separate model instances.

2. **LoRA rank controls the knowledge capacity**: Rank=16 is the industry sweet spot for instruction tuning. Rank=1 is almost no capacity (barely changes behaviour). Rank=256 approaches full fine-tuning cost/performance. The rank-to-quality curve is logarithmic — most gains come from r=4 to r=32.

3. **Fine-tuning doesn't inject new facts reliably**: Fine-tuning is great for *style, format, and reasoning patterns* — not for memorising new facts (e.g., "The Lakers won 52 games in 2024"). Facts are better served via RAG. Fine-tuning a model to recall specific game scores often leads to hallucination of wrong scores. The right split: fine-tune for "how to reason about sports", RAG for "what actually happened."
