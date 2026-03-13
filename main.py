import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Import our new modular engines
from github_service import GitHubService
from metrics_engine import BehavioralMetricsEngine
from scoring_engine import ProfileScoringEngine

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthcheck():
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*50)
    print("🚀 V2 BEHAVIORAL INTELLIGENCE SERVER IS RUNNING")
    print("📋 Copy the link to the website: http://localhost:8000")
    print("="*50 + "\n")

class RequestData(BaseModel):
    username: str


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _log_openai_request(system_instruction: str, user_content: str) -> None:
    print("🤖 OpenAI system prompt:")
    print(system_instruction.strip())
    print("🤖 OpenAI user payload:")
    print(user_content)
    print(
        "📏 Estimated input tokens:",
        {
            "system_prompt": _estimate_tokens(system_instruction),
            "user_payload": _estimate_tokens(user_content),
            "combined_estimate": _estimate_tokens(system_instruction) + _estimate_tokens(user_content),
        },
    )


def _build_velocity_microcopy(metrics_payload: dict, scoring_payload: dict) -> str:
    return (
        f"{metrics_payload.get('commit_velocity_last_90_days', 0)} commits in the last 90 days "
        f"across {metrics_payload.get('active_repositories_last_6_months', 0)} active repositories."
    )


def _build_lifecycle_microcopy(metrics_payload: dict, scoring_payload: dict) -> str:
    return (
        f"Average active repository lifespan is "
        f"{metrics_payload.get('avg_active_repo_longevity_months', 0)} months."
    )


def _fallback_narrative(data: RequestData, metrics_payload: dict, scoring_payload: dict) -> dict:
    name = metrics_payload.get("name") or data.username
    risk_flags = scoring_payload.get("risk_flags", [])
    risk_text = (
        "No material GitHub risks detected."
        if risk_flags == ["no major deterministic risks"]
        else ", ".join(risk_flags)
    )
    collaboration_profile = scoring_payload.get("collaboration_profile", "Balanced Collaborator")
    stack = ", ".join(scoring_payload.get("core_stack", [])[:3]) or "their core stack"
    merge_ratio = metrics_payload.get("pr_merge_ratio_pct", 0)
    review_ratio = metrics_payload.get("review_to_pr_ratio", 0)
    longevity = metrics_payload.get("avg_active_repo_longevity_months", 0)
    active_repos = metrics_payload.get("active_repositories_last_6_months", 0)
    commit_velocity = metrics_payload.get("commit_velocity_last_90_days", 0)

    snapshot = (
        f"{name}'s GitHub points to an engineer working primarily across {stack} with a mix of recent output, "
        f"merged pull requests, and ongoing repository maintenance rather than a purely cosmetic profile. "
        f"The visible work suggests someone contributing real code and staying engaged with active projects."
    )
    github_signal = (
        f"{commit_velocity} recent commits across {active_repos} active repositories, a {merge_ratio}% PR merge ratio, "
        f"and {review_ratio} reviews per PR suggest {name} is not just experimenting in isolation but showing "
        f"{scoring_payload['execution_velocity'].lower()} execution with a {collaboration_profile.lower()} style. "
        f"The {longevity}-month average repository lifespan also adds signal about follow-through and maintenance behavior."
    )
    business_value = (
        f"Place {name} into teams that need hands-on engineering output in {stack} and value contributors who can ship, "
        f"work within an existing codebase, and show evidence of follow-through. "
        f"This profile fits best where sustained execution and practical delivery matter more than resume polish."
    )

    return {
        "snapshot": snapshot,
        "github_signal": github_signal,
        "business_value": business_value,
        "interview_risks": risk_text,
        "velocity_microcopy": _build_velocity_microcopy(metrics_payload, scoring_payload),
        "lifecycle_microcopy": _build_lifecycle_microcopy(metrics_payload, scoring_payload),
    }


def _build_narrative_context(data: RequestData, metrics_payload: dict, scoring_payload: dict) -> dict:
    return {
        "name": metrics_payload.get("name") or data.username,
        "username": data.username,
        "seniority_estimate": scoring_payload["seniority_estimate"],
        "archetype": scoring_payload["archetype"],
        "execution_velocity": scoring_payload["execution_velocity"],
        "lifecycle_fit": scoring_payload["lifecycle_fit"],
        "collaboration_profile": scoring_payload["collaboration_profile"],
        "risk_flags": scoring_payload["risk_flags"],
        "core_stack": scoring_payload["core_stack"],
        "metrics": {
            "commit_velocity_last_90_days": metrics_payload.get("commit_velocity_last_90_days", 0),
            "active_repositories_last_6_months": metrics_payload.get("active_repositories_last_6_months", 0),
            "pr_merge_ratio_pct": metrics_payload.get("pr_merge_ratio_pct", 0),
            "review_to_pr_ratio": metrics_payload.get("review_to_pr_ratio", 0),
            "code_reviews_conducted": metrics_payload.get("code_reviews_conducted", 0),
            "avg_active_repo_longevity_months": metrics_payload.get("avg_active_repo_longevity_months", 0),
            "external_pr_ratio": metrics_payload.get("external_pr_ratio", 0),
            "repositories_contributed_to": metrics_payload.get("repositories_contributed_to", 0),
        },
    }

