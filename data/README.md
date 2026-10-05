# data/

Everything under this directory has a documented origin. **The fatwa and hadith texts are not in the public
repository**: they belong to their publishers. The repository ships `corpus/manifest.jsonl` (source, id, URL,
collection, categories and the SHA-256 of each verbatim text, no text), and the texts are fetched from the original
websites:

```bash
node scripts/py.mjs -m tibyan_ai.cli fetch-corpus            # every missing snapshot (about an hour, 1 request/s)
node scripts/py.mjs -m tibyan_ai.cli fetch-corpus --source binbaz --ids-file services/ai/tests/fixture_fatwas.txt
```

`docker compose up` runs the first command before seeding. A text that changed on the website since indexing is
reported (its hash no longer matches); `corpus-manifest` rewrites the manifest from the local snapshots.

| Path                         | Content                                                  | Origin                                                                                                     |
| ---------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `sources/registry.yaml`      | Approved Source Whitelist (approved / pending / blocked) | Governance lead                                                                                            |
| `escalation/bodies.yaml`     | Official referral bodies with verification date + method | Governance lead                                                                                            |
| `corpus/binbaz/*.json`       | Verbatim fatwa snapshots                                 | Fetched from binbaz.org.sa by `tibyan_ai.ingestion.binbaz`                                                 |
| `corpus/binothaimeen/*.json` | Verbatim fatwa snapshots                                 | Fetched from old.binothaimeen.net (the official site's HTML edition) by `tibyan_ai.ingestion.binothaimeen` |
| `corpus/hadeethenc/*.json`   | Verbatim hadith snapshots (text, grade, explanation)     | Fetched from the HadeethEnc public API by `tibyan_ai.ingestion.hadeethenc`                                 |
| `corpus/manifest.jsonl`      | The indexed snapshots without their text (versioned)     | `tibyan_ai.cli corpus-manifest`                                                                            |
| `eval/questions.yaml`        | Evaluation questions with expected outcomes              | Team                                                                                                       |

## Corpus snapshot format

```json
{
  "source_slug": "binbaz",
  "external_id": "1896",
  "url": "https://binbaz.org.sa/fatwas/1896/…",
  "title": "…",
  "question": "…", // verbatim
  "answer": "…", // verbatim; paragraphs separated by blank lines
  "collection": "فتاوى الجامع الكبير",
  "categories": [{ "id": 53, "name": "أحكام الجمع" }],
  "audio_url": "…",
  "fetched_at": "2026-10-03T00:40:00+00:00",
  "content_sha256": "…", // sha256(question + "\n\n" + answer)
  "fetcher": "tibyan_ai.ingestion.binbaz/1"
}
```

Rules:

- Never edit snapshot text by hand. Re-fetch instead:
  `node scripts/py.mjs -m tibyan_ai.cli fetch-binbaz --categories 50:4,53:3`
  (`--categories all:1 --limit N` takes page 1 of every leaf fiqh category and spreads N new fatwas over them;
  `fetch-binothaimeen` takes the same options).
- `content_sha256` is verified at ingestion; a mismatch aborts seeding.
- Only sources with status `approved` are retrievable.
