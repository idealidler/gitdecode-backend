import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from github_service import GitHubService
from metrics_engine import BehavioralMetricsEngine
from feature_engine import FeatureEngineeringEngine
from dimension_engine import DimensionScoringEngine
from domain_inference import DomainInferenceEngine
from placement_engine import PlacementEngine
from evidence_engine import EvidenceGroupingEngine
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


def _fallback_narrative(data: RequestData, metrics_payload: dict, scoring_payload: dict, placement_payload: dict) -> dict:
    name = metrics_payload.get("name") or data.username
    risk_flags = scoring_payload.get("risk_flags", [])
    no_risks = risk_flags == ["no major deterministic risks"]
    domain_focus = scoring_payload.get("domain_focus", "Generalist Software Engineering")
    placement_recommendations = placement_payload.get("placement_recommendations", [])
    placement_text = placement_recommendations[0] if placement_recommendations else "general product engineering team"
    active_repos = metrics_payload.get("active_repositories_last_6_months", 0)
    owned_repos = metrics_payload.get("owned_repositories_count", 0)
    followers = metrics_payload.get("followers", 0)
    stars = metrics_payload.get("stars_on_owned_repos", 0)
    repo_longevity = round(metrics_payload.get("avg_active_repo_longevity_months", 0))
    execution_signal = next(
        (signal.get("summary") for signal in scoring_payload.get("engineering_signals", []) if signal.get("label") == "Execution"),
        "Shows sustained public engineering output."
    )
    commits_90d = metrics_payload.get("commit_velocity_last_90_days", 0)
    prs_90d = metrics_payload.get("pull_requests_opened_last_90_days", 0)

    snapshot = (
        f"{name}'s public GitHub reads like a {domain_focus.lower()} profile with a real operating footprint rather than a portfolio-only presence. "
        f"{execution_signal} The account has stayed active across {active_repos} repositories, with maintained work averaging about {repo_longevity} months and public traction from {followers} followers and {stars} stars on owned repositories."
    )
    github_activity_read = (
        "Recent GitHub activity is exceptionally strong and sustained, with clear signs of active development rather than occasional maintenance."
        if commits_90d >= 180 or (active_repos >= 5 and commits_90d >= 90)
        else "Recent GitHub activity looks steady and real, with enough visible output to suggest ongoing development work."
        if commits_90d >= 30 or active_repos >= 2 or prs_90d >= 3
        else "Recent GitHub activity looks light or sporadic, so the public profile says less about current hands-on development than it does about older work."
    )
    placement_summary = (
        f"Place {name} into a {placement_text.lower()} where visible ownership, sustained shipping, and technical judgment matter more than polished self-presentation. "
        f"This profile is most useful in teams that need someone trusted to carry meaningful product or systems responsibility with a credible public body of work behind them."
    )
    if no_risks:
        risk_text = "No material GitHub risks detected."
    else:
        unknown_risks = []
        concrete_risks = []
        for flag in risk_flags:
            if flag in {"low review participation", "low external collaboration"}:
                unknown_risks.append(flag.replace("low ", "limited "))
            else:
                concrete_risks.append(flag.replace("shallow ", "limited "))

        parts = []
        if concrete_risks:
            parts.append(f"GitHub raises some caution around {', '.join(concrete_risks)}.")
        if unknown_risks:
            parts.append(
                f"Public GitHub also leaves some collaboration evidence unclear, especially around {', '.join(unknown_risks)}."
            )
        risk_text = " ".join(parts) or "No material GitHub risks detected."

    return {
        "github_activity_read": github_activity_read,
        "snapshot": snapshot,
        "placement_summary": placement_summary,
        "interview_risks": risk_text,
    }


