# GitDecode Backend

FastAPI service that fetches public GitHub activity, computes deterministic engineering signals, and returns recruiter-friendly summaries.

## Responsibilities

- Query GitHub GraphQL for public activity
- Compute behavioral metrics in [metrics_engine.py](/gitdecode/backend/metrics_engine.py)
- Assign deterministic labels in [scoring_engine.py](/gitdecode/backend/scoring_engine.py)
- Generate narrative copy in [main.py](/gitdecode/backend/main.py) without overriding deterministic fields

## Run Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Required environment variables:

- `OPENAI_API_KEY`
- `GITHUB_TOKEN`

## API

### `POST /generate-summary`

Request body:

```json
{
  "username": "octocat"
}
```

Response shape:

- deterministic labels such as `seniority_estimate` and `archetype`
- recruiter-facing prose fields such as `snapshot`, `github_signal`, `business_value`, and `interview_risks`
- `raw_evidence` for the extension evidence panel

### `GET /healthz`

Returns:

```json
{ "status": "ok" }
```

## Test

```bash
python3 -m unittest discover -s tests
python3 -m py_compile main.py metrics_engine.py github_service.py scoring_engine.py
```

## Deploy

Render deployment is defined in [render.yaml](/gitdecode/backend/render.yaml).
