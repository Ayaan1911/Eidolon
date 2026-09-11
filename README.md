# Eidolon

Eidolon answers one question: what can someone discover about you without you realizing it?

It works in two movements. **The Mirror** shows you your own exposure — breach data, leaked
secrets, photo metadata — the same footprint an attacker would find. **The Trap** (a later
phase) plants deception tied to what the Mirror finds, so if someone acts on that exposure,
you know.

This repo currently builds only the Mirror, one piece at a time. `legacy/` holds the previous
implementation for reference only — it isn't part of the build.

## Structure

- `backend/` — FastAPI service (breach + password exposure checks)
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
