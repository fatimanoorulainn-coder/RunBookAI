# RunBookAI

**An autonomous SRE incident investigator.** Ask why a service is degraded, and
an LLM agent gathers evidence from live infrastructure metadata, application
logs, and a runbook knowledge base, correlates it, and returns a **grounded
verdict with a confidence score** — or honestly abstains when the evidence
isn't there.

The emphasis throughout is on **trustworthy machine reasoning**: the model never
scores its own confidence, every conclusion is checked for groundedness against
the evidence, generated SQL is validated and sandboxed, and "I don't know" is a
first-class outcome rather than a hallucinated guess.

---

## What it does

Given a question like *"why is payment-service degraded?"*, the agent:

1. **Queries service metadata** — deployment health and pod status from Postgres.
2. **Searches logs** — error patterns for the affected service.
3. **Searches runbooks** — semantically retrieves the relevant SRE playbook.
4. **Submits a finding** — a root cause and a status (`resolved` or
   `insufficient_evidence`), after which confidence is computed deterministically
   from the collected evidence.

The web UI renders the verdict, an **execution timeline** (each tool call with
its input, output, and latency), and an **evidence tree** showing the provenance
behind the conclusion.

---

## Key design decisions

The interesting parts of this project are less about the agent loop and more
about making its output *trustworthy*.

### The model never scores its own confidence
`submit_finding` deliberately has no `confidence_score` field. Confidence is
computed **deterministically** (`api/confidence.py`) from the collected
evidence — number of independent sources, source diversity, and whether the
evidence contains contradictions. A self-reported confidence from an LLM is
theater; a score derived from what was actually found is auditable.

### Abstention is a first-class outcome
When the agent is forced to conclude (step budget reached) with confidence below
threshold, the result is downgraded to `insufficient_evidence` rather than
presented as a best guess. A nonexistent service returns *no evidence* → the
agent abstains instead of inventing a root cause. The UI renders this state
visually distinctly — it never looks like a confident answer.

### Real SQL generation with a safety layer
`query_service_metadata` has the model generate a **parameterized SQL query**
against the known schema, rather than running a hardcoded lookup. Because
LLM-generated SQL is untrusted, it passes through a defense-in-depth gate before
execution (`api/tools/sql_guard.py`):

- single statement only (no stacking)
- must be `SELECT` (no DDL/DML/CTE)
- tables restricted to an `ALLOWED_TABLES` allowlist
- forbidden keywords/functions rejected (`DROP`, `GRANT`, `INTO`, `pg_sleep`, …)
- a row `LIMIT` is enforced

As a database-level backstop, the agent connects as a **read-only Postgres role**,
so even a validator bypass is physically refused (`DROP TABLE` →
`ReadOnlySqlTransaction`). If generation or validation ever fails, the tool falls
back to a trusted static query — a bad LLM turn degrades to "still works," never
"incident breaks." Adversarial coverage lives in `scripts/test_sql_safety.py`
(15 attack shapes, all rejected).

### Groundedness checking
`check_groundedness()` measures the fraction of the root cause's content-words
that appear in the evidence — a cheap hallucination guard. On the benchmark,
resolved findings average **0.90** groundedness with none below the 0.4 threshold,
i.e. no resolved conclusion is unsupported by its evidence.

> Caveat: this is approximate **lexical overlap, not NLI entailment**. It catches
> word-level divergence (a root cause naming something absent from the evidence)
> but cannot detect semantic contradiction — "caused by X" and "not caused by X"
> share the same words and score identically. A smoke alarm, not a proof.

### Structured, provenanced evidence
Every piece of evidence carries `id`, `source`, `source_location`, `timestamp`,
and a `relevance_score` computed deterministically from lexical overlap with the
question (never an LLM-assigned number). `source_location` records provenance —
the DB tables, the log file path, or the specific runbook `doc_id`s — so the
final answer is fully traceable back to its inputs.

---

## Retrieval: chunker comparison (Recall@K)

