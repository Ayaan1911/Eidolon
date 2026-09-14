import os

import httpx

TELEGRAM_API_BASE = "https://api.telegram.org"


async def send_trap_alert(trap_name: str, alert: dict) -> None:
    """Send a real-time Telegram notification when a trap fires.

    Missing config is a warning, not a crash — the alert is already durably
    logged in the DB by the time this is called, regardless of whether
    Telegram is set up or reachable.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(
            "[trap] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set - "
            "skipping Telegram alert, the trigger was still logged"
        )
        return

    text = (
        f"\U0001fada Trap '{trap_name}' triggered!\n"
        f"IP: {alert['ip']}\n"
        f"Location: {alert['location']}\n"
        f"ISP: {alert['isp']}\n"
        f"Browser: {alert['browser']}\n"
        f"OS: {alert['os']}\n"
        f"Device: {alert['device']}"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[trap] Telegram alert failed to send: {e}")
