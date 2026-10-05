# Demo script — تِبْيان | Tibyan

Audience: hackathon judges. Duration: ~5 minutes. Everything shown is live: real retrieval over the indexed
corpus, real verification, persisted traces. Nothing is pre-recorded or hard-coded.

## Before the demo

```bash
cp .env.example .env               # once
# optional: put OPENAI_API_KEY + OPENAI_MODEL (or ANTHROPIC_API_KEY) in .env for LLM mode — never commit them
docker compose up -d --wait
curl -s localhost:4000/api/health  # api, database, ai: "ok"
curl -s 127.0.0.1:8000/health      # llm_provider / llm_model / llm_available
```

| `/health` shows                                                  | Mode during the demo                                                           |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `llm_provider: "none"`                                           | Extractive — answers are verbatim source sentences                             |
| `llm_provider: "openai"` or `"anthropic"`, `llm_available: true` | The LLM writes the summary from evidence; every claim verified                 |
| `llm_provider: "openai"`/`"anthropic"`, `llm_available: false`   | Recent API failure — extractive fallback for 60 s (10 min after an auth error) |

Run one warm-up question before going on stage (loads models, checks the key). In LLM mode, expect answers to
take longer than in extractive mode — **latency with a valid key has not been measured yet**; if it is too slow, set
`LLM_CLASSIFIER=false` and/or `ANTHROPIC_GENERATION_EFFORT=low`, then `docker compose up -d ai`.

Use Chrome or Safari for voice. Allow microphone access once before going on stage.

## 1. The principle (30 s)

Open `http://localhost:3000/ar`. Read the hero line and the principle: **«لا نُنشئ الفتوى، نوصلك إليها.»**
Say what the model is and is not: the language model never answers from its own knowledge — it only restates
evidence retrieved from approved sources, and a separate check verifies every claim against the source text.

## 2. Scenario A — answer + source + trust chain + voice (90 s)

1. Click **اسأل صوتيًا** and say: «ما المدة التي يقصر فيها المسافر الصلاة؟»
2. The transcript fills the box and is sent through the normal pipeline (same as typed questions).
3. Walk through the card: **الخلاصة** → **المصدر** (official site of Sh. Ibn Baz, "مصدر معتمد") →
   **النص المستند إليه** (the source's own wording is highlighted inside the verbatim fatwa) → **فتح المصدر**.
4. The answer is read aloud — only the verified text.
5. Expand **كيف وصلنا لهذه الإجابة؟**: sources searched (pending / not-indexed sources shown as _excluded_),
   evidence with scores, generation mode (OpenAI, Claude or extractive), claims, per-claim verification, total time.

## 3. Scenario B — clarification (45 s)

Type «هل يجوز لي قصر الصلاة؟». Tibyan does not assume: **«هل أنت مسافر أم مقيم؟»** (no model call is made).
Choose **مسافر** → verified answer.

## 4. Scenario C — abstention + official escalation (45 s)

Type «طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟». Classified as a personal case → no ruling and no generation →
**هذه المسألة تحتاج إلى جهة مختصة** with official bodies whose websites were verified (date shown) and general readings
labelled as no substitute. No phone numbers or links that were not verified.

Then «ما حكم بيع العملات الرقمية؟» → **لم نجد مرجعًا كافيًا للإجابة.** The corpus does not cover it, so Tibyan says so.

## 5. Optional — governance and resilience (30 s each)

- `/ar/admin` (token from `.env`): set the Ibn Baz source to _pending_ → ask Scenario A again → abstention, because
  unapproved sources are never searched. Approve it again; show the audit-log entry.
- Resilience (rehearsal only): with an invalid key or no network, answers continue in extractive mode and the card
  shows «تعذّر إكمال المعالجة بالذكاء الاصطناعي، لذلك استخدمنا الإجابة المستخرجة من المصدر.» Tested against the real
  OpenAI and Anthropic APIs (`401`) and a simulated outage.

## What not to claim on stage

- Not "100 % accurate" and not "0 % hallucination". Say instead: claims that are not grounded in the retrieved
  source are not shown, and when evidence is insufficient the system abstains.
- The internal regression set (18/18) is small and was written during tuning — it is not a benchmark.
- LLM mode has not yet been run with a valid key (see docs/LLM_EVALUATION.md); rehearse with the key before the demo.
- The corpus is 3,000 fatwas (2,000 Ibn Baz, 1,000 Ibn Uthaymeen) across all fiqh chapters, but only the first
  pages of each category; questions outside it will — correctly — abstain.

## If something goes wrong

- `docker compose logs ai` — pipeline logs with request ids (provider failures and fallbacks are logged).
- Voice unavailable in the browser → type the question; the pipeline is identical.
