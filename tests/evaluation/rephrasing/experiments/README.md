# Hybrid retrieval experiment (retrieval only; production code unchanged)

`hybrid_experiment.py` copies the ranking step of `retrieve()` and changes one interpretable part at a time.
It runs the same 400 questions as `../benchmark.yaml`; labels are unchanged.

- The `baseline` configuration is asserted to reproduce production retrieval exactly.
- The relevance filter, evidence selection (top 6, at most 2 chunks per fatwa) and the gate are unchanged.

Buckets:

- **A**: the correct fatwa is not in the evidence.
- **B**: the correct fatwa is in the evidence, but not first.
- **C**: the correct fatwa is first.
- **D**: the top-1 fatwa comes from a different category than every acceptable fatwa (unrelated).

## Results (2026-10-04, multilingual-e5-large)

| Config                              | Reworded top-1 | Reworded top-3 | A   | B   | C   | D   |
| ----------------------------------- | -------------- | -------------- | --- | --- | --- | --- |
| baseline (production)               | 62.3           | 77.4           | 57  | 75  | 268 | 55  |
| pool 64 (instead of 24 + 24)        | 62.3           | 76.9           | 58  | 74  | 268 | 55  |
| sparse candidates by IDF coverage   | 62.3           | 76.9           | 57  | 75  | 268 | 55  |
| IDF-weighted coverage in the hybrid | 64.0           | 78.6           | 52  | 74  | 274 | 47  |
| sparse IDF + coverage IDF           | 63.4           | 79.1           | 54  | 74  | 272 | 49  |
| RRF instead of the linear hybrid    | 54.3           | 71.4           | 66  | 97  | 237 | 59  |
| RRF + sparse IDF                    | 61.4           | 76.6           | 51  | 84  | 265 | 46  |
| **dense only (ablation)**           | **66.9**       | **79.4**       | 49  | 67  | 284 | 40  |

## Findings

- **Recall is not the bottleneck.** The correct fatwa is almost always already in the 24 + 24 candidate pool, so a
  bigger pool changes nothing.
- **The ranking is the bottleneck.** The lexical bonus (`0.25·coverage + 0.10·title`) is worth up to 0.35, while e5
  cosines sit in a narrow 0.75–0.90 band. The bonus therefore outweighs the semantic signal on reworded questions:
  dense-only ranking beats the hybrid (synonym top-1 34 → 52, formal 82 → 92).
- **Dense-only loses where the lexical signal helps:** short questions (top-3 98 → 92) and indirect top-3 (50 → 46).
- **«العلكة» / "chewing gum" ↔ «اللبان»:** the stem «علك» occurs in no indexed fatwa, so no lexical method can match
  it, and e5 does not place fatwa 8398 in the top 64 either. Fixing it needs an explicit synonym entry or a
  different model. Nothing was added.
- **IDF weighting helps only a little** (top-1 +1.7 points, A 57 → 52, D 55 → 47), and similarly on both halves of
  the benchmark.

## Lexical-weight calibration (`calibrate_lexical_weight.py`)

Only the coverage weight changes; the title bonus stays at 0.10. The protocol was fixed before running:

- **Split:** by fatwa (`items[0::2]` tuning, `items[1::2]` validation), 200 questions each.
- **Selection, tuning split only:** fewest D, then fewest B, then most C. A weight is excluded if A rises, or if
  Short or Indirect Top-3 drops by more than one question.
- **Validation:** the chosen weight and 0.25 run once.

| Coverage weight | Tuning top-1 | Tuning top-3 | A   | B   | C   | D   | Eligible                         |
| --------------- | ------------ | ------------ | --- | --- | --- | --- | -------------------------------- |
| 0.00            | 71.0         | 84.0         | 22  | 36  | 142 | 20  | no (Indirect top-3 −2 questions) |
| **0.05**        | **73.0**     | **84.5**     | 23  | 31  | 146 | 20  | yes (chosen)                     |
| 0.10            | 73.0         | 84.0         | 21  | 33  | 146 | 21  | yes                              |
| 0.15            | 71.0         | 84.0         | 22  | 36  | 142 | 24  | yes                              |
| 0.20            | 70.0         | 83.0         | 24  | 36  | 140 | 27  | yes                              |
| 0.25 (previous) | 68.0         | 82.5         | 25  | 39  | 136 | 29  | yes                              |

**Validation, run once:**

| Weight | Top-1 | Top-3 | Top-5 | A   | B   | C   | D   |
| ------ | ----- | ----- | ----- | --- | --- | --- | --- |
| 0.25   | 66.0  | 78.0  | 81.5  | 32  | 36  | 132 | 26  |
| 0.05   | 69.0  | 80.0  | 84.5  | 27  | 35  | 138 | 20  |

**Validation per wording, top-1 / top-3, 0.25 → 0.05:**

| Formal         | Colloquial    | Short         | Indirect      | Synonym       | Typo          | English       |
| -------------- | ------------- | ------------- | ------------- | ------------- | ------------- | ------------- |
| 88/96 → 96/100 | 60/80 → 52/80 | 84/96 → 92/92 | 28/44 → 32/48 | 28/44 → 40/52 | 76/88 → 80/92 | 64/76 → 64/76 |

**Independent check on `data/eval/semantic_questions.yaml`** (219 questions on 39 other fatwas, retrieval only),
0.25 → 0.05:

- Top-1 68.9 → 69.4, Top-3 82.2 → 84.0, Top-5 85.8 → 89.5.
- A 30 → 22, B 38 → 45, C 151 → 152, D 14 → 15.

**Decision: REDUCE LEXICAL WEIGHT to 0.05** (`LEXICAL_COVERAGE_WEIGHT` in `pipeline/retrieval.py`).

- With the new weight, production reproduces the experiment: C = 284 of 400.
- Full run with the new weight: `../results/rephrasing_results_lexical_0.05.json`.
- Known cost: validation colloquial top-1 −2 questions, and Short top-3 −1 question.
