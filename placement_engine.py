from __future__ import annotations

from typing import Any, Dict, List


class PlacementEngine:
    def __init__(self, metrics_payload: Dict[str, Any], dimension_scores: Dict[str, int], domain_payload: Dict[str, Any]):
        self.metrics = metrics_payload
        self.scores = dimension_scores
        self.domain = domain_payload

    def _team_fit(self) -> List[str]:
        primary_domain = self.domain.get("primary_domain")
        execution = self.scores.get("execution", 0)
        maintenance = self.scores.get("maintenance", 0)
        ownership = self.scores.get("ownership", 0)
        collaboration = self.scores.get("collaboration", 0)

        recommendations: List[str] = []

        if primary_domain == "Backend":
            recommendations.append("Backend product team")
        elif primary_domain == "Frontend":
            recommendations.append("Frontend product team")
        elif primary_domain == "Platform / Infra":
            recommendations.append("Platform or infrastructure team")
        elif primary_domain == "Data / ML":
            recommendations.append("Data or ML engineering team")
        elif primary_domain == "Mobile":
            recommendations.append("Mobile engineering team")
        elif primary_domain == "DevTools / OSS":
            recommendations.append("Developer tools or OSS-facing team")
        else:
            recommendations.append("General product engineering team")

        if maintenance >= 72:
            recommendations.append("Mature codebase / scale-and-optimize environment")
        elif execution >= 65 and ownership >= 55:
            recommendations.append("Startup or fast-moving build team")
        else:
            recommendations.append("Core feature delivery team")

        if collaboration >= 70:
            recommendations.append("Team that values code review and technical mentorship")

        deduped: List[str] = []
        seen = set()
        for item in recommendations:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped[:3]

    def _environment_fit(self) -> str:
        execution = self.scores.get("execution", 0)
        maintenance = self.scores.get("maintenance", 0)
        ownership = self.scores.get("ownership", 0)

        if maintenance >= 72:
            return "Best suited to mature environments where reliability, stewardship, and codebase continuity matter."
        if execution >= 65 and ownership >= 55:
            return "Best suited to fast-moving teams that need builders who can ship and own meaningful parts of the product."
        return "Best suited to teams that need steady feature delivery inside an existing engineering system."

    def _fit_tags(self) -> List[str]:
        tags = []
        if self.scores.get("execution", 0) >= 65:
            tags.append("High Execution")
        if self.scores.get("maintenance", 0) >= 65:
            tags.append("Maintenance Fit")
        if self.scores.get("collaboration", 0) >= 65:
            tags.append("Collaboration Fit")
        if self.scores.get("ownership", 0) >= 60:
            tags.append("Ownership Signal")
        if self.scores.get("oss_presence", 0) >= 60:
            tags.append("OSS Signal")
        return tags[:4]

    def generate_payload(self) -> Dict[str, Any]:
        return {
            "placement_recommendations": self._team_fit(),
            "environment_fit": self._environment_fit(),
            "team_fit_tags": self._fit_tags(),
        }
