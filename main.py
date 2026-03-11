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
        followers {{ totalCount }}
        pinnedItems(first: 3, types: REPOSITORY) {{
          nodes {{
            ... on Repository {{
              name
              description
              primaryLanguage {{ name }}
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
        You are an expert technical recruiter assistant. Read the raw GitHub API JSON data and translate it into a highly scannable summary.
        
        CRITICAL RULES FOR CONSISTENCY:
        1. TECH STACK: Strictly ignore markup, configuration, or notebook formats (e.g., Jupyter Notebook, HTML, CSS, SCSS, Dockerfile). Classify Jupyter Notebook as "Python". Focus ONLY on core programming languages.
        2. SENIORITY RUBRIC: You MUST choose exactly one of these three:
           - "Junior": Projects look like bootcamp assignments, very few commits, or basic scripts.
           - "Mid-Level": Complete, functional projects with good descriptions, or consistent activity. (DEFAULT TO THIS IF UNSURE).
           - "Senior": Complex architecture, highly starred repositories, or deep open-source contributions.
        3. Output EXACTLY 3 bullet points. Start the bullet directly with the data.
        
        FORMAT YOUR OUTPUT EXACTLY LIKE THIS:
        • **Tech Stack:** [List the 3-4 core languages based on Rule 1].
        • **Seniority & Focus:** [State Junior, Mid-Level, or Senior based on Rule 2] [State their focus, e.g., Data Engineer].
        • **Impact & Signals:** [Mention follower count and highlight the single best project].
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