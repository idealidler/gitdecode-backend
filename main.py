import os
import json
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
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
    
    # UPGRADE: Added repositoryTopics (frameworks) and updatedAt (recency)
    query = f"""
    query {{
      user(login: "{username}") {{
        name
        company
        location
        followers {{ totalCount }}
        repositories(first: 6, ownerAffiliations: OWNER, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
          nodes {{
            name
            primaryLanguage {{ name }}
            repositoryTopics(first: 4) {{
              nodes {{
                topic {{ name }}
              }}
            }}
            stargazerCount
            updatedAt
          }}
        }}
        repositoriesContributedTo(first: 4, contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {{
          nodes {{
            name
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
              repositoryTopics(first: 4) {{
                nodes {{
                  topic {{ name }}
                }}
              }}
              stargazerCount
              updatedAt
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

def clean_github_data(raw_data: dict) -> dict:
    """ETL step: Parses the raw GraphQL JSON into a lean, flat dictionary."""
    try:
        user = raw_data.get('data', {}).get('user', {})
        if not user:
            return {"error": "No user data found"}

        def get_lang(node):
            return node.get('primaryLanguage', {}).get('name') if node.get('primaryLanguage') else "Unknown"

        # UPGRADE: Helper to extract framework tags
        def get_topics(node):
            topics = node.get('repositoryTopics', {}).get('nodes', [])
            return [t.get('topic', {}).get('name') for t in topics if t and t.get('topic')]

        clean_data = {
            "name": user.get('name'),
            "company": user.get('company'),
            "location": user.get('location'),
            "followers": user.get('followers', {}).get('totalCount', 0),
            "total_contributions_last_year": user.get('contributionsCollection', {}).get('contributionCalendar', {}).get('totalContributions', 0),
            "pinned_repos": [
                {
                    "name": n.get('name'), 
                    "lang": get_lang(n), 
                    "frameworks": get_topics(n),
                    "stars": n.get('stargazerCount', 0), 
                    "desc": n.get('description'),
                    "last_updated": n.get('updatedAt')
                }
                for n in user.get('pinnedItems', {}).get('nodes', []) if n
            ],
            "recent_repos": [
                {
                    "name": n.get('name'), 
                    "lang": get_lang(n), 
                    "frameworks": get_topics(n),
                    "stars": n.get('stargazerCount', 0),
                    "last_updated": n.get('updatedAt')
                }
                for n in user.get('repositories', {}).get('nodes', []) if n
            ],
            "contributed_to": [
                {"name": n.get('name'), "lang": get_lang(n)}
                for n in user.get('repositoriesContributedTo', {}).get('nodes', []) if n
            ]
        }
        return clean_data
    except Exception as e:
        print(f"Data cleaning error: {e}")
        return raw_data 

@app.post("/generate-summary")
async def generate_summary(data: RequestData):
    print(f"✅ Processing request for: {data.username}")
    
    try:
        github_raw_data = fetch_github_data(data.username)
        clean_data = clean_github_data(github_raw_data)
        github_json_string = json.dumps(clean_data)

        system_instruction = """
        You are an expert technical recruiter assistant. Read the provided parsed GitHub data and output a strictly formatted JSON object.

        CRITICAL RULES:
        1. FRAMEWORKS OVER LANGUAGES: Highlight frameworks (react, django, fastapi) over base languages.
        2. RECENCY BIAS: Heavily weight repositories updated recently. 
        3. SENIORITY RUBRIC: Choose exactly one: "Junior", "Mid-Level", or "Senior". Default to "Mid-Level" if unsure.

        OUTPUT EXACTLY THIS JSON STRUCTURE:
        {
          "snapshot": "One-sentence overview of their strongest technical theme.",
          "seniority": "Junior, Mid-Level, or Senior",
          "role": "Likely role/focus (e.g., Data Engineer)",
          "core_stack": ["Array", "of", "4 to 6", "Top", "Technologies"],
          "evidence": "Specific proof points from repos, emphasizing recent impact.",
          "risks": "What cannot be confidently inferred or looks limited."
        }
        """

        ai_response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"}, # This forces OpenAI to return perfect JSON
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Analyze this GitHub data for {data.username}:\n{github_json_string}"}
            ]
        )
        
        # Parse the JSON string from OpenAI into a real dictionary
        ai_data = json.loads(ai_response.choices[0].message.content)
        return {"summary": ai_data}
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))