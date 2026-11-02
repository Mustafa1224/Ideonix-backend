# Ideonix backend

FastAPI backend for Ideonix: idea in, competitor and review analysis, score and verdict, feature
evaluation, MVP roadmap out. Runs fully on stub data until the real pieces are wired in (USE_STUB_GEMINI and USE_STUB_PLAYSTORE in .env).

## Run

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    uvicorn app.main:app --reload

Open http://localhost:8000/docs for the live API contract.

## Flow

    POST /auth/signup  ->  token
    POST /analyses     ->  202 + id          (starts the background pipeline)
    GET  /analyses/{id}/status               (poll: queued / running + stage / completed / failed)
    GET  /analyses/{id}                      (partial result while running, full result when done)
    GET  /analyses                           (history with verdict and score)

## Who plugs in where

- Divyanshi (NLP): replace the body of `analyze_reviews` in `app/nlp_interface.py`. Keep the signature.
- Play Store data: replace the two functions in `app/play_store.py` (google-play-scraper).
- Gemini: set GEMINI_API_KEY and USE_STUB_GEMINI=false. Prompts are in `app/prompts.py`.
- Contracts for every stage are in `app/schemas.py`. Change them only after telling the team.
