"""
Classification pipeline built as a LangGraph state graph:

    embed_and_match --(confidence >= threshold)--> finalize
                    --(low confidence + LLM configured)--> rag_retrieve -> llm_fallback -> finalize

Stage 1 (embed_and_match): embed the video's title/channel/description with
a sentence-transformers model and cosine-match it against pre-computed
category anchor embeddings. Cheap, fast, no network call — this alone
replaces the brittle keyword matching from the browser-extension version.

Stage 2 (rag_retrieve): when stage 1 isn't confident, pull the most similar
previously-classified videos from the cache table as few-shot context —
this is the "retrieval" half of RAG.

Stage 3 (llm_fallback): hand the video + retrieved examples + category list
to an LLM to make the final call. Only runs if ANTHROPIC_API_KEY is set;
otherwise the pipeline accepts the embedding-only guess even if it's below
the confidence threshold, rather than failing the request.

Stage 4 (finalize): cache the result so the same video is never
re-classified twice.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import embeddings as emb
from app import focus
from app.config import settings
from app.models import Category, ClassificationCache

logger = logging.getLogger(__name__)


class PipelineState(TypedDict, total=False):
    title: str
    channel: str
    description: str
    thumbnail_url: Optional[str]
    text: str
    db: Session
    category_embeddings: dict[str, tuple[str, list[float]]]
    query_embedding: list[float]
    best_category: Optional[str]
    best_label: Optional[str]
    best_confidence: float
    similar_examples: list[dict]
    final_category: Optional[str]
    final_label: Optional[str]
    final_confidence: float
    focus_score: float
    method: str
    used_vision: bool


def cache_key(title: str, channel: str) -> str:
    return hashlib.sha256(f"{title}|{channel}".encode("utf-8")).hexdigest()


def load_category_embeddings(db: Session) -> dict[str, tuple[str, list[float]]]:
    rows = db.execute(select(Category)).scalars().all()
    return {row.key: (row.label, row.embedding) for row in rows}


def node_embed_and_match(state: PipelineState) -> PipelineState:
    text = f"{state['title']} {state['channel']} {state.get('description', '')}".strip()
    query_embedding = emb.embed(text)

    best_key, best_label, best_score = None, None, -1.0
    for key, (label, vector) in state["category_embeddings"].items():
        score = emb.cosine_similarity(query_embedding, vector)
        if score > best_score:
            best_key, best_label, best_score = key, label, score

    focus_score = focus.compute_focus_score(query_embedding)

    return {
        **state,
        "text": text,
        "query_embedding": query_embedding,
        "best_category": best_key,
        "best_label": best_label,
        "best_confidence": best_score,
        "focus_score": focus_score,
    }


def route_after_embed(state: PipelineState) -> str:
    if state["best_confidence"] >= settings.confidence_threshold:
        return "finalize"
    if not settings.anthropic_api_key:
        return "finalize"
    return "rag_retrieve"


def node_rag_retrieve(state: PipelineState) -> PipelineState:
    db = state["db"]
    query_embedding = state["query_embedding"]
    try:
        rows = (
            db.query(ClassificationCache)
            .order_by(ClassificationCache.text_embedding.cosine_distance(query_embedding))
            .limit(settings.rag_neighbor_count)
            .all()
        )
    except Exception as exc:  # pgvector op needs the extension; degrade gracefully
        logger.warning("RAG retrieval failed, continuing without examples: %s", exc)
        rows = []

    examples = [
        {"title": r.title, "category": r.category_key, "confidence": r.confidence}
        for r in rows
    ]
    return {**state, "similar_examples": examples}


def node_llm_fallback(state: PipelineState) -> PipelineState:
    from anthropic import Anthropic

    from app.vision import fetch_thumbnail_base64

    client = Anthropic(api_key=settings.anthropic_api_key)
    category_options = "\n".join(
        f"- {k}: {v[0]}" for k, v in state["category_embeddings"].items()
    )
    examples_block = "\n".join(
        f'  - "{e["title"]}" -> {e["category"]}' for e in state.get("similar_examples", [])
    ) or "  (none)"

    thumbnail = fetch_thumbnail_base64(state.get("thumbnail_url"))
    used_vision = thumbnail is not None

    vision_instruction = (
        "Look at the attached thumbnail image as well as the text below — "
        "the thumbnail often reveals the true content type even when the "
        "title is ambiguous or clickbait-y (e.g. a gaming video titled "
        '"X EXPLAINED" should be classified as Gaming, not Education, if '
        "the thumbnail clearly shows gameplay).\n\n"
        if used_vision else ""
    )

    prompt = f"""You are classifying a YouTube video into exactly one official YouTube category.

