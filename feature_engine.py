from __future__ import annotations

from collections import Counter
from math import log2, log10
from typing import Any, Dict, List


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


class FeatureEngineeringEngine:
    def __init__(self, metrics_payload: Dict[str, Any]):
        self.metrics = metrics_payload

    def _language_entropy(self, items: List[str]) -> float:
        if not items:
            return 0.0

        counts = Counter(items)
        total = sum(counts.values())
        entropy = 0.0
        for count in counts.values():
            probability = count / total
            entropy -= probability * log2(probability)
        max_entropy = log2(len(counts)) if len(counts) > 1 else 1
        return round(entropy / max_entropy, 3)

    def _domain_focus(self) -> str:
        languages = [str(item).lower() for item in self.metrics.get("top_languages", [])]
        frameworks = [str(item).lower() for item in self.metrics.get("dominant_frameworks", [])]
        signals = languages + frameworks + [str(item).lower() for item in self.metrics.get("pinned_topics", [])]

        scorecard = {
            "Backend": 0,
            "Frontend": 0,
            "Data / ML": 0,
            "Platform / Infra": 0,
            "Mobile": 0,
            "DevTools / OSS": 0,
        }

        for signal in signals:
            if signal in {"python", "go", "java", "kotlin", "rust", "fastapi", "django", "flask", "spring", "node", "postgres"}:
                scorecard["Backend"] += 1
            if signal in {"typescript", "javascript", "react", "nextjs", "vue", "frontend", "css", "tailwind"}:
                scorecard["Frontend"] += 1
            if signal in {"python", "jupyter", "pandas", "numpy", "tensorflow", "pytorch", "machine-learning", "data-science"}:
                scorecard["Data / ML"] += 1
            if signal in {"docker", "kubernetes", "terraform", "ansible", "devops", "aws", "gcp", "infrastructure", "platform"}:
                scorecard["Platform / Infra"] += 1
            if signal in {"swift", "objective-c", "android", "ios", "mobile", "flutter", "react-native"}:
                scorecard["Mobile"] += 1
            if signal in {"cli", "tooling", "developer-tools", "opensource", "open-source", "oss", "library"}:
                scorecard["DevTools / OSS"] += 1

        return max(scorecard, key=scorecard.get) if any(scorecard.values()) else "Generalist Software Engineering"

    def _log_normalize(self, value: float, max_power: float) -> float:
        if value <= 0:
            return 0.0
        return _clamp(log10(value + 1) / max_power)

    def generate_payload(self) -> Dict[str, Any]:
        m = self.metrics
        top_languages = m.get("top_languages", [])
        dominant_frameworks = m.get("dominant_frameworks", [])

        features = {
            "profile": {
                "name": m.get("name"),
                "bio": m.get("bio"),
                "company": m.get("company"),
                "location": m.get("location"),
                "followers": m.get("followers", 0),
                "following": m.get("following", 0),
                "account_age_months": m.get("account_age_months", 0),
            },
            "activity": {
                "commit_intensity": _clamp(m.get("commit_velocity_last_90_days", 0) / 240),
                "pr_volume": _clamp(m.get("pull_requests_opened_last_90_days", 0) / 40),
                "active_repo_spread": _clamp(m.get("active_repositories_last_6_months", 0) / 8),
            },
            "collaboration": {
                "review_participation": _clamp(m.get("review_to_pr_ratio", 0.0) / 1.0),
                "review_volume": _clamp(m.get("code_reviews_conducted", 0) / 40),
                "external_contribution": _clamp(m.get("external_pr_ratio", 0.0) / 0.6),
            },
            "ownership": {
                "owned_repo_footprint": _clamp(m.get("owned_repositories_count", 0) / 30),
                "stars_signal": self._log_normalize(m.get("stars_on_owned_repos", 0), 6),
                "pinned_repo_signal": _clamp(m.get("pinned_repositories_count", 0) / 6),
            },
            "maintenance": {
                "repo_longevity": _clamp(m.get("avg_active_repo_longevity_months", 0.0) / 24),
                "merge_quality": _clamp(m.get("pr_merge_ratio_pct", 0.0) / 100),
                "maintenance_continuity": _clamp(m.get("active_repositories_last_6_months", 0) / 6),
            },
            "technical": {
                "language_entropy": self._language_entropy(top_languages),
                "stack_breadth": min(1.0, (len(top_languages) + len(dominant_frameworks)) / 7),
                "domain_focus": self._domain_focus(),
            },
            "market_signal": {
                "followers_signal": _clamp(m.get("followers", 0) / 250),
                "repo_popularity": self._log_normalize(m.get("stars_on_owned_repos", 0), 6),
                "contribution_reach": _clamp(m.get("repositories_contributed_to", 0) / 25),
            },
        }

        return features
