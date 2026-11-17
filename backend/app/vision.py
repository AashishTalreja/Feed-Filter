"""
Fetches a video's thumbnail image so it can be included in the LLM fallback
call as a vision input. Only invoked for videos the embedding stage was
already uncertain about — this keeps the (slower, costlier) vision path
reserved for genuinely ambiguous cases, same cost-conscious design as the
text LLM fallback it extends.

Host-allowlisted to YouTube's own thumbnail CDNs since the URL comes from
a browser extension's DOM scrape — fetching an arbitrary attacker-supplied
URL server-side would be an SSRF risk otherwise.
"""

import logging

import requests

logger = logging.getLogger(__name__)

ALLOWED_THUMBNAIL_HOSTS = {"i.ytimg.com", "img.youtube.com", "yt3.ggpht.com"}
MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024  # 2MB safety cap
FETCH_TIMEOUT_SECONDS = 4


def _host_is_allowed(url: str) -> bool:
    from urllib.parse import urlparse

    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host in ALLOWED_THUMBNAIL_HOSTS


def fetch_thumbnail_base64(url: str | None) -> tuple[str, str] | None:
    """Returns (base64_data, media_type) on success, None on any failure.
    Never raises — a thumbnail fetch failure should degrade to text-only
    classification, not break the request."""
    if not url or not _host_is_allowed(url):
        if url:
            logger.warning("Rejected thumbnail URL from disallowed host: %s", url)
        return None

    try:
        response = requests.get(url, timeout=FETCH_TIMEOUT_SECONDS, stream=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not content_type.startswith("image/"):
            return None

        content = response.content
        if len(content) > MAX_THUMBNAIL_BYTES:
            logger.warning("Thumbnail exceeded size cap, skipping: %s", url)
            return None

        import base64

        return base64.b64encode(content).decode("utf-8"), content_type
    except Exception as exc:  # noqa: BLE001 - degrade gracefully, never break classification
        logger.warning("Thumbnail fetch failed for %s: %s", url, exc)
        return None
