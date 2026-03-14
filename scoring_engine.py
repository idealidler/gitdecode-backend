from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class ScoreTrace:
    category: str
    signal: str
    value: Any
    impact: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "signal": self.signal,
            "value": self.value,
            "impact": self.impact,
            "reason": self.reason,
        }


def _bucket(score: int, low: str, medium: str, high: str) -> str:
    if score >= 75:
        return high
    if score >= 45:
        return medium
    return low


class ProfileScoringEngine:
    def __init__(self, metrics_payload: Dict[str, Any], feature_payload: Dict[str, Any], dimension_payload: Dict[str, Any], domain_payload: Dict[str, Any]):
        self.metrics = metrics_payload
        self.features = feature_payload
        self.dimensions = dimension_payload["scores"]
        self.domain_focus = domain_payload["primary_domain"]
        self.secondary_domain_focus = domain_payload["secondary_domain"]
        self.domain_scorecard = domain_payload["scorecard"]
        self.traces: List[ScoreTrace] = []

    def _trace(self, category: str, signal: str, value: Any, impact: str, reason: str) -> None:
        self.traces.append(ScoreTrace(category, signal, value, impact, reason))

    def _is_maintainer_workflow_profile(self) -> bool:
        return (
            self.metrics.get("pull_requests_opened_last_90_days", 0) == 0
            and self.metrics.get("total_recent_prs", 0) == 0
            and self.metrics.get("commit_velocity_last_90_days", 0) >= 150
            and self.metrics.get("avg_active_repo_longevity_months", 0) >= 24
            and self.metrics.get("active_repositories_last_6_months", 0) >= 3
            and (
                self.metrics.get("stars_on_owned_repos", 0) >= 10000
                or self.dimensions.get("public_credibility", 0) >= 80
            )
        )

    def _is_high_impact_creator_profile(self) -> bool:
        return (
            self.metrics.get("stars_on_owned_repos", 0) >= 10000
            or self.metrics.get("followers", 0) >= 10000
            or (
                self.dimensions.get("public_credibility", 0) >= 72
                and self.dimensions.get("ownership", 0) >= 55
                and self.dimensions.get("execution", 0) >= 55
            )
        )

    def _core_stack(self) -> List[str]:
        stack: List[str] = []
        seen = set()
        candidates = (
            self.metrics.get("top_languages", [])
            + self.metrics.get("dominant_frameworks", [])
            + self.metrics.get("pinned_languages", [])
        )
        for item in candidates:
            normalized = str(item).strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                stack.append(item)
            if len(stack) >= 5:
                break
        return stack

    def _score_seniority(self) -> str:
        execution = self.dimensions["execution"]
        collaboration = self.dimensions["collaboration"]
        ownership = self.dimensions["ownership"]
        maintenance = self.dimensions["maintenance"]
        maturity = self.dimensions["delivery_maturity"]
        public_credibility = self.dimensions["public_credibility"]
        maintainer_workflow = self._is_maintainer_workflow_profile()
        high_impact_creator = self._is_high_impact_creator_profile()

        composite = round(
            (execution * 0.18)
            + (collaboration * 0.08)
            + (ownership * 0.24)
            + (maintenance * 0.18)
            + (maturity * 0.12)
            + (public_credibility * 0.2)
        )

        if (
            maintainer_workflow
            and maintenance >= 60
            and ownership >= 60
            and (
                public_credibility >= 60
                or self.metrics.get("stars_on_owned_repos", 0) >= 100000
            )
        ):
            label = "Staff"
            self._trace(
                "seniority",
                "maintainer_override",
                {
                    "public_credibility": public_credibility,
                    "ownership": ownership,
                    "maintenance": maintenance,
                    "commit_velocity_last_90_days": self.metrics.get("commit_velocity_last_90_days", 0),
                },
                "positive",
                "Founder-maintainer workflow override assigned Staff despite low PR/review workflow signals."
            )
        elif (
            high_impact_creator
            and public_credibility >= 70
            and ownership >= 55
            and (execution >= 55 or maintenance >= 65)
        ):
            label = "Staff"
            self._trace(
                "seniority",
                "creator_override",
                {
                    "public_credibility": public_credibility,
                    "execution": execution,
                    "ownership": ownership,
                    "stars_on_owned_repos": self.metrics.get("stars_on_owned_repos", 0),
                    "followers": self.metrics.get("followers", 0),
                },
                "positive",
                "High-impact public creator override assigned Staff despite lighter collaboration workflow signals."
            )
        elif (
            high_impact_creator
            and public_credibility >= 58
            and execution >= 45
            and ownership >= 45
        ):
            label = "Senior"
            self._trace(
                "seniority",
                "creator_floor",
                {
                    "public_credibility": public_credibility,
                    "execution": execution,
                    "ownership": ownership,
                    "stars_on_owned_repos": self.metrics.get("stars_on_owned_repos", 0),
                    "followers": self.metrics.get("followers", 0),
                },
                "positive",
                "High-impact public creator floor prevented seniority from being dragged down by review-centric collaboration gaps."
            )
        elif public_credibility >= 88 and ownership >= 72 and maintenance >= 50:
            label = "Staff"
        elif composite >= 74:
            label = "Staff"
        elif composite >= 52:
            label = "Senior"
        elif composite >= 34:
            label = "Mid-Level"
        else:
            label = "Junior"

        self._trace("seniority", "dimension_composite", composite, "neutral", f"Seniority assigned from execution, collaboration, ownership, maintenance, and delivery maturity as {label}.")
        return label

    def _score_execution_velocity(self) -> str:
        score = self.dimensions["execution"]
        if score >= 62:
            label = "Top 10% Contributor"
        elif score >= 35:
            label = "Consistent Output"
        else:
            label = "Sporadic / Bursty"
        self._trace("velocity", "execution", score, "neutral", f"Execution velocity assigned as {label}.")
        return label

    def _score_lifecycle_fit(self) -> str:
        longevity = self.metrics.get("avg_active_repo_longevity_months", 0.0)
        if longevity < 3:
            label = "Zero-to-One / Greenfield"
        elif longevity <= 18:
            label = "Core Contributor"
        else:
            label = "Scale & Optimize"
        self._trace("lifecycle", "avg_active_repo_longevity_months", longevity, "neutral", f"Lifecycle fit assigned as {label}.")
        return label

    def _score_collaboration_profile(self) -> str:
        score = self.dimensions["collaboration"]
        return _bucket(score, "Primarily Individual Contributor", "Balanced Collaborator", "Mentor / Reviewer")

    def _score_archetype(self) -> str:
        external_weight = int(self.metrics.get("external_pr_ratio", 0) * 160)
        stars = self.metrics.get("stars_on_owned_repos", 0)
        public_credibility = self.dimensions["public_credibility"]
        ownership = self.dimensions["ownership"]
        maintainer_workflow = self._is_maintainer_workflow_profile()

        if (
            maintainer_workflow
            and ownership >= 60
            and (
                public_credibility >= 60
                or stars >= 100000
                or self.metrics.get("avg_active_repo_longevity_months", 0) >= 48
            )
        ):
            archetype = "OSS Titan"
            self._trace(
                "archetype",
                "maintainer_override",
                {"public_credibility": public_credibility, "ownership": ownership, "stars_on_owned_repos": stars},
                "positive",
                "Founder-maintainer workflow override assigned OSS Titan."
            )
            return archetype

        if stars >= 50000 and ownership >= 55:
            archetype = "OSS Titan"
            self._trace("archetype", "creator_override", {"stars_on_owned_repos": stars, "ownership": ownership}, "positive", "High-impact public creator override assigned as OSS Titan.")
            return archetype

        if public_credibility >= 70 and ownership >= 55 and self.dimensions["maintenance"] >= 70:
            archetype = "OSS Titan"
            self._trace(
                "archetype",
                "credibility_override",
                {
                    "public_credibility": public_credibility,
                    "ownership": ownership,
                    "maintenance": self.dimensions["maintenance"],
                },
                "positive",
                "High-impact creator with strong maintenance and ownership assigned as OSS Titan."
            )
            return archetype

        scores = {
            "OSS Titan": self.dimensions["oss_presence"] + external_weight + int(self.metrics.get("repositories_contributed_to", 0) * 6) + public_credibility,
            "Enterprise Architect": self.dimensions["maintenance"] + self.dimensions["delivery_maturity"],
            "Product Builder": self.dimensions["execution"] + self.dimensions["ownership"],
            "Consistent Craftsman": self.dimensions["execution"] + self.dimensions["maintenance"],
            "Startup Generalist": self.dimensions["execution"] + self.dimensions["technical_breadth"] + self.dimensions["ownership"],
            "Deep Specialist": self.dimensions["maintenance"] + max(0, 100 - self.dimensions["technical_breadth"]),
            "Rapid Experimenter": self.dimensions["execution"] + max(0, 100 - self.dimensions["maintenance"]),
            "Portfolio Builder": self.dimensions["ownership"] + self.dimensions["technical_breadth"],
            "Early Career Developer": max(0, 120 - self.dimensions["execution"] - self.dimensions["collaboration"]),
        }
        archetype = max(scores, key=scores.get)
        self._trace("archetype", "archetype_scorecard", sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3], "neutral", f"Archetype assigned as {archetype}.")
        return archetype

    def _engineering_signals(self) -> List[Dict[str, Any]]:
        score_map = {
            "Execution": self.dimensions["execution"],
            "Collaboration": self.dimensions["collaboration"],
            "Ownership": self.dimensions["ownership"],
            "Maintenance": self.dimensions["maintenance"],
        }

        signal_copy = {
            "Execution": _bucket(
                score_map["Execution"],
                "Output is visible but not yet consistently sustained across recent public work.",
                "Shows steady delivery across recent GitHub activity without looking purely experimental.",
                "Shows sustained recent output with enough volume to look like meaningful engineering work."
            ),
            "Collaboration": _bucket(
                score_map["Collaboration"],
                "Public GitHub suggests limited review participation and fewer collaborative signals so far.",
                "Signals a healthy mix of shipping and participating in team workflows.",
                "Strong review participation suggests mentorship, influence, or active involvement in shared code quality."
            ),
            "Ownership": _bucket(
                score_map["Ownership"],
                "Public ownership signals are present but still fairly shallow or early-stage.",
                "Shows clear evidence of owning repositories and curating a real technical footprint.",
                "Strong ownership signal through maintained repositories, visible footprint, and credible public project presence."
            ),
            "Maintenance": _bucket(
                score_map["Maintenance"],
                "The profile leans more toward short-lived or newer work than long-term stewardship.",
                "Shows evidence of shipping within existing codebases and maintaining active repositories.",
                "Strong maintenance signal with longer-lived active repositories and production-aligned merge behavior."
            ),
        }

        cards = []
        for label, score in score_map.items():
            cards.append({
                "label": label,
                "score": score,
                "summary": signal_copy[label],
            })
        return cards

    def _creator_signal(self) -> Dict[str, Any]:
        stars = self.metrics.get("stars_on_owned_repos", 0)
        contributed_projects = self.metrics.get("repositories_contributed_to", 0)
        score = self.dimensions.get("public_credibility", 0)

        if score >= 70:
            summary = "Strong public creator signal with visible traction on owned repositories and evidence of contribution breadth across multiple projects."
        elif score >= 45:
            summary = "Credible public creator signal with some traction on owned work and contribution activity beyond a single codebase."
        else:
            summary = "Early-stage public creator signal; there is some visible work, but limited public traction or contribution breadth so far."

        self._trace(
            "creator_signal",
            "public_credibility",
            {"score": score, "stars_on_owned_repos": stars, "repositories_contributed_to": contributed_projects},
            "neutral",
            "Creator signal assigned from repository traction and number of projects contributed to."
        )
        return {
            "score": score,
            "stars_on_owned_repos": stars,
            "repositories_contributed_to": contributed_projects,
            "summary": summary,
        }

    def _derive_risk_flags(self) -> List[str]:
        flags: List[str] = []
        m = self.metrics
        d = self.dimensions
        maintainer_workflow = self._is_maintainer_workflow_profile()

        if d["collaboration"] < 35 and not maintainer_workflow:
            flags.append("low review participation")
        if (
            m.get("external_pr_ratio", 0.0) < 0.1
            and m.get("repositories_contributed_to", 0) < 2
            and not maintainer_workflow
        ):
            flags.append("low external collaboration")
        if m.get("pr_merge_ratio_pct", 0.0) < 60 and m.get("total_recent_prs", 0) >= 5:
            flags.append("low merge success")
        if d["maintenance"] < 35 and m.get("active_repositories_last_6_months", 0) >= 2:
            flags.append("shallow maintenance history")
        if d["execution"] < 25:
            flags.append("low recent activity")

        if not flags:
            flags.append("no major deterministic risks")

        for flag in flags:
            self._trace("risk", "risk_flag", flag, "neutral", f"Risk flag added: {flag}.")
        return flags

    def generate_payload(self) -> Dict[str, Any]:
        seniority_estimate = self._score_seniority()
        execution_velocity = self._score_execution_velocity()
        lifecycle_fit = self._score_lifecycle_fit()
        collaboration_profile = self._score_collaboration_profile()
        archetype = self._score_archetype()
        risk_flags = self._derive_risk_flags()
        engineering_signals = self._engineering_signals()
        creator_signal = self._creator_signal()

        return {
            "seniority_estimate": seniority_estimate,
            "archetype": archetype,
            "execution_velocity": execution_velocity,
            "lifecycle_fit": lifecycle_fit,
            "collaboration_profile": collaboration_profile,
            "risk_flags": risk_flags,
            "core_stack": self._core_stack(),
            "domain_focus": self.domain_focus,
            "secondary_domain_focus": self.secondary_domain_focus,
            "domain_scorecard": self.domain_scorecard,
            "dimension_scores": self.dimensions,
            "engineering_signals": engineering_signals,
            "creator_signal": creator_signal,
            "rule_trace": [trace.to_dict() for trace in self.traces],
            "raw_evidence": self.metrics,
        }
