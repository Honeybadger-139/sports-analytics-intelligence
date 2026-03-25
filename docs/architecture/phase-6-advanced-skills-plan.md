# Phase 6: Advanced Skills Implementation Plan

> **Goal**: Add 8 advanced skill modules to the Sports Analytics Intelligence Platform, targeting Data Scientist / Applied Scientist role readiness for 2026.
>
> **Principle**: Every module integrates naturally into the NBA analytics domain — no standalone scripts. Each module is a real feature, not a tutorial exercise.
>
> **Linear Master**: [SCR-307](https://linear.app/scrape-project/issue/SCR-307)
>
> **Last updated**: 2026-03-25

---

## Linear Issue Tracker

| # | Module | Linear ID | Status | Priority | Depends On |
|---|--------|-----------|--------|----------|------------|
| 6.1 | LangChain/LangGraph Enhancement | [SCR-313](https://linear.app/scrape-project/issue/SCR-313) | Backlog | High | None — **START HERE** |
| 6.2 | PyTorch Neural Network | [SCR-308](https://linear.app/scrape-project/issue/SCR-308) | Backlog | High | None |
| 6.3 | Multi-Agent System | [SCR-309](https://linear.app/scrape-project/issue/SCR-309) | Backlog | Medium | 6.1 |
| 6.4 | Statistics (A/B, Bayesian, Causal) | [SCR-310](https://linear.app/scrape-project/issue/SCR-310) | Backlog | Medium | None |
| 6.5 | Time-Series Forecasting | [SCR-311](https://linear.app/scrape-project/issue/SCR-311) | Backlog | Medium | 6.2 |
| 6.6 | LLM Fine-tuning (LoRA/PEFT) | [SCR-312](https://linear.app/scrape-project/issue/SCR-312) | Backlog | Medium | 6.2 |
| 6.7 | NLP Engine | [SCR-314](https://linear.app/scrape-project/issue/SCR-314) | **DEFERRED** | Low | None |
| 6.8 | Knowledge Graphs (Neo4j) | [SCR-315](https://linear.app/scrape-project/issue/SCR-315) | **DEFERRED** | Low | None |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SPORTS ANALYTICS INTELLIGENCE — PHASE 6               │
│                                                                          │
│  ┌── ACTIVE WAVE (implement now) ──────────────────────────────────┐    │
│  │                                                                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │    │
│  │  │  6.1          │  │  6.2          │  │  6.4          │          │    │
│  │  │  LangChain    │  │  PyTorch      │  │  Statistics    │          │    │
│  │  │  Enhancement  │  │  Neural Nets  │  │  A/B+Bayesian  │          │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────────┘          │    │
│  │         │                  │                                     │    │
│  │  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────────────┐          │    │
│  │  │  6.3          │  │  6.5          │  │  6.6          │          │    │
│  │  │  Multi-Agent  │  │  Time-Series  │  │  Fine-tuning  │          │    │
│  │  │  System       │  │  Forecasting  │  │  LoRA/PEFT    │          │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌── DEFERRED WAVE (later) ────────────────────────────────────────┐    │
│  │  ┌──────────────┐  ┌──────────────┐                             │    │
│  │  │  6.7          │  │  6.8          │                             │    │
│  │  │  NLP Engine   │  │  Knowledge    │                             │    │
│  │  │  Sentiment    │  │  Graphs Neo4j │                             │    │
│  │  └──────────────┘  └──────────────┘                             │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                   EXISTING PLATFORM LAYERS                        │   │
│  │  FastAPI · PostgreSQL · pgvector · Vertex AI · Cloud Run · React  │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Dependency Graph & Build Order

```
6.1: LangChain ────────────→ 6.3: Multi-Agent (needs LangChain tools)
                                    │
6.2: PyTorch ──────────────→ 6.5: Time-Series (needs entity embeddings)
                     │
                     └──────→ 6.6: Fine-tuning (needs PyTorch familiarity)

6.4: Statistics ──── (independent, can start anytime)

DEFERRED:
6.7: NLP Engine ──── (activate later; enriches Multi-Agent + Fine-tuning)
6.8: Knowledge Graphs ── (activate later; independent)
```

**Execution order (Active Wave)**:
1. **6.1 LangChain** (SCR-313) → foundational for Multi-Agent
2. **6.2 PyTorch** (SCR-308) → foundational for Time-Series + Fine-tuning
3. **6.3 Multi-Agent** (SCR-309) → depends on 6.1
4. **6.4 Statistics** (SCR-310) → independent, high interview value
5. **6.5 Time-Series** (SCR-311) → depends on 6.2 entity embeddings
6. **6.6 Fine-tuning** (SCR-312) → capstone, depends on 6.2

**Note**: 6.1 and 6.2 can be built in parallel (no dependency between them).
6.4 Statistics is independent and can be interleaved anywhere.

---

## Module 1: LangChain / LangGraph Enhancement

### WHAT & WHY

The project already has `langgraph_chat_service.py` with a basic graph workflow and `langchain==0.2.16` in requirements. But the current usage is shallow — it wraps legacy ChatService calls in LangGraph nodes without using LangChain's tool abstraction, memory, structured output, or chain composition.

**Why it matters**: 50% of DS/AI jobs on LinkedIn explicitly require LangChain/LangGraph. The difference between "I imported LangChain" and "I built a tool-calling agent with memory and structured output" is the difference between a rejected resume and an offer.

### APPROACH COMPARISON

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| A. Keep direct Gemini calls, add LangChain wrappers | Minimal change, safe | Superficial — doesn't demonstrate real LangChain skill | ❌ |
| B. Replace chatbot core with LangChain chains + tools | Deep skill signal, production-grade | More refactoring, migration risk | ✅ |
| C. Build separate LangChain demo app | Easy to implement | Doesn't integrate with platform, feels like a toy | ❌ |

**Choice: B** — Refactor the LangGraph service to use proper LangChain primitives.

### WHAT TO BUILD

**1.1 — LangChain Tools (wrap existing capabilities)**
```
File: backend/src/intelligence/langchain_tools.py

Tools to create:
  - SQLQueryTool      → wraps feature_store.py SQL execution
  - PredictionTool    → wraps predictor.py model inference
  - RAGRetrieverTool  → wraps vector_store.py similarity search
  - TeamStatsTool     → wraps routes.py team stats queries
  - ExplainabilityTool → wraps explainability.py SHAP values
```

**1.2 — Structured Output with Pydantic**
```
File: backend/src/intelligence/output_schemas.py

Schemas:
  - GameAnalysis(teams, prediction, confidence, key_factors, narrative)
  - StatsSummary(metric_name, value, trend, context)
  - RAGResponse(answer, citations, confidence, source_quality)
```

**1.3 — Conversation Memory**
```
File: backend/src/intelligence/memory.py

- PostgreSQL-backed ConversationBufferMemory
- Stores chat history per session in DB (not just in-memory)
- Enables "What did I ask you earlier about the Lakers?"
```

**1.4 — Refactored LangGraph Workflow**
```
File: backend/src/intelligence/langgraph_chat_service.py (refactor)

New graph:
  policy_gate → intent_router → tool_selector → [tool execution] →
  structured_output → quality_gate → memory_update → response
```

### FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `backend/src/intelligence/langchain_tools.py` | **CREATE** — 5 LangChain tools |
| `backend/src/intelligence/output_schemas.py` | **CREATE** — Pydantic structured output schemas |
| `backend/src/intelligence/memory.py` | **CREATE** — PostgreSQL-backed conversation memory |
| `backend/src/intelligence/langgraph_chat_service.py` | **MODIFY** — Refactor to use tools + memory |
| `backend/src/api/chat_routes.py` | **MODIFY** — Pass session_id for memory |
| `alembic/versions/0003_add_chat_memory_table.py` | **CREATE** — Migration for conversation memory |
| `backend/tests/test_langchain_tools.py` | **CREATE** — Tool unit tests |
| `docs/learning-notes/langchain-langgraph-deep-dive.md` | **CREATE** — Learning notes |

### DEPENDENCIES TO ADD
```
langchain-google-genai>=2.0.0    # Google Gemini LangChain integration
langchain-community>=0.2.0       # Community tools and utilities
```

### INTERVIEW ANGLES

- **Junior**: "I used LangChain to call an LLM"
- **Senior**: "I designed a LangGraph state machine with 5 tool-calling nodes, PostgreSQL-backed conversation memory, and Pydantic-validated structured outputs. The tool abstraction lets me swap any capability (SQL, prediction, RAG) without changing the orchestration logic."
- **Awe moment**: "I wrapped existing production services as LangChain tools — this means the chatbot uses the same prediction engine as the API, not a separate model. Zero capability duplication."

---

## Module 2: PyTorch Neural Network Baseline

### WHAT & WHY

The trainer currently has Logistic Regression → XGBoost → LightGBM → Ensemble. All are tree-based or linear. 65% of DS jobs require PyTorch/TensorFlow. Adding a neural network model demonstrates you understand **when trees beat NNs** (tabular data) and **when NNs are appropriate** (embeddings, sequence data).

### APPROACH COMPARISON

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| A. Simple MLP for game prediction | Clean comparison with trees, shows tabular NN pattern | Won't beat trees on this data (expected & educational) | ✅ |
| B. LSTM on game sequences | Time-series angle, more impressive | More complex, overlaps with Module 8 | ❌ for now |
| C. Graph Neural Network on team-player data | Cutting-edge | Too complex for baseline, overlaps Module 7 | ❌ for now |

**Choice: A** — MLP first. The point is showing the trees-vs-NNs trade-off conversation. B and C come later in Modules 7/8.

### WHAT TO BUILD

**2.1 — PyTorch MLP Model**
```
File: backend/src/models/pytorch_model.py

class NBAGamePredictor(nn.Module):
    - Input: 24 features (same FEATURE_COLUMNS as tree models)
    - Architecture: 24 → 64 → 32 → 16 → 1 (sigmoid)
    - Dropout: 0.3 per hidden layer
    - BatchNorm between layers
    - Binary cross-entropy loss
    - Adam optimizer with learning rate scheduler
```

**2.2 — PyTorch Training Pipeline**
```
File: backend/src/models/pytorch_trainer.py

class PyTorchTrainer:
    - Custom Dataset class for NBA features
    - TimeSeriesSplit-aware data loader (same split strategy as trees)
    - Early stopping with patience
    - Learning rate warm-up + cosine annealing
    - TensorBoard logging (optional)
    - Model export: .pt (native) + ONNX conversion
```

**2.3 — Integration into Existing Trainer**
```
File: backend/src/models/trainer.py (MODIFY)

- Add "pytorch_mlp" to MODEL_REGISTRY
- Train alongside XGBoost/LightGBM/LogReg
- Include in ensemble with learned weight
- Compare metrics: accuracy, AUC, Brier score, log loss
- Log to Vertex AI Experiments
```

**2.4 — Feature Embedding Layer (bonus)**
```
File: backend/src/models/feature_embeddings.py

- Entity embeddings for categorical features (team_id, is_home)
- Continuous feature normalization layer
- Reusable embedding module for Module 8 (LSTM) later
```

### FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `backend/src/models/pytorch_model.py` | **CREATE** — MLP architecture |
| `backend/src/models/pytorch_trainer.py` | **CREATE** — Training pipeline with early stopping |
| `backend/src/models/feature_embeddings.py` | **CREATE** — Entity embeddings for categorical features |
| `backend/src/models/trainer.py` | **MODIFY** — Add PyTorch to model registry + ensemble |
| `backend/src/models/predictor.py` | **MODIFY** — Load and serve PyTorch models |
| `backend/tests/test_pytorch_model.py` | **CREATE** — Model + training tests |
| `docs/learning-notes/pytorch-tabular-deep-dive.md` | **CREATE** — Learning notes |

### DEPENDENCIES TO ADD
```
torch>=2.2.0
torchvision>=0.17.0    # For transforms (optional)
tensorboard>=2.16.0    # Training visualization
```

### INTERVIEW ANGLES

- **Junior**: "I used PyTorch because it's popular"
- **Senior**: "I deliberately added a neural network baseline to our ensemble. On tabular data with 24 features, XGBoost outperformed the MLP by 3.2% AUC — consistent with the Grinsztajn 2022 NeurIPS benchmark. But the MLP's entity embeddings for team_id captured latent team representations that improved the ensemble by 0.8% when combined."
- **Awe moment**: "The MLP alone is weaker, but its learned team embeddings become features for the tree models — creating a 'neural embedding → tree model' pipeline that captures both representation learning and tabular structure."

---

## Module 3: Agentic AI — Multi-Agent System

### WHAT & WHY

Current chatbot is a single LangGraph workflow with hardcoded routing. 35% of DS jobs now list "Agentic AI" or "multi-agent". Building a supervisor + specialist agent architecture demonstrates orchestration thinking.

### APPROACH COMPARISON

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| A. LangGraph multi-agent with supervisor | Native to existing stack, clean state management | Requires Module 1 completion first | ✅ |
| B. AutoGen/CrewAI framework | Trendy, easier setup | Adds heavy dependency, less control, harder to debug | ❌ |
| C. Custom agent loop with function calling | Maximum control | Reinvents the wheel | ❌ |

**Choice: A** — LangGraph multi-agent. Extends existing graph, stays in the LangChain ecosystem.

### ARCHITECTURE

```
                    ┌─────────────┐
                    │  Supervisor  │ ← Decides which agent(s) to invoke
                    │  Agent       │ ← Handles multi-turn coordination
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
    │  Stats     │   │  News      │   │  Prediction│
    │  Agent     │   │  Agent     │   │  Agent     │
    │            │   │            │   │            │
    │ SQL query  │   │ RAG search │   │ Model      │
    │ Feature    │   │ Sentiment  │   │ inference  │
    │ store      │   │ analysis   │   │ SHAP       │
    └───────────┘   └───────────┘   └───────────┘
```

### WHAT TO BUILD

**3.1 — Specialist Agents**
```
File: backend/src/intelligence/agents/stats_agent.py
  - Owns: SQL queries, team/player stats, standings, feature store
  - Tools: SQLQueryTool, TeamStatsTool (from Module 1)

File: backend/src/intelligence/agents/news_agent.py
  - Owns: RAG retrieval, news summarization, sentiment context
  - Tools: RAGRetrieverTool, SentimentTool (from Module 5)

File: backend/src/intelligence/agents/prediction_agent.py
  - Owns: Model inference, SHAP explanations, confidence scoring
  - Tools: PredictionTool, ExplainabilityTool (from Module 1)
```

**3.2 — Supervisor Agent**
```
File: backend/src/intelligence/agents/supervisor.py
  - Intent decomposition: complex queries → subtask list
  - Agent selection: which specialist(s) to invoke
  - Response synthesis: combine multi-agent outputs
  - Conflict resolution: when agents disagree
```

**3.3 — LangGraph Multi-Agent Graph**
```
File: backend/src/intelligence/multi_agent_graph.py
  - State: shared context across agents
  - Conditional edges: supervisor → specialist routing
  - Parallel execution: stats + news agents can run concurrently
  - Human-in-the-loop: optional confirmation for high-stakes queries
```

### FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `backend/src/intelligence/agents/__init__.py` | **CREATE** — Agent module |
| `backend/src/intelligence/agents/stats_agent.py` | **CREATE** — SQL/stats specialist |
| `backend/src/intelligence/agents/news_agent.py` | **CREATE** — RAG/news specialist |
| `backend/src/intelligence/agents/prediction_agent.py` | **CREATE** — Model inference specialist |
| `backend/src/intelligence/agents/supervisor.py` | **CREATE** — Orchestration agent |
| `backend/src/intelligence/multi_agent_graph.py` | **CREATE** — LangGraph graph definition |
| `backend/src/api/chat_routes.py` | **MODIFY** — Route to multi-agent graph |
| `frontend/src/components/Chatbot/AgentTrace.tsx` | **CREATE** — Show which agents were invoked |
| `backend/tests/test_multi_agent.py` | **CREATE** — Agent orchestration tests |
| `docs/learning-notes/multi-agent-systems.md` | **CREATE** — Learning notes |

### INTERVIEW ANGLES

- **Junior**: "I used multiple LLM calls"
- **Senior**: "I built a supervisor-worker agent architecture where a supervisor decomposes complex queries into subtasks, routes to specialist agents (stats, news, prediction), and synthesizes their outputs. Each agent has its own tool set and can be tested independently."
- **Awe moment**: "When a user asks 'Should I bet on the Lakers tonight?', the supervisor dispatches to all three agents in parallel: stats pulls recent form, news checks for injuries, and prediction runs the ensemble model. The supervisor then synthesizes a response that weighs model confidence against contextual risk factors."

---

## Module 4: Statistics (A/B Testing, Bayesian, Causal Inference)

### WHAT & WHY

30% of DS jobs require statistical rigor beyond ML. Google, Microsoft, and quantitative roles consistently ask about A/B testing, Bayesian methods, and causal inference. This module adds three capabilities that elevate the project from "ML engineering" to "data science."

### WHAT TO BUILD

**4.1 — A/B Testing Framework (Champion vs Challenger)**
```
File: backend/src/stats/ab_testing.py

class ModelABTest:
    - Traffic splitting: assign games to champion vs challenger model
    - Sequential testing: monitor with CUSUM / Wald's SPRT
    - Significance testing: two-proportion z-test for accuracy difference
    - Sample size calculator: minimum games needed for power=0.8
    - Auto-promotion: if challenger wins at significance, swap champion

Integrates with:
    - predictor.py → route % of predictions through challenger
    - mlops_routes.py → expose /mlops/ab-test/status endpoint
    - Lab page → A/B test dashboard card
```

**4.2 — Bayesian Team Strength Ratings**
```
File: backend/src/stats/bayesian_ratings.py

class BayesianTeamRatings:
    - Prior: team strength ~ N(1500, 300) (Elo-like)
    - Likelihood: game outcome given strength difference
    - Posterior update: after each game, update both teams
    - PyMC3 or NumPyro for MCMC sampling
    - Credible intervals: "Lakers are 70% likely to be top-5 strength"

Integrates with:
    - feature_store.py → bayesian_strength as a new model feature
    - routes.py → /api/v1/stats/team-ratings endpoint
    - Arena page → Bayesian strength ranking visualization
```

**4.3 — Causal Inference: Home Court Advantage**
```
File: backend/src/stats/causal_inference.py

class HomeCourteAnalysis:
    - Method 1: Propensity Score Matching
      → Match home/away games on team strength, rest days, opponent
      → Estimate ATE (Average Treatment Effect) of home court
    - Method 2: Difference-in-Differences
      → COVID empty arenas (2020-21) as natural experiment
      → Compare home advantage pre/during/post-COVID
    - Method 3: Instrumental Variables (advanced)
      → Schedule density as instrument for rest days

Integrates with:
    - feature_store.py → causal home_advantage_effect feature
    - Scribble page → causal analysis notebook template
    - intelligence layer → RAG context for home/away narratives
```

### FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `backend/src/stats/__init__.py` | **CREATE** — Stats module |
| `backend/src/stats/ab_testing.py` | **CREATE** — A/B testing framework |
| `backend/src/stats/bayesian_ratings.py` | **CREATE** — Bayesian team ratings |
| `backend/src/stats/causal_inference.py` | **CREATE** — Causal analysis |
| `backend/src/stats/experiment_store.py` | **CREATE** — Experiment persistence |
| `backend/src/api/stats_routes.py` | **CREATE** — Statistics API endpoints |
| `backend/src/models/trainer.py` | **MODIFY** — Add Bayesian strength feature |
| `alembic/versions/0004_add_experiments_table.py` | **CREATE** — A/B test tracking |
| `frontend/src/pages/Stats.tsx` | **CREATE** — Statistics dashboard page |
| `backend/tests/test_ab_testing.py` | **CREATE** — Statistical tests |
| `backend/tests/test_causal.py` | **CREATE** — Causal inference tests |
| `docs/learning-notes/statistics-deep-dive.md` | **CREATE** — Learning notes |

### DEPENDENCIES TO ADD
```
scipy>=1.12.0       # Already likely present via scikit-learn
statsmodels>=0.14.0  # For propensity scores, DiD, hypothesis testing
pymc>=5.10.0         # Bayesian inference (or numpyro as lighter alternative)
arviz>=0.17.0        # Bayesian visualization and diagnostics
```

### INTERVIEW ANGLES

- **Junior**: "I compared two models and picked the one with higher accuracy"
- **Senior**: "I implemented sequential A/B testing using Wald's SPRT for model comparison. This lets us detect a 2% accuracy improvement with 80% power using 40% fewer games than a fixed-horizon test. I also built Bayesian team ratings where posterior credible intervals capture uncertainty that point estimates miss."
- **Awe moment**: "I used COVID-era empty arenas as a natural experiment for causal inference on home court advantage. Pre-COVID, home teams won 59% of games. During empty arenas, it dropped to 52%. Post-COVID with fans back, it recovered to 57%. This DiD estimate gives us a 5-7% causal effect of crowd noise on game outcomes — which I feed as an adjusted feature into the prediction model."

---

## Module 5: NLP Engine (Classification, Embeddings, Sentiment)

### WHAT & WHY

The project already does RAG retrieval over sports news. But it treats text as opaque chunks — no classification, no sentiment, no entity extraction. 35% of DS jobs require NLP beyond retrieval. Adding NLP transforms the news pipeline from "search" to "understanding."

### WHAT TO BUILD

**5.1 — News Sentiment Analysis**
```
File: backend/src/nlp/sentiment.py

class SportsSentimentAnalyzer:
    - Fine-grained sentiment per team mention (not just doc-level)
    - Categories: positive / negative / neutral / injury / trade_rumor
    - Model: HuggingFace distilbert-base-uncased-finetuned-sst-2 (baseline)
           → Fine-tuned on sports corpus later (Module 6)
    - Output: { team: "LAL", sentiment: -0.72, category: "injury", entity: "LeBron" }

Integrates with:
    - news_agent.py → enrich news documents with sentiment before RAG indexing
    - vector_store.py → sentiment as metadata filter
    - prediction context → "negative sentiment trend for Lakers this week"
```

**5.2 — Named Entity Recognition (NER)**
```
File: backend/src/nlp/entity_extraction.py

class SportsNER:
    - Entities: PLAYER, TEAM, GAME_EVENT, INJURY, STAT_VALUE
    - Model: spaCy NER + custom rules for NBA-specific entities
    - Linking: map extracted "LeBron" → player_id in our DB
    - Output enriches every news document in the RAG pipeline

Integrates with:
    - ingestion pipeline → extract entities during news fetch
    - Knowledge Graph (Module 7) → entities become graph nodes
    - Chat intent routing → entity-aware query understanding
```

**5.3 — Text Classification for News Categorization**
```
File: backend/src/nlp/classifier.py

class NewsClassifier:
    - Categories: game_recap, injury_report, trade_rumor, analysis,
                  betting_line, player_spotlight, team_update
    - Model: scikit-learn TF-IDF + Logistic Regression (baseline)
           → Transformer classifier later (Module 6)
    - Used to: filter noisy betting content from RAG, prioritize
      injury reports for rule evaluation

Integrates with:
    - rules.py → category-aware rule evaluation
    - RAG quality scoring → boost analysis, penalize betting spam
    - Pulse page → categorized news feed
```

**5.4 — Custom Embedding Comparison**
```
File: backend/src/nlp/embeddings_comparison.py

class EmbeddingBenchmark:
    - Compare: Gemini embeddings vs sentence-transformers vs TF-IDF
    - Metrics: retrieval recall@k, MRR, NDCG on sports Q&A test set
    - Output: which embedding model gives best RAG performance
```

### FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `backend/src/nlp/__init__.py` | **CREATE** — NLP module |
| `backend/src/nlp/sentiment.py` | **CREATE** — Sentiment analysis |
| `backend/src/nlp/entity_extraction.py` | **CREATE** — NER for sports |
| `backend/src/nlp/classifier.py` | **CREATE** — News text classification |
| `backend/src/nlp/embeddings_comparison.py` | **CREATE** — Embedding benchmark |
| `backend/src/intelligence/news_agent.py` | **MODIFY** — Enrich docs with NLP |
| `backend/src/intelligence/vector_store.py` | **MODIFY** — Metadata filtering |
| `backend/src/intelligence/rules.py` | **MODIFY** — Category-aware rules |
| `backend/src/api/nlp_routes.py` | **CREATE** — NLP analysis endpoints |
| `frontend/src/components/Pulse/SentimentBadge.tsx` | **CREATE** — Sentiment UI |
| `backend/tests/test_nlp_pipeline.py` | **CREATE** — NLP tests |
| `docs/learning-notes/nlp-sports-deep-dive.md` | **CREATE** — Learning notes |

### DEPENDENCIES TO ADD
```
transformers>=4.38.0     # HuggingFace models
sentence-transformers>=2.5.0  # Embedding models
spacy>=3.7.0             # NER pipeline
datasets>=2.17.0         # HuggingFace datasets for fine-tuning data
```

### INTERVIEW ANGLES

- **Junior**: "I used a pre-trained sentiment model"
- **Senior**: "I built a three-layer NLP pipeline: entity extraction identifies players and teams, sentiment analysis scores team-level sentiment from news, and text classification filters noisy betting content from analysis. The sentiment signal becomes a feature in our prediction model — teams with sustained negative news sentiment (injury cascades) see 4% lower win rates than their statistical form suggests."
- **Awe moment**: "By enriching RAG documents with entity-level sentiment before indexing, my chatbot can answer 'What's the mood around the Lakers?' with quantified evidence, not just retrieved text."

---

## Module 6: LLM Fine-tuning (LoRA/PEFT/RLHF)

### WHAT & WHY

25% of DS jobs require fine-tuning experience. This module fine-tunes a small open-source model (Phi-3-mini or Llama 3.1 8B) on sports analytics Q&A data generated from our platform. This is the capstone skill — it combines NLP, PyTorch, and domain knowledge.

### APPROACH COMPARISON

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| A. LoRA fine-tune Phi-3-mini (3.8B) | Runs on local GPU/Colab, fast iteration | Smaller model, less impressive | ✅ Start here |
| B. LoRA fine-tune Llama 3.1 8B | Better quality, more recognized | Needs A100 or Colab Pro | ✅ Stretch goal |
| C. Full fine-tune | Shows depth | Impractical without significant compute | ❌ |
| D. RLHF with human feedback | Most impressive | Requires feedback infrastructure | ⚠️ Phase 2 |

**Choice: A first, then B. D as a stretch goal.**

### WHAT TO BUILD

**6.1 — Training Data Generation**
```
File: backend/src/finetuning/data_generator.py

class SportsQADataGenerator:
    - Source 1: Platform API responses → Q&A pairs
      "What's the Lakers' win percentage?" → actual API answer
    - Source 2: SHAP explanations → "Why did the model predict X?"
    - Source 3: RAG-generated narratives → refinement pairs
    - Source 4: SQL query-answer pairs from Scribble usage
    - Target: 5,000-10,000 instruction-following examples
    - Format: Alpaca/ShareGPT format for compatibility
```

**6.2 — LoRA Fine-tuning Pipeline**
```
File: backend/src/finetuning/lora_trainer.py

class LoRAFineTuner:
    - Base model: microsoft/Phi-3-mini-4k-instruct
    - LoRA config: r=16, alpha=32, target_modules=["q_proj", "v_proj"]
    - Training: 3 epochs, batch_size=4, gradient_accumulation=4
    - Evaluation: BLEU, ROUGE-L, BERTScore on held-out test set
    - Export: merged model + adapter-only checkpoint
    - Quantization: 4-bit QLoRA for inference efficiency
```

**6.3 — Evaluation Framework**
```
File: backend/src/finetuning/eval_suite.py

class FineTuneEval:
    - Domain accuracy: sports fact correctness
    - Hallucination rate: claims not in context
    - Response quality: coherence, specificity
    - A/B comparison: fine-tuned vs base Gemini on same queries
    - Latency benchmark: fine-tuned local vs API-based Gemini
```

**6.4 — Integration as Alternative LLM**
```
File: backend/src/intelligence/llm_router.py

class LLMRouter:
    - Route: simple queries → fine-tuned local model (fast, free)
    - Route: complex/creative queries → Gemini API (higher quality)
    - Fallback: if local model unavailable → always use Gemini
    - Config: model routing weights in settings.yaml
```

### FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `backend/src/finetuning/__init__.py` | **CREATE** — Fine-tuning module |
| `backend/src/finetuning/data_generator.py` | **CREATE** — Q&A dataset builder |
| `backend/src/finetuning/lora_trainer.py` | **CREATE** — LoRA training pipeline |
| `backend/src/finetuning/eval_suite.py` | **CREATE** — Evaluation framework |
| `backend/src/intelligence/llm_router.py` | **CREATE** — Model routing |
| `notebooks/finetuning_experiment.ipynb` | **CREATE** — Interactive training notebook |
| `backend/tests/test_finetuning.py` | **CREATE** — Fine-tuning tests |
| `docs/learning-notes/llm-finetuning-deep-dive.md` | **CREATE** — Learning notes |

### DEPENDENCIES TO ADD
```
peft>=0.9.0              # Parameter-efficient fine-tuning (LoRA)
trl>=0.7.0               # Transformer Reinforcement Learning (SFT, DPO)
bitsandbytes>=0.42.0     # 4-bit quantization
accelerate>=0.27.0       # Distributed training utilities
evaluate>=0.4.0          # HuggingFace evaluation metrics
```

### INTERVIEW ANGLES

- **Junior**: "I fine-tuned a model using a tutorial"
- **Senior**: "I generated 8,000 domain-specific Q&A pairs from our platform's API responses, SHAP explanations, and RAG narratives. I fine-tuned Phi-3-mini with LoRA (r=16, targeting attention projections) and achieved 23% better sports-fact accuracy than the base model while reducing hallucination rate from 12% to 4%. The fine-tuned model serves simple queries locally at 3x lower latency and zero API cost."
- **Awe moment**: "I built an LLM router that dispatches simple queries to the fine-tuned local model and complex queries to Gemini. This cut our API costs by 60% while maintaining quality on hard questions."

---

## Module 7: Knowledge Graphs (Neo4j)

### WHAT & WHY

10% of DS jobs list knowledge graphs, but they're typically senior-level roles at JPMorgan, Deloitte, and ServiceNow. This module models the NBA as a graph — teams, players, games, trades, and relationships — enabling queries that relational SQL cannot express elegantly.

### WHAT TO BUILD

**7.1 — Neo4j Graph Schema**
```
File: backend/src/graph/schema.py

Nodes:
  (:Team {team_id, name, conference, division})
  (:Player {player_id, name, position, age})
  (:Game {game_id, date, season})
  (:Season {year, type})

Relationships:
  (:Player)-[:PLAYS_FOR {since, until}]->(:Team)
  (:Team)-[:PLAYED_IN {score, home_away}]->(:Game)
  (:Player)-[:PLAYED_IN {points, rebounds, assists, minutes}]->(:Game)
  (:Team)-[:IN_CONFERENCE]->(:Conference)
  (:Player)-[:TRADED_FROM {date}]->(:Team)
  (:Player)-[:TEAMMATES_WITH {games_together, net_rating}]->(:Player)
```

**7.2 — Graph Population Pipeline**
```
File: backend/src/graph/neo4j_sync.py

class GraphSync:
    - Read from PostgreSQL (source of truth)
    - Populate Neo4j with MERGE (idempotent)
    - Sync on schedule (after ingestion completes)
    - Derive implicit relationships:
      → TEAMMATES_WITH from co-game appearances
      → Win rate edges between matchup pairs
```

**7.3 — Graph Analytics**
```
File: backend/src/graph/analytics.py

class GraphAnalytics:
    - Team chemistry score: PageRank on player-teammate net_rating graph
    - Trade impact analysis: what changes in graph connectivity when
      Player X moves from Team A to Team B?
    - Shortest path: degrees of separation between any two players
    - Community detection: identify player clusters/cliques
    - Centrality: who is the most "connected" player (betweenness)
```

**7.4 — Graph-Augmented Features**
```
File: backend/src/graph/graph_features.py

class GraphFeatureExtractor:
    - team_chemistry_score → feature for prediction model
    - roster_stability_index → how many roster changes this season
    - opponent_familiarity → games played against opponent's key players
    - These become new columns in match_features table
```

### FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `backend/src/graph/__init__.py` | **CREATE** — Graph module |
| `backend/src/graph/schema.py` | **CREATE** — Node/relationship definitions |
| `backend/src/graph/neo4j_client.py` | **CREATE** — Neo4j connection management |
| `backend/src/graph/neo4j_sync.py` | **CREATE** — PostgreSQL → Neo4j sync |
| `backend/src/graph/analytics.py` | **CREATE** — Graph algorithms |
| `backend/src/graph/graph_features.py` | **CREATE** — Features from graph |
| `backend/src/api/graph_routes.py` | **CREATE** — Graph API endpoints |
| `docker-compose.yml` | **MODIFY** — Add Neo4j service |
| `frontend/src/pages/Graph.tsx` | **CREATE** — Graph visualization page |
| `backend/tests/test_graph_analytics.py` | **CREATE** — Graph tests |
| `docs/learning-notes/knowledge-graphs-deep-dive.md` | **CREATE** — Learning notes |

### DEPENDENCIES TO ADD
```
neo4j>=5.17.0            # Official Neo4j Python driver
neomodel>=5.3.0          # OGM (Object-Graph Mapper) - optional
networkx>=3.2.0          # For local graph algorithms without Neo4j
```

### DOCKER ADDITION
```yaml
# docker-compose.yml
neo4j:
  image: neo4j:5-community
  ports:
    - "7474:7474"  # Browser
    - "7687:7687"  # Bolt
  environment:
    NEO4J_AUTH: neo4j/sports_analytics
  volumes:
    - neo4j_data:/data
```

### INTERVIEW ANGLES

- **Junior**: "I stored data in a graph database"
- **Senior**: "I modeled NBA relationships as a knowledge graph where team chemistry is derived from PageRank on player co-performance edges. When a trade happens, I can quantify the graph topology change — losing a high-centrality player breaks more team connections than losing a role player with the same stats. This graph-derived chemistry score improved prediction accuracy by 1.2% for teams with recent roster changes."
- **Awe moment**: "I used community detection to identify player cliques — groups of 3-4 players who perform significantly better together than their individual stats suggest. This is a signal that box scores alone can't capture."

---

## Module 8: Time-Series Forecasting

### WHAT & WHY

20% of DS jobs require time-series expertise (Amgen, Deloitte, Live Connections). The project computes rolling features but doesn't model temporal dynamics explicitly. This module adds proper time-series forecasting for team performance trajectories.

### WHAT TO BUILD

**8.1 — Classical Time-Series Models**
```
File: backend/src/timeseries/classical.py

class TeamPerformanceForecaster:
    - Prophet: team win probability trajectory over next 14 days
      → Captures seasonality (back-to-back fatigue patterns)
      → Holiday effects (Christmas games, All-Star break)
    - ARIMA/SARIMA: point differential time-series
      → Stationarity tests (ADF)
      → ACF/PACF for order selection
    - Exponential Smoothing: momentum scoring
      → Holt-Winters with damped trend
```

**8.2 — Deep Learning Time-Series (LSTM)**
```
File: backend/src/timeseries/lstm_model.py

class TeamSequenceModel(nn.Module):
    - Input: sequence of last N games (features per game)
    - Architecture:
        Embedding(team_id) → LSTM(hidden=64, layers=2) →
        Attention → FC(32) → FC(1)
    - Predicts: next game win probability
    - Key: captures momentum, streaks, fatigue patterns
    - Uses entity embeddings from Module 2

Note: This is where PyTorch shines over trees — sequence
modeling is a genuine NN advantage.
```

**8.3 — Momentum & Trajectory Features**
```
File: backend/src/timeseries/momentum.py

class MomentumEngine:
    - EMA-weighted form score (recent games weighted more)
    - Changepoint detection: when did a team's form shift?
    - Trajectory classification: improving / stable / declining
    - Forecast confidence intervals: not just point estimates

Integrates with:
    - feature_store.py → momentum_score, trajectory_class as features
    - prediction model → LSTM ensemble member
    - Pulse page → team trajectory charts
```

**8.4 — Forecasting API & Visualization**
```
File: backend/src/api/forecast_routes.py

Endpoints:
    GET /api/v1/forecast/team/{team_id}?horizon=14
      → Returns: daily win probability forecast with confidence bands
    GET /api/v1/forecast/season-trajectory?team_id=LAL
      → Returns: rest-of-season projected wins with uncertainty
```

### FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `backend/src/timeseries/__init__.py` | **CREATE** — Time-series module |
| `backend/src/timeseries/classical.py` | **CREATE** — Prophet, ARIMA, ETS |
| `backend/src/timeseries/lstm_model.py` | **CREATE** — LSTM sequence model |
| `backend/src/timeseries/momentum.py` | **CREATE** — Momentum scoring engine |
| `backend/src/timeseries/changepoint.py` | **CREATE** — Form shift detection |
| `backend/src/api/forecast_routes.py` | **CREATE** — Forecasting endpoints |
| `backend/src/models/trainer.py` | **MODIFY** — Add LSTM to ensemble |
| `frontend/src/pages/Forecast.tsx` | **CREATE** — Trajectory visualization |
| `frontend/src/components/Forecast/TeamTrajectory.tsx` | **CREATE** — Chart component |
| `backend/tests/test_timeseries.py` | **CREATE** — Forecasting tests |
| `docs/learning-notes/timeseries-deep-dive.md` | **CREATE** — Learning notes |

### DEPENDENCIES TO ADD
```
prophet>=1.1.5           # Facebook Prophet
statsmodels>=0.14.0      # ARIMA, ETS, stationarity tests (shared with Module 4)
ruptures>=1.1.0          # Changepoint detection
```

### INTERVIEW ANGLES

- **Junior**: "I used Prophet to forecast"
- **Senior**: "I built a multi-model forecasting ensemble: Prophet captures weekly seasonality in NBA schedules, ARIMA models the autoregressive structure of point differentials, and an LSTM captures non-linear sequence dependencies that classical models miss. The LSTM with attention outperformed Prophet by 8% MAPE on 14-day forecasts because it learns interaction effects between features across time steps."
- **Awe moment**: "I used changepoint detection (PELT algorithm) to identify when a team's underlying form shifts — for example, when a key player returns from injury. This feeds into the prediction model as a regime-change feature: predictions made during a detected shift get wider confidence intervals, and the chatbot flags this uncertainty to users."

---

## Full Dependency List (All Modules Combined)

```
# === Module 1: LangChain Enhancement ===
langchain-google-genai>=2.0.0
langchain-community>=0.2.0

# === Module 2: PyTorch ===
torch>=2.2.0
tensorboard>=2.16.0

# === Module 4: Statistics ===
statsmodels>=0.14.0
pymc>=5.10.0
arviz>=0.17.0

# === Module 5: NLP ===
transformers>=4.38.0
sentence-transformers>=2.5.0
spacy>=3.7.0
datasets>=2.17.0

# === Module 6: Fine-tuning ===
peft>=0.9.0
trl>=0.7.0
bitsandbytes>=0.42.0
accelerate>=0.27.0
evaluate>=0.4.0

# === Module 7: Knowledge Graphs ===
neo4j>=5.17.0
networkx>=3.2.0

# === Module 8: Time-Series ===
prophet>=1.1.5
ruptures>=1.1.0
```

---

## Database Migrations Required

| Migration | Module | Table/Change |
|-----------|--------|-------------|
| `0003_add_chat_memory_table` | 1 | `chat_sessions`, `chat_messages` |
| `0004_add_experiments_table` | 4 | `ab_experiments`, `experiment_assignments` |
| `0005_add_nlp_metadata` | 5 | Add `sentiment`, `entities`, `category` columns to news docs |
| `0006_add_graph_features` | 7 | Add `chemistry_score`, `roster_stability` to `match_features` |
| `0007_add_forecasts_table` | 8 | `team_forecasts` with time-series outputs |

---

## Frontend Pages to Add

| Page | Module | Purpose |
|------|--------|---------|
| Enhanced Chatbot (agent trace) | 3 | Show which agents contributed to each response |
| Stats Lab | 4 | A/B test dashboard, Bayesian ratings, causal analysis |
| Graph Explorer | 7 | Interactive team-player knowledge graph visualization |
| Forecast | 8 | Team trajectory charts with confidence bands |

---

## Testing Strategy

Each module follows the same test pattern:

1. **Unit tests** — Pure function logic (sentiment scoring, LSTM forward pass, graph features)
2. **Integration tests** — API endpoint contracts (FastAPI TestClient)
3. **DB tests** — Schema changes verified with temp-table isolation pattern
4. **Evaluation tests** — Model quality benchmarks (accuracy thresholds, BLEU scores)

---

## Success Criteria

| Module | Metric | Target |
|--------|--------|--------|
| 1. LangChain | Tool execution success rate | >95% |
| 2. PyTorch | MLP vs XGBoost AUC comparison documented | Any result is valid |
| 3. Multi-Agent | Complex query decomposition accuracy | >80% |
| 4. Statistics | A/B test detects 2% accuracy diff at p<0.05 | Demonstrated |
| 5. NLP | Sentiment F1 on sports text | >0.75 |
| 6. Fine-tuning | Sports-fact accuracy improvement over base | >15% |
| 7. Knowledge Graphs | Chemistry score feature importance rank | Top 10 SHAP |
| 8. Time-Series | 14-day forecast MAPE | <15% |

---

## Timeline Estimate

| Module | Effort | Dependencies |
|--------|--------|-------------|
| 1. LangChain | 3-4 days | None |
| 5. NLP | 3-4 days | None |
| 2. PyTorch | 3-4 days | None |
| 3. Multi-Agent | 4-5 days | Modules 1, 5 |
| 4. Statistics | 4-5 days | None |
| 8. Time-Series | 3-4 days | Module 2 (embeddings) |
| 7. Knowledge Graphs | 3-4 days | None |
| 6. Fine-tuning | 5-6 days | Modules 2, 5 |
| **Total** | **~28-36 days** | |

---

## Quiz Bank (Post-Module Interview Prep)

After completing each module, test yourself on these:

### Module 1 — LangChain
1. What is the difference between a Chain and an Agent in LangChain?
2. When would you use ConversationBufferMemory vs ConversationSummaryMemory?
3. How does LangGraph's state machine differ from LangChain's sequential chains?

### Module 2 — PyTorch
1. Why do tree models generally outperform neural networks on tabular data?
2. Explain entity embeddings for categorical features. When are they useful?
3. What is the vanishing gradient problem and how does BatchNorm help?

### Module 3 — Multi-Agent
1. What are the trade-offs between supervisor vs peer-to-peer agent architectures?
2. How do you handle conflicting outputs from different agents?
3. What failure modes exist in multi-agent systems and how do you mitigate them?

### Module 4 — Statistics
1. Explain the difference between frequentist A/B testing and Bayesian A/B testing.
2. What is the fundamental problem of causal inference?
3. When would you use Difference-in-Differences vs propensity score matching?

### Module 5 — NLP
1. What is the difference between token-level and document-level sentiment?
2. How do contextual embeddings (BERT) differ from static embeddings (Word2Vec)?
3. When would you use TF-IDF over transformer embeddings?

### Module 6 — Fine-tuning
1. What does LoRA do mechanically? Why rank 16 and not rank 256?
2. What is catastrophic forgetting and how does PEFT mitigate it?
3. When should you fine-tune vs use in-context learning (few-shot prompting)?

### Module 7 — Knowledge Graphs
1. When is a graph database better than a relational database?
2. Explain PageRank in the context of player importance.
3. What is the difference between a knowledge graph and an ontology?

### Module 8 — Time-Series
1. What is stationarity and why does it matter for ARIMA?
2. When would an LSTM outperform Prophet?
3. What is a changepoint and how do you detect one?

---

*Plan created: 2026-03-25*
*Project: Sports Analytics Intelligence Platform*
*Target: Data Scientist roles — 2026*
