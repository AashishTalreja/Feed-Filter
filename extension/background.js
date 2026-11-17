// background.js
// The extension's background service worker is the only place cross-origin
// fetches to the classification backend are allowed to happen without
// running into the page's CORS policy (a content script's fetch is subject
// to CORS; a background worker's fetch, backed by a declared
// host_permission, is not). The content script sends a message here and
// gets the classification result back.

const DEFAULT_API_BASE = "http://localhost:8000";

// Small in-memory cache so repeated videos in the same browsing session
// don't round-trip to the backend again (the backend also caches, but this
// saves the network hop entirely).
const memoryCache = new Map();

function cacheKey(title, channel) {
  return `${title}::${channel}`;
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(
    [
      "enabled", "allowedCategories", "useBackend", "apiBase", "userId",
      "studyMode", "focusThreshold", "blockKeywords"
    ],
    (res) => {
      const updates = {};
      if (res.enabled === undefined) updates.enabled = false;
      if (res.allowedCategories === undefined) updates.allowedCategories = [];
      if (res.useBackend === undefined) updates.useBackend = false;
      if (res.apiBase === undefined) updates.apiBase = DEFAULT_API_BASE;
      if (res.userId === undefined) updates.userId = crypto.randomUUID();
      if (res.studyMode === undefined) updates.studyMode = false;
      if (res.focusThreshold === undefined) updates.focusThreshold = 0.5;
      if (res.blockKeywords === undefined) updates.blockKeywords = [];
      if (Object.keys(updates).length) chrome.storage.sync.set(updates);
    }
  );
});

async function classifyRemote({ title, channel, description, thumbnail_url }) {
  const key = cacheKey(title, channel);
  if (memoryCache.has(key)) {
    return memoryCache.get(key);
  }

  const { apiBase, userId } = await chrome.storage.sync.get(["apiBase", "userId"]);
  const base = apiBase || DEFAULT_API_BASE;

  const response = await fetch(`${base}/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title, channel, description, thumbnail_url,
      user_id: userId || "default"
    })
  });

  if (!response.ok) {
    throw new Error(`Classify request failed: ${response.status}`);
  }

  const result = await response.json();
  memoryCache.set(key, result);
  return result;
}

async function trustRemote({ channel }) {
  const { apiBase, userId } = await chrome.storage.sync.get(["apiBase", "userId"]);
  const base = apiBase || DEFAULT_API_BASE;

  await fetch(`${base}/trust`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel, user_id: userId || "default" })
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "classify") {
    classifyRemote(message.payload)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true; // keep the message channel open for the async response
  }

  if (message?.type === "trust") {
    trustRemote(message.payload)
      .then(() => sendResponse({ ok: true }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
});
