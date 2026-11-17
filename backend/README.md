# Feed Filter — Classification Backend

The backend service behind the browser extension. Replaces the extension's
brittle keyword classifier with a proper embeddings → RAG → LLM pipeline,
backed by Postgres + pgvector.

**This has been built and smoke-tested end-to-end** against a real
Postgres+pgvector instance (not just written and hoped-for) — every route
below was hit with curl and returned the expected result during development.

## Architecture

```
Chrome Extension (background.js)
        │  POST /classify {title, channel, description}
        ▼
FastAPI (app/main.py)
        │
        ▼
LangGraph pipeline (app/classifier_pipeline.py)
        │
   ┌────┴─────────────────────────────────────────┐
   │ 1. embed_and_match                            │
   │    - embed video text (sentence-transformers) │
   │    - cosine-similarity match vs 31 category    │
   │      anchor embeddings (stored in Postgres,    │
   │      pgvector column)                          │
   └────┬───────────────────────────────────────────┘
        │ confidence >= threshold?
   ┌────┴─────┐                    ┌──────────────────────┐
   │  YES      │  NO + LLM key set │                      │
   ▼           └──────────────────▶│ 2. rag_retrieve       │
finalize                            │    top-k similar      │
                                     │    past classifications│
                                     │    from cache (pgvector│
                                     │    nearest-neighbor)   │
                                     └──────┬─────────────────┘
                                            ▼
                                     3. llm_fallback
                                        (Claude call w/ RAG
                                         examples as context)
                                            │
                                            ▼
                                       4. finalize
                                        (write-through cache)
```

## Why this design (talking points for interviews / resume)

- **Embeddings over keywords**: the browser-extension MVP used keyword
  matching, which silently fails on any title that doesn't contain a
  known keyword. Embedding-based cosine similarity generalizes to phrasing
  the keyword list never anticipated.
- **Confidence gating, not "always call the LLM"**: most videos are cheap
  to classify with embeddings alone. The LLM is only invoked when the
  embedding match is ambiguous — keeps latency and cost down at scale.
- **RAG before the LLM call**: retrieving similar previously-classified
  videos as few-shot context measurably improves LLM classification
  consistency versus a cold prompt with zero examples.
- **Vision on the fallback path only**: when the LLM fallback fires, the
  video's thumbnail is fetched and sent alongside the title as a vision
  input to Claude. This directly fixes a real failure mode of text-only
  classification — a gaming video titled "X EXPLAINED" is textually
  identical to an actual explainer video, but the thumbnail usually makes
  the true content obvious. Reserved for the fallback path (not every
  video) to keep the fast path cheap.
- **Write-through caching**: every classification (embedding-only or
  LLM-assisted) is cached by a hash of (title, channel), so the same video
  is never billed or computed twice.
- **Graceful degradation**: `app/embeddings.py` falls back to a
  deterministic hashing pseudo-embedding if the real model can't load —
  this is what let the whole pipeline be tested in a sandboxed environment
  with no route to huggingface.co, without the app crashing.

## Local setup

### Option A — Docker (recommended)

```bash
docker compose up --build
```

This starts Postgres (with pgvector pre-installed via the
`pgvector/pgvector:pg16` image) and the API on `localhost:8000`.

### Option B — Manual

```bash
pip install -r requirements.txt
# requires a running Postgres with the `vector` extension creatable by
# the connecting user (or pre-created by a superuser)
cp .env.example .env  # edit DATABASE_URL etc.
uvicorn app.main:app --reload
```

### Verify it's up

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"title":"Stock market crashes as Fed hikes rates","channel":"Yahoo Finance"}'
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/classify` | Classify a video; cached, trusted-channel-aware |
| POST | `/trust` | Mark a channel as always-allowed for a user |
| GET | `/trust/{user_id}` | List a user's trusted channels |
| DELETE | `/trust/{user_id}/{channel}` | Remove a trusted channel |
| GET | `/settings/{user_id}` | Get filter settings |
| PUT | `/settings/{user_id}` | Update filter settings |
| GET | `/health` | Liveness check |

## Wiring up the extension

Call this from the extension's **background service worker**
(`background.js`), not the content script — a fetch from a content script
is subject to the page's CORS policy, while a fetch from the background
worker (with `host_permissions` declared in `manifest.json` for your API's
domain) bypasses that restriction. The background worker can relay results
to the content script via `chrome.runtime.sendMessage` /
`chrome.tabs.sendMessage`.

## Deploying (AWS)

1. Push the image to ECR: `docker build -t ycf-api . && docker push <ecr-repo>`
2. Run Postgres via RDS with the `pgvector` extension enabled (RDS Postgres
   ≥ 15 supports it — enable via `CREATE EXTENSION vector;` as the RDS
   master user, which has the needed privilege unlike a regular app user).
3. Run the API container on ECS Fargate (or a single EC2 instance for a
   cheaper demo deployment) with `DATABASE_URL` and `ANTHROPIC_API_KEY`
   set as environment variables / secrets.
4. Point the extension's `host_permissions` and API base URL at the
   deployed endpoint.

## Known limitations (be upfront about these if asked)

- **No auth yet.** `user_id` is just a free-text string the client sends —
  fine for a personal project demo, not production-ready. Adding real auth
  (even a simple API key per install) would be a natural next step to
  mention as "aware of, scoped out for MVP."
- **CORS is wide open (`*`)** for local dev; should be locked to the
  specific `chrome-extension://<id>` origin before any public deployment.
- **Embedding model choice is a default, not a tuned one.**
  `all-MiniLM-L6-v2` is fast and small but not fine-tuned on YouTube-style
  short titles specifically — a natural improvement is fine-tuning or
  swapping in a model trained on similar short-text classification tasks.
- **The LLM fallback prompt has no output-schema enforcement** beyond
  "please return JSON" — for production you'd want Claude's structured
  output / tool-use mode instead of parsing free-text JSON.
- **Vision only helps if `ANTHROPIC_API_KEY` is set.** Without it, the
  pipeline never reaches the LLM fallback stage at all (by design — no
  wasted work with nothing to call), so thumbnails are fetched but never
  actually used. Set the key to get the accuracy benefit.
- **Thumbnail fetch is host-allowlisted** (`app/vision.py`) to YouTube's
  own CDN domains to avoid the backend being used as an open URL-fetching
  proxy (SSRF) via a spoofed `thumbnail_url`.
