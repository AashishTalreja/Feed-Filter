"""
Official YouTube video category taxonomy (mirrors the YouTube Data API's
videoCategories.list, and the same set used in the browser extension's
classifier.js). Each category carries a handful of representative phrases —
these get embedded once at seed time and act as the category's semantic
anchor for cosine-similarity matching against incoming video text.
"""

CATEGORIES: dict[str, dict] = {
    "filmAnimation": {
        "label": "Film & Animation",
        "seed_phrases": [
            "a short animated film with 3D animation and visual effects",
            "behind the scenes of an indie film production and storyboarding",
        ],
    },
    "autosVehicles": {
        "label": "Autos & Vehicles",
        "seed_phrases": [
            "a car review and test drive of a new SUV or sedan",
            "a motorcycle engine build and horsepower breakdown",
        ],
    },
    "music": {
        "label": "Music",
        "seed_phrases": [
            "an official music video or lyric video for a new song",
            "a live concert performance and album release",
        ],
    },
    "petsAnimals": {
        "label": "Pets & Animals",
        "seed_phrases": [
            "a dog training and puppy care video",
            "wildlife and animal rescue footage",
        ],
    },
    "sports": {
        "label": "Sports",
        "seed_phrases": [
            "football, basketball, or cricket match highlights and scores",
            "a tournament recap with athletes and championship results",
        ],
    },
    "shortMovies": {
        "label": "Short Movies",
        "seed_phrases": ["a short narrative film under 40 minutes"],
    },
    "travelEvents": {
        "label": "Travel & Events",
        "seed_phrases": [
            "a travel vlog exploring a new city with a trip itinerary",
            "coverage of a festival or live conference event",
        ],
    },
    "gaming": {
        "label": "Gaming",
        "seed_phrases": [
            "gameplay walkthrough or let's play of a video game",
            "esports tournament and gaming console review",
        ],
    },
    "videoblogging": {
        "label": "Videoblogging",
        "seed_phrases": ["a personal daily or weekly video blog update"],
    },
    "peopleBlogs": {
        "label": "People & Blogs",
        "seed_phrases": [
            "a day in my life vlog with a personal storytime",
            "life advice and personal opinion commentary",
        ],
    },
    "comedy": {
        "label": "Comedy",
        "seed_phrases": [
            "a funny sketch, prank, or stand-up comedy performance",
            "a meme compilation or comedic reaction video",
        ],
    },
    "entertainment": {
        "label": "Entertainment",
        "seed_phrases": [
            "celebrity news, movie trailers, and award show coverage",
            "a TV series recap or Hollywood interview",
        ],
    },
    "newsPolitics": {
        "label": "News & Politics",
        "seed_phrases": [
            "breaking news coverage of government and elections",
            "political analysis of economic policy and the stock market",
        ],
    },
    "howtoStyle": {
        "label": "Howto & Style",
        "seed_phrases": [
            "a DIY tutorial, makeup routine, or fashion styling guide",
            "a cooking recipe or home decor how-to",
        ],
    },
    "education": {
        "label": "Education",
        "seed_phrases": [
            "an educational lecture explaining a science or math concept",
            "a university course crash-course study guide",
        ],
    },
    "scienceTech": {
        "label": "Science & Technology",
        "seed_phrases": [
            "a smartphone or laptop tech review and unboxing",
            "an explainer on AI, machine learning, or software programming",
        ],
    },
    "nonprofitsActivism": {
        "label": "Nonprofits & Activism",
        "seed_phrases": ["a charity fundraiser or human rights activism campaign"],
    },
    "movies": {
        "label": "Movies",
        "seed_phrases": ["a full-length feature film or movie premiere"],
    },
    "animeAnimation": {
        "label": "Anime/Animation",
        "seed_phrases": ["an anime episode review or manga discussion"],
    },
    "actionAdventure": {
        "label": "Action/Adventure",
        "seed_phrases": ["an action-packed adventure film with stunts and chase scenes"],
    },
    "classics": {
        "label": "Classics",
        "seed_phrases": ["a classic vintage film retrospective"],
    },
    "documentary": {
        "label": "Documentary",
        "seed_phrases": ["a documentary telling a true story or investigative report"],
    },
    "drama": {
        "label": "Drama",
        "seed_phrases": ["an emotional drama series or film scene"],
    },
    "family": {
        "label": "Family",
        "seed_phrases": ["family-friendly content and a kids' cartoon show"],
    },
    "foreign": {
        "label": "Foreign",
        "seed_phrases": ["a subtitled foreign film or international cinema"],
    },
    "horror": {
        "label": "Horror",
        "seed_phrases": ["a scary horror movie with jump scares"],
    },
    "scifiFantasy": {
        "label": "Sci-Fi/Fantasy",
        "seed_phrases": ["a science fiction or fantasy film with a dystopian world"],
    },
    "thriller": {
        "label": "Thriller",
        "seed_phrases": ["a psychological thriller with a suspenseful plot twist"],
    },
    "shorts": {
        "label": "Shorts",
        "seed_phrases": ["a quick vertical short-form video under 60 seconds"],
    },
    "shows": {
        "label": "Shows",
        "seed_phrases": ["a TV series episode or web series"],
    },
    "trailers": {
        "label": "Trailers",
        "seed_phrases": ["an official movie trailer or teaser first look"],
    },
}
