# Security Policy

## Reporting a vulnerability

Do **not** open a public issue for security problems. Contact the team lead privately with:
a description, reproduction steps, impact, and any suggested fix. We aim to acknowledge
reports within 72 hours during the hackathon period.

## Secrets

- Secrets live only in `.env` (git-ignored) or the deployment platform's secret store.
- `.env.example` contains placeholders only.
- CI runs without any real provider keys.
- If a secret is committed by mistake: **rotate it immediately** (deleting the commit is not
  enough — it remains in history and forks), then tell the team lead. Do not paste the
  secret into issues or chat while reporting it.

### Secret incidents log

| Date | What                                           | Status |
| ---- | ---------------------------------------------- | ------ |
| —    | No secrets have been found in this repository. | —      |

## Data protection

- User questions are scanned for personal data (names, phone numbers, e-mails, national IDs,
  IBANs, card numbers) and **redacted before** they are stored or sent to any AI provider.
- Only the redacted question is persisted. PII findings are stored as types and counts, never values.
- IP addresses are stored only as salted hashes in the audit log.
- Sessions are anonymous random identifiers in an `HttpOnly`, `SameSite=Lax` cookie.

## AI-specific threats

| Threat                                    | Control                                                                                                                                                                  |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Prompt injection inside retrieved sources | Evidence is passed as delimited data; the system prompt states it is not instructions; every output claim is independently verified against the evidence before display. |
| Hallucinated rulings                      | Claims must quote the cited evidence verbatim and pass entailment; otherwise removed or the system abstains.                                                             |
| Unapproved sources leaking into answers   | Retrieval SQL filters `sources.status = 'approved'` and `documents.status = 'active'`.                                                                                   |
| Voice bypassing safety                    | Transcripts enter the same `/api/questions` pipeline; TTS only speaks stored, verified answers by id.                                                                    |
| Abuse / cost exhaustion                   | Rate limiting on the API gateway; request size limits; internal token between API and AI service.                                                                        |
| Admin misuse                              | Admin endpoints require `ADMIN_TOKEN`; every status change is written to `audit_logs`.                                                                                   |

## Supported versions

Only the latest `main` is supported during the demo phase.
