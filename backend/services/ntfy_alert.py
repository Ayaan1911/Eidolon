import os

import httpx

NTFY_BASE = "https://ntfy.sh"


async def send_ntfy_alert(title: str, fields: dict[str, str]) -> None:
    """Post a real-time ntfy.sh notification when a trap fires.

    Missing config is a warning, not a crash - alerting should never be what
    stops a trap from doing its job.
    """
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print(f"[trap] NTFY_TOPIC not set - skipping ntfy alert for '{title}'")
        return

    body = "\n".join(f"{k}: {v}" for k, v in fields.items())
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{NTFY_BASE}/{topic}",
                content=body.encode("utf-8"),
                headers={"Title": title},
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[trap] ntfy alert failed to send: {e}")
