# Feed Filter (formerly "YouTube Content Filter")

Hides YouTube videos whose title/channel don't match categories you've
chosen. Works on the home feed, search results, sidebar recommendations,
and shorts shelf.

## Load it in Chrome

1. Go to `chrome://extensions`
2. Turn on **Developer mode** (top right)
3. Click **Load unpacked**
4. Select this folder (`youtube-content-filter`)
5. Click the extension icon in your toolbar, turn the filter **on**, and
   check the categories you want to see (e.g. Sports, News & Politics)
6. Go to youtube.com — anything outside your chosen categories collapses
   into a thin gray strip. Click a strip to reveal that one video anyway.

## Using the smart backend (embeddings + LLM classification)

By default the extension classifies with local keyword matching only —
fast, but blunt (see `classifier.js`). If you've deployed the
[classification backend](../ycf-backend), you can switch to it:

1. Start the backend (`docker compose up` in the backend folder, or run it
   locally — see its README).
2. Open the extension popup, enter the backend's URL in the "API URL"
   field (defaults to `http://localhost:8000`) and click **Save API URL**.
   Chrome will prompt you to grant permission for that origin — accept it.
3. Toggle **Use smart backend** on.

Once enabled, every video gets classified twice: instantly by the local
keyword matcher (so nothing flashes visible before disappearing), then
authoritatively by the backend once its response arrives, which can
change a video from hidden to shown or vice versa if the local guess was
wrong. Debug mode logs both passes to the console so you can see the
local guess get superseded.

If the backend is unreachable, the extension silently keeps the local
keyword-only result — no errors surface to the user, it just behaves as
if the backend toggle were off for that video.

## Study Mode

Category filtering alone has a gap: a video can be correctly tagged
"Education" and still be a hype-driven clickbait video, and a channel you'd
normally block might occasionally post something calm and on-topic. Study
Mode adds a second, independent axis — a "focus score" — on top of category
filtering, plus a hard rule for Shorts:

- **Category allow-list** (existing behavior) still applies first.
- **Focus score**: even a video in an allowed category gets hidden if it
  scores below your chosen strictness threshold on the focus/distraction
  scale. This uses the backend's semantic score when available (see
  `app/focus.py`), or a local keyword heuristic otherwise.
- **Shorts are blocked outright** when Study Mode is on, regardless of
  category or focus score — the format itself is built for endless
  scrolling. Trusted channels are exempt.
- **Custom block keywords**: an explicit, always-wins override. Add
  comma-separated terms (e.g. `prank, reaction, vs`) and any matching
  title is hidden no matter what category or focus score it gets.

Turn it on in the popup, pick a strictness level (Lenient/Balanced/Strict),
and optionally add block keywords. Works with or without the smart backend
enabled — the local keyword heuristic (`classifyFocus` in `classifier.js`)
covers the no-backend case, just less accurately.

## How classification works right now

Pure keyword matching against video title + channel name + description
snippet (see `classifier.js`). No network calls, no ML model — fast enough
to keep up with scrolling, but it will misclassify things a smarter model
wouldn't. That's expected for this stage.

## Known limitations (MVP, by design)

- **Keyword classifier is blunt.** A video titled "Why the Fed just changed
  everything" will hit Finance AND News keywords — whichever list matches
  more keywords wins, which isn't always the "correct" call.
- **No category = no filtering.** If you haven't checked any categories yet,
  everything shows (so you're not staring at a blank YouTube on first
  install).
- **Uncategorized videos are hidden**, not shown, once filtering is on —
  intentional fail-closed behavior, since the whole point is "don't show me
  stuff I didn't ask for."
- **Shorts within a regular video's page** and some experimental YouTube
  layouts may not be caught yet; YouTube changes its DOM structure often.
- **No sync across devices beyond Chrome's own `storage.sync`.**

## Natural next steps

1. Swap/augment the keyword classifier with a small on-device model
   (e.g. via transformers.js) for cases keywords miss.
2. Add a "trusted channels" allow-list so a finance YouTuber's vlog-style
   video isn't hidden just because it lacks finance keywords.
3. Track how much content gets hidden per session — a lightweight stat
   that shows the user "you skipped X non-matching videos today" is good
   for both delight and validating the tool is working.
4. Port to Android via an Accessibility Service for native-app coverage
   (Instagram, TikTok) — a much bigger lift, separate project phase.
5. Handle YouTube's SPA navigation more explicitly (listen for
   `yt-navigate-finish` events) rather than relying purely on
   MutationObserver.
