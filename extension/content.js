// content.js
// Watches YouTube's feed (home, search, sidebar, shorts shelf) and hides
// any video card whose title/channel doesn't match an allowed category.
//
// Classification happens in two phases:
//   1. Instant local keyword guess (classifier.js) - applied immediately so
//      nothing flashes visible-then-hidden while we wait on a network call.
//   2. If "use backend" is on, the background worker calls the FastAPI
//      classification service (embeddings + RAG + LLM) and the result
//      supersedes the local guess once it arrives.

const CONTAINER_SELECTORS = [
  "ytd-rich-item-renderer",        // home grid
  "ytd-video-renderer",            // search results (classic)
  "ytd-compact-video-renderer",    // watch page sidebar
  "ytd-grid-video-renderer",       // channel/grid pages (classic)
  "ytd-reel-item-renderer",        // shorts shelf items
  "ytd-rich-grid-media",           // some home layouts
  "yt-lockup-view-model"           // newer YouTube markup — appears bare
                                    // (unwrapped) on search results and
                                    // channel pages, not just nested inside
                                    // the classic renderers above
];

const SELECTOR_STRING = CONTAINER_SELECTORS.join(",");
const processed = new WeakSet();

// content-script-level cache so repeated appearances of the same video
// (e.g. in the sidebar) don't trigger duplicate background messages.
const remoteResultCache = new Map();

// Some pages nest a matched selector inside another matched selector
// (e.g. home page: ytd-rich-item-renderer > ... > yt-lockup-view-model).
// Only the outermost one should actually get hidden — hiding both is
// harmless visually but wastes a duplicate classification + reveal strip.
function outermostOnly(nodeList) {
  const nodes = Array.from(nodeList);
  return nodes.filter((node) => !nodes.some((other) => other !== node && other.contains(node)));
}

let settings = {
  enabled: false,
  allowedCategories: [],
  debug: false,
  trustedChannels: [],
  useBackend: false,
  studyMode: false,
  focusThreshold: 0.5,
  blockKeywords: []
};

function loadSettings(cb) {
  chrome.storage.sync.get(
    [
      "enabled", "allowedCategories", "debug", "trustedChannels", "useBackend",
      "studyMode", "focusThreshold", "blockKeywords"
    ],
    (res) => {
      settings = {
        enabled: !!res.enabled,
        allowedCategories: res.allowedCategories || [],
        debug: !!res.debug,
        trustedChannels: res.trustedChannels || [],
        useBackend: !!res.useBackend,
        studyMode: !!res.studyMode,
        focusThreshold: typeof res.focusThreshold === "number" ? res.focusThreshold : 0.5,
        blockKeywords: res.blockKeywords || []
      };
      if (cb) cb();
    }
  );
}

function extractTitle(container) {
  // Try the classic (pre-2026) structure first — still present on some
  // cards during YouTube's staggered rollout of yt-lockup-view-model.
  const classicTitleEl = container.querySelector("#video-title, #video-title-link");
  if (classicTitleEl && classicTitleEl.textContent.trim()) {
    return classicTitleEl.textContent.trim();
  }

  // yt-lockup-view-model fallback: the anchor linking to the video almost
  // always carries a `title` attribute with the exact video title, even
  // when the internal div/class structure around it changes. This is an
  // accessibility attribute, so it's far more stable than class names.
  const watchLink = container.querySelector('a[href*="/watch"], a[href*="/shorts/"]');
  if (watchLink) {
    const titleAttr = watchLink.getAttribute("title");
    if (titleAttr && titleAttr.trim()) return titleAttr.trim();

    const ariaLabel = watchLink.getAttribute("aria-label");
    if (ariaLabel && ariaLabel.trim()) {
      // aria-label is often "<title> by <channel> <views> <time ago> <duration>"
      // — strip the trailing " by <channel> ..." if present, best-effort.
      const byIndex = ariaLabel.indexOf(" by ");
      return (byIndex > 0 ? ariaLabel.slice(0, byIndex) : ariaLabel).trim();
    }
  }

  // Last resort: any element that still uses the classic id, anywhere
  // inside a lockup wrapper.
  const lockupTitle = container.querySelector(
    "yt-lockup-metadata-view-model h3, yt-lockup-metadata-view-model a"
  );
  return lockupTitle ? lockupTitle.textContent.trim() : "";
}

function extractChannel(container) {
  const classicChannelEl = container.querySelector("#channel-name, ytd-channel-name");
  if (classicChannelEl && classicChannelEl.textContent.trim()) {
    return classicChannelEl.textContent.trim();
  }

  // Channel links are consistently /@handle or /channel/<id> regardless of
  // the surrounding markup version.
  const channelLink = container.querySelector('a[href^="/@"], a[href*="/channel/"]');
  return channelLink ? channelLink.textContent.trim() : "";
}

