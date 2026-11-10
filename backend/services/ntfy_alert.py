import logging
import os

import httpx

NTFY_BASE = "https://ntfy.sh"

log = logging.getLogger("eidolon.ntfy")


async def send_ntfy_alert(title: str, fields: dict[str, str]) -> None:
    """Post a real-time ntfy.sh notification when a trap fires.

    Missing config is a warning, not a crash - alerting should never be what
    stops a trap from doing its job.
    """
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        log.warning("NTFY_TOPIC not set - skipping ntfy alert")
        return

    body = "\n".join(f"{k}: {v}" for k, v in fields.items())
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{NTFY_BASE}/{topic}",
                content=body.encode("utf-8"),
                # bytes, not str: httpx ASCII-encodes str header values, so an em dash
                # or curly quote in a trap name would raise (and 500 the trap endpoint).
                headers={"Title": title.encode("utf-8")},
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        # The class name only: the error text contains the request URL, and the URL contains the topic.
        log.warning("ntfy alert failed to send: %s", type(e).__name__)
