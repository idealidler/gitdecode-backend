from __future__ import annotations

from typing import Any, Dict, List


class EvidenceGroupingEngine:
    def __init__(self, metrics_payload: Dict[str, Any]):
        self.metrics = metrics_payload

    def generate_payload(self) -> List[Dict[str, Any]]:
        m = self.metrics
        return [
            {
                "title": "Activity",
                "items": [
                    {"label": "Commits in last 90 days", "value": m.get("commit_velocity_last_90_days", 0)},
                    {"label": "Pull requests opened in last 90 days", "value": m.get("pull_requests_opened_last_90_days", 0)},
                    {"label": "Active repositories in last 6 months", "value": m.get("active_repositories_last_6_months", 0)},
                ],
            },
            {
                "title": "Collaboration",
                "items": [
                    {"label": "Code reviews conducted", "value": m.get("code_reviews_conducted", 0)},
                    {"label": "Review to PR ratio", "value": m.get("review_to_pr_ratio", 0)},
                    {"label": "External PR ratio", "value": m.get("external_pr_ratio", 0)},
                    {"label": "Repositories contributed to", "value": m.get("repositories_contributed_to", 0)},
                ],
            },
            {
                "title": "Ownership",
                "items": [
                    {"label": "Owned repositories", "value": m.get("owned_repositories_count", 0)},
                    {"label": "Stars on owned repos", "value": m.get("stars_on_owned_repos", 0)},
                    {"label": "Pinned repositories", "value": m.get("pinned_repositories_count", 0)},
                    {"label": "Followers", "value": m.get("followers", 0)},
                ],
            },
            {
                "title": "Maintenance",
                "items": [
                    {"label": "PR merge ratio", "value": f"{m.get('pr_merge_ratio_pct', 0)}%"},
                    {"label": "Average repository longevity", "value": f"{m.get('avg_active_repo_longevity_months', 0)} months"},
                ],
            },
            {
                "title": "Stack",
                "items": [
                    {"label": "Top languages", "value": ", ".join(m.get("top_languages", [])) or "N/A"},
                    {"label": "Framework signals", "value": ", ".join(m.get("dominant_frameworks", [])) or "N/A"},
                    {"label": "Pinned topics", "value": ", ".join(m.get("pinned_topics", [])) or "N/A"},
                ],
            },
        ]
