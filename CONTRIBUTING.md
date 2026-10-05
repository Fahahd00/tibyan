# Contributing to تِبْيان | Tibyan

Thank you for helping build Tibyan. This guide is the team contract: follow it so that
anyone can pick up anyone else's work.

> **Golden rule:** if source safety and convenience disagree, source safety wins.
> If speed and verification disagree, verification wins.

---

## 1. Local setup

Prerequisites: **Git**, **Docker Desktop** (or Docker Engine + Compose v2), **Node.js ≥ 20.9**,
**Python ≥ 3.11** (only if you run the AI service outside Docker).

```bash
git clone <repo-url> tibyan
cd tibyan
cp .env.example .env          # then edit values you need
docker compose up --build     # db → migrate → seed/index → ai → api → web
```

Open http://localhost:3000.

### Running services outside Docker (faster iteration)

```bash
npm install                                   # all JS workspaces
docker compose up -d db                       # just the database
npm run db:migrate                            # apply SQL migrations
npm run ai:setup                              # create services/ai/.venv and install deps
npm run db:seed                               # register sources + index corpus
npm run dev                                   # web + api + ai with hot reload
```

---

## 2. Branches

| Prefix       | Use for                     | Example                     |
| ------------ | --------------------------- | --------------------------- |
| `feature/*`  | New capability              | `feature/voice`             |
| `fix/*`      | Bug fix                     | `fix/empty-retrieval`       |
| `refactor/*` | Behaviour-preserving change | `refactor/source-ingestion` |
| `docs/*`     | Documentation only          | `docs/setup-windows`        |
| `test/*`     | Tests only                  | `test/abstention-cases`     |
| `chore/*`    | Tooling, deps, CI           | `chore/upgrade-next`        |

- `main` — always demo-able. Only receives merges from `develop` (or hotfixes) via PR.
- `develop` — integration branch. All feature PRs target `develop`.
- Branch from the latest `develop`: `git switch develop && git pull && git switch -c feature/x`.
- **Never** `git push --force` to `main`, `develop`, or anyone else's branch.
  On your own branch prefer `git push --force-with-lease` if you must rewrite history.
- Never delete a teammate's branch. Never `git reset --hard` over uncommitted work you did not write.

## 3. Commits — Conventional Commits

```
<type>(optional scope): <imperative summary>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`, `build`.

Good:

```
feat(rag): add hybrid dense + sparse retrieval
fix(verification): reject claims whose quote is not in the cited chunk
docs: document seed process
```

Not accepted: `update`, `changes`, `fix stuff`, `final`, `final2`.

The `commit-msg` hook enforces the format locally.

## 4. Pull requests

1. Keep PRs focused on one concern; split large work into reviewable PRs.
2. Fill in the PR template (what / why / files / how to run / how to test).
3. CI must be green (lint → typecheck → tests → build).
4. At least one teammate approval. Changes to `data/sources/**`, `services/ai/tibyan_ai/rules/**`
   or `services/ai/tibyan_ai/pipeline/safety.py` also need the **governance lead**.
5. Squash-merge or merge-commit into `develop`; delete _your own_ branch after merge.

## 5. Quality gates

```bash
npm run lint          # ESLint (web, api, contracts) + ruff (ai)
npm run typecheck     # tsc --noEmit for TS workspaces
npm test              # vitest (api) + pytest (ai)
npm run build         # production builds
npm run format        # Prettier
```

Husky + lint-staged run Prettier/ESLint on staged files before each commit.

Python only:

```bash
cd services/ai
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest -q
```

## 6. Environment variables

- Add every new variable to `.env.example` with a comment, in the same PR.
- Never commit `.env`, keys, tokens, passwords, or service-account files.
- CI and tests must never require real provider keys — use the test providers.

## 7. Database

- Schema changes go in a **new** file in `db/migrations/` named `NNNN_short_description.sql`.
  Never edit a migration that has been merged; add a new one instead.
- `npm run db:migrate` applies pending migrations (checksummed; edits to applied files are rejected).
- Seed data must have a documented, verifiable origin (see `data/README.md`).

## 8. Sources and content

- New sources are added to `data/sources/registry.yaml` with status `pending`.
  Only the governance lead moves a source to `approved` or `blocked`.
- Corpus snapshots are verbatim. Do not edit fetched text by hand.
- Never add fabricated fatwas, citations, phone numbers, or links — not even "for testing".
  Unit tests use clearly synthetic fixtures that are never loaded into the real database.

## 9. Team ownership

| Area                  | Primary paths                                                               | Owner role               |
| --------------------- | --------------------------------------------------------------------------- | ------------------------ |
| Frontend / UI-UX      | `apps/web`                                                                  | Full-stack               |
| Backend API           | `apps/api`, `packages/contracts`                                            | Full-stack               |
| AI / RAG              | `services/ai/tibyan_ai/{pipeline,providers,ingestion}`                      | AI engineer              |
| Verification & safety | `services/ai/tibyan_ai/pipeline/{verification,safety}.py`, `rules/`         | AI engineer + governance |
| Voice                 | `services/ai/tibyan_ai/providers/*speech*`, `apps/web/src/components/voice` | Full-stack + AI          |
| Database              | `db/migrations`, `apps/api/src/db`                                          | Full-stack               |
| DevOps                | `docker-compose.yml`, `**/Dockerfile`, `.github/workflows`                  | Any (rotating)           |
| Sources & governance  | `data/sources`, `data/escalation`                                           | Governance lead          |
| Testing & evaluation  | `**/tests`, `data/eval`                                                     | Everyone                 |

Every area has docs and tests so that no feature depends on a single person.