Three chunking strategies were built over the same 76-doc runbook corpus
(Kubernetes pods + networking + AWS database playbooks) and indexed with local
`all-MiniLM-L6-v2` embeddings. Each was scored on a 35-question eval set skewed
toward symptom-based and explanatory phrasing (e.g. "why would a container exit
with code 137" rather than "OOMKilled").

Metric is **doc-level Recall@K**: a question is a hit if any of the top-K
retrieved chunks belongs to an expected doc. Doc-level, not chunk-level, because
each strategy emits different chunk IDs — only doc membership is comparable
across them. Reporting K = 1, 3, 5 rather than only K = 5, because K = 5 is
generous enough to hide differences the agent actually cares about.

| Chunker      | R@1    | R@3    | R@5    | Chunks | Avg chunk (chars) |
|--------------|--------|--------|--------|--------|-------------------|
| fixed        | 80.00% | 91.43% | 97.14% | 737    | 473               |
| heading      | 77.14% | 91.43% | 94.29% | 306    | 1021              |
| parent_child | 74.29% | 88.57% | 97.14% | 1345   | 260 (match)       |

**Reading the table:** at R@5 the strategies look nearly tied, but the stricter
R@1 spreads them out. `fixed` leads at every K. `parent_child` ties `fixed` at
R@5 but is weakest at R@1 — its many tiny (~260-char) match fragments are easy
to confuse across the corpus's near-duplicate docs (e.g. the crash-loop and
ingress families), so its single top hit is noisier. `fixed`'s larger 500-char
slices carry enough context to nail the top hit more often. Every miss across
all strategies was a symptom-based or ambiguous question; the keyword-matchable
ones were solved by everyone.

**Chosen strategy: `heading`.** The eval measures *doc retrieval*, but the
agent's real job is *reasoning over the returned text*, so the deciding factor
is evidence quality at near-equal recall. `heading` is within 3 points of
`fixed` at R@1 and identical at R@3, while being the only high-recall strategy
that returns coherent, heading-prefixed sections (`[Meaning]`, `[Diagnosis]`,
`[Playbook]`) instead of mid-sentence fragments. `fixed` retrieves marginally
better but hands the LLM choppier slices; `parent_child` returns whole sections
too but costs ~6 points of R@1. `heading` is the best balance of finding the
right doc near the top and giving the agent readable evidence to reason over.

---

## Architecture

```
question
   │
   ▼
┌─────────────────────────────────────────────┐
│  Agent loop  (api/agent.py, Groq llama-3.3)  │
│  - tool calling with a hard step budget      │
│  - duplicate-call detection                  │
│  - submit_finding is the ONLY exit           │
└───────┬───────────────┬───────────────┬──────┘
        ▼               ▼               ▼
  query_service     search_logs    search_runbooks
    _metadata           │               │
        │               │               │
  generated SQL    keyword match   semantic search
  → validated      over log file   (MiniLM + heading
  → read-only DB                    chunk index)
        │               │               │
        └───────────────┴───────────────┘
                        ▼
              structured Evidence[]
        (source_location, relevance_score)
                        ▼
        deterministic confidence + groundedness
                        ▼
              Investigation  →  FastAPI  →  Next.js UI
```

---

## Tech stack

- **Agent / API:** Python, FastAPI, Groq (`llama-3.3-70b-versatile`)
- **Data:** PostgreSQL (service metadata), file-based logs
- **Retrieval:** `sentence-transformers` (`all-MiniLM-L6-v2`), local NumPy vector index
- **Frontend:** Next.js (App Router), TypeScript
- **Evaluation:** custom incident benchmark + Recall@K + groundedness harnesses

---

## Project structure

