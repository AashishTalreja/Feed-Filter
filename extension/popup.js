const DEFAULT_API_BASE = "http://localhost:8000";

const listEl = document.getElementById("categoryList");
const toggleEl = document.getElementById("enabledToggle");
const debugToggleEl = document.getElementById("debugToggle");
const backendToggleEl = document.getElementById("backendToggle");
const apiBaseInputEl = document.getElementById("apiBaseInput");
const apiBaseSaveEl = document.getElementById("apiBaseSave");
const studyModeToggleEl = document.getElementById("studyModeToggle");
const focusStrictnessEl = document.getElementById("focusStrictness");
const blockKeywordsInputEl = document.getElementById("blockKeywordsInput");
const blockKeywordsSaveEl = document.getElementById("blockKeywordsSave");
const statusEl = document.getElementById("statusMsg");

function renderCategories(allowedCategories) {
  listEl.innerHTML = "";
  Object.entries(window.__ycf_CATEGORIES).forEach(([key, def]) => {
    const row = document.createElement("label");
    row.className = "category-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = allowedCategories.includes(key);
    checkbox.dataset.key = key;
    checkbox.addEventListener("change", onCategoryChange);

    const span = document.createElement("span");
    span.textContent = def.label;

    row.appendChild(checkbox);
    row.appendChild(span);
    listEl.appendChild(row);
  });
}

function getSelectedCategories() {
  return Array.from(listEl.querySelectorAll("input[type=checkbox]:checked")).map(
    (el) => el.dataset.key
  );
}

function onCategoryChange() {
  const allowedCategories = getSelectedCategories();
  chrome.storage.sync.set({ allowedCategories }, () => {
    flashStatus(`Showing ${allowedCategories.length || "all"} categor${allowedCategories.length === 1 ? "y" : "ies"}`);
  });
}

function onToggleChange() {
  chrome.storage.sync.set({ enabled: toggleEl.checked }, () => {
    flashStatus(toggleEl.checked ? "Filter on" : "Filter off");
  });
}

function flashStatus(msg) {
  statusEl.textContent = msg;
  setTimeout(() => {
    statusEl.textContent = "";
  }, 2000);
}

function originPatternFor(urlString) {
  try {
    const url = new URL(urlString);
    return `${url.origin}/*`;
  } catch {
    return null;
  }
}

function requestPermissionFor(urlString) {
  return new Promise((resolve) => {
    const pattern = originPatternFor(urlString);
    if (!pattern) {
      resolve(false);
      return;
    }
    chrome.permissions.request({ origins: [pattern] }, (granted) => resolve(!!granted));
  });
}

async function onBackendToggleChange() {
  if (!backendToggleEl.checked) {
    chrome.storage.sync.set({ useBackend: false });
    flashStatus("Using local keyword matching");
    return;
  }

  const { apiBase } = await chrome.storage.sync.get(["apiBase"]);
  const base = apiBase || DEFAULT_API_BASE;
  const granted = await requestPermissionFor(base);

  if (!granted) {
    backendToggleEl.checked = false;
    flashStatus("Permission denied — backend not enabled");
    return;
  }

  chrome.storage.sync.set({ useBackend: true });
  flashStatus("Backend classification on");
}

async function onApiBaseSave() {
  const value = apiBaseInputEl.value.trim() || DEFAULT_API_BASE;
  const granted = await requestPermissionFor(value);

  if (!granted) {
    flashStatus("Permission denied — URL not saved");
    return;
  }

  chrome.storage.sync.set({ apiBase: value }, () => {
    flashStatus("API URL saved");
  });
}

function onStudyModeToggle() {
  chrome.storage.sync.set({ studyMode: studyModeToggleEl.checked }, () => {
    flashStatus(studyModeToggleEl.checked ? "Study Mode on" : "Study Mode off");
  });
}

function onStrictnessChange() {
  const focusThreshold = parseFloat(focusStrictnessEl.value);
  chrome.storage.sync.set({ focusThreshold }, () => {
    flashStatus("Strictness saved");
  });
}

function onBlockKeywordsSave() {
  const blockKeywords = blockKeywordsInputEl.value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  chrome.storage.sync.set({ blockKeywords }, () => {
    flashStatus(`Blocking ${blockKeywords.length} keyword${blockKeywords.length === 1 ? "" : "s"}`);
  });
}

chrome.storage.sync.get(
  [
    "enabled", "allowedCategories", "debug", "useBackend", "apiBase",
    "studyMode", "focusThreshold", "blockKeywords"
  ],
  (res) => {
    toggleEl.checked = !!res.enabled;
    debugToggleEl.checked = !!res.debug;
    backendToggleEl.checked = !!res.useBackend;
    apiBaseInputEl.value = res.apiBase || DEFAULT_API_BASE;
    studyModeToggleEl.checked = !!res.studyMode;
    focusStrictnessEl.value = String(typeof res.focusThreshold === "number" ? res.focusThreshold : 0.5);
    blockKeywordsInputEl.value = (res.blockKeywords || []).join(", ");
    renderCategories(res.allowedCategories || []);
  }
);

toggleEl.addEventListener("change", onToggleChange);
debugToggleEl.addEventListener("change", () => {
  chrome.storage.sync.set({ debug: debugToggleEl.checked });
});
backendToggleEl.addEventListener("change", onBackendToggleChange);
apiBaseSaveEl.addEventListener("click", onApiBaseSave);
studyModeToggleEl.addEventListener("change", onStudyModeToggle);
focusStrictnessEl.addEventListener("change", onStrictnessChange);
blockKeywordsSaveEl.addEventListener("click", onBlockKeywordsSave);
