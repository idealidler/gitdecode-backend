import os
import json
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Load secrets from .env
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

# Allow the Chrome Extension to talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, we will lock this down, but '*' is safest for local testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestData(BaseModel):
    username: str

def fetch_github_data(username: str):
    """Fetches the developer's public data using the GitHub GraphQL API."""
    url = 'https://api.github.com/graphql'
    headers = {
        'Authorization': f'bearer {GITHUB_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    query = f"""
    query {{
      user(login: "{username}") {{
        name
        bio
        company
        location
        followers {{ totalCount }}
        repositories(first: 6, ownerAffiliations: OWNER, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
          totalCount
          nodes {{
            name
            description
            primaryLanguage {{ name }}
            stargazerCount
            forkCount
            updatedAt
          }}
        }}
        repositoriesContributedTo(first: 4, contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {{
          totalCount
          nodes {{
            name
            description
            primaryLanguage {{ name }}
            stargazerCount
          }}
        }}
        contributionsCollection {{
          contributionCalendar {{
            totalContributions
          }}
        }}
        pinnedItems(first: 3, types: REPOSITORY) {{
          nodes {{
            ... on Repository {{
              name
              description
              primaryLanguage {{ name }}
              stargazerCount
              forkCount
            }}
          }}
        }}
      }}
    }}
    """
    
    response = requests.post(url, json={'query': query}, headers=headers)
    if response.status_code != 200:
        raise Exception(f"GitHub API failed with status code {response.status_code}")
    return response.json()

@app.post("/generate-summary")
async def generate_summary(data: RequestData):
    print(f"✅ Processing request for: {data.username}")
    
    try:
        # 1. Fetch data from GitHub securely on the backend
        github_raw_data = fetch_github_data(data.username)
        github_json_string = json.dumps(github_raw_data)

        # 2. Production-Grade Rubric
        system_instruction = """
        You are an expert technical recruiter assistant. Read the raw GitHub API JSON data and translate it into a highly scannable recruiter brief.

        RULES:
        1. Use ONLY evidence visible in the GitHub data. If a signal is weak or missing, say so explicitly.
        2. TECH STACK: Ignore markup, styling, config, and notebook formats. Treat Jupyter Notebook as Python. Focus on core engineering languages and technologies.
        3. SENIORITY RUBRIC: Choose exactly one of these and do not hedge with multiple levels:
           - Junior
           - Mid-Level
           - Senior
           Default to Mid-Level if evidence is mixed or incomplete.
        4. Keep each bullet concise and recruiter-friendly. No filler.
        5. Mention specific repo names when citing evidence.

        OUTPUT EXACTLY 5 BULLETS IN THIS FORMAT:
        • **Snapshot:** [One-sentence overview of the candidate's likely profile and strongest technical theme.]
        • **Seniority & Fit:** [Chosen level] [likely role/focus] [confidence: Low, Medium, or High].
        • **Core Stack:** [Top languages/technologies plus brief specialization note.]
        • **Evidence:** [Specific proof points from followers, contributions, pinned repos, recent repos, or contributed repos.]
        • **Risks / Unknowns:** [What cannot be confidently inferred or what looks limited from GitHub alone.]
        """

        # 3. Call OpenAI
        ai_response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Analyze this GitHub data for {data.username}:\n{github_json_string}"}
            ]
        )
        
        ai_summary = ai_response.choices[0].message.content
        return {"summary": ai_summary}
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*50)
    print("🚀 SECURE API SERVER IS RUNNING")
    print("📋 Copy this link to view your API docs: http://127.0.0.1:8000/docs")
    print("="*50 + "\n")
