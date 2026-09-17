# Eidolon

> Eidolon answers one question: what can someone discover about you without you realizing it?

![Eidolon hero](docs/hero.jpg)

## What it does

Eidolon works in two movements.

**The Mirror** shows you your own exposure — the same footprint an attacker would find:

- **Breach & password exposure** — checks an email against known breaches and scores password strength
- **Photo metadata** — pulls EXIF/GPS data out of a photo to show what it leaks about where it was taken
- **Repo secret scanning** — scans a GitHub user's public repos for committed secrets

**The Trap** plants deception tied to what the Mirror finds, so if someone acts on that exposure, you
know. Right now that's one working trap type: a decoy API key (`eidolon_live_...`) that's
self-verifying via an HMAC signature — no database required — and posts a Discord alert with the
requester's IP and rough geolocation the moment it's used. Other trap types (tied directly to
Mirror findings) aren't built yet.

## Status

- **Mirror** — complete: all three checks above are built and working end to end.
- **Trap** — in progress: the honeytoken trap is built and verified manually (signature check,
  Discord alert, generic error response). It isn't wired into the Mirror dossier UI yet, and it's
  the only trap type so far.

`legacy/` holds the previous implementation for reference only — it isn't part of the build.

## Structure

- `backend/` — FastAPI service (exposure checks + trap endpoints)
- `frontend/` — React + Vite + Tailwind UI

## Running locally

```bash
# backend
cd backend
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# frontend
cd frontend
npm install
npm run dev
```
