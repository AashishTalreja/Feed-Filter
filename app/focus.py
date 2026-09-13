"""
A second, orthogonal classification axis: how "focus-friendly" a video is,
independent of its topic category. A video can be correctly tagged
Education and still be clickbaity/hype-driven; a calm documentary can sit
in a category the user would otherwise block. Study Mode combines this
score with the category allow-list rather than relying on category alone.

The score is computed the same way as category matching: embed two anchor
phrase sets (focus-friendly vs distracting) once, then compare each video's
embedding against both and take the relative distance.
"""

FOCUS_FRIENDLY_PHRASES = [
    "a calm educational lecture explaining a concept step by step",
    "an in-depth tutorial or documentary with careful explanation",
    "a focused study session, course walkthrough, or exam preparation",
    "a technical deep dive without jokes, hype, or dramatic reactions",
    "a research talk, academic lecture, or textbook explanation",
]

DISTRACTING_PHRASES = [
    "a funny prank, reaction video, or comedy sketch meant to entertain",
    "a dramatic clickbait thumbnail with shocking claims and hype editing",
    "a gaming Let's Play, gossip, meme compilation, or drama video",
    "a short, fast-cut entertainment video designed for endless scrolling",
    "celebrity news, viral trends, or emotionally provocative content",
]

_focus_anchor = None
_distract_anchor = None


def _get_anchors():
    global _focus_anchor, _distract_anchor
    if _focus_anchor is None or _distract_anchor is None:
        from app import embeddings as emb  # local import avoids circular import at module load

        _focus_anchor = emb.embed(". ".join(FOCUS_FRIENDLY_PHRASES))
        _distract_anchor = emb.embed(". ".join(DISTRACTING_PHRASES))
    return _focus_anchor, _distract_anchor


def compute_focus_score(query_embedding: list[float]) -> float:
    """Returns a 0.0-1.0 score. Higher = more focus-friendly/study-appropriate.
    0.5 is neutral (no strong signal either way)."""
    from app import embeddings as emb

    focus_anchor, distract_anchor = _get_anchors()
    focus_sim = emb.cosine_similarity(query_embedding, focus_anchor)
    distract_sim = emb.cosine_similarity(query_embedding, distract_anchor)

    raw = 0.5 + (focus_sim - distract_sim)
    return max(0.0, min(1.0, raw))
