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
better but hands the LLM choppier slices (e.g. "configuration: retrieve the
imagePullSecrets..."); `parent_child` returns whole sections too but costs ~6
points of R@1. `heading` is the best balance of finding the right doc near the
top and giving the agent readable evidence to reason over.