def _build_narrative_context(data: RequestData, metrics_payload: dict, feature_payload: dict, scoring_payload: dict, placement_payload: dict) -> dict:
    return {
        "name": metrics_payload.get("name") or data.username,
        "username": data.username,
        "domain_focus": scoring_payload["domain_focus"],
        "placement_recommendations": placement_payload["placement_recommendations"],
        "environment_fit": placement_payload["environment_fit"],
        "team_fit_tags": placement_payload["team_fit_tags"],
        "risk_flags": scoring_payload["risk_flags"],
        "engineering_signals": scoring_payload["engineering_signals"],
        "profile": feature_payload["profile"],
        "evidence": {
            "account_age_months": metrics_payload.get("account_age_months", 0),
            "followers": metrics_payload.get("followers", 0),
            "owned_repositories_count": metrics_payload.get("owned_repositories_count", 0),
            "active_repositories_last_6_months": metrics_payload.get("active_repositories_last_6_months", 0),
            "avg_active_repo_longevity_months": metrics_payload.get("avg_active_repo_longevity_months", 0),
            "commit_velocity_last_90_days": metrics_payload.get("commit_velocity_last_90_days", 0),
            "pull_requests_opened_last_90_days": metrics_payload.get("pull_requests_opened_last_90_days", 0),
            "repositories_contributed_to": metrics_payload.get("repositories_contributed_to", 0),
            "code_reviews_conducted": metrics_payload.get("code_reviews_conducted", 0),
            "stars_on_owned_repos": metrics_payload.get("stars_on_owned_repos", 0),
            "forks_on_owned_repos": metrics_payload.get("forks_on_owned_repos", 0),
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

        feature_engine = FeatureEngineeringEngine(metrics_payload)
        feature_payload = feature_engine.generate_payload()

        dimension_engine = DimensionScoringEngine(metrics_payload, feature_payload)
        dimension_payload = dimension_engine.generate_payload()

        domain_engine = DomainInferenceEngine(metrics_payload)
        domain_payload = domain_engine.generate_payload()

        scoring_engine = ProfileScoringEngine(metrics_payload, feature_payload, dimension_payload, domain_payload)
        scoring_payload = scoring_engine.generate_payload()

        placement_engine = PlacementEngine(metrics_payload, scoring_payload["dimension_scores"], domain_payload)
        placement_payload = placement_engine.generate_payload()

        evidence_engine = EvidenceGroupingEngine(metrics_payload)
        evidence_groups = evidence_engine.generate_payload()

        narrative_context = _build_narrative_context(data, metrics_payload, feature_payload, scoring_payload, placement_payload)

        system_instruction = """
        Write concise recruiter-facing copy for a GitHub analysis widget. The UI already shows deterministic labels, stack, stats, and evidence, so add judgment, not repetition.

        Use the input as truth. Do not invent facts or reinterpret deterministic labels, scores, tags, recommendations, or numeric evidence.

        Output:
        - github_activity_read: exactly 1 sentence; a direct read of the person's recent GitHub activity only; comment on whether recent activity looks active, sustained, sporadic, light, or strong; mention what stands out about recent GitHub behavior; do not summarize the whole profile; no seniority, archetype, stack labels, or raw numbers.
        - snapshot: exactly 2 sentences; sentence 1 = technical identity and engineering shape, sentence 2 = what the public GitHub footprint suggests about credibility, consistency, ownership, or working style; avoid visible labels and numbers unless necessary.
        - placement_summary: exactly 2 sentences; answer "Where would I place this person?"; sentence 1 = best-fit team or environment, sentence 2 = hiring problem or responsibility they seem suited for; use placement recommendations and environment fit; do not repeat snapshot or raw metrics.
        - interview_risks: 1 or 2 sentences; translate risk flags into recruiter cautions or unknowns; distinguish true caution from missing public evidence; if there are no meaningful risks, return exactly "No material GitHub risks detected."

        Style:
        - Write for recruiters and hiring managers in plain-English, specific, unsentimental language.
        - Use the real name when present; otherwise use the username.
        - Keep it personal but not casual. Do not guess gender; use the name or neutral phrasing unless gender is explicit in the input.
        - Avoid hype, generic praise, repeated phrasing, and repeating strengths in interview_risks.
        - If the profile looks like a maintainer-founder workflow rather than a PR-heavy contributor workflow, do not frame low PR or review counts as weakness unless the risk flags require it.

        Return a strict JSON object with exactly these keys: github_activity_read, snapshot, placement_summary, interview_risks.
        """

        narrative = _fallback_narrative(data, metrics_payload, scoring_payload, placement_payload)

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
            "domain_focus": scoring_payload["domain_focus"],
            "secondary_domain_focus": scoring_payload["secondary_domain_focus"],
            "risk_flags": scoring_payload["risk_flags"],
            "core_stack": scoring_payload["core_stack"],
            "dimension_scores": scoring_payload["dimension_scores"],
            "engineering_signals": scoring_payload["engineering_signals"],
            "creator_signal": scoring_payload["creator_signal"],
            "placement_recommendations": placement_payload["placement_recommendations"],
            "environment_fit": placement_payload["environment_fit"],
            "team_fit_tags": placement_payload["team_fit_tags"],
            "rule_trace": scoring_payload["rule_trace"],
            "raw_evidence": scoring_payload["raw_evidence"],
            "evidence_groups": evidence_groups,
        }

        return {"summary": response_payload}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
