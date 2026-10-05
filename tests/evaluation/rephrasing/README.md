# Rephrasing benchmark (retrieval only)

Does تِبْيان reach the same fatwa when the same question is asked in completely different words?

Evaluation data only. Nothing here is imported by production code.

## Contents

| File                              | What                                                                                      |
| --------------------------------- | ----------------------------------------------------------------------------------------- |
| `benchmark.yaml`                  | 50 fatwas × 7 hand-written variants (+ the original read from the source) = 400 questions |
| `evaluate.py`                     | Runs production retrieval on every variant and computes the metrics below                 |
| `results/rephrasing_results.json` | Per-variant results and the summary of the last run                                       |

### Dataset

- 50 fatwas from `data/corpus/binbaz`, across all 13 categories, chosen roughly in proportion to each category's
  size. None of them is in `data/eval/semantic_questions.yaml` or `semantic_hard_cases.yaml`.
- Each fatwa has these variants:
  - `original`: the asker's question, read verbatim from the source.
  - `formal`, `colloquial` (Saudi), `short`, `indirect` (describes the situation, never names the ruling),
    `synonym` (key terms replaced), `typo` and `english`: written by hand.
- Variants preserve the meaning and deliberately avoid the original's words. Average share of each variant's key
  terms that also appear in the original question:

  | indirect | synonym | colloquial | formal | typo | short | english |
  | -------- | ------- | ---------- | ------ | ---- | ----- | ------- |
  | 14%      | 14%     | 25%        | 36%    | 52%  | 54%   | 0%      |

- Each variant carries `expected_fatwa_id`, `expected_topic` and `language` (`ar`, `ar-SA` or `en`).
- `also` lists other fatwas in the corpus that answer the same issue (near-duplicates). The lenient metric counts
  them as correct.
- The `also` lists are conservative: a fatwa on the same ruling that is not listed counts as a miss.
- The variants were written by the AI assistant without a generator. They need review by a native speaker or the
  governance lead before any public claim.

## Run

Needs the indexed database and the embedding model, as configured in `.env`. No LLM or OpenAI is used, and nothing
is written to the database.

```bash
services/ai/.venv/bin/python tests/evaluation/rephrasing/evaluate.py            # all 400 questions
services/ai/.venv/bin/python tests/evaluation/rephrasing/evaluate.py --limit 2  # smoke test
```

## Metrics

- **Top-k (lenient):** the expected fatwa, or a listed same-issue fatwa, is among the first k distinct fatwas in
  the final ranking. **Strict** counts only the expected fatwa.
- **Gate:** the retrieval sufficiency decision the pipeline makes before generation.
- **Semantic consistency:**
  - `rephrased_top1_correct`: share of the 350 rephrased variants whose top-1 is correct.
  - `agreement_with_original_top1`: share whose top-1 is the same fatwa the original wording retrieved first.
  - `items_robust_all_variants_top3`: share of questions for which all 8 wordings put a correct fatwa in the
    top 3.

### Failure classes

Applied to every variant whose top-1 is wrong, plus a correct top-1 that the gate rejected. Rules are checked in
this order:

| Class                                  | Rule                                                                                                                                                   |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 8. Correct retrieval but wrong gate    | Top-1 correct, but the gate judged the evidence insufficient                                                                                           |
| 7. Correct retrieval but wrong ranking | The correct fatwa is in the evidence the pipeline uses (top 6), but not first                                                                          |
| 5 / 6 / 3 / 4                          | Not in the evidence. `english` → English retrieval failure, `typo` → Typo failure, `colloquial` → Colloquial mismatch, `short` → Short query ambiguity |
| 2. Vocabulary mismatch                 | `formal`, `indirect`, `synonym` or `original` not in the evidence, and fewer than half of the question's key terms occur in the fatwa                  |
| 1. Exact wording dependency            | As above, but the fatwa does contain most of the question's terms, and the original wording found it                                                   |

## Results (run of 2026-10-03, `multilingual-e5-large`, `rrf`, branch `eval/rephrasing-benchmark`)

| Variant    | Top-1 | Top-3 | Top-5 | Top-1 strict |
| ---------- | ----- | ----- | ----- | ------------ |
| Original   | 100%  | 100%  | 100%  | 96%          |
| Formal     | 82%   | 90%   | 98%   | 70%          |
| Colloquial | 60%   | 76%   | 82%   | 50%          |
| Short      | 86%   | 98%   | 98%   | 76%          |
| Indirect   | 28%   | 50%   | 58%   | 24%          |
| Synonym    | 34%   | 52%   | 56%   | 24%          |
| Typo       | 84%   | 92%   | 94%   | 76%          |
| English    | 62%   | 84%   | 90%   | 52%          |

**Semantic consistency:**

- Rephrased top-1 correct: 62.3%.
- Rephrased top-3 correct: 77.4%.
- Agreement with the original's top-1: 53.7%.
- Questions robust in all 8 wordings (top 3): 24%.

**Failures (132 wrong top-1 out of 400):**

| Class                               | Count | Breakdown                                  |
| ----------------------------------- | ----- | ------------------------------------------ |
| Correct retrieval but wrong ranking | 75    | —                                          |
| Vocabulary mismatch                 | 40    | synonym 21, indirect 19                    |
| Colloquial mismatch                 | 9     | —                                          |
| English retrieval failure           | 5     | —                                          |
| Typo failure                        | 2     | —                                          |
| Exact wording dependency            | 1     | —                                          |
| Short query ambiguity               | 0     | the 7 short misses were all ranking misses |
| Correct retrieval but wrong gate    | 0     | —                                          |

**Gate:** the retrieval gate judged the evidence sufficient for all 400 questions, including all 132 with a wrong
top-1. With e5 it does not discriminate; see `KNOWN_ISSUES.md` A1.

**Retrieval latency:** median 39 ms, p95 72 ms (in process).
