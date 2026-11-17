// classifier.js
// Lightweight, on-device keyword classifier. Runs fast enough to keep up
// with scroll speed. No network calls, no per-post latency.
//
// Each category maps to a set of keyword patterns. A video is scored against
// every category using its title + channel name + (if available) description
// snippet, and assigned to whichever category scores highest above a
// minimum threshold. If nothing matches confidently, it falls into
// "uncategorized" and is hidden by default (fail-closed, not fail-open —
// the whole point is to default to NOT showing you random stuff).

// Official YouTube video category taxonomy (from the YouTube Data API
// videoCategories.list). Not every category is commonly used for real
// uploads (e.g. 30-44 are mostly legacy/movie-listing categories) but
// they're included for completeness since the classifier works off
// keywords anyway, not real category IDs assigned by YouTube itself.

const CATEGORIES = {
  filmAnimation: {
    label: "Film & Animation",
    keywords: [
      "short film", "animated short", "animation", "animated", "cgi",
      "3d animation", "storyboard", "film production", "indie film",
      "student film", "vfx breakdown", "stop motion"
    ]
  },
  autosVehicles: {
    label: "Autos & Vehicles",
    keywords: [
      "car review", "test drive", "suv", "sedan", "motorcycle", "bike review",
      "engine", "horsepower", "0 to 60", "car mods", "restoration", "ev review",
      "electric vehicle", "truck review", "car show", "track day", "car build"
    ]
  },
  music: {
    label: "Music",
    keywords: [
      "official music video", "official audio", "lyric video", "album",
      "ep release", "new single", "cover song", "acoustic version", "remix",
      "live performance", "concert", "music producer", "beat making",
      "songwriting", "band", "artist", "playlist", "official mv"
    ]
  },
  petsAnimals: {
    label: "Pets & Animals",
    keywords: [
      "dog training", "puppy", "kitten", "cat behavior", "pet care",
      "wildlife", "animal rescue", "vet visit", "aquarium", "zoo",
      "horse riding", "exotic pets", "bird watching", "animal documentary"
    ]
  },
  sports: {
    label: "Sports",
    keywords: [
      "football", "soccer", "basketball", "baseball", "hockey", "nba", "nfl",
      "mlb", "nhl", "fifa", "premier league", "champions league", "world cup",
      "cricket", "ipl", "tennis", "olympics", "highlights", "match highlights",
      "tournament", "playoffs", "final score", "coach", "transfer news",
      "athlete", "marathon", "boxing", "ufc", "mma", "wrestling", "wwe", "f1",
      "formula 1", "goal", "hat trick", "championship"
    ]
  },
  shortMovies: {
    label: "Short Movies",
    keywords: [
      "short movie", "short film festival", "micro film", "5 minute film",
      "student short", "narrative short"
    ]
  },
  travelEvents: {
    label: "Travel & Events",
    keywords: [
      "travel vlog", "travel guide", "backpacking", "itinerary", "flight review",
      "hotel review", "tourist spots", "solo travel", "roadtrip", "festival",
      "expo", "conference highlights", "visa guide", "travel tips", "destination guide"
    ]
  },
  gaming: {
    label: "Gaming",
    keywords: [
      "gameplay", "walkthrough", "let's play", "lets play", "speedrun",
      "gaming", "playstation", "ps5", "xbox", "nintendo", "switch", "steam",
      "esports", "twitch", "game review", "dlc", "patch notes", "video game",
      "boss fight", "fps", "rpg", "minecraft", "fortnite", "valorant",
      "call of duty", "gta", "roblox", "gaming pc", "console"
    ]
  },
  videoblogging: {
    label: "Videoblogging",
    keywords: [
      "vlog", "vlogger", "daily vlog", "weekly vlog", "personal update",
      "life update", "storytime", "q&a video", "behind the scenes vlog"
    ]
  },
  peopleBlogs: {
    label: "People & Blogs",
    keywords: [
      "day in my life", "morning routine", "night routine", "get ready with me",
      "grwm", "haul", "personal story", "life advice", "relationship advice",
      "chit chat", "rant", "opinion video", "my experience"
    ]
  },
  comedy: {
    label: "Comedy",
    keywords: [
      "funny", "comedy", "meme", "memes", "prank", "compilation", "fails",
      "try not to laugh", "reaction video", "stand up comedy", "sketch",
      "parody", "roast", "hilarious", "comedy skit"
    ]
  },
  entertainment: {
    label: "Entertainment",
    keywords: [
      "trailer", "official trailer", "movie review", "film review", "celebrity",
      "celebrities", "reality tv", "tv show", "series review", "episode recap",
      "gossip", "award show", "oscars", "grammys", "premiere", "box office",
      "album review", "concert", "interview with", "actor", "actress",
      "hollywood", "bollywood", "netflix series", "streaming", "red carpet"
    ]
  },
  newsPolitics: {
    label: "News & Politics",
    keywords: [
      "breaking news", "news update", "headlines", "reuters", "associated press",
      "bbc", "cnn", "al jazeera", "election", "elections", "vote", "voting",
      "government", "senate", "congress", "parliament", "president",
      "prime minister", "minister", "war", "conflict", "ceasefire", "protest",
      "policy", "legislation", "bill passed", "supreme court", "verdict",
      "investigation", "press conference", "geopolitics", "diplomacy",
      "sanctions", "crisis", "current affairs", "political analysis",
      "economy", "inflation", "interest rate", "fed", "federal reserve",
      "stock market", "recession"
    ]
  },
  howtoStyle: {
    label: "Howto & Style",
    keywords: [
      "how to", "diy", "tutorial", "life hack", "skincare", "makeup tutorial",
      "outfit", "fashion", "styling tips", "haircut", "hairstyle", "home decor",
      "cleaning hacks", "cooking", "recipe", "baking", "fitness routine",
      "workout", "yoga", "budgeting tips", "personal finance", "investing basics"
    ]
  },
  education: {
    label: "Education",
    keywords: [
      "lecture", "explained", "course", "learn", "learning", "documentary",
      "history of", "science", "physics", "chemistry", "biology", "math",
      "mathematics", "algebra", "calculus", "study", "study tips", "lesson",
      "crash course", "exam prep", "textbook", "professor", "university",
      "college", "coding tutorial", "programming", "concept explained",
      "beginners guide", "step by step"
    ]
  },
  scienceTech: {
    label: "Science & Technology",
    keywords: [
      "review", "unboxing", "smartphone", "iphone", "android phone", "laptop",
      "macbook", "software", "coding", "programmer", "developer", "ai model",
      "artificial intelligence", "machine learning", "llm", "chatgpt", "gpt",
      "startup", "app update", "tech news", "gadget", "gadgets", "processor",
      "cpu", "gpu", "chip", "benchmark", "operating system", "github",
      "framework", "api", "space", "nasa", "spacex", "physics experiment",
      "research study", "scientific discovery", "engineering"
    ]
  },
  nonprofitsActivism: {
    label: "Nonprofits & Activism",
    keywords: [
      "charity", "nonprofit", "ngo", "fundraiser", "donation drive",
      "activism", "human rights", "climate activism", "volunteer",
      "social cause", "awareness campaign", "advocacy"
    ]
  },
  movies: {
    label: "Movies",
    keywords: [
      "full movie", "feature film", "movie trailer", "film premiere",
      "box office", "movie review", "director's cut", "cinema release"
    ]
  },
  animeAnimation: {
    label: "Anime/Animation",
    keywords: [
      "anime", "manga", "otaku", "anime review", "anime episode", "shonen",
      "seinen", "anime opening", "dub", "sub", "crunchyroll"
    ]
  },
  actionAdventure: {
    label: "Action/Adventure",
    keywords: [
      "action movie", "adventure film", "stunt", "action scene", "chase scene",
      "explosion scene", "action packed"
    ]
  },
  classics: {
    label: "Classics",
    keywords: [
      "classic film", "old movie", "vintage cinema", "black and white film",
      "golden age hollywood", "retrospective"
    ]
  },
  documentary: {
    label: "Documentary",
    keywords: [
      "documentary", "true story", "docuseries", "investigative documentary",
      "behind the story", "real events", "biopic"
    ]
  },
  drama: {
    label: "Drama",
    keywords: [
      "drama series", "drama film", "emotional story", "family drama",
      "melodrama", "drama scene"
    ]
  },
  family: {
    label: "Family",
    keywords: [
      "family friendly", "kids show", "cartoon for kids", "family movie",
      "children's content", "family vlog"
    ]
  },
  foreign: {
    label: "Foreign",
    keywords: [
      "foreign film", "subtitled", "international cinema", "korean drama",
      "kdrama", "world cinema", "dubbed movie"
    ]
  },
  horror: {
    label: "Horror",
    keywords: [
      "horror movie", "scary", "horror story", "creepypasta", "paranormal",
      "haunted", "jump scare", "horror game"
    ]
  },
  scifiFantasy: {
    label: "Sci-Fi/Fantasy",
    keywords: [
      "sci-fi", "science fiction", "fantasy film", "space opera", "dystopian",
      "alien", "magic system", "fantasy world"
    ]
  },
  thriller: {
    label: "Thriller",
    keywords: [
      "thriller", "suspense", "psychological thriller", "crime thriller",
      "mystery movie", "plot twist"
    ]
  },
  shorts: {
    label: "Shorts",
    keywords: [
      "#shorts", "short video", "60 seconds", "quick clip"
    ]
  },
  shows: {
    label: "Shows",
    keywords: [
      "tv series", "episode", "season", "web series", "show recap",
      "series trailer"
    ]
  },
  trailers: {
    label: "Trailers",
    keywords: [
      "official trailer", "teaser trailer", "trailer reaction", "first look",
      "sneak peek"
    ]
  }
};