function extractDescription(container) {
  const classicDescEl = container.querySelector("#description-text, .metadata-snippet-text");
  if (classicDescEl && classicDescEl.textContent.trim()) {
    return classicDescEl.textContent.trim();
  }
  const lockupMetaRow = container.querySelector(
    ".yt-content-metadata-view-model-wiz__metadata-row, .yt-lockup-metadata-view-model-wiz__metadata-row"
  );
  return lockupMetaRow ? lockupMetaRow.textContent.trim() : "";
}

// YouTube video IDs are always present in the watch/shorts link's href,
// regardless of markup version or lazy-loaded <img src> state. Building
// the thumbnail URL from the ID (YouTube's public thumbnail CDN pattern)
// is far more reliable than reading the <img> tag directly, since
// thumbnails are lazy-loaded and often still show a placeholder src at
// the moment we scan the DOM.
function extractThumbnailUrl(container) {
  const link = container.querySelector('a[href*="/watch"], a[href*="/shorts/"]');
  if (!link) return null;

  const href = link.getAttribute("href") || "";
  const watchMatch = href.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
  const shortsMatch = href.match(/\/shorts\/([a-zA-Z0-9_-]{11})/);
  const videoId = (watchMatch && watchMatch[1]) || (shortsMatch && shortsMatch[1]);

  if (!videoId) return null;
  return `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;
}

function extractParts(container) {
  const title = extractTitle(container);
  const channel = extractChannel(container);
  const desc = extractDescription(container);
  const thumbnailUrl = extractThumbnailUrl(container);

  return { title, channel, desc, thumbnailUrl, text: `${title} ${channel} ${desc}`.trim() };
}

function remoteCacheKey(parts) {
  return `${parts.title}::${parts.channel}`;
}

function isShortsContainer(container) {
  const tag = container.tagName.toLowerCase();
  return tag === "ytd-reel-item-renderer" || !!container.querySelector('a[href*="/shorts/"]');
}

function matchesBlockKeyword(text) {
  const normalized = text.toLowerCase();
  return settings.blockKeywords.find((kw) => kw && normalized.includes(kw.toLowerCase()));
}

function applyDecision(container, parts, result, { provisional }) {
  container.classList.remove("ycf-hidden", "ycf-visible");

  if (!settings.enabled) {
    container.classList.add("ycf-visible");
    delete container.dataset.ycfCategory;
    return;
  }

  // Custom block keywords are an explicit, manual override — they win
  // regardless of category, trust, or study mode.
  const blockedKeyword = matchesBlockKeyword(parts.text);
  if (blockedKeyword) {
    container.classList.add("ycf-hidden");
    container.dataset.ycfCategory = "blocked-keyword";
    ensureRevealStrip(container, parts, { category: null, label: `Blocked: "${blockedKeyword}"` });
    if (settings.debug) {
      console.log(`[YCF] "${parts.title.slice(0, 60)}" | blocked by custom keyword "${blockedKeyword}"`);
    }
    return;
  }

  const isTrustedChannel =
    parts.channel && settings.trustedChannels.includes(parts.channel);

  // Study Mode hard rule: Shorts are structurally built for endless
  // scrolling regardless of topic, so they're blocked outright unless the
  // channel is explicitly trusted.
  if (settings.studyMode && !isTrustedChannel && isShortsContainer(container)) {
    container.classList.add("ycf-hidden");
    container.dataset.ycfCategory = "shorts-blocked";
    ensureRevealStrip(container, parts, { category: null, label: "Shorts (blocked in Study Mode)" });
    return;
  }

  const allowed = settings.allowedCategories;
  const categoryAllowed =
    allowed.length === 0 || // nothing selected yet = don't filter
    isTrustedChannel ||
    (result.category && allowed.includes(result.category));

  // Focus score: prefer the backend's semantic score when available
  // (present on the "final" result), otherwise fall back to the local
  // keyword heuristic for the instant provisional pass.
  const focusScore = typeof result.focus_score === "number"
    ? result.focus_score
    : window.__ycf_classifyFocus(parts.text);

  const focusOk = !settings.studyMode || isTrustedChannel || focusScore >= settings.focusThreshold;
  const isAllowed = categoryAllowed && focusOk;

  if (settings.debug) {
    const matchedInfo = result.matched ? ` hits: ${result.matched.join(", ")}` : "";
    console.log(
      `[YCF] ${provisional ? "(provisional) " : "(final) "}"${parts.title.slice(0, 60)}" ` +
      `| channel="${parts.channel}" | category=${result.category || "none"} ` +
      `(${result.confidence?.toFixed ? result.confidence.toFixed(2) : result.confidence}${matchedInfo}) ` +
      `| focus=${focusScore.toFixed(2)}${settings.studyMode ? ` (threshold ${settings.focusThreshold})` : ""} ` +
      `| method=${result.method || "keyword"} | trusted=${isTrustedChannel} | => ${isAllowed ? "SHOW" : "HIDE"}`
    );
  }

  container.dataset.ycfProvisional = provisional ? "1" : "0";

  if (isAllowed) {
    container.classList.add("ycf-visible");
    delete container.dataset.ycfCategory;
  } else {
    container.classList.add("ycf-hidden");
    container.dataset.ycfCategory = result.category || "uncategorized";
    ensureRevealStrip(container, parts, result);
  }
}

function trustChannel(channel) {
  if (!channel) return;
  chrome.storage.sync.get(["trustedChannels"], (res) => {
    const list = res.trustedChannels || [];
    if (!list.includes(channel)) {
      list.push(channel);
      chrome.storage.sync.set({ trustedChannels: list });
    }
  });
  // Persist server-side too, if a backend is configured, so the trust
  // decision survives a reinstall / follows the user across devices.
  if (settings.useBackend) {
    chrome.runtime.sendMessage({ type: "trust", payload: { channel } });
  }
}

function ensureRevealStrip(container, parts, result) {
  const existing = container.querySelector(".ycf-reveal-strip");
  if (existing) existing.remove(); // rebuild in case the label changed on the final result

  const categoryDef = result.category && window.__ycf_CATEGORIES[result.category];
  const label = categoryDef ? categoryDef.label : (result.label || "Uncategorized");

  const strip = document.createElement("div");
  strip.className = "ycf-reveal-strip";

  const showOnce = document.createElement("span");
  showOnce.textContent = `Hidden (${label}) — show anyway`;
  showOnce.className = "ycf-reveal-action";
  showOnce.addEventListener("click", (e) => {
    e.stopPropagation();
    e.preventDefault();
    container.classList.remove("ycf-hidden");
    container.classList.add("ycf-visible", "ycf-revealed-once");
  });

  strip.appendChild(showOnce);

  if (parts.channel) {
    const trustLink = document.createElement("span");
    trustLink.textContent = " · always allow this channel";
    trustLink.className = "ycf-trust-action";
    trustLink.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      trustChannel(parts.channel);
      container.classList.remove("ycf-hidden");
      container.classList.add("ycf-visible", "ycf-revealed-once");
    });
    strip.appendChild(trustLink);
  }

  container.appendChild(strip);
}

function requestRemoteClassification(container, parts) {
  const key = remoteCacheKey(parts);

  if (remoteResultCache.has(key)) {
    if (container.isConnected) {
      applyDecision(container, parts, remoteResultCache.get(key), { provisional: false });
    }
    return;
  }

  chrome.runtime.sendMessage(
    {
      type: "classify",
      payload: {
        title: parts.title,
        channel: parts.channel,
        description: parts.desc,
        thumbnail_url: parts.thumbnailUrl
      }
    },
    (response) => {
      if (chrome.runtime.lastError) {
        if (settings.debug) console.warn("[YCF] backend call failed:", chrome.runtime.lastError.message);
        return; // keep the provisional local-keyword decision
      }
      if (!response || !response.ok) {
        if (settings.debug) console.warn("[YCF] backend returned an error:", response?.error);
        return;
      }

      const remote = response.result; // { category, label, confidence, method, cached }
      remoteResultCache.set(key, remote);

      if (container.isConnected) {
        applyDecision(container, parts, remote, { provisional: false });
      }
    }
  );
}

function processContainer(container) {
  const parts = extractParts(container);

  if (settings.debug && !parts.title) {
    console.warn(
      "[YCF] Could not extract a title from this container — YouTube's markup " +
      "may have changed again. Container:", container
    );
  }

  // Phase 1: instant local guess, applied immediately.
  const localResult = window.__ycf_classifyText(parts.text);
  applyDecision(container, parts, localResult, { provisional: true });

  // Phase 2: authoritative backend result, applied when it arrives.
  if (settings.useBackend) {
    requestRemoteClassification(container, parts);
  }

  processed.add(container);
}

function scan(root = document) {
  const rawNodes = root.querySelectorAll
    ? root.querySelectorAll(SELECTOR_STRING)
    : [];
  outermostOnly(rawNodes).forEach((node) => {
    if (!processed.has(node)) {
      processContainer(node);
    }
  });
}

function reprocessAll() {
  remoteResultCache.clear();
  outermostOnly(document.querySelectorAll(SELECTOR_STRING)).forEach((node) => {
    processContainer(node);
  });
}

let scheduled = false;
function scheduleScan() {
  if (scheduled) return;
  scheduled = true;
  setTimeout(() => {
    scheduled = false;
    scan();
  }, 150);
}

function init() {
  loadSettings(() => {
    scan();
    const observer = new MutationObserver(() => scheduleScan());
    observer.observe(document.documentElement, { childList: true, subtree: true });
  });
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "sync") return;
  loadSettings(() => reprocessAll());
});

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
