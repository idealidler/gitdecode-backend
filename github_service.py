import os
import requests
from datetime import datetime, timedelta, timezone

# We will load the token in main.py, but the service needs access to it
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

class GitHubService:
    @staticmethod
    def fetch_behavioral_data(username: str) -> dict:
        """
        Dynamically builds a time-boxed GraphQL query to extract only 
        the behavioral signals required by the Metrics Engine.
        """
        # Ensure we have the token
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN is missing from environment variables.")

        url = 'https://api.github.com/graphql'
        headers = {
            'Authorization': f'bearer {token}',
            'Content-Type': 'application/json',
        }
        
        # Calculate exactly 90 days ago in UTC for the GraphQL filter
        ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # The highly targeted V2 GraphQL Query
        query = f"""
        query {{
          user(login: "{username}") {{
            name
            bio
            company
            location
            createdAt
            followers {{
              totalCount
            }}
            following {{
              totalCount
            }}
            # 1. Time-boxed Velocity & Review Signals (Last 90 Days)
            contributionsCollection(from: "{ninety_days_ago}") {{
              totalCommitContributions
              totalPullRequestContributions
              totalPullRequestReviewContributions
              totalRepositoriesWithContributedPullRequests
            }}
            
            # 2. Collaboration footprint (Recent 100 PRs to check external merge ratios)
            pullRequests(first: 100, states: [MERGED, CLOSED], orderBy: {{field: CREATED_AT, direction: DESC}}) {{
              nodes {{
                state
                createdAt
                repository {{
                  owner {{
                    login
                  }}
                }}
              }}
            }}
            
            # 3. Repository Quality & Tech Stack (Top 50 recently updated)
            repositories(first: 50, ownerAffiliations: OWNER, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
              totalCount
              nodes {{
                createdAt
                updatedAt
                description
                isArchived
                isFork
                stargazerCount
                forkCount
                primaryLanguage {{ name }}
                repositoryTopics(first: 5) {{
                  nodes {{
                    topic {{ name }}
                  }}
                }}
              }}
            }}

            pinnedItems(first: 6, types: REPOSITORY) {{
              nodes {{
                ... on Repository {{
                  name
                  stargazerCount
                  primaryLanguage {{ name }}
                  repositoryTopics(first: 5) {{
                    nodes {{
                      topic {{ name }}
                    }}
                  }}
                }}
              }}
            }}
            
          }}
        }}
        """
        
        response = requests.post(url, json={'query': query}, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"GitHub API failed with status code {response.status_code}: {response.text}")

        payload = response.json()
        if payload.get("errors"):
            messages = ", ".join(error.get("message", "Unknown GraphQL error") for error in payload["errors"])
            raise Exception(f"GitHub GraphQL returned errors: {messages}")

        return payload
