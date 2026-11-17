# Feed Filter

**Category-level content filtering for YouTube — because app blockers don't work.**

Feed Filter is a Chrome extension + AI backend that filters *what* you see within an app, not whether you can open it at all. Pick the categories you actually want (Education, News, Sports, etc.) and everything else on your YouTube feed collapses into a one-line strip — still there if you genuinely need it, but no longer the thing your eyes land on when you open the app "just to check one thing."

---

## The problem

Screen-time limiters and app blockers operate at the wrong layer. Blocking Instagram or YouTube entirely doesn't work in practice — you reopen the app for a legitimate reason (a work notification, a specific video someone sent you) and end up doomscrolling anyway, because once the app is open, *everything* in it is equally accessible. The blocker can't tell the difference between the video you meant to watch and the forty minutes of recommended content next to it.

Feed Filter works one layer deeper: it reads the actual content on the page in real time and hides what doesn't match your intent, without blocking the app itself.

## How it works

```
Chrome Extension (content script)
        │  scans the DOM, extracts title/channel/thumbnail per video
        ▼
Local keyword classifier (instant, no network)
        │  applied immediately — nothing flashes visible before disappearing
        ▼
Background service worker ──► FastAPI backend
                                     │
                          LangGraph classification pipeline
                                     │
                   ┌─────────────────┴──────────────────┐
                   │ 1. Embed title + channel text        │
                   │    (sentence-transformers)            │
                   │ 2. Cosine-match against 31 official   │
                   │    YouTube category embeddings         │
                   │    (pgvector)                          │
                   └─────────────────┬──────────────────┘
                          confident? ──yes──► done
                                     │ no
                   ┌─────────────────▼──────────────────┐
                   │ 3. Retrieve similar past             │
                   │    classifications (RAG)              │
                   │ 4. Send title + thumbnail image to    │
                   │    a vision LLM for a final call      │
                   └─────────────────┬──────────────────┘
                                     ▼
                         Cached result returned to extension
                                     │
                                     ▼
                     Video shown or collapsed in the feed
```

Two independent signals decide what's shown:
- **Category match** — does this video belong to a category you've allowed?
- **Focus score** — is this video actually calm/on-task, or is it clickbait/hype dressed up in an allowed category? (A video titled "MATH TRICK THAT WILL BLOW YOUR MIND 🤯" can be nominally "Education" and still be exactly what you're trying to avoid.)

**Study Mode** combines both with a hard rule: Shorts are blocked outright regardless of category, since the format itself — not any specific video — is what's built for endless scrolling.

## Key features

- **Category filtering** across all 31 official YouTube video categories
- **Study Mode** — focus-score threshold + automatic Shorts blocking + custom block-keyword overrides
- **Trusted channels** — always-allow list that bypasses classification entirely
- **Multimodal fallback** — when text alone is ambiguous (e.g. "This Game EXPLAINED" reads identically to a real explainer, text-only), the backend sends the thumbnail image itself to a vision-capable LLM for the final call
- **Cost-conscious pipeline** — fast local matching first, embeddings second, LLM/vision only invoked when genuinely uncertain
- **Reveal, don't delete** — anything hidden is one click away, so the tool never feels like it's fighting you

## Tech stack

| Layer | Tech |
|---|---|
| Extension | JavaScript, Chrome Manifest V3, MutationObserver |
| Backend | Python, FastAPI |
| Orchestration | LangGraph |
| Embeddings | Sentence-Transformers (`all-MiniLM-L6-v2`) |
| Vector search | PostgreSQL + pgvector |
| LLM / Vision | Any OpenAI-compatible API — Groq (default, Llama 4 Scout), Gemini, OpenAI |
| Infra | Docker, Docker Compose |

## Repo structure

```
extension/            Chrome extension (Manifest V3)
  ├── manifest.json
  ├── content.js       DOM scanning + local classifier + hide/reveal logic
  ├── background.js    talks to the backend API
  ├── classifier.js    local keyword classifier + focus heuristic
  └── popup.{html,js,css}

backend/               FastAPI classification service
  ├── app/
  │   ├── main.py
  │   ├── classifier_pipeline.py   LangGraph pipeline
  │   ├── embeddings.py            sentence-transformers wrapper
  │   ├── focus.py                 focus/distraction scoring
  │   ├── vision.py                thumbnail fetch for vision fallback
  │   ├── categories.py            official YouTube taxonomy
  │   └── routers/                 classify / trust / settings endpoints
  ├── docker-compose.yml
  └── Dockerfile
```

## Setup

**Backend:**
```bash
cd backend
cp .env.example .env   # add LLM_API_KEY (free Groq or Gemini key)
docker compose up --build
```

**Extension:**
1. `chrome://extensions` → enable Developer mode → **Load unpacked** → select the `extension/` folder
2. Open the extension popup, save the backend's URL, grant the permission prompt, and turn the filter on

Full setup/troubleshooting details are in each folder's own README.

## Development notes — what actually broke and how it got fixed

This project went through a few real debugging cycles worth mentioning, because the failures were more informative than the happy path:

- **v1 (keyword-only) over-hid almost everything.** Most video titles simply don't contain literal keywords for their genre, so most videos fell into "uncategorized" and got hidden by default. This wasn't a filtering-logic bug — it was a classifier coverage problem, fixed by moving to embedding-based semantic matching instead of exact keyword hits.
- **Extraction silently broke mid-project** when YouTube rolled out a new internal component (`yt-lockup-view-model`), replacing the classic `#video-title` / `#channel-name` IDs the extension depended on. Fixed by extracting the video ID from the link's `href` instead — a much more stable signal than any specific class name, since YouTube's routing structure changes far less often than its internal markup.
- **Category alone wasn't sufficient** even after fixing extraction — a video correctly tagged "Education" could still be a hype-driven clickbait video. This is what motivated the separate focus-score axis rather than trying to force everything through a single classification dimension.

## Known limitations

- No auth on the backend yet — fine for personal/self-hosted use, not ready for arbitrary public traffic without adding API keys + rate limiting first
- Classification quality depends on the real embedding model being loaded; if `sentence-transformers` fails to install, the backend falls back to a much weaker hashing-based embedding so the pipeline doesn't crash, but accuracy drops noticeably
- Vision fallback only activates when `LLM_API_KEY` is set (and `LLM_MODEL` is vision-capable) and the text-only match is already ambiguous — no key means no vision-assisted classification, silently
- CORS is wide open (`*`) for local development and should be scoped to the specific extension origin before any public deployment

## Roadmap

- [ ] Labeled evaluation set + measured accuracy numbers
- [ ] Automated test suite (pytest)
- [ ] Public deployment + Chrome Web Store listing
- [ ] Per-install API keys + rate limiting
- [ ] Android version via Accessibility Service, for filtering outside the browser

## License

MIT