@app.post("/generate-summary")
async def generate_summary(data: RequestData):
    print(f"✅ Processing V2 request for: {data.username}")
    
    try:
        # 1. Fetch exactly the raw data we need
        raw_github_data = GitHubService.fetch_behavioral_data(data.username)
        
        # 2. Run the math to generate behavioral signals
        metrics_engine = BehavioralMetricsEngine(data.username, raw_github_data)
        metrics_payload = metrics_engine.generate_payload()
        
        # If the engine hit an error (e.g., no user found), abort early
        if "error" in metrics_payload:
            raise HTTPException(status_code=404, detail="GitHub user data could not be parsed.")

        scoring_engine = ProfileScoringEngine(metrics_payload)
        scoring_payload = scoring_engine.generate_payload()
        narrative_context = _build_narrative_context(data, metrics_payload, scoring_payload)

        # 3. Ask AI only for prose, not for label assignment
        system_instruction = """
        You are writing recruiter-facing copy for a GitHub analysis widget.

        Use the deterministic payload exactly as provided. Do not change, reinterpret, or restate the deterministic labels.

        The widget has four sections. Each field must have a distinct job and must not feel redundant:

        1. snapshot
        - 2 sentences max.
        - Purpose: describe the candidate's technical identity and whether the GitHub looks meaningfully active.
        - Do not mention seniority, archetype, confidence, risk flags, or direct team placement.
        - Do not simply restate the visible top-skills list.

        2. github_signal
        - 2 sentences max.
        - Purpose: explain what the activity pattern says about engineering behavior.
        - Focus on behavior signals like shipping consistency, collaboration, ownership, review participation, and maintenance follow-through.
        - Do not recommend teams or roles here.

        3. business_value
        - 2 sentences max.
        - Purpose: answer "Where would I place this person?"
        - Describe the type of team, environment, or hiring use case where this person looks strongest.
        - Do not repeat raw metrics or restate github_signal.

        4. interview_risks
        - 2 sentences max.
        - Purpose: translate deterministic risk flags into concise recruiter concerns or unknowns.
        - If there are no meaningful risks, return exactly: "No material GitHub risks detected."
        - Do not repeat strengths here.

        Global rules:
        - Write for recruiters and hiring managers.
        - Use the candidate's provided name.
        - Keep the tone analytical, direct, and plain-English.
        - Avoid buzzwords, hype, and filler.
        - Avoid repeating the same idea across fields.

        Return STRICT JSON:
        {
          "snapshot": "...",
          "github_signal": "...",
          "business_value": "...",
          "interview_risks": "..."
        }
        """

        narrative = _fallback_narrative(data, metrics_payload, scoring_payload)

        if client:
            try:
                user_content = json.dumps(narrative_context, separators=(",", ":"))
                _log_openai_request(system_instruction, user_content)
                ai_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"}, 
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {
                            "role": "user",
                            "content": user_content,
                        },
                    ],
                    temperature=0.2,
                    max_completion_tokens=220,
                )
                if ai_response.usage:
                    print(
                        "💸 OpenAI token usage:",
                        {
                            "input_tokens": ai_response.usage.prompt_tokens,
                            "output_tokens": ai_response.usage.completion_tokens,
                            "total_tokens": ai_response.usage.total_tokens,
                        },
                    )
                narrative = {**narrative, **json.loads(ai_response.choices[0].message.content)}
            except Exception as ai_error:
                print(f"⚠️ Narrative generation failed, using fallback prose: {ai_error}")

        response_payload = {
            **narrative,
            "seniority_estimate": scoring_payload["seniority_estimate"],
            "archetype": scoring_payload["archetype"],
            "execution_velocity": scoring_payload["execution_velocity"],
            "lifecycle_fit": scoring_payload["lifecycle_fit"],
            "risk_flags": scoring_payload["risk_flags"],
            "core_stack": scoring_payload["core_stack"],
            "rule_trace": scoring_payload["rule_trace"],
            "raw_evidence": scoring_payload["raw_evidence"],
        }
        response_payload["velocity_microcopy"] = _build_velocity_microcopy(metrics_payload, scoring_payload)
        response_payload["lifecycle_microcopy"] = _build_lifecycle_microcopy(metrics_payload, scoring_payload)

        return {"summary": response_payload}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