{vision_instruction}Categories:
{category_options}

Similar previously-classified videos (for reference):
{examples_block}

Video to classify:
Title: {state['title']}
Channel: {state['channel']}
Description: {state.get('description', '')}

Respond with ONLY a JSON object, no other text: {{"category": "<category_key>", "confidence": <0.0-1.0>}}"""

    if used_vision:
        b64_data, media_type = thumbnail
        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64_data},
            },
            {"type": "text", "text": prompt},
        ]
    else:
        content = prompt

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=100,
            messages=[{"role": "user", "content": content}],
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        category_key = parsed.get("category")
        confidence = float(parsed.get("confidence", 0.5))

        if category_key not in state["category_embeddings"]:
            # Model returned a key outside our taxonomy - don't trust it,
            # fall back to the embedding-only guess instead.
            category_key = state["best_category"]
            confidence = state["best_confidence"]

        label = state["category_embeddings"].get(category_key, (None,))[0]
        return {
            **state,
            "used_vision": used_vision,
            "final_category": category_key,
            "final_label": label,
            "final_confidence": confidence,
            "method": "llm",
        }
    except Exception as exc:  # noqa: BLE001 - never let a flaky LLM call 500 the request
        logger.warning("LLM fallback failed, using embedding guess: %s", exc)
        return {
            **state,
            "used_vision": False,
            "final_category": state["best_category"],
            "final_label": state["best_label"],
            "final_confidence": state["best_confidence"],
            "method": "embedding",
        }


def node_finalize(state: PipelineState) -> PipelineState:
    if "final_category" not in state:
        state = {
            **state,
            "used_vision": False,
            "final_category": state["best_category"],
            "final_label": state["best_label"],
            "final_confidence": state["best_confidence"],
            "method": "embedding",
        }

    db = state["db"]
    video_key = cache_key(state["title"], state["channel"])
    existing = db.query(ClassificationCache).filter_by(video_key=video_key).first()
    if existing is None:
        db.add(
            ClassificationCache(
                video_key=video_key,
                title=state["title"],
                channel=state["channel"],
                text_embedding=state["query_embedding"],
                category_key=state["final_category"] or "uncategorized",
                confidence=state["final_confidence"],
                focus_score=state.get("focus_score", 0.5),
                method=state["method"],
            )
        )
        db.commit()
    return state


_compiled_graph = None


def get_pipeline():
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    graph = StateGraph(PipelineState)
    graph.add_node("embed_and_match", node_embed_and_match)
    graph.add_node("rag_retrieve", node_rag_retrieve)
    graph.add_node("llm_fallback", node_llm_fallback)
    graph.add_node("finalize", node_finalize)

    graph.set_entry_point("embed_and_match")
    graph.add_conditional_edges(
        "embed_and_match",
        route_after_embed,
        {"finalize": "finalize", "rag_retrieve": "rag_retrieve"},
    )
    graph.add_edge("rag_retrieve", "llm_fallback")
    graph.add_edge("llm_fallback", "finalize")
    graph.add_edge("finalize", END)

    _compiled_graph = graph.compile()
    return _compiled_graph


def classify_video(
    db: Session, title: str, channel: str, description: str = "", thumbnail_url: str | None = None
) -> dict:
    """Entry point used by the /classify route."""
    video_key = cache_key(title, channel)
    cached = db.query(ClassificationCache).filter_by(video_key=video_key).first()
    if cached:
        label = None
        category_embeddings = load_category_embeddings(db)
        if cached.category_key in category_embeddings:
            label = category_embeddings[cached.category_key][0]
        return {
            "category": cached.category_key,
            "label": label,
            "confidence": cached.confidence,
            "focus_score": cached.focus_score,
            "method": "cache",
            "used_vision": False,
            "cached": True,
        }

    category_embeddings = load_category_embeddings(db)
    initial_state: PipelineState = {
        "title": title,
        "channel": channel,
        "description": description,
        "thumbnail_url": thumbnail_url,
        "db": db,
        "category_embeddings": category_embeddings,
    }
    result = get_pipeline().invoke(initial_state)
    return {
        "category": result["final_category"],
        "label": result["final_label"],
        "confidence": result["final_confidence"],
        "focus_score": result.get("focus_score", 0.5),
        "method": result["method"],
        "used_vision": result.get("used_vision", False),
        "cached": False,
    }
