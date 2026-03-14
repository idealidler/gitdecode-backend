# GitDecode Backend

FastAPI service that fetches public GitHub activity, computes deterministic engineering signals, and returns recruiter-friendly summaries.

## Responsibilities

- Query GitHub GraphQL for public activity
- Compute behavioral metrics in [metrics_engine.py](/gitdecode/backend/metrics_engine.py)
- Normalize features in [feature_engine.py](/Users/akshayjain/Documents/GitDecode/gitdecode/backend/feature_engine.py)
- Score dimensions in [dimension_engine.py](/Users/akshayjain/Documents/GitDecode/gitdecode/backend/dimension_engine.py)
- Infer domain in [domain_inference.py](/Users/akshayjain/Documents/GitDecode/gitdecode/backend/domain_inference.py)
- Generate placement guidance in [placement_engine.py](/Users/akshayjain/Documents/GitDecode/gitdecode/backend/placement_engine.py)
- Group evidence in [evidence_engine.py](/Users/akshayjain/Documents/GitDecode/gitdecode/backend/evidence_engine.py)
- Assign deterministic labels in [scoring_engine.py](/Users/akshayjain/Documents/GitDecode/gitdecode/backend/scoring_engine.py)
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

- deterministic labels such as `seniority_estimate`, `archetype`, `domain_focus`, and creator signal
- deterministic dimension outputs such as execution, collaboration, ownership, maintenance, and public credibility
- placement outputs such as `placement_recommendations`, `environment_fit`, and `team_fit_tags`
- recruiter-facing prose fields such as `github_activity_read`, `snapshot`, `placement_summary`, and `interview_risks`
- `raw_evidence` and `evidence_groups` for the extension evidence panel

### `GET /healthz`

Returns:

```json
{ "status": "ok" }
```

## Test

```bash
python3 -m unittest discover -s tests
python3 -m py_compile main.py metrics_engine.py github_service.py scoring_engine.py feature_engine.py dimension_engine.py domain_inference.py placement_engine.py evidence_engine.py
```

## Deploy

Render deployment is defined in [render.yaml](/gitdecode/backend/render.yaml).