function normalize(str) {
  return (str || "").toLowerCase();
}

// Word-boundary-ish match instead of raw substring, so "war" doesn't match
// inside "warm", "software", etc. Multi-word keywords (e.g. "interest rate")
// just need to appear as a substring since \b\b around spaces is fine.
function keywordHits(text, keyword) {
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(?:^|[^a-z0-9])${escaped}(?:[^a-z0-9]|$)`, "i");
  return pattern.test(text);
}

// Returns { category: string|null, confidence: number, matched: string[] }
function classifyText(rawText) {
  const text = normalize(rawText);
  if (!text.trim()) {
    return { category: null, confidence: 0, matched: [] };
  }

  let best = { category: null, confidence: 0, matched: [] };

  for (const [key, def] of Object.entries(CATEGORIES)) {
    const matched = def.keywords.filter((kw) => keywordHits(text, kw));
    if (matched.length > best.confidence) {
      best = { category: key, confidence: matched.length, matched };
    }
  }

  // Require at least one solid keyword hit to commit to a category.
  if (best.confidence === 0) {
    return { category: null, confidence: 0, matched: [] };
  }
  return best;
}

// Exposed for content.js
window.__ycf_classifyText = classifyText;
window.__ycf_CATEGORIES = CATEGORIES;

// --- Study Mode: focus/distraction scoring (independent of category) ---
// Mirrors the backend's app/focus.py anchor phrases conceptually, but as a
// keyword heuristic for the instant local pass. A video can be correctly
// categorized as Education and still be a distracting clickbait video, or
// vice versa — this is a second, orthogonal signal, not a replacement for
// category filtering.

const FOCUS_FRIENDLY_KEYWORDS = [
  "lecture", "tutorial", "explained", "documentary", "course", "study",
  "step by step", "walkthrough", "deep dive", "textbook", "exam prep",
  "crash course", "seminar", "research", "thesis", "concept explained",
  "full course", "masterclass", "workshop"
];

const DISTRACTING_KEYWORDS = [
  "prank", "reaction", "you won't believe", "insane", "gone wrong",
  "clickbait", "shocking", "broke my", "cried", "roast", "drama",
  "gossip", "meme", "compilation", "try not to laugh", "vs", "challenge",
  "satisfying", "asmr", "mukbang"
];

// Returns 0.0-1.0, higher = more focus-friendly. 0.5 = neutral/no signal.
function classifyFocus(rawText) {
  const text = normalize(rawText);
  if (!text.trim()) return 0.5;

  const focusHits = FOCUS_FRIENDLY_KEYWORDS.filter((kw) => keywordHits(text, kw)).length;
  const distractHits = DISTRACTING_KEYWORDS.filter((kw) => keywordHits(text, kw)).length;

  if (focusHits === 0 && distractHits === 0) return 0.5;

  const raw = 0.5 + 0.15 * (focusHits - distractHits);
  return Math.max(0, Math.min(1, raw));
}

window.__ycf_classifyFocus = classifyFocus;