```
api/
  agent.py            # the investigation loop
  confidence.py       # deterministic confidence + contradiction detection
  groundedness.py     # lexical-overlap groundedness / relevance
  evidence_utils.py   # provenance + relevance for evidence objects
  models.py           # Pydantic models (Evidence, Finding, Investigation, tool schemas)
  main.py             # FastAPI app + /investigate endpoint
  tools/
    metadata.py       # query_service_metadata (model-generated, validated SQL)
    logs.py           # search_logs (keyword match over log file)
    runbooks.py       # search_runbooks (semantic runbook retrieval)
    sql_gen.py        # SQL generation + trusted static fallback
    sql_guard.py      # SQL validation + LIMIT enforcement
retrieval/
  corpus.py           # load + parse runbook docs
  chunkers.py         # fixed / heading / parent-child chunkers
  embed.py            # local embedding wrapper
  index.py            # build / save / load / search vector index
  build_index.py      # CLI to build indexes
  recall_eval.py      # Recall@K evaluation
db/
  schema.sql          # tables: services, deployments, pods, investigations, traces
  readonly_role.sql   # least-privilege role for the agent
evals/
  run_incidents.py    # 12-incident benchmark (+ groundedness metric)
  incidents/          # scenario/expected pairs
  retrieval_questions.json
scripts/
  test_sql_safety.py  # adversarial SQL tests
frontend/             # Next.js app (verdict view, timeline, evidence tree)
data/
  logs/               # service-tagged log lines + Loghub OpenStack noise
  runbooks/           # 76-doc runbook subset (gitignored; staged from upstream)
  indexes/            # built vector indexes (gitignored; rebuildable)
```

---

## Setup

**Prerequisites:** Python 3.12+, PostgreSQL, Node.js 18+, a Groq API key.

```bash
# 1. Python deps
pip install -r requirements.txt
pip install sentence-transformers numpy

# 2. Environment
#    create .env with:
#      GROQ_API_KEY=...
#      DB_PASSWORD=...

# 3. Database
psql -U postgres -d runbookai -f db/schema.sql
psql -U postgres -d runbookai -f db/readonly_role.sql
python -m db.seed            # seed demo services / deployments / pods

# 4. Runbook corpus + indexes
git clone --depth 1 https://github.com/Scoutflo/Scoutflo-SRE-Playbooks.git
python -m retrieval.stage_corpus Scoutflo-SRE-Playbooks
python -m retrieval.build_index          # builds all three chunker indexes
```

**Run it** (two servers):

```bash
# backend
uvicorn api.main:app --reload            # :8000

# frontend
cd frontend && npm install && npm run dev # :3000
```

Open http://localhost:3000 and investigate a service.

---

## Evaluation

```bash
python -m evals.run_incidents     # 12-incident benchmark + groundedness
python -m retrieval.recall_eval   # Recall@1/3/5 across the three chunkers
python -m scripts.test_sql_safety # adversarial SQL rejection tests
```

- **Incident benchmark:** scores each scenario on status, root-cause keywords,
  confidence band, and correct abstention.
- **Groundedness:** reported per incident; resolved findings average ~0.90.
- **SQL safety:** 15 adversarial inputs, all rejected.

---

## Honest limitations

This is a **closed, reproducible demo**, not a production tool wired to live
infrastructure. Specifically:

- **Model non-determinism.** Running on Groq's free tier with a 70B model, some
  incidents resolve differently run-to-run, and the benchmark passes ~8/12. The
  guardrails (deterministic confidence, abstention, groundedness) are precisely
  what keep this non-determinism from producing confidently-wrong answers.

---

## Roadmap

Ordered by effort, easiest first:

1. **Bring-your-own scenario.** Let a user paste a JSON blob describing a service,
   its pods, and log lines, and have the agent investigate *that* instead of the
   seed DB — the same agent fed user-supplied evidence, no infrastructure needed.
2. **Live Kubernetes metadata.** Point `query_service_metadata` at a local
   `minikube`/`kind` cluster via the Kubernetes API, replacing the seed lookup
   with real pod/deployment state.
3. **Log-backend integration.** Read real pod logs (Loki / Elasticsearch /
   CloudWatch) instead of the file-based log search.