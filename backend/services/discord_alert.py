import os

import httpx


async def send_discord_alert(title: str, fields: dict[str, str]) -> None:
    """Post a real-time Discord webhook notification when a trap fires.

    Missing config is a warning, not a crash - alerting should never be what
    stops a trap from doing its job.
    """
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print(f"[trap] DISCORD_WEBHOOK_URL not set - skipping Discord alert for '{title}'")
        return

    text = f"\U0001fada {title}\n" + "\n".join(f"**{k}**: {v}" for k, v in fields.items())
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, json={"content": text})
            resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[trap] Discord alert failed to send: {e}")
