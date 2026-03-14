from __future__ import annotations

from typing import Any, Dict


def _to_score(value: float) -> int:
    return round(max(0.0, min(1.0, value)) * 100)


class DimensionScoringEngine:
    def __init__(self, metrics_payload: Dict[str, Any], feature_payload: Dict[str, Any]):
        self.metrics = metrics_payload
        self.features = feature_payload

    def generate_payload(self) -> Dict[str, Any]:
        activity = self.features["activity"]
        collaboration = self.features["collaboration"]
        ownership = self.features["ownership"]
        maintenance = self.features["maintenance"]
        technical = self.features["technical"]
        market = self.features["market_signal"]

        dimensions = {
            "execution": _to_score((activity["commit_intensity"] * 0.5) + (activity["pr_volume"] * 0.2) + (activity["active_repo_spread"] * 0.3)),
            "collaboration": _to_score((collaboration["review_participation"] * 0.45) + (collaboration["review_volume"] * 0.35) + (collaboration["external_contribution"] * 0.2)),
            "ownership": _to_score((ownership["owned_repo_footprint"] * 0.45) + (ownership["stars_signal"] * 0.35) + (ownership["pinned_repo_signal"] * 0.2)),
            "maintenance": _to_score((maintenance["repo_longevity"] * 0.45) + (maintenance["merge_quality"] * 0.35) + (maintenance["maintenance_continuity"] * 0.2)),
            "technical_breadth": _to_score((technical["stack_breadth"] * 0.6) + (technical["language_entropy"] * 0.4)),
            "oss_presence": _to_score((collaboration["external_contribution"] * 0.6) + (market["followers_signal"] * 0.15) + (market["repo_popularity"] * 0.25)),
            "delivery_maturity": _to_score((maintenance["merge_quality"] * 0.5) + (maintenance["repo_longevity"] * 0.25) + (collaboration["review_participation"] * 0.25)),
            "public_credibility": _to_score((market["repo_popularity"] * 0.55) + (market["contribution_reach"] * 0.2) + (market["followers_signal"] * 0.25)),
        }

        return {
            "scores": dimensions,
            "domain_focus": technical["domain_focus"],
        